#!/usr/bin/env bash
# GİRVAK — one-shot production deploy on the VPS.
#
# Checks prerequisites, installs Cloudflare Origin TLS + Real IP, reloads host
# nginx, builds and starts docker compose (db + backend + frontend), migrates,
# then smoke-tests local upstreams (and the public URL when reachable).
#
# Usage (from the repo root, as a user with sudo):
#   ./deploy/deploy.sh
#   ./deploy/deploy.sh --check-only
#   ./deploy/deploy.sh --skip-pull
#   ./deploy/deploy.sh --skip-build
#
# Cloudflare DNS (your only manual step): A/AAAA for @ and www → this host,
# Proxied; SSL/TLS mode Full (strict). Origin cert: see deploy/ssl/README.md.

set -euo pipefail

DOMAIN="${DOMAIN:-girisimcilikvakfi.org}"
SITE_URL="${SITE_URL:-https://${DOMAIN}}"
SSL_DIR="${SSL_DIR:-/etc/ssl/girvak}"
NGINX_SITE_AVAILABLE="${NGINX_SITE_AVAILABLE:-/etc/nginx/sites-available/girvak}"
NGINX_SITE_ENABLED="${NGINX_SITE_ENABLED:-/etc/nginx/sites-enabled/girvak}"
CF_REALIP_CONF="${CF_REALIP_CONF:-/etc/nginx/conf.d/cloudflare-realip.conf}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

CHECK_ONLY=0
SKIP_PULL=0
SKIP_BUILD=0
SKIP_PUBLIC=0

for arg in "$@"; do
  case "$arg" in
    --check-only) CHECK_ONLY=1 ;;
    --skip-pull)  SKIP_PULL=1 ;;
    --skip-build) SKIP_BUILD=1 ;;
    --skip-public) SKIP_PUBLIC=1 ;;
    -h|--help)
      sed -n '2,18p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "Unknown option: $arg" >&2
      exit 2
      ;;
  esac
done

log()  { printf '\n==> %s\n' "$*"; }
ok()   { printf '    OK  %s\n' "$*"; }
warn() { printf '    WARN %s\n' "$*" >&2; }
die()  { printf '    FAIL %s\n' "$*" >&2; exit 1; }

need_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    case "$1" in
      nginx)
        die "missing command: nginx — install with: sudo apt-get update && sudo apt-get install -y nginx"
        ;;
      docker)
        die "missing command: docker — install Docker Engine, then: sudo usermod -aG docker \$USER"
        ;;
      *)
        die "missing command: $1"
        ;;
    esac
  fi
}

run_sudo() {
  if [[ "${EUID}" -eq 0 ]]; then
    "$@"
  else
    sudo "$@"
  fi
}

# ---------- checks ----------

check_prereqs() {
  log "Checking prerequisites"
  need_cmd docker
  need_cmd nginx
  need_cmd curl
  need_cmd openssl

  if docker compose version >/dev/null 2>&1; then
    COMPOSE=(docker compose)
  elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE=(docker-compose)
  else
    die "docker compose plugin (or docker-compose) is required"
  fi
  ok "docker + compose"

  docker info >/dev/null 2>&1 || die "docker daemon is not reachable (is it running?)"
  ok "docker daemon"

  [[ -f "$ROOT/docker-compose.yml" ]] || die "docker-compose.yml not found in $ROOT"
  [[ -f "$ROOT/deploy/nginx-site.conf" ]] || die "deploy/nginx-site.conf missing"

  [[ -f "$ROOT/.env" ]] || die ".env missing at repo root — cp .env.example .env and fill production values"

  # shellcheck disable=SC1091
  set -a
  # shellcheck source=/dev/null
  source "$ROOT/.env"
  set +a
  [[ -n "${POSTGRES_PASSWORD:-}" ]] || die "POSTGRES_PASSWORD is empty in .env"

  grep -q '^CONTENT__SOURCE=airtable' "$ROOT/.env" \
    || warn "CONTENT__SOURCE is not airtable in .env (seed-only is fine for a dry run)"

  for key in ADMIN_API_KEY AIRTABLE__API_KEY AIRTABLE__BASE_ID; do
    if ! grep -qE "^${key}=.+" "$ROOT/.env"; then
      die ".env: ${key} is missing or empty"
    fi
  done
  ok "env file (.env at repo root)"

  if ! nginx -t >/dev/null 2>&1 && ! run_sudo nginx -t >/dev/null 2>&1; then
    # First install may fail until our site + certs exist; only warn here.
    warn "nginx -t not clean yet (expected before first SSL/site install)"
  else
    ok "nginx present"
  fi
}

