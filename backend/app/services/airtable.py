"""Airtable adapter — maps the real GİRVAK `WEBSITE` base onto our models.

The base stores content as *tagged fragments*: every row has
`name` / `text` / `hover text` / `attachments` / `tag`, and each page's rows
share a tag family (index_* for home, fellow_* for the fellow program, …).
People (trustees / directors / fellows) live in their own `people` table.

Strategy: start from the local seed as a baseline `HomeContent`, then OVERRIDE
the parts Airtable provides. Anything a table doesn't supply (SEO, footer, nav,
CTA hrefs) keeps its seed value, so the site never renders empty.

The `dynamic` checkbox is *written by the backend* (not an editor publish gate):
after each sync, ticked rows are the ones the site logic actually pulls. Editors
use it to see live vs unused fragments. Disable writes with AIRTABLE_SYNC_DYNAMIC=false.

Images are mirrored to disk by `services.media` and handed out as `/media/...`
URLs. Airtable's own attachment links expire after a few hours, which used to
make a static build's images 403 by the next day; the mirror is keyed by the
stable attachment id, so a build stays valid until the content itself changes.
"""
from __future__ import annotations

import html
import random
import re
from typing import Any, Dict, List, Optional, Set
from urllib.parse import quote

import httpx

from ..config import settings
from ..security import safe_href
from .media import mirror
from ..models import (
    AboutContent,
    AboutCtaBand,
    AboutMission,
    AboutSectionHead,
    AboutWwsStrip,
    CTA,
    Fellow,
    FellowContent,
    FellowCta,
    FellowExpectCard,
    FellowHowBlock,
    FellowWydItem,
    HomeContent,
    ImpactTile,
    Partner,
    Person,
    PeopleContent,
    WhatWeDoCard,
)

API_ROOT = "https://api.airtable.com/v0"
PALETTE = ["teal", "coral", "ink"]

# Airtable fields that carry content — never treated as publish checkboxes.
_CONTENT_FIELD_KEYS = frozenset({
    "name", "text", "hover text", "attachments", "tag", "tags", "key", "value",
    "organization", "organisation", "photo", "linkedin", "title", "university",
    "department", "e-mail", "email", "created", "link", "external link",
    "external_link", "external link url", "negative_logo",
    "positive_logo", "year", "cohort", "dönem", "donem", "period", "class",
    "fellow_year", "fellow year", "order", "sort", "rank", "notes", "note",
})

# Backend marks rows the site uses — Airtable checkbox (case-insensitive name match).
_DYNAMIC_CHECKBOX = "dynamic"

# Checkbox columns from Airtable Meta API (unchecked boxes are omitted in records).
_META_CHECKBOX: Dict[str, List[str]] = {}


