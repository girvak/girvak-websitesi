# Origin TLS for Cloudflare Full (strict)

Edge certificates (visitor ↔ Cloudflare) are automatic once DNS is **Proxied**.
This folder is only for the **origin** certificate (Cloudflare ↔ this VPS).

## One-time: create a Cloudflare Origin CA certificate

1. Cloudflare dashboard → **SSL/TLS** → **Origin Server** → **Create certificate**
2. Hostnames: `girisimcilikvakfi.org` and `*.girisimcilikvakfi.org` (defaults are fine)
3. Validity: 15 years is fine for Origin CA
4. Save the certificate PEM and private key

## Install on the server

Either copy into this folder before `deploy.sh` (git-ignored):

```bash
# on the VPS, from the repo root
install -d -m 700 deploy/ssl
# paste/copy the PEM and key:
#   deploy/ssl/origin.pem
#   deploy/ssl/origin.key
chmod 600 deploy/ssl/origin.key
sudo ./deploy/deploy.sh
```

Or place them directly where nginx expects them:

```bash
sudo install -d -m 755 /etc/ssl/girvak
sudo install -m 644 origin.pem /etc/ssl/girvak/origin.pem
sudo install -m 600 origin.key /etc/ssl/girvak/origin.key
```

`deploy.sh` copies `deploy/ssl/origin.*` → `/etc/ssl/girvak/` when the live
files are missing.

## Cloudflare dashboard (once)

| Setting | Value |
|---|---|
| DNS `A` / `AAAA` for `@` and `www` | this VPS IP, **Proxied** (orange cloud) |
| SSL/TLS encryption mode | **Full (strict)** |
| Always Use HTTPS | On (optional; nginx also redirects) |

Do **not** use Flexible — Cloudflare would talk HTTP to the origin and break
redirects / cookies.

## Notes

- Origin CA is trusted by Cloudflare, not by browsers. Hitting the VPS IP on
  `:443` directly will show a warning; that is expected.
- Replacing the nginx site file no longer requires certbot — TLS paths are in
  `deploy/nginx-site.conf`.
