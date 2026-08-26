"""
Module: girvak/modules/content/markup.py
Layer: Service
Purpose: Turn editor copy into the exact markup the design expects: inline
         highlights, paragraph splits, and the few headline shapes the pages
         style by hand. Everything an editor writes is escaped first — only the
         spans this file adds are markup.

Dependencies: none
Called by: modules/content/{home,about,fellow}.py
Calls: nothing
"""

from __future__ import annotations

import html
import re

_HIGHLIGHT_BOLD_ITALIC = re.compile(r"\*\*_(.+?)_\*\*")
_HIGHLIGHT_BOLD = re.compile(r"\*\*(.+?)\*\*")


def highlight(value: str) -> str:
    """Render inline markdown emphasis as the design's highlight span.

    `**x**` becomes `<span class="hl">x</span>`; `**_x_**` adds an `<em>`.

    Args:
        value: Editor copy, possibly with `**` emphasis.

    Returns:
        Escaped HTML with highlight spans.
    """
    parts: list[str] = []
    index = 0
    while index < len(value):
        bold_italic = _HIGHLIGHT_BOLD_ITALIC.match(value, index)
        if bold_italic:
            parts.append(f'<span class="hl"><em>{html.escape(bold_italic.group(1))}</em></span>')
            index = bold_italic.end()
            continue
        bold = _HIGHLIGHT_BOLD.match(value, index)
        if bold:
            parts.append(f'<span class="hl">{html.escape(bold.group(1))}</span>')
            index = bold.end()
            continue
        next_marker = value.find("**", index)
        chunk = value[index:] if next_marker < 0 else value[index:next_marker]
        parts.append(html.escape(chunk))
        if next_marker < 0:
            break
        index = next_marker
    return "".join(parts)


def strong(value: str) -> str:
    """Render `**x**` as `<strong>x</strong>`.

    Args:
        value: Editor copy.

    Returns:
        Escaped HTML with strong runs.
    """
    parts = re.split(r"\*\*(.+?)\*\*", value)
    return "".join(
        f"<strong>{html.escape(part)}</strong>" if index % 2 else html.escape(part)
        for index, part in enumerate(parts)
    )


def parse_stat(value: str) -> tuple[float, int, str, str] | None:
    """Read an impact tile out of one line of copy.

    `"1.3M+ applications"` becomes `(1.3, 1, "M+", "applications")`.

    Args:
        value: The fragment's text.

    Returns:
        Count, decimal places, suffix, and label — or None when the line is not
        a statistic (which is how non-stat rows in the family are skipped).
    """
    match = re.match(r"^([\d.,]+)([^\s]*)\s+(.+)$", value.strip(), re.S)
    if not match:
        return None
    number, unit, label = match.groups()
    try:
        count = float(number.replace(",", ""))
    except ValueError:
        return None
    decimals = len(number.split(".")[1]) if "." in number else 0
    return count, decimals, unit.strip(), label.strip()


def split_lead(value: str) -> tuple[str, str]:
    """Split a card's copy at the "That's ..." clause.

    Args:
        value: The fragment's text.

    Returns:
        Front lead and front subtitle.
    """
    for marker in ("That's", "That’s"):
        index = value.find(marker)
        if index > 0:
            return value[:index].strip(), value[index:].strip()
    return value.strip(), ""


def eyebrow(subtitle: str) -> str:
    """Reduce a subtitle to the back-of-card eyebrow.

    Args:
        subtitle: The front subtitle.

    Returns:
        The eyebrow text.
    """
    without_prefix = re.sub(r"^That['’]s\s+", "", subtitle).strip().rstrip(".")
    return re.sub(r"^the\s+", "", without_prefix).strip()


def split_subhead(value: str, current: tuple[str, str, str]) -> tuple[str, str, str]:
    """Split the hero subheadline into pre / highlighted / post.

    Args:
        value: Editor copy, optionally marking the highlight with `**`.
        current: The seed's split, used when the copy marks nothing.

    Returns:
        The three parts the hero renders.
    """
    raw = value.strip()
    if not raw:
        return current

    marked = re.match(r"(.+?)\*\*(.+?)\*\*(.*)", raw, re.S)
    if marked:
        return marked.group(1), marked.group(2), marked.group(3)

    highlighted = current[1] or "a way of looking at the world."
    needle = highlighted.lower().rstrip(".")
    index = raw.lower().find(needle)
    if index >= 0:
        end = index + len(needle)
        while end < len(raw) and raw[end] in ". ":
            end += 1
        return raw[:index], raw[index:end].strip(), raw[end:]
    return raw, "", ""


def title_desc(value: str) -> tuple[str, str]:
    """Split a card into its title and its description.

    Accepts `**Title**\\ndesc` and `Title\\ndesc`.

    Args:
        value: The fragment's text.

    Returns:
        Title and description.
    """
    stripped = value.strip()
    marked = re.match(r"\*\*(.+?)\*\*\s*(.*)", stripped, re.S)
    if marked:
        return marked.group(1).strip(), marked.group(2).strip()

    lines = [line.strip() for line in stripped.split("\n") if line.strip()]
    if not lines:
        return "", ""
    if len(lines) == 1:
        return lines[0], ""
    return lines[0], " ".join(lines[1:])