# --------------------------------------------------------------------------- #
# Low-level fetch
# --------------------------------------------------------------------------- #
def _fetch_table(table: str) -> List[Dict[str, Any]]:
    """Return all records of a table as a list of {id, fields} dicts (paginated)."""
    url = f"{API_ROOT}/{settings.airtable_base_id}/{_enc(table)}"
    headers = {"Authorization": f"Bearer {settings.airtable_api_key}"}
    records: List[Dict[str, Any]] = []
    offset: Optional[str] = None
    with httpx.Client(timeout=15) as client:
        while True:
            params: Dict[str, Any] = {"pageSize": 100}
            if offset:
                params["offset"] = offset
            resp = client.get(url, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()
            records.extend(data.get("records", []))
            offset = data.get("offset")
            if not offset:
                break
    return records


def _enc(table: str) -> str:
    return quote(table, safe="")


def _safe(table: str) -> List[Dict[str, Any]]:
    try:
        return _fetch_table(table)
    except httpx.HTTPError as exc:
        print(f"[content] Airtable fetch failed for {table!r}: {exc}")
        return []
    except Exception as exc:
        print(f"[content] Airtable fetch error for {table!r}: {exc}")
        return []


# --------------------------------------------------------------------------- #
# Field helpers (tolerant to naming / type differences)
# --------------------------------------------------------------------------- #
def pick(fields: Dict[str, Any], *names: str) -> Any:
    """First matching field value, case-insensitively, trying each alias."""
    lower = {k.lower(): v for k, v in fields.items()}
    for n in names:
        if n.lower() in lower:
            return lower[n.lower()]
    return None


def txt(value: Any) -> str:
    """Trim an Airtable text/richText field to a clean single string."""
    if value is None:
        return ""
    return str(value).strip()


def _link_from_fields(fields: Dict[str, Any], fallback: str = "#") -> str:
    """URL-only link fields (never treat image attachments as hrefs)."""
    href = txt(
        pick(
            fields,
            "link",
            "url",
            "href",
            "external link",
            "external_link",
            "external link url",
        )
    )
    return safe_href(href, fallback)


def _href_from_fields(fields: Dict[str, Any], fallback: str = "#") -> str:
    """CTA / card link from Airtable (`link`, `external link`, attachment URL, …)."""
    href = txt(
        pick(
            fields,
            "link",
            "url",
            "href",
            "external link",
            "external_link",
            "external link url",
        )
    )
    if not href:
        href = first_attachment(pick(fields, "attachments"), None) or fallback
    return safe_href(href, fallback)


def _normalize_linkedin(value: Any) -> str:
    """First usable LinkedIn profile URL; empty if missing / homepage-only."""
    raw = txt(value)
    if not raw:
        return ""
    for part in re.split(r"\s+", raw):
        part = part.strip().rstrip(".,;")
        if not part:
            continue
        if "linkedin.com" not in part.lower() and not part.startswith("http"):
            continue
        if not re.match(r"^https?://", part, re.I):
            part = "https://" + part.lstrip("/")
        # Require /in/… profile path — bare linkedin.com is useless.
        if re.search(r"linkedin\.com/in/", part, re.I):
            return part
    return ""


def _att_url(att: Dict[str, Any], prefer: Optional[str]) -> str:
    """Attachment URL, optionally preferring an Airtable thumbnail size.

    `prefer=None` returns the original — used for partner logos (PNG alpha).
    Hero / section imagery uses `photo_attachment()` (`full`, ~3000px) to stay
    sharp on retina displays; person cards use `person_photo()` (`large`,
    ~512px) because they render small and dominate total page weight.
    """
    if prefer:
        thumb = (att.get("thumbnails") or {}).get(prefer)
        if isinstance(thumb, dict) and thumb.get("url"):
            return mirror(att, thumb["url"], prefer)
    url = att.get("url", "")
    return mirror(att, url, "orig") if url else ""


def photo_attachment(value: Any) -> str:
    """Best on-page photo URL: full thumbnail, else original."""
    return first_attachment(value, "full") or first_attachment(value, None)


def logo_attachment(value: Any) -> str:
    """Partner / logo URL — always original (keeps PNG transparency)."""
    return first_attachment(value, None)


def person_photo(value: Any) -> str:
    """Photo for a person card — `large` (512px), not the 3000px original.

    People render at ~200-400px in the grids, so `full` cost roughly 12x the
    bytes for no visible gain: person photos alone were 94% of the site's image
    weight (430 MB of 454 MB), which is what pushed `/board-of-trustees` to
    262 MB for a visitor who scrolls the list. Hero and section images are few
    and stay on `photo_attachment()` (full).

    Falls back to the original when Airtable has no `large` thumbnail (SVG and
    other formats it can't rasterise).
    """
    return first_attachment(value, "large")


def attachments(value: Any, prefer: Optional[str] = None) -> List[str]:
    """All URLs from a multipleAttachments field, in order."""
    urls: List[str] = []
    if isinstance(value, list):
        for a in value:
            if isinstance(a, dict):
                url = _att_url(a, prefer)
                if url:
                    urls.append(url)
    return urls


def first_attachment(value: Any, prefer: Optional[str] = None) -> str:
    urls = attachments(value, prefer)
    return urls[0] if urls else ""


def _trailing_int(name: str) -> int:
    """Ordering key: the trailing integer in a fragment name (index_impact_5 → 5)."""
    m = re.search(r"(\d+)\s*$", name or "")
    return int(m.group(1)) if m else 0


def clear_publish_meta_cache() -> None:
    _META_CHECKBOX.clear()


def _meta_checkbox_fields(table: str) -> List[str]:
    """All checkbox field names on a table (from Meta API — includes empty/unchecked)."""
    if table in _META_CHECKBOX:
        return _META_CHECKBOX[table]
    names: List[str] = []
    try:
        url = f"{API_ROOT}/meta/bases/{settings.airtable_base_id}/tables"
        headers = {"Authorization": f"Bearer {settings.airtable_api_key}"}
        with httpx.Client(timeout=15) as client:
            resp = client.get(url, headers=headers)
            resp.raise_for_status()
            for t in resp.json().get("tables", []):
                if t.get("name") == table:
                    for f in t.get("fields", []):
                        if f.get("type") == "checkbox":
                            names.append(f["name"])
                    break
    except httpx.HTTPError as exc:
        print(f"[content] Airtable meta fetch failed for {table!r}: {exc}")
    _META_CHECKBOX[table] = names
    return names


def _dynamic_column(table: str, records: List[Dict[str, Any]]) -> Optional[str]:
    """Actual Airtable field name for the `dynamic` checkbox, if the column exists."""
    for k in _meta_checkbox_fields(table):
        if k.lower() == _DYNAMIC_CHECKBOX:
            return k
    for r in records:
        for k in r.get("fields", {}):
            if k.lower() == _DYNAMIC_CHECKBOX:
                return k
    return None


def _dynamic_field_names(records: List[Dict[str, Any]], table: str) -> List[str]:
    col = _dynamic_column(table, records)
    return [col] if col else []


def _row_dynamic(fields: Dict[str, Any], dynamic_key: str) -> bool:
    return pick(fields, dynamic_key) is True


def _partner_approved(fields: Dict[str, Any]) -> bool:
    """Partner table `onay` checkbox — only approved rows appear on the site."""
    return pick(fields, "onay", "approved", "approval") is True


def _records_by_name(records: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for r in records:
        name = txt(pick(r.get("fields", {}), "name"))
        if name:
            out[name] = r
    return out


def _mark_record(used: Set[str], record: Optional[Dict[str, Any]]) -> None:
    if record and record.get("id"):
        used.add(record["id"])


def _batch_patch_records(table: str, updates: List[Dict[str, Any]]) -> None:
    if not updates:
        return
    url = f"{API_ROOT}/{settings.airtable_base_id}/{_enc(table)}"
    headers = {
        "Authorization": f"Bearer {settings.airtable_api_key}",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=30) as client:
        for i in range(0, len(updates), 10):
            chunk = updates[i : i + 10]
            resp = client.patch(url, headers=headers, json={"records": chunk})
            try:
                resp.raise_for_status()
            except httpx.HTTPError as exc:
                print(f"[content] Airtable dynamic sync failed for {table!r}: {exc}")


def _home_used_ids(records: List[Dict[str, Any]]) -> Set[str]:
    used: Set[str] = set()
    by_name = _records_by_name(records)

    hero_img = by_name.get("index_hero_image")
    if hero_img and photo_attachment(pick(hero_img.get("fields", {}), "attachments")):
        _mark_record(used, hero_img)

    impact_img = by_name.get("index_impact_image")
    if impact_img and photo_attachment(pick(impact_img.get("fields", {}), "attachments")):
        _mark_record(used, impact_img)

    for key in ("index_hero_cta_primary", "index_hero_cta_secondary", "index_hero_headline"):
        row = by_name.get(key)
        if row and txt(pick(row.get("fields", {}), "text")):
            _mark_record(used, row)

    for r in records:
        f = r.get("fields", {})
        name = txt(pick(f, "name"))
        if name.startswith("index_impact_") and _parse_stat(txt(pick(f, "text"))) is not None:
            _mark_record(used, r)

    for r in records:
        f = r.get("fields", {})
        name = txt(pick(f, "name"))
        if name.startswith("index_whatwedo_") and txt(pick(f, "text")):
            _mark_record(used, r)

    for key in ("index_partners_headline", "index_partners_text"):
        row = by_name.get(key)
        if row and txt(pick(row.get("fields", {}), "text")):
            _mark_record(used, row)

    return used


def _partner_used_ids(records: List[Dict[str, Any]]) -> Set[str]:
    used: Set[str] = set()
    featured: Optional[Dict[str, Any]] = None
    for r in records:
        f = r.get("fields", {})
        if not _partner_approved(f):
            continue
        name = txt(pick(f, "organization", "name"))
        logo = logo_attachment(pick(f, "positive_logo", "logo", "negative_logo"))
        if not name or not logo:
            continue
        tags = pick(f, "Tags", "tags") or []
        is_main = isinstance(tags, list) and any("main" in str(t).lower() for t in tags)
        if is_main and featured is None:
            featured = r
        else:
            _mark_record(used, r)
    if featured:
        _mark_record(used, featured)
    return used


def _people_used_ids(records: List[Dict[str, Any]]) -> Set[str]:
    used: Set[str] = set()
    site_tags = frozenset({"mh", "yk", "team", "fellow", "alumni", "challenger", "challlenger", "challengers"})
    for r in records:
        f = r.get("fields", {})
        if not txt(pick(f, "name")):
            continue
        if site_tags.intersection(_tags(f)):
            _mark_record(used, r)
    return used


def _about_used_ids(records: List[Dict[str, Any]]) -> Set[str]:
    used: Set[str] = set()
    by_name = _records_by_name(records)

    if txt(pick(by_name.get("about_aboutus_headline", {}).get("fields", {}), "text")):
        _mark_record(used, by_name.get("about_aboutus_headline"))
    if txt(pick(by_name.get("about_aboutus_text", {}).get("fields", {}), "text")):
        _mark_record(used, by_name.get("about_aboutus_text"))

    mission = by_name.get("about_mission_headline")
    if mission:
        mf = mission.get("fields", {})
        if (
            txt(pick(mf, "text"))
            or txt(pick(by_name.get("about_mission_text", {}).get("fields", {}), "text"))
            or photo_attachment(pick(mf, "attachments"))
        ):
            _mark_record(used, mission)
    mission_text = by_name.get("about_mission_text")
    if mission_text and txt(pick(mission_text.get("fields", {}), "text")):
        _mark_record(used, mission_text)

    for key in ("about_ourstory_headline", "about_ourstory_text", "about_whatwesolve_headline"):
        row = by_name.get(key)
        if row and txt(pick(row.get("fields", {}), "text")):
            _mark_record(used, row)

    for r in records:
        f = r.get("fields", {})
        if re.match(r"about_whatwesolve_\d+\s*$", txt(pick(f, "name"))):
            _mark_record(used, r)

    for headline_key, sub_key in (
        ("about_boardoftrustees_headline", "about_boardoftrustees_subheadline"),
        ("about_board_headline", "about_board_subheadline"),
        ("about_team_headline", "about_team_subheadline"),
    ):
        for key in (headline_key, sub_key):
            row = by_name.get(key)
            if row and txt(pick(row.get("fields", {}), "text")):
                _mark_record(used, row)

    for headline_key, text_key, cta_key in (
        ("about_reports_headline", "about_reports_text", "about_reports_cta"),
        ("about_workwithus_headline", "about_workwithus_text", "about_workwithus_cta"),
    ):
        for key in (headline_key, text_key, cta_key):
            row = by_name.get(key)
            if row and txt(pick(row.get("fields", {}), "text")):
                _mark_record(used, row)

    return used


def _fellow_used_ids(records: List[Dict[str, Any]]) -> Set[str]:
    """Rows from the `fellow` table that `build_fellow_content` actually reads.

    Respects the same `active` gate as the page builder.
    """
    used: Set[str] = set()
    active_fields = _fellow_active_fields(records)
    active_names = {txt(pick(f, "name")) for f in active_fields}

    for r in records:
        f = r.get("fields", {})
        name = txt(pick(f, "name"))
        if name not in active_names:
            continue
        tag = _row_tag(f).lower()
        if not tag.startswith("fellow_") and not tag.startswith("challenger_"):
            continue
        if txt(pick(f, "text")) or photo_attachment(pick(f, "attachments")):
            _mark_record(used, r)
    return used


def sync_dynamic_checkboxes() -> Dict[str, Any]:
    """Tick `dynamic` on rows the site uses; clear it on rows it does not."""
    if not settings.airtable_sync_dynamic:
        return {"enabled": False}

    tables: List[tuple[str, Any]] = [
        (settings.airtable_table_home, _home_used_ids),
        (settings.airtable_table_about, _about_used_ids),
        (settings.airtable_table_people, _people_used_ids),
        (settings.airtable_table_partner, _partner_used_ids),
        (settings.airtable_table_fellow, _fellow_used_ids),
    ]
    summary: Dict[str, Any] = {"enabled": True, "tables": {}}
    for table, used_fn in tables:
        records = _safe(table)
        col = _dynamic_column(table, records)
        if not col:
            summary["tables"][table] = {"dynamic_column": None, "skipped": True}
            continue
        used = used_fn(records)
        updates: List[Dict[str, Any]] = []
        for r in records:
            want = r.get("id") in used
            have = _row_dynamic(r.get("fields", {}), col)
            if want == have:
                continue
            updates.append({"id": r["id"], "fields": {col: want}})
        _batch_patch_records(table, updates)
        summary["tables"][table] = {
            "dynamic_column": col,
            "site_used_rows": len(used),
            "patched_rows": len(updates),
            "total_rows": len(records),
        }
    return summary


def publish_guide() -> Dict[str, Any]:
    """Which Airtable rows the site reads — reflected in the `dynamic` checkbox."""
    return {
        "hint": (
            "The backend sets the `dynamic` checkbox on rows it actually pulls into "
            "the website (POST /api/content/refresh). "
            "Do not use `dynamic` as a manual publish switch — it is a live mirror "
            "of what the site uses."
        ),
        "tables": {
            settings.airtable_table_home: {
                "used_by": "Homepage (/)",
                "row_names": [
                    "index_hero_headline", "index_hero_image", "index_hero_cta_primary",
                    "index_hero_cta_secondary", "index_impact_image", "index_impact_* (stat rows)",
                    "index_whatwedo_* (text + attachments per card)",
                    "index_partners_headline", "index_partners_text",
                ],
                "notes": "Hero rotator words still come from seed unless added as fragments.",
            },
            settings.airtable_table_about: {
                "used_by": "About (/about)",
                "row_names": [
                    "about_aboutus_headline", "about_aboutus_text",
                    "about_mission_headline (photo attachments here)", "about_mission_text",
                    "about_ourstory_headline", "about_ourstory_text",
                    "about_whatwesolve_headline", "about_whatwesolve_1..3",
                    "about_boardoftrustees_*", "about_board_*", "about_team_*",
                    "about_reports_*", "about_workwithus_*",
                ],
            },
            settings.airtable_table_people: {
                "used_by": "About people grids, homepage fellows, fellow-program",
                "filter": "tag contains mh, yk, team, fellow, alumni, challenger",
                "notes": "About trustees preview: first 10 by table order; full list on /board-of-trustees.",
            },
            settings.airtable_table_partner: {
                "used_by": "Homepage partners section",
                "filter": "needs organization + positive_logo or negative_logo",
            },
            settings.airtable_table_fellow: {
                "used_by": "Fellow program page — tag families on `fellow` table",
                "filter": "If any row has active=true, only active rows are used",
                "row_names": [
                    "tag fellow_hero / fellow_about / fellow_application / fellow_whattoexpect",
                    "tag fellow_fellows / fellow_alumni / fellow_giveback",
                    "tag challenger_hero / challenger_application / challenger_whatyou'lldo / challenger_challengers",
                ],
            },
        },
    }


def _fmt_fellow_year(raw: str) -> str:
    s = (raw or "").strip()
    if not s:
        return ""
    if s[0] in "'\u2019":
        return s if s.startswith("\u2019") else f"\u2019{s[1:]}"
    m = re.match(r"^(\d{4})$", s)
    if m:
        return f"\u2019{m.group(1)[2:]}"
    m = re.match(r"^(\d{2})$", s)
    if m:
        return f"\u2019{m.group(1)}"
    return s


def _fellow_year(fields: Dict[str, Any]) -> str:
    raw = txt(
        pick(
            fields,
            "year",
            "cohort",
            "dönem",
            "donem",
            "period",
            "class",
            "fellow_year",
            "Fellow Year",
        )
    )
    if raw:
        return _fmt_fellow_year(raw)
    for t in _tags(fields):
        m = re.search(r"(?:^|_|-)(['\u2019]?)(\d{2})$", str(t))
        if m:
            return _fmt_fellow_year(m.group(2))
    return ""


def _by_name(records: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {txt(pick(r.get("fields", {}), "name")): r.get("fields", {}) for r in records}


def _family(records: List[Dict[str, Any]], prefix: str) -> List[Dict[str, Any]]:
    """Fragment rows whose `name` starts with `prefix`, ordered by trailing int."""
    rows = [
        r.get("fields", {})
        for r in records
        if txt(pick(r.get("fields", {}), "name")).startswith(prefix)
    ]
    return sorted(rows, key=lambda f: _trailing_int(txt(pick(f, "name"))))


# --------------------------------------------------------------------------- #
# Home content (seed + overrides)
# --------------------------------------------------------------------------- #
def build_home_content(seed: HomeContent) -> HomeContent:
    content = seed.model_copy(deep=True)

    home = _safe(settings.airtable_table_home)
    partner = _safe(settings.airtable_table_partner)

    by_name = _by_name(home)
    _apply_seo(content, by_name)
    _apply_hero(content, home, by_name)
    _apply_hero_subhead(content, by_name)
    _apply_impact(content, home)
    _apply_impact_image(content, by_name)
    _apply_whatwedo(content, home)
    _apply_fellows_section(content, by_name)
    _apply_partners(content, partner, by_name)
    _apply_footer(content, by_name)
    # Fellows on the homepage are filled per-request via pick_fellow_spotlight().

    return content


def _apply_hero(content: HomeContent, home: List[Dict[str, Any]], by_name: Dict[str, Dict[str, Any]]) -> None:
    imgs = attachments(pick(by_name.get("index_hero_image", {}), "attachments"), "full")
    if not imgs:
        imgs = attachments(pick(by_name.get("index_hero_image", {}), "attachments"), None)
    if imgs:
        content.hero.images = imgs

    primary = txt(pick(by_name.get("index_hero_cta_primary", {}), "text"))
    secondary = txt(pick(by_name.get("index_hero_cta_secondary", {}), "text"))
    if primary or secondary:
        ctas: List[CTA] = []
        if secondary:
            sec_row = by_name.get("index_hero_cta_secondary", {})
            ctas.append(
                CTA(
                    label=secondary,
                    href=_link_from_fields(
                        sec_row,
                        content.hero.ctas[0].href if content.hero.ctas else "#",
                    ),
                )
            )
        if primary:
            pri_row = by_name.get("index_hero_cta_primary", {})
            ctas.append(
                CTA(
                    label=primary,
                    href=_link_from_fields(
                        pri_row,
                        content.hero.ctas[1].href if len(content.hero.ctas) > 1 else "#wwd",
                    ),
                )
            )
        content.hero.ctas = ctas

    # Headline + rotator words stay on the seed/design split (`base_text` +
    # `rotator_words`). Airtable `index_hero_headline` is a single line and
    # breaks the word rotator when pasted in wholesale.


def _apply_seo(content: HomeContent, by_name: Dict[str, Dict[str, Any]]) -> None:
    title = txt(pick(by_name.get("index_seo_title", {}), "text"))
    desc = txt(pick(by_name.get("index_seo_description", {}), "text"))
    if title:
        content.seo.title = title
    if desc:
        content.seo.description = desc


def _split_subhead(raw: str, current: Hero) -> tuple[str, str, str]:
    """Parse subhead into pre / coral highlight / post."""
    raw = raw.strip()
    if not raw:
        return current.subhead_pre, current.subhead_highlight, current.subhead_post
    m = re.match(r"(.+?)\*\*(.+?)\*\*(.*)", raw, re.S)
    if m:
        return m.group(1), m.group(2), m.group(3)
    highlight = current.subhead_highlight or "a way of looking at the world."
    idx = raw.lower().find(highlight.lower().rstrip("."))
    if idx >= 0:
        end = idx + len(highlight.rstrip("."))
        while end < len(raw) and raw[end] in ". ":
            end += 1
        return raw[:idx], raw[idx:end].strip(), raw[end:]
    return raw, "", ""


def _apply_hero_subhead(content: HomeContent, by_name: Dict[str, Dict[str, Any]]) -> None:
    raw = txt(pick(by_name.get("index_hero_subheadline", {}), "text"))
    if not raw:
        return
    pre, hi, post = _split_subhead(raw, content.hero)
    content.hero.subhead_pre = pre
    content.hero.subhead_highlight = hi
    content.hero.subhead_post = post


def _apply_fellows_section(content: HomeContent, by_name: Dict[str, Dict[str, Any]]) -> None:
    headline = txt(pick(by_name.get("index_fellows_headline", {}), "text"))
    if headline:
        content.fellows_headline = headline
    cta_row = by_name.get("index_fellows_cta", {})
    cta_label = txt(pick(cta_row, "text"))
    if cta_label:
        content.fellows_cta = CTA(
            label=cta_label,
            href=_link_from_fields(cta_row, content.fellows_cta.href),
        )


def _apply_footer(content: HomeContent, by_name: Dict[str, Dict[str, Any]]) -> None:
    """Map `index_footer_*` fragments onto the footer model when present."""
    mapping = {
        "index_footer_newsletter_title": ("newsletter_title", None),
        "index_footer_newsletter_text": ("newsletter_text", None),
        "index_footer_brand_text": ("brand_text", None),
        "index_footer_copyright": ("copyright", None),
        "index_footer_address": ("contact.address", None),
        "index_footer_email": ("contact.email", None),
        "index_footer_phone": ("contact.phone", None),
        "index_footer_phone_href": ("contact.phone_href", None),
    }
    for key, (path, _) in mapping.items():
        val = txt(pick(by_name.get(key, {}), "text"))
        if not val:
            continue
        if path.startswith("contact."):
            setattr(content.footer.contact, path.split(".", 1)[1], val)
        else:
            setattr(content.footer, path, val)
    # Explore links: index_footer_explore_1 .. n  (text + link fields)
    explore: List[CTA] = []
    for f in sorted(
        [by_name[k] for k in by_name if re.match(r"index_footer_explore_\d+\s*$", k)],
        key=lambda row: _trailing_int(txt(pick(row, "name"))),
    ):
        label = txt(pick(f, "text"))
        if label:
            explore.append(CTA(label=label, href=_link_from_fields(f, "#")))
    if explore:
        content.footer.explore_links = explore


def _apply_impact(content: HomeContent, home: List[Dict[str, Any]]) -> None:
    # Keep only rows that actually parse into a stat (drops e.g.
    # index_impact_image), THEN position — so the 3×3 grid stays r1-3 / c1-3.
    parsed = [
        (f, _parse_stat(txt(pick(f, "text"))))
        for f in _family(home, "index_impact_")
    ]
    stats = [(f, p) for f, p in parsed if p is not None]
    tiles: List[ImpactTile] = []
    for i, (f, (count, decimals, suffix, label)) in enumerate(stats):
        tiles.append(ImpactTile(
            count=count,
            decimals=decimals,
            prefix="",
            suffix=suffix,
            label=label,
            desc=txt(pick(f, "hover text")),
            color=PALETTE[i % 3],
            row=i // 3 + 1,
            col=i % 3 + 1,
        ))
    if tiles:
        content.impact = tiles


def _apply_impact_image(content: HomeContent, by_name: Dict[str, Dict[str, Any]]) -> None:
    row = by_name.get("index_impact_image")
    if not row:
        return
    img = photo_attachment(pick(row, "attachments"))
    if img:
        content.impact_image = img


def _parse_stat(text: str):
    """"1.3M+ applications" → (1.3, 1, "M+", "applications"). None if unparseable."""
    m = re.match(r"^([\d.,]+)([^\s]*)\s+(.+)$", text.strip(), re.S)
    if not m:
        return None
    num_str, unit, label = m.groups()
    try:
        count = float(num_str.replace(",", ""))
    except ValueError:
        return None
    decimals = len(num_str.split(".")[1]) if "." in num_str else 0
    return count, decimals, unit.strip(), label.strip()


def _apply_whatwedo(content: HomeContent, home: List[Dict[str, Any]]) -> None:
    rows = _family(home, "index_whatwedo_")
    seed = list(content.what_we_do)
    cards: List[WhatWeDoCard] = []
    for i, f in enumerate(rows):
        text = txt(pick(f, "text"))
        if not text:
            continue
        lead, sub = _split_lead(text)
        eyebrow = _eyebrow(sub)
        seed_card = seed[i] if i < len(seed) else None
        img = (
            photo_attachment(pick(f, "attachments"))
            or photo_attachment(pick(f, "photo", "image"))
        )
        if not img and seed_card:
            img = seed_card.image
        link = txt(
            pick(
                f,
                "link",
                "url",
                "href",
                "external link",
                "external_link",
                "external link url",
            )
        )
        cards.append(WhatWeDoCard(
            href=link or (seed_card.href if seed_card else "#"),
            image=img or (seed_card.image if seed_card else ""),
            lead=lead,
            sub=sub,
            eyebrow=eyebrow,
            text=txt(pick(f, "hover text")) or (seed_card.text if seed_card else ""),
            color=seed_card.color if seed_card else PALETTE[i % 3],
        ))
    if cards:
        content.what_we_do = cards


def _split_lead(text: str):
    """'We back potential. That's the Fellow Program.' → (lead, sub)."""
    idx = text.find("That's")
    if idx == -1:
        idx = text.find("That’s")
    if idx > 0:
        return text[:idx].strip(), text[idx:].strip()
    return text.strip(), ""


def _eyebrow(sub: str) -> str:
    e = re.sub(r"^That['’]s\s+", "", sub).strip().rstrip(".")
    return re.sub(r"^the\s+", "", e).strip()


def _apply_partners(content: HomeContent, partner: List[Dict[str, Any]], by_name: Dict[str, Dict[str, Any]]) -> None:
    headline = txt(pick(by_name.get("index_partners_headline", {}), "text"))
    if headline:
        # Split so the last clause can be coral-highlighted (design intent).
        parts = headline.rsplit(",", 1)
        if len(parts) == 2:
            content.partners.headline_pre = parts[0] + ", "
            content.partners.headline_highlight = parts[1].strip()
        else:
            content.partners.headline_pre = headline
            content.partners.headline_highlight = ""
    sub = txt(pick(by_name.get("index_partners_text", {}), "text"))
    if sub:
        content.partners.sub = sub

    logos: List[Partner] = []
    featured: Optional[Partner] = None
    for r in partner:
        f = r.get("fields", {})
        if not _partner_approved(f):
            continue
        name = txt(pick(f, "organization", "name"))
        logo = logo_attachment(pick(f, "positive_logo", "logo", "negative_logo"))
        if not name or not logo:
            continue
        link = _link_from_fields(f, "#")
        p = Partner(name=name, logo=logo, href=link)
        tags = pick(f, "Tags", "tags") or []
        is_main = isinstance(tags, list) and any("main" in str(t).lower() for t in tags)
        if is_main and featured is None:
            featured = p
        else:
            logos.append(p)
    if featured:
        content.partners.featured = featured
    if logos:
        logos.sort(key=lambda p: (p.name or "").casefold())
        content.partners.logos = logos


def pick_people_spotlight(pool: List[Person], count: Optional[int] = None) -> List[Person]:
    """Random homepage fellow cards from the live people pool."""
    if not pool:
        return []
    k = count if count is not None else settings.home_fellows_spotlight_count
    k = max(1, min(k, len(pool)))
    return random.sample(pool, k)


def build_home_fellow_pool() -> List[Fellow]:
    """All homepage-eligible fellows from Airtable (`people`, tag fellow)."""
    people = _safe(settings.airtable_table_people)
    pool: List[Fellow] = []
    for f in _people_with_tag(people, "fellow"):
        name = txt(pick(f, "name"))
        photo = person_photo(pick(f, "photo"))
        if not name or not photo:
            continue
        pool.append(Fellow(
            year=_fellow_year(f),
            name=name,
            university=txt(pick(f, "university")),
            department=txt(pick(f, "department")),
            image=photo,
            color="teal",
        ))
    return pool


def pick_fellow_spotlight(pool: List[Fellow], count: Optional[int] = None) -> List[Fellow]:
    """Random subset with teal / coral / ink rotation (homepage belt)."""
    if not pool:
        return []
    k = count if count is not None else settings.home_fellows_spotlight_count
    k = max(1, min(k, len(pool)))
    picked = random.sample(pool, k)
    return [
        f.model_copy(update={"color": PALETTE[i % len(PALETTE)]})
        for i, f in enumerate(picked)
    ]


def _apply_fellows(content: HomeContent, people: List[Dict[str, Any]]) -> None:
    """Legacy helper — prefer build_home_fellow_pool + pick_fellow_spotlight."""
    pool = build_home_fellow_pool()
    if pool:
        content.fellows = pick_fellow_spotlight(pool)


# --------------------------------------------------------------------------- #
# People (about page)
# --------------------------------------------------------------------------- #
def build_people() -> PeopleContent:
    people = _safe(settings.airtable_table_people)
    return PeopleContent(
        trustees=_sort_persons_alpha(_persons(people, "mh")),
        directors=_sort_trustees_priority(_persons(people, "yk")),
        team=_sort_persons_alpha(_persons(people, "team")),
        fellows=_sort_persons_alpha(_persons(people, "fellow")),
        alumni=_sort_persons_alpha(_persons(people, "alumni")),
        challengers=_sort_persons_alpha(_persons(people, "challenger")),
    )


def _tags(fields: Dict[str, Any]) -> List[str]:
    t = pick(fields, "tag") or pick(fields, "tags") or []
    if isinstance(t, list):
        return [str(x) for x in t]
    return [str(t)] if t else []


# Airtable typos / plurals → canonical site tags.
_TAG_ALIASES: Dict[str, frozenset[str]] = {
    "challenger": frozenset({"challenger", "challengers", "challlenger"}),
    "team": frozenset({"team", "ekip", "staff"}),
}


def _has_tag(tags: List[str], tag: str) -> bool:
    want = tag.lower()
    aliases = _TAG_ALIASES.get(want, frozenset({want}))
    return any(str(t).lower() in aliases for t in tags)


def _people_with_tag(people: List[Dict[str, Any]], tag: str) -> List[Dict[str, Any]]:
    """Preserve Airtable row order; alphabetical sort applied per section when needed."""
    rows: List[Dict[str, Any]] = []
    for r in people:
        f = r.get("fields", {})
        if _has_tag(_tags(f), tag):
            rows.append(f)
    return rows


def _persons(people: List[Dict[str, Any]], tag: str) -> List[Person]:
    out: List[Person] = []
    for f in _people_with_tag(people, tag):
        name = txt(pick(f, "name"))
        first, last = _split_name(name)
        out.append(Person(
            first=first,
            last=last,
            company=txt(pick(f, "organisation", "organization", "company")),
            position=txt(pick(f, "title", "position")),
            university=txt(pick(f, "university")),
            department=txt(pick(f, "department")),
            photo=person_photo(pick(f, "photo"))
            or person_photo(pick(f, "attachments", "Attachment", "image")),
            linkedin=_normalize_linkedin(pick(f, "linkedin")),
            roles=_tags(f),
            year=_fellow_year(f),
        ))
    return out


def _tr_sort_key(s: str) -> str:
    """Turkish collation key (Ç, Ğ, I/İ, Ö, Ş, Ü). Falls back to folded ASCII-ish."""
    try:
        import locale

        locale.setlocale(locale.LC_COLLATE, "tr_TR.UTF-8")
        return locale.strxfrm(s)
    except locale.Error:
        try:
            import locale

            locale.setlocale(locale.LC_COLLATE, "tr_TR")
            return locale.strxfrm(s)
        except locale.Error:
            # Manual fold when Turkish locale is unavailable.
            table = str.maketrans({
                "İ": "i", "I": "ı", "Ş": "s\u035f", "ş": "s\u035f",
                "Ğ": "g\u035f", "ğ": "g\u035f", "Ü": "u\u035f", "ü": "u\u035f",
                "Ö": "o\u035f", "ö": "o\u035f", "Ç": "c\u035f", "ç": "c\u035f",
            })
            return s.translate(table).casefold()


def _person_full_name(p: Person) -> str:
    return f"{p.first} {p.last}".strip()


# Board of directors (yk): chair first, vice second, then Turkish A–Z.
_TRUSTEE_PRIORITY = ("sina", "yomi")


def _trustee_rank(p: Person) -> int:
    first = p.first.casefold().strip()
    fn = _person_full_name(p).casefold()
    for i, key in enumerate(_TRUSTEE_PRIORITY):
        if first == key or fn.startswith(f"{key} "):
            return i
    return len(_TRUSTEE_PRIORITY)


def _sort_trustees_priority(people: List[Person]) -> List[Person]:
    return sorted(
        people,
        key=lambda p: (_trustee_rank(p), _tr_sort_key(_person_full_name(p))),
    )


def _sort_persons_alpha(people: List[Person]) -> List[Person]:
    """Sort by full name as in Airtable (first + last), Turkish alphabetical order."""
    return sorted(
        people,
        key=lambda p: _tr_sort_key(f"{p.first} {p.last}".strip()),
    )


def _split_name(name: str):
    """'Deniz Hale Durakbaşı' → ('Deniz Hale', 'Durakbaşı')."""
    parts = name.split()
    if len(parts) <= 1:
        return name, ""
    return " ".join(parts[:-1]), parts[-1]


# --------------------------------------------------------------------------- #
# Fellow program page (`fellow` table)
# --------------------------------------------------------------------------- #
# Airtable `fellow` rows are tagged fragments:
#   fellow_hero | fellow_about | fellow_application | fellow_whattoexpect |
#   fellow_fellows | fellow_alumni | fellow_giveback |
#   challenger_hero | challenger_application | challenger_whatyou'lldo |
#   challenger_challengers
# Fields: name, text, hover text, attachments, tag, dynamic, active.
# If any row has `active` checked, only active rows are used (Airtable "active" view).

_WTE_CAPS = [
    "cap-top cap-left",
    "cap-bottom cap-right",
    "cap-top cap-left",
    "cap-bottom cap-right",
    "cap-top cap-left",
    "cap-bottom cap-right",
]

_WYD_FALLBACK_ICONS = [
    "/images/chal-1-key.png",
    "/images/chal-2-workshop.png",
    "/images/chal-3-talk.png",
    "/images/chal-4-heads.png",
    "/images/chal-5-spark.png",
]


def build_fellow_content(seed: FellowContent) -> FellowContent:
    """Map Airtable `fellow` tab fragments onto FellowContent (seed + overrides)."""
    records = _safe(settings.airtable_table_fellow)
    if not records:
        return seed

    fields_list = _fellow_active_fields(records)
    by_name = {txt(pick(f, "name")): f for f in fields_list}
    content = seed.model_copy(deep=True)

    # --- fellow_hero ---
    hero = _frag(by_name, "fellow_hero_headline")
    hero_text = txt(pick(hero, "text"))
    hero_img = photo_attachment(pick(hero, "attachments"))
    if hero_text:
        content.hero_headline = hero_text
        content.hero_headline_html = _fellow_hero_html(hero_text)
    if hero_img:
        content.hero_image = hero_img
    content.hero_cta_primary = _fellow_cta_from(by_name, "fellow_hero_cta_primary", content.hero_cta_primary)
    content.hero_cta_secondary = _fellow_cta_from(by_name, "fellow_hero_cta_secondary", content.hero_cta_secondary)

    # --- fellow_about ---
    about = txt(pick(_frag(by_name, "fellow_about_text"), "text"))
    if about:
        content.about_html = _md_hl(about) if ("**" in about) else _fellow_about_html(about)

    # --- fellow_application (criteria + selection) ---
    content.application = _how_block_fields(
        by_name, "fellow_application_1_subheadline", "fellow_application_1_text", content.application
    )
    content.selection = _how_block_fields(
        by_name, "fellow_application_2_subheadline", "fellow_application_2_text", content.selection
    )

    # --- fellow_whattoexpect ---
    wte_h = txt(pick(_frag(by_name, "fellow_whattoexpect_headline"), "text"))
    if wte_h:
        content.what_to_expect_headline = wte_h
    wte_cards = _tagged_numbered(fields_list, "fellow_whattoexpect", "fellow_whattoexpect_")
    if wte_cards:
        cards: List[FellowExpectCard] = []
        for i, f in enumerate(wte_cards):
            name, desc = _title_desc(txt(pick(f, "text")))
            hover = txt(pick(f, "hover text", "hover_text"))
            if hover and not desc:
                desc = hover
            img = photo_attachment(pick(f, "attachments"))
            if not name and not img:
                continue
            prior = content.what_to_expect[i] if i < len(content.what_to_expect) else None
            cards.append(FellowExpectCard(
                name=name or (prior.name if prior else ""),
                desc=desc or (prior.desc if prior else ""),
                image=img or (prior.image if prior else ""),
                cap=_WTE_CAPS[i % len(_WTE_CAPS)],
            ))
        if cards:
            content.what_to_expect = cards

    # --- fellow_fellows ---
    fh = txt(pick(_frag(by_name, "fellow_fellows_headline"), "text"))
    if fh:
        content.fellows_headline = fh
    content.fellows_cta = _fellow_cta_from(by_name, "fellow_fellows_cta", content.fellows_cta)

    # --- fellow_alumni ---
    ah = txt(pick(_frag(by_name, "fellow_alumni_headline"), "text"))
    if ah:
        content.alumni_headline = ah
        content.alumni_headline_html = _alumni_headline_html(ah)
    ai = txt(pick(_frag(by_name, "fellow_alumni_text"), "text"))
    if ai:
        content.alumni_intro = ai
    al = txt(pick(_frag(by_name, "fellow_alumni_subheadline"), "text"))
    if al:
        content.alumni_label = al
    ab = txt(pick(_frag(by_name, "fellow_alumni_subtext"), "text"))
    if ab:
        content.alumni_bullets = _paragraphs(ab)
    content.alumni_cta = _fellow_cta_from(by_name, "fellow_alumni_cta", content.alumni_cta)

    # --- fellow_giveback ---
    gh = txt(pick(_frag(by_name, "fellow_giveback_headline"), "text"))
    if gh:
        content.giveback_headline = gh
        content.giveback_headline_html = _giveback_headline_html(gh)
    gt = txt(pick(_frag(by_name, "fellow_giveback_text"), "text"))
    if gt:
        paras = _paragraphs(gt)
        if paras:
            content.giveback_lead = paras[0]
            content.giveback_body = " ".join(paras[1:]) if len(paras) > 1 else content.giveback_body
    content.giveback_cta = _fellow_cta_from(by_name, "fellow_giveback_cta", content.giveback_cta)

    # --- challenger_hero ---
    ch = _frag(by_name, "challenger_hero_headline")
    cht = txt(pick(ch, "text"))
    chi = photo_attachment(pick(ch, "attachments"))
    if cht:
        content.challenger_hero_headline = cht
        content.challenger_hero_headline_html = _challenger_hero_html(cht)
    if chi:
        content.challenger_hero_image = chi
    ctext = txt(pick(_frag(by_name, "challenger_hero_text"), "text"))
    if ctext:
        blocks = [b.strip() for b in re.split(r"\n\s*\n", ctext) if b.strip()]
        if len(blocks) < 2:
            blocks = _paragraphs(ctext)
        content.challenger_paragraphs = [_challenger_para_html(b) for b in blocks]
    content.challenger_cta_primary = _fellow_cta_from(
        by_name, "challenger_hero_cta_primary", content.challenger_cta_primary
    )
    content.challenger_cta_secondary = _fellow_cta_from(
        by_name, "challenger_hero_cta_secondary", content.challenger_cta_secondary
    )

    # --- challenger_application ---
    content.challenger_application = _how_block_fields(
        by_name,
        "challenger_application_1_subheadline",
        "challenger_application_1_text",
        content.challenger_application,
    )
    content.challenger_selection = _how_block_fields(
        by_name,
        "challenger_application_2_subheadline",
        "challenger_application_2_text",
        content.challenger_selection,
    )

    # --- challenger_whatyou'lldo ---
    # Airtable naming varies: you might have `challenger_whatyou'lldo` (headline)
    # or `challenger_whatyou'lldo_headline`. Icons live in `challenger_whatyou'lldo_1..5`.
    wyd_h = txt(pick(_frag(by_name, "challenger_whatyou'lldo_headline"), "text"))
    if not wyd_h:
        wyd_h = txt(pick(_frag(by_name, "challenger_whatyou'lldo"), "text"))
    if not wyd_h:
        # Fallback: find anything in the tag family that matches the headline name.
        for f in _fields_with_tag(fields_list, "challenger_whatyou'lldo"):
            nm = txt(pick(f, "name")).lower()
            if re.match(r"^challenger_whatyou.?ll.?do(_headline)?\s*$", nm, re.I):
                wyd_h = txt(pick(f, "text"))
                break
    if wyd_h:
        content.what_youll_do_headline = wyd_h

    # Prefer exact numbered fragment fields, independent of tag mismatch.
    named_wyd_rows = [
        f for f in fields_list
        if re.match(r"challenger_whatyou.?ll.?do_\d+\s*$", txt(pick(f, "name")), re.I)
    ]
    named_wyd_rows = sorted(named_wyd_rows, key=lambda f: _trailing_int(txt(pick(f, "name"))))

    vyd_rows = named_wyd_rows
    if not vyd_rows:
        vyd_rows = _tagged_numbered(
            fields_list,
            "challenger_whatyou'lldo",
            "challenger_whatyou'lldo_",
        )
    if not vyd_rows:
        vyd_rows = [
            f for f in fields_list
            if re.match(r"challenger_whatyou.?ll.?do_\d+\s*$", txt(pick(f, "name")), re.I)
        ]
        vyd_rows = sorted(vyd_rows, key=lambda f: _trailing_int(txt(pick(f, "name"))))
    if vyd_rows:
        items: List[FellowWydItem] = []
        for i, f in enumerate(vyd_rows):
            text = txt(pick(f, "text"))
            img = (
                photo_attachment(pick(f, "attachments"))
                or photo_attachment(pick(f, "photo"))
                or photo_attachment(pick(f, "image"))
            )
            # Allow plain URL fields if Airtable stores icon as a URL text.
            if not img:
                url = txt(pick(f, "photo", "image", "icon", "url"))
                if url.startswith("http"):
                    img = url
            prior = content.what_youll_do[i] if i < len(content.what_youll_do) else None
            items.append(FellowWydItem(
                text=text or (prior.text if prior else ""),
                image=img or (prior.image if prior else (_WYD_FALLBACK_ICONS[i] if i < len(_WYD_FALLBACK_ICONS) else "")),
            ))
        if items:
            content.what_youll_do = items

    # --- challenger_challengers ---
    chh = txt(pick(_frag(by_name, "challenger_challengers_headline"), "text"))
    if chh:
        content.challengers_headline = chh
    content.challengers_cta = _fellow_cta_from(
        by_name, "challenger_challengers_cta", content.challengers_cta
    )

    return content


def _fellow_active_fields(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return field dicts; if any `active` is checked, keep only those rows."""
    all_fields = [r.get("fields", {}) for r in records]
    active = [f for f in all_fields if pick(f, "active") is True]
    return active if active else all_fields


def _frag(by_name: Dict[str, Dict[str, Any]], name: str) -> Dict[str, Any]:
    return by_name.get(name, {})


def _row_tag(fields: Dict[str, Any]) -> str:
    t = pick(fields, "tag") or pick(fields, "tags") or ""
    if isinstance(t, list):
        return str(t[0]).strip() if t else ""
    return str(t).strip()


def _fields_with_tag(fields_list: List[Dict[str, Any]], tag: str) -> List[Dict[str, Any]]:
    want = tag.lower()
    return [f for f in fields_list if _row_tag(f).lower() == want]


def _tagged_numbered(
    fields_list: List[Dict[str, Any]], tag: str, name_prefix: str
) -> List[Dict[str, Any]]:
    """Numbered cards in a tag family (`…_1`, `…_2`, …), excluding `…_headline`."""
    tagged = _fields_with_tag(fields_list, tag)
    strict = [
        f for f in tagged
        if re.match(re.escape(name_prefix) + r"\d+\s*$", txt(pick(f, "name")))
    ]
    if strict:
        return sorted(strict, key=lambda f: _trailing_int(txt(pick(f, "name"))))
    loose = [
        f for f in tagged
        if re.search(r"_\d+\s*$", txt(pick(f, "name")))
        and "headline" not in txt(pick(f, "name")).lower()
    ]
    return sorted(loose, key=lambda f: _trailing_int(txt(pick(f, "name"))))


def _numbered_fields(records: List[Dict[str, Any]], prefix: str) -> List[Dict[str, Any]]:
    """Rows named `{prefix}{n}` ordered by n (excludes `…_headline`)."""
    out: List[Dict[str, Any]] = []
    for r in records:
        f = r.get("fields", {})
        name = txt(pick(f, "name"))
        if re.match(re.escape(prefix) + r"\d+\s*$", name):
            out.append(f)
    return sorted(out, key=lambda f: _trailing_int(txt(pick(f, "name"))))


def _fellow_cta_from(by_name: Dict[str, Dict[str, Any]], key: str, current: FellowCta) -> FellowCta:
    f = by_name.get(key, {})
    label = txt(pick(f, "text"))
    href = _href_from_fields(f, current.href or "#")
    if not label:
        return current
    return FellowCta(label=label, href=href)


def _how_block_fields(
    by_name: Dict[str, Dict[str, Any]],
    label_key: str,
    text_key: str,
    current: FellowHowBlock,
) -> FellowHowBlock:
    label = txt(pick(by_name.get(label_key, {}), "text"))
    raw = txt(pick(by_name.get(text_key, {}), "text"))
    if not label and not raw:
        return current
    paragraphs: List[str] = []
    kicker = current.kicker
    if raw:
        lines = _paragraphs(raw)
        if lines:
            last = lines[-1]
            bare = re.sub(r"[*_]", "", last).strip().lower().replace("\u2019", "'")
            if bare.startswith("that's it") or (last.startswith("**") and last.endswith("**")):
                kicker = re.sub(r"\*+", "", last).strip()
                lines = lines[:-1]
            paragraphs = [_md_hl(ln) for ln in lines]
    return FellowHowBlock(
        label=label or current.label,
        paragraphs=paragraphs or current.paragraphs,
        kicker=kicker,
    )


def _title_desc(text: str) -> tuple[str, str]:
    """`**Title**\\ndesc` or `Title\\ndesc` → (title, desc)."""
    text = text.strip()
    m = re.match(r"\*\*(.+?)\*\*\s*(.*)", text, re.S)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    lines = _paragraphs(text)
    if not lines:
        return "", ""
    if len(lines) == 1:
        return lines[0], ""
    return lines[0], " ".join(lines[1:])


def _md_hl(s: str) -> str:
    """Inline markdown: **_x_** / **x** → <span class=\"hl\"> (with optional <em>)."""
    parts: List[str] = []
    i = 0
    while i < len(s):
        m_bi = re.match(r"\*\*_(.+?)_\*\*", s[i:])
        if m_bi:
            parts.append(f'<span class="hl"><em>{html.escape(m_bi.group(1))}</em></span>')
            i += m_bi.end()
            continue
        m_b = re.match(r"\*\*(.+?)\*\*", s[i:])
        if m_b:
            parts.append(f'<span class="hl">{html.escape(m_b.group(1))}</span>')
            i += m_b.end()
            continue
        nxt = s.find("**", i)
        chunk = s[i:] if nxt < 0 else s[i:nxt]
        parts.append(html.escape(chunk))
        if nxt < 0:
            break
        i = nxt
    return "".join(parts)


def _fellow_hero_html(raw: str) -> str:
    """'A community that backs you. For life.' → last sentence highlighted."""
    text = raw.strip()
    m = re.match(r"^(.+?\.)\s+(.+)$", text)
    if m:
        return f'{html.escape(m.group(1))}<br /><span class="hl">{html.escape(m.group(2))}</span>'
    return html.escape(text)


def _fellow_about_html(raw: str) -> str:
    """Highlight key phrases when Airtable sends plain text (no markdown)."""
    text = html.escape(raw)
    phrases = [
        "GİRVAK Fellow Program",
        "entrepreneurial mindset",
        "don't need to be entrepreneurs",
        "don\u2019t need to be entrepreneurs",
        "proactive, solution-oriented, and resilient",
    ]
    for p in phrases:
        esc = html.escape(p)
        if esc in text:
            text = text.replace(esc, f'<span class="hl">{esc}</span>', 1)
    return text


def _alumni_headline_html(raw: str) -> str:
    text = raw.strip().rstrip(".")
    m = re.match(r"^(once a fellow,)\s*(always)\s*(a fellow)\.?$", text, re.I)
    if m:
        return (
            f'{html.escape(m.group(1))} <span class="falum-em">{html.escape(m.group(2))}</span> '
            f"{html.escape(m.group(3))}."
        )
    return html.escape(raw.strip())


def _giveback_headline_html(raw: str) -> str:
    text = raw.strip()
    m = re.match(r"^(.*\bmoves\s+)(forward\.?)\s*$", text, re.I)
    if m:
        return f'{html.escape(m.group(1))}<span class="fbecause-em">{html.escape(m.group(2))}</span>'
    return html.escape(text)


def _challenger_hero_html(raw: str) -> str:
    text = raw.strip()
    m = re.match(r"^(Your first step)\s+(into the entrepreneurial world)\.?$", text, re.I)
    if m:
        return (
            f'<span style="color: #f2a81d">{html.escape(m.group(1))}</span><br />'
            f'<span style="color: #373d42">{html.escape(m.group(2))}</span>'
        )
    parts = text.split()
    if len(parts) >= 4:
        left = " ".join(parts[:3])
        right = " ".join(parts[3:])
        return (
            f'<span style="color: #f2a81d">{html.escape(left)}</span><br />'
            f'<span style="color: #373d42">{html.escape(right)}</span>'
        )
    return html.escape(text)


def _challenger_para_html(raw: str) -> str:
    text = html.escape(raw)
    for p in (
        "Challenger Program",
        "first and second-year university students",
        "early discovery track",
    ):
        esc = html.escape(p)
        if esc in text:
            text = text.replace(esc, f'<span class="chl">{esc}</span>', 1)
    return text


# --------------------------------------------------------------------------- #
# About page (`about` table)
# --------------------------------------------------------------------------- #
_WWS_COLORS = ["#19BAD1", "#373D42", "#F76C53"]
_WWS_FALLBACK_IMAGES = [
    "/images/wd-talent.jpg",
    "/images/wd-entrepreneur.jpg",
    "/images/wd-commonground.jpg",
]


def build_about_content(seed: AboutContent) -> AboutContent:
    rows = _safe(settings.airtable_table_about)
    if not rows:
        return seed

    by_name = _by_name(rows)
    content = seed.model_copy(deep=True)

    hero_raw = txt(pick(by_name.get("about_aboutus_headline", {}), "text"))
    if hero_raw:
        content.hero_html = _about_hero_html(hero_raw)

    about_body = txt(pick(by_name.get("about_aboutus_text", {}), "text"))
    if about_body:
        content.about_paragraphs = _paragraphs(about_body)

    mk = txt(pick(by_name.get("about_mission_headline", {}), "text"))
    mt = txt(pick(by_name.get("about_mission_text", {}), "text"))
    mi = photo_attachment(pick(by_name.get("about_mission_headline", {}), "attachments"))
    if mk or mt or mi:
        content.mission = AboutMission(
            kicker=mk or content.mission.kicker,
            headline=mt or content.mission.headline,
            image=mi or content.mission.image,
        )

    sh = txt(pick(by_name.get("about_ourstory_headline", {}), "text"))
    st = txt(pick(by_name.get("about_ourstory_text", {}), "text"))
    if sh:
        content.story_headline = sh
    if st:
        content.story_paragraphs = [_rich_para(p) for p in _paragraphs(st)]

    wwh = txt(pick(by_name.get("about_seo_title", {}), "text"))
    wwd = txt(pick(by_name.get("about_seo_description", {}), "text"))
    if wwh:
        content.seo_title = wwh
    if wwd:
        content.seo_description = wwd

    wwh = txt(pick(by_name.get("about_whatwesolve_headline", {}), "text"))
    if wwh:
        content.what_we_solve_headline = wwh

    strips: List[AboutWwsStrip] = []
    wws_rows = sorted(
        [
            r.get("fields", {})
            for r in rows
            if re.match(r"about_whatwesolve_\d+\s*$", txt(pick(r.get("fields", {}), "name")))
        ],
        key=lambda f: _trailing_int(txt(pick(f, "name"))),
    )
    for i, f in enumerate(wws_rows):
        label = txt(pick(f, "text")).title()
        hover = txt(pick(f, "hover text"))
        headline, desc = _wws_hover(hover, label)
        img = (
            photo_attachment(pick(f, "attachments"))
            or photo_attachment(pick(f, "photo", "image"))
            or _WWS_FALLBACK_IMAGES[i % 3]
        )
        strips.append(AboutWwsStrip(
            label=label,
            headline=headline,
            desc=desc,
            overlay_color=_WWS_COLORS[i % 3],
            image=img,
            href=txt(
                pick(
                    f,
                    "link",
                    "url",
                    "href",
                    "external link",
                    "external_link",
                    "external link url",
                )
            ) or "#",
        ))
    if strips:
        content.what_we_solve_strips = strips

    content.trustees = _section_head(
        by_name, "about_boardoftrustees_headline", "about_boardoftrustees_subheadline", content.trustees
    )
    content.directors = _section_head(
        by_name, "about_board_headline", "about_board_subheadline", content.directors
    )
    content.team = _section_head(
        by_name, "about_team_headline", "about_team_subheadline", content.team
    )
    content.reports = _cta_band(
        by_name, "about_reports_headline", "about_reports_text", "about_reports_cta", content.reports
    )
    content.work_with_us = _cta_band(
        by_name, "about_workwithus_headline", "about_workwithus_text", "about_workwithus_cta", content.work_with_us
    )

    return content


def _section_head(by_name, headline_key, sub_key, current: AboutSectionHead) -> AboutSectionHead:
    h = txt(pick(by_name.get(headline_key, {}), "text"))
    s = txt(pick(by_name.get(sub_key, {}), "text"))
    if not h and not s:
        return current
    return AboutSectionHead(
        headline=h or current.headline,
        subheadline=s or current.subheadline,
    )


def _cta_band(by_name, headline_key, text_key, cta_key, current: AboutCtaBand) -> AboutCtaBand:
    h = txt(pick(by_name.get(headline_key, {}), "text"))
    t = txt(pick(by_name.get(text_key, {}), "text"))
    cta_row = by_name.get(cta_key, {})
    c = txt(pick(cta_row, "text"))
    if not (h or t or c):
        return current
    return AboutCtaBand(
        headline=h or current.headline,
        text=t or current.text,
        cta_label=c or current.cta_label,
        cta_href=_link_from_fields(cta_row, current.cta_href),
    )


def _paragraphs(text: str) -> List[str]:
    lines = [ln.strip() for ln in text.replace("\r\n", "\n").split("\n")]
    return [ln for ln in lines if ln]


def _rich_para(s: str) -> str:
    parts = re.split(r"\*\*(.+?)\*\*", s)
    out: List[str] = []
    for i, part in enumerate(parts):
        if i % 2 == 1:
            out.append(f"<strong>{html.escape(part)}</strong>")
        else:
            out.append(html.escape(part))
    return "".join(out)


def _wws_hover(hover: str, label: str) -> tuple[str, str]:
    if not hover:
        return label, ""
    lines = _paragraphs(hover)
    if len(lines) >= 2:
        return lines[0], " ".join(lines[1:])
    return lines[0] if lines else label, ""


def _about_hero_html(raw: str) -> str:
    text = raw.strip().replace("\u2019", "'").replace("\u2018", "'")
    m = re.match(
        r"^(Entrepreneurship is not just about)\s+(starting companies\.)\s+"
        r"(It(?:'s))\s+(a mindset)\.?\s*$",
        text,
        re.I,
    )
    if m:
        return (
            f"{html.escape(m.group(1))}<br /> {html.escape(m.group(2))}<br /> "
            f"{html.escape(m.group(3))} <span class=\"ab-accent\">{html.escape(m.group(4))}</span>"
            f"<span class=\"ab-dot\">.</span>"
        )
    # Generic: honour explicit line breaks from Airtable.
    if "\n" in text:
        return "<br />".join(html.escape(ln) for ln in _paragraphs(text))
    return html.escape(text)
