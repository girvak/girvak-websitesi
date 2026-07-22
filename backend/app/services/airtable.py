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

Images use the direct Airtable attachment URL. NOTE: those URLs are refreshed
periodically by Airtable, so a static build should be rebuilt when content
changes (e.g. via the /api/content/refresh webhook + a redeploy).
"""
from __future__ import annotations

import html
import random
import re
from typing import Any, Dict, List, Optional, Set
from urllib.parse import quote

import httpx

from ..config import settings
from ..models import (
    AboutContent,
    AboutCtaBand,
    AboutMission,
    AboutSectionHead,
    AboutWwsStrip,
    CTA,
    Fellow,
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
    "department", "e-mail", "email", "created", "link", "negative_logo",
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
    except httpx.HTTPError:
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


def _att_url(att: Dict[str, Any], prefer: Optional[str]) -> str:
    """Attachment URL, optionally preferring an Airtable thumbnail size.

    `prefer=None` returns the original — used for partner logos (PNG alpha).
    Photos use `photo_attachment()` which prefers `full` (~3000px) over `large`
    (~512px) so hero / card imagery stays sharp on retina displays.
    """
    if prefer:
        thumb = (att.get("thumbnails") or {}).get(prefer)
        if isinstance(thumb, dict) and thumb.get("url"):
            return thumb["url"]
    return att.get("url", "")


def photo_attachment(value: Any) -> str:
    """Best on-page photo URL: full thumbnail, else original."""
    return first_attachment(value, "full") or first_attachment(value, None)


def logo_attachment(value: Any) -> str:
    """Partner / logo URL — always original (keeps PNG transparency)."""
    return first_attachment(value, None)


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
    site_tags = frozenset({"mh", "yk", "team", "fellow", "alumni", "challenger"})
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


def sync_dynamic_checkboxes() -> Dict[str, Any]:
    """Tick `dynamic` on rows the site uses; clear it on rows it does not."""
    if not settings.airtable_sync_dynamic:
        return {"enabled": False}

    tables: List[tuple[str, Any]] = [
        (settings.airtable_table_home, _home_used_ids),
        (settings.airtable_table_about, _about_used_ids),
        (settings.airtable_table_people, _people_used_ids),
        (settings.airtable_table_partner, _partner_used_ids),
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
                "used_by": "Fellow program page (when wired)",
                "row_names": ["fellow_* fragments"],
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
    _apply_hero(content, home, by_name)
    _apply_impact(content, home)
    _apply_impact_image(content, by_name)
    _apply_whatwedo(content, home)
    _apply_partners(content, partner, by_name)
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
        # Keep seed hrefs (Airtable holds only labels); order: build → open.
        ctas: List[CTA] = []
        if secondary:
            ctas.append(CTA(label=secondary, href=content.hero.ctas[0].href if content.hero.ctas else "#"))
        if primary:
            ctas.append(CTA(label=primary, href=content.hero.ctas[1].href if len(content.hero.ctas) > 1 else "#wwd"))
        content.hero.ctas = ctas

    # Headline + rotator words stay on the seed/design split (`base_text` +
    # `rotator_words`). Airtable `index_hero_headline` is a single line and
    # breaks the word rotator when pasted in wholesale.


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
        img = photo_attachment(pick(f, "attachments"))
        if not img and seed_card:
            img = seed_card.image
        cards.append(WhatWeDoCard(
            href=seed_card.href if seed_card else ("#"),
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
        name = txt(pick(f, "organization", "name"))
        logo = logo_attachment(pick(f, "positive_logo", "logo", "negative_logo"))
        if not name or not logo:
            continue
        p = Partner(name=name, logo=logo)
        tags = pick(f, "Tags", "tags") or []
        is_main = isinstance(tags, list) and any("main" in str(t).lower() for t in tags)
        if is_main and featured is None:
            featured = p
        else:
            logos.append(p)
    if featured:
        content.partners.featured = featured
    if logos:
        content.partners.logos = logos


def build_home_fellow_pool() -> List[Fellow]:
    """All homepage-eligible fellows from Airtable (`people`, tag fellow)."""
    people = _safe(settings.airtable_table_people)
    pool: List[Fellow] = []
    for f in _people_with_tag(people, "fellow"):
        name = txt(pick(f, "name"))
        photo = photo_attachment(pick(f, "photo"))
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
        trustees=_persons(people, "mh"),
        directors=_persons(people, "yk"),
        team=_persons(people, "team"),
        fellows=_persons(people, "fellow"),
        alumni=_persons(people, "alumni"),
        challengers=_persons(people, "challenger"),
    )


def _tags(fields: Dict[str, Any]) -> List[str]:
    t = pick(fields, "tag") or pick(fields, "tags") or []
    if isinstance(t, list):
        return [str(x) for x in t]
    return [str(t)] if t else []


def _has_tag(tags: List[str], tag: str) -> bool:
    want = tag.lower()
    return any(str(t).lower() == want for t in tags)


def _people_with_tag(people: List[Dict[str, Any]], tag: str) -> List[Dict[str, Any]]:
    """Preserve Airtable row order (no alphabetical re-sort)."""
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
            photo=photo_attachment(pick(f, "photo")),
            linkedin=txt(pick(f, "linkedin")),
            roles=_tags(f),
            year=_fellow_year(f),
        ))
    return out


def _split_name(name: str):
    """'Deniz Hale Durakbaşı' → ('Deniz Hale', 'Durakbaşı')."""
    parts = name.split()
    if len(parts) <= 1:
        return name, ""
    return " ".join(parts[:-1]), parts[-1]


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
        img = photo_attachment(pick(f, "attachments")) or _WWS_FALLBACK_IMAGES[i % 3]
        strips.append(AboutWwsStrip(
            label=label,
            headline=headline,
            desc=desc,
            overlay_color=_WWS_COLORS[i % 3],
            image=img,
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
    c = txt(pick(by_name.get(cta_key, {}), "text"))
    if not (h or t or c):
        return current
    return AboutCtaBand(
        headline=h or current.headline,
        text=t or current.text,
        cta_label=c or current.cta_label,
        cta_href=current.cta_href,
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