check_ssl_material() {
  log "Checking origin TLS material"
  local live_pem="${SSL_DIR}/origin.pem"
  local live_key="${SSL_DIR}/origin.key"
  local src_pem="${ROOT}/deploy/ssl/origin.pem"
  local src_key="${ROOT}/deploy/ssl/origin.key"

  if [[ -f "$live_pem" && -f "$live_key" ]]; then
    ok "found ${live_pem} + key"
    return 0
  fi
  if [[ -f "$src_pem" && -f "$src_key" ]]; then
    ok "found deploy/ssl/origin.* (will install to ${SSL_DIR})"
    return 0
  fi
  die "no origin certificate. Create a Cloudflare Origin CA cert and place:
    ${src_pem}
    ${src_key}
  or install directly under ${SSL_DIR}/
  See deploy/ssl/README.md"
}

check_dns_hint() {
  log "DNS hint (Cloudflare)"
  local resolved=""
  if command -v dig >/dev/null 2>&1; then
    resolved="$(dig +short "$DOMAIN" A | head -n1 || true)"
  elif command -v getent >/dev/null 2>&1; then
    resolved="$(getent ahostsv4 "$DOMAIN" | awk '{print $1; exit}' || true)"
  fi
  if [[ -n "$resolved" ]]; then
    ok "${DOMAIN} resolves to ${resolved} (confirm this is this VPS and Proxied in Cloudflare)"
  else
    warn "could not resolve ${DOMAIN} — point Cloudflare A/AAAA at this host before going public"
  fi
}

# ---------- SSL + nginx ----------

install_ssl() {
  log "Installing origin TLS under ${SSL_DIR}"
  run_sudo install -d -m 755 "$SSL_DIR"

  local live_pem="${SSL_DIR}/origin.pem"
  local live_key="${SSL_DIR}/origin.key"
  local src_pem="${ROOT}/deploy/ssl/origin.pem"
  local src_key="${ROOT}/deploy/ssl/origin.key"

  if [[ ! -f "$live_pem" || ! -f "$live_key" ]]; then
    [[ -f "$src_pem" && -f "$src_key" ]] || die "SSL source files disappeared"
    run_sudo install -m 644 "$src_pem" "$live_pem"
    run_sudo install -m 600 "$src_key" "$live_key"
    ok "copied deploy/ssl/origin.* → ${SSL_DIR}"
  else
    ok "keeping existing ${SSL_DIR} certs"
  fi

  openssl x509 -in "$live_pem" -noout -checkend 86400 >/dev/null 2>&1 \
    || warn "origin.pem expires within 24h — renew in Cloudflare Origin Server"
  ok "certificate readable"
}