def fellow_hero_html(value: str) -> str:
    """Break the fellow hero after the first sentence and highlight the rest.

    Args:
        value: Editor copy.

    Returns:
        Escaped HTML for the hero headline.
    """
    text = value.strip()
    match = re.match(r"^(.+?\.)\s+(.+)$", text)
    if match:
        return (
            f"{html.escape(match.group(1))}<br />"
            f'<span class="hl">{html.escape(match.group(2))}</span>'
        )
    return html.escape(text)


def fellow_about_html(value: str) -> str:
    """Highlight the program's key phrases when the copy carries no markdown.

    Args:
        value: Editor copy.

    Returns:
        Escaped HTML with the design's highlight spans.
    """
    text = html.escape(value)
    for phrase in (
        "GİRVAK Fellow Program",
        "entrepreneurial mindset",
        "don't need to be entrepreneurs",
        "don’t need to be entrepreneurs",
        "proactive, solution-oriented, and resilient",
    ):
        escaped = html.escape(phrase)
        if escaped in text:
            text = text.replace(escaped, f'<span class="hl">{escaped}</span>', 1)
    return text


def alumni_headline_html(value: str) -> str:
    """Emphasise the middle word of "once a fellow, always a fellow".

    Args:
        value: Editor copy.

    Returns:
        Escaped HTML for the alumni headline.
    """
    text = value.strip().rstrip(".")
    match = re.match(r"^(once a fellow,)\s*(always)\s*(a fellow)\.?$", text, re.I)
    if match:
        return (
            f"{html.escape(match.group(1))} "
            f'<span class="falum-em">{html.escape(match.group(2))}</span> '
            f"{html.escape(match.group(3))}."
        )
    return html.escape(value.strip())


def giveback_headline_html(value: str) -> str:
    """Emphasise the closing word of the give-back headline.

    Args:
        value: Editor copy.

    Returns:
        Escaped HTML for the give-back headline.
    """
    text = value.strip()
    match = re.match(r"^(.*\bmoves\s+)(forward\.?)\s*$", text, re.I)
    if match:
        return (
            f"{html.escape(match.group(1))}"
            f'<span class="fbecause-em">{html.escape(match.group(2))}</span>'
        )
    return html.escape(text)


def challenger_hero_html(value: str) -> str:
    """Two-colour, two-line challenger hero.

    Args:
        value: Editor copy.

    Returns:
        Escaped HTML for the challenger hero headline.
    """
    text = value.strip()
    match = re.match(
        r"^(Your first step)\s+(into the entrepreneurial world)\.?$",
        text,
        re.I,
    )
    if match:
        left, right = match.group(1), match.group(2)
    else:
        words = text.split()
        if len(words) < 4:
            return html.escape(text)
        left, right = " ".join(words[:3]), " ".join(words[3:])

    return (
        f'<span style="color: #f2a81d">{html.escape(left)}</span><br />'
        f'<span style="color: #373d42">{html.escape(right)}</span>'
    )


def challenger_paragraph_html(value: str) -> str:
    """Highlight the challenger programme's key phrases.

    Args:
        value: Editor copy.

    Returns:
        Escaped HTML for one paragraph.
    """
    text = html.escape(value)
    for phrase in (
        "Challenger Program",
        "first and second-year university students",
        "early discovery track",
    ):
        escaped = html.escape(phrase)
        if escaped in text:
            text = text.replace(escaped, f'<span class="chl">{escaped}</span>', 1)
    return text


def about_hero_html(value: str) -> str:
    """The about hero's three-line break with the accented last word.

    Args:
        value: Editor copy.

    Returns:
        Escaped HTML for the about hero.
    """
    text = value.strip().replace("’", "'").replace("‘", "'")
    match = re.match(
        r"^(Entrepreneurship is not just about)\s+(starting companies\.)\s+"
        r"(It(?:'s))\s+(a mindset)\.?\s*$",
        text,
        re.I,
    )
    if match:
        return (
            f"{html.escape(match.group(1))}<br /> {html.escape(match.group(2))}<br /> "
            f"{html.escape(match.group(3))} "
            f'<span class="ab-accent">{html.escape(match.group(4))}</span>'
            f'<span class="ab-dot">.</span>'
        )
    if "\n" in text:
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        return "<br />".join(html.escape(line) for line in lines)
    return html.escape(text)


def format_year(value: str) -> str:
    """Render a cohort year the way the cards show it: `2021` becomes `’21`.

    Args:
        value: Raw year, cohort, or class value.

    Returns:
        The display string, empty when there is nothing to show.
    """
    text = (value or "").strip()
    if not text:
        return ""
    if text[0] in "'’":
        return text if text.startswith("’") else f"’{text[1:]}"
    if re.match(r"^\d{4}$", text):
        return f"’{text[2:]}"
    if re.match(r"^\d{2}$", text):
        return f"’{text}"
    return text