install_cloudflare_realip() {
  log "Writing Cloudflare Real IP ranges → ${CF_REALIP_CONF}"
  local tmp
  tmp="$(mktemp)"

  {
    echo "# Generated by deploy/deploy.sh — $(date -u +%Y-%m-%dT%H:%MZ)"
    echo "# Source: https://www.cloudflare.com/ips-v4 and ips-v6"
    echo "real_ip_header CF-Connecting-IP;"
    echo "real_ip_recursive on;"
    local ip
    while IFS= read -r ip; do
      [[ -n "$ip" ]] && echo "set_real_ip_from ${ip};"
    done < <(curl -fsS --max-time 15 https://www.cloudflare.com/ips-v4 || true)
    while IFS= read -r ip; do
      [[ -n "$ip" ]] && echo "set_real_ip_from ${ip};"
    done < <(curl -fsS --max-time 15 https://www.cloudflare.com/ips-v6 || true)
  } >"$tmp"

  if ! grep -q 'set_real_ip_from' "$tmp"; then
    warn "Cloudflare IP fetch failed — installing fallback ranges (re-run when online)"
    cat >"$tmp" <<'EOF'
# Fallback Cloudflare ranges — refresh by re-running deploy.sh when online
real_ip_header CF-Connecting-IP;
real_ip_recursive on;
set_real_ip_from 173.245.48.0/20;
set_real_ip_from 103.21.244.0/22;
set_real_ip_from 103.22.200.0/22;
set_real_ip_from 103.31.4.0/22;
set_real_ip_from 141.101.64.0/18;
set_real_ip_from 108.162.192.0/18;
set_real_ip_from 190.93.240.0/20;
set_real_ip_from 188.114.96.0/20;
set_real_ip_from 197.234.240.0/22;
set_real_ip_from 198.41.128.0/17;
set_real_ip_from 162.158.0.0/15;
set_real_ip_from 104.16.0.0/13;
set_real_ip_from 104.24.0.0/14;
set_real_ip_from 172.64.0.0/13;
set_real_ip_from 131.0.72.0/22;
set_real_ip_from 2400:cb00::/32;
set_real_ip_from 2606:4700::/32;
set_real_ip_from 2803:f800::/32;
set_real_ip_from 2405:b500::/32;
set_real_ip_from 2405:8100::/32;
set_real_ip_from 2a06:98c0::/29;
set_real_ip_from 2c0f:f248::/32;
EOF
  fi

  run_sudo install -d -m 755 "$(dirname "$CF_REALIP_CONF")"
  run_sudo install -m 644 "$tmp" "$CF_REALIP_CONF"
  rm -f "$tmp"
  ok "real IP config installed"
}

install_nginx_site() {
  log "Installing nginx site → ${NGINX_SITE_AVAILABLE}"
  run_sudo install -m 644 "$ROOT/deploy/nginx-site.conf" "$NGINX_SITE_AVAILABLE"
  run_sudo ln -sfn "$NGINX_SITE_AVAILABLE" "$NGINX_SITE_ENABLED"

  # Drop default site if it would steal :80/:443
  if [[ -e /etc/nginx/sites-enabled/default ]]; then
    run_sudo rm -f /etc/nginx/sites-enabled/default
    ok "disabled sites-enabled/default"
  fi

  run_sudo nginx -t
  if systemctl is-active --quiet nginx 2>/dev/null; then
    run_sudo systemctl reload nginx
  else
    run_sudo systemctl enable --now nginx
  fi
  ok "nginx reloaded"
}

# ---------- compose ----------

compose_up() {
  log "Docker Compose"
  if [[ "$SKIP_PULL" -eq 0 ]]; then
    if [[ -d "$ROOT/.git" ]]; then
      git pull --ff-only || warn "git pull failed — continuing with the working tree"
    fi
  else
    ok "skipping git pull"
  fi

  if [[ "$SKIP_BUILD" -eq 0 ]]; then
    "${COMPOSE[@]}" build
  else
    ok "skipping image build"
  fi

  "${COMPOSE[@]}" run --rm backend alembic upgrade head
  "${COMPOSE[@]}" up -d
  ok "containers up"
}

wait_local_health() {
  log "Waiting for local upstreams"
  local i
  for i in $(seq 1 60); do
    if curl -fsS --max-time 2 "http://127.0.0.1:8082/health" >/dev/null 2>&1; then
      ok "backend :8082/health"
      break
    fi
    [[ "$i" -eq 60 ]] && die "backend did not become healthy on :8082"
    sleep 2
  done

  for i in $(seq 1 60); do
    local code
    code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 3 "http://127.0.0.1:8083/" || true)"
    if [[ "$code" =~ ^(200|301|302|307|308)$ ]]; then
      ok "frontend :8083 → HTTP ${code}"
      break
    fi
    [[ "$i" -eq 60 ]] && die "frontend did not answer on :8083 (last code=${code:-none})"
    sleep 2
  done
}

smoke() {
  log "Smoke checks"
  curl -fsS "http://127.0.0.1:8082/health" | head -c 200
  echo
  ok "local API health"

  local code
  code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 5 "http://127.0.0.1:8083/" || true)"
  [[ "$code" =~ ^(200|301|302)$ ]] || die "local site unexpected status ${code}"
  ok "local site HTTP ${code}"

  # Through host nginx (TLS). -k because Origin CA is not browser-trusted.
  code="$(curl -skS -o /dev/null -w '%{http_code}' --max-time 5 --resolve "${DOMAIN}:443:127.0.0.1" "https://${DOMAIN}/api/health" || true)"
  if [[ "$code" == "200" ]]; then
    ok "nginx TLS → /api/health (local resolve)"
  else
    warn "nginx local TLS smoke got HTTP ${code:-none} — check nginx error log"
  fi

  if [[ "$SKIP_PUBLIC" -eq 0 ]]; then
    code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 15 "${SITE_URL}/api/health" || true)"
    if [[ "$code" == "200" ]]; then
      ok "public ${SITE_URL}/api/health"
    else
      warn "public health HTTP ${code:-none} — DNS/Cloudflare may still be propagating, or SSL mode is not Full (strict)"
    fi
  fi
}

# ---------- main ----------

main() {
  check_prereqs
  check_ssl_material
  check_dns_hint

  if [[ "$CHECK_ONLY" -eq 1 ]]; then
    log "Check-only mode — no changes made"
    exit 0
  fi

  install_ssl
  install_cloudflare_realip
  install_nginx_site
  compose_up
  wait_local_health
  # Reload again once upstreams answer (harmless if already good)
  run_sudo nginx -t && run_sudo systemctl reload nginx
  smoke

  log "Deploy finished"
  echo "  Site:    ${SITE_URL}"
  echo "  Logs:    (cd ${ROOT} && docker compose logs -f backend frontend)"
  echo "  Refresh: curl -X POST -H \"X-Admin-Token: \$ADMIN_API_KEY\" ${SITE_URL}/api/v1/content/refresh"
}

main
