#!/usr/bin/env python3
"""Builds the website from src/ into dist/. New here? Read README.md first."""

import argparse
import csv
import datetime
import hashlib
import html
import io
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import urllib.error
import urllib.request
import zoneinfo
from pathlib import Path

# Checked before importing tomllib, which would otherwise fail with a confusing traceback.
if sys.version_info < (3, 11):
    sys.exit("This build needs Python 3.11 or newer. Get it from https://www.python.org/downloads/")

import tomllib

# To upgrade Tailwind: change this version and replace tailwind.sha256 with that
# release's sha256sums.txt from https://github.com/tailwindlabs/tailwindcss/releases
TAILWIND_VERSION = "4.3.3"

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
DIST = ROOT / "dist"
PARTIALS = SRC / "partials"
DOMAIN_PLACEHOLDER = "DOMAIN_PLACEHOLDER"
ENGLISH = "en"
PORTUGUESE = "pt-BR"
PORTUGUESE_DIR = "pt"
SHEET_URL = "https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
CAMPUS_TIMEZONE = "America/Chicago"
PAST_EVENTS_SHOWN = 5
LARGE_IMAGE_BYTES = 1_000_000
EVENT_COLUMNS = (
    "date", "start_time", "end_time", "title", "description_pt", "description_en",
    "location", "rsvp_url", "image_path", "instagram_link", "include",
)
BOARD_COLUMNS = ("order", "name", "role_pt", "role_en", "major", "class_year", "image_path", "include")
MONTHS = {
    ENGLISH: (
        "January", "February", "March", "April", "May", "June", "July",
        "August", "September", "October", "November", "December",
    ),
    PORTUGUESE: (
        "janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
        "agosto", "setembro", "outubro", "novembro", "dezembro",
    ),
}


def load_config() -> dict:
    try:
        return tomllib.loads((SRC / "site.toml").read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as error:
        sys.exit(f"src/site.toml has a typo: {error}. Check for a missing quote on that line.")


def read_partial(name: str, lang: str) -> str:
    """Prefers a translated partial such as header.pt-BR.html when one exists."""
    translated = PARTIALS / f"{name}.{lang}.html"
    path = translated if translated.exists() else PARTIALS / f"{name}.html"
    if not path.exists():
        sys.exit(f"Missing partial: src/partials/{name}.html")

    return path.read_text(encoding="utf-8")


def expand_partials(text: str, lang: str) -> str:
    pattern = re.compile(r"\{\{>\s*([\w-]+)\s*\}\}")
    while pattern.search(text):
        text = pattern.sub(lambda match: read_partial(match[1], lang), text)

    return text


def fill(text: str, values: dict[str, str], source: str) -> str:
    """Fills {{NAME}} tokens, and keeps {{#NAME}}...{{/NAME}} only if NAME is set ({{^NAME}} if unset)."""

    def section(match: re.Match) -> str:
        wanted = match[1] == "#"
        return match[3] if bool(values.get(match[2])) == wanted else ""

    def token(match: re.Match) -> str:
        if match[1] not in values:
            sys.exit(f"{source} uses {{{{{match[1]}}}}}, which is not defined in src/site.toml.")

        return values[match[1]]

    text = re.sub(r"\{\{([#^])(\w+)\}\}(.*?)\{\{/\2\}\}", section, text, flags=re.DOTALL)

    return re.sub(r"\{\{(\w+)\}\}", token, text)


def display(value: str) -> str:
    """Escapes a site.toml value for HTML and makes leftover TODOs visible on the page."""
    escaped = html.escape(value)
    return f'<span class="todo">{escaped}</span>' if value.startswith("TODO") else escaped


def initials(name: str) -> str:
    words = name.split()
    return (words[0][0] + words[-1][0]).upper() if len(words) > 1 else words[0][0].upper()


def translated(item: dict[str, str], field: str, lang: str) -> str:
    """Stops the build rather than letting English text appear on a Portuguese page."""
    english = item.get(field, "")
    if lang == ENGLISH or not english:
        return english

    portuguese = item.get(f"{field}_pt", "")
    if not portuguese:
        sys.exit(f'src/site.toml: add {field}_pt, the Portuguese for "{english}".')

    return portuguese


def fetch_tab(config: dict, tab: str, gid_key: str, columns: tuple[str, ...]) -> list[dict[str, str]]:
    """Returns the rows with include checked, adding "row" so errors can name the spreadsheet line."""
    url = SHEET_URL.format(sheet_id=config["sheet"]["id"], gid=config["sheet"][gid_key])
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            text = response.read().decode("utf-8-sig")
    except (urllib.error.URLError, TimeoutError) as error:
        sys.exit(f"Could not read the {tab} tab of the Google Sheet ({error}). Is it shared with anyone with the link?")

    reader = csv.DictReader(io.StringIO(text))
    missing = [column for column in columns if column not in (reader.fieldnames or [])]
    if missing:
        sys.exit(f"The {tab} tab of the Google Sheet is missing these columns: {', '.join(missing)}")

    rows = []
    for number, raw in enumerate(reader, start=2):
        row = {key: " ".join((value or "").split()) for key, value in raw.items() if key in columns}
        if row["include"].upper() == "TRUE":
            rows.append({**row, "row": str(number)})

    return rows


def sheet_error(tab: str, row: dict[str, str], message: str) -> None:
    sys.exit(f"Google Sheet, {tab} tab, row {row['row']}: {message}")


def require(tab: str, row: dict[str, str], *fields: str) -> None:
    for field in fields:
        if not row[field]:
            sheet_error(tab, row, f"{field} is empty.")


def checked_url(tab: str, row: dict[str, str], field: str) -> str:
    if row[field] and not row[field].startswith("https://"):
        sheet_error(tab, row, f"{field} must start with https://")

    return html.escape(row[field])


def image_url_path(tab: str, row: dict[str, str]) -> str:
    """Accepts .jpg and .jpeg interchangeably, the mix-up people are most likely to make in the sheet."""
    if not row["image_path"]:
        return ""

    path = Path(row["image_path"])
    if path.parts[:2] != ("src", "assets") or ".." in path.parts:
        sheet_error(tab, row, f"image_path must start with src/assets/: {row['image_path']}")

    alternates = {".jpg": ".jpeg", ".jpeg": ".jpg"}
    candidates = [path, path.with_suffix(alternates.get(path.suffix.lower(), path.suffix))]
    found = next((ROOT / candidate for candidate in candidates if (ROOT / candidate).is_file()), None)
    if found is None:
        sheet_error(tab, row, f"image not found, upload it to the repository: {row['image_path']}")

    if found.stat().st_size > LARGE_IMAGE_BYTES:
        print(f"WARNING: {found.relative_to(ROOT)} is over 1 MB and will slow the page down.")

    return html.escape(found.relative_to(SRC).as_posix())


def load_board(config: dict) -> list[dict[str, str]]:
    rows = fetch_tab(config, "Board", "board_gid", BOARD_COLUMNS)
    for row in rows:
        require("Board", row, "name", "role_pt", "role_en", "major")

    rows.sort(key=lambda row: float(row["order"]) if row["order"].replace(".", "", 1).isdigit() else float("inf"))

    return [
        {
            "name": html.escape(row["name"]),
            "role_en": html.escape(row["role_en"]),
            "role_pt": html.escape(row["role_pt"]),
            "major": html.escape(row["major"]),
            "class_text": html.escape(f"Class of {row['class_year']}") if row["class_year"] else "",
            "image": image_url_path("Board", row),
            "initials": html.escape(initials(row["name"])),
        }
        for row in rows
    ]


def parse_date(row: dict[str, str]) -> datetime.date:
    try:
        return datetime.datetime.strptime(row["date"], "%Y-%m-%d").date()
    except ValueError:
        sheet_error("Events", row, f"date must look like 2026-09-25, not {row['date']}")


def parse_time(row: dict[str, str], field: str) -> datetime.time | None:
    if not row[field]:
        return None

    for time_format in ("%I:%M %p", "%I:%M:%S %p", "%H:%M"):
        try:
            return datetime.datetime.strptime(row[field], time_format).time()
        except ValueError:
            continue

    sheet_error("Events", row, f"{field} must look like 8:00 PM, not {row[field]}")


def format_time(moment: datetime.time, lang: str) -> str:
    if lang == PORTUGUESE:
        return f"{moment.hour}h{moment.minute:02d}" if moment.minute else f"{moment.hour}h"

    return f"{moment.hour % 12 or 12}:{moment.minute:02d} {'AM' if moment.hour < 12 else 'PM'}"


def format_when(date: datetime.date, start: datetime.time | None, end: datetime.time | None, lang: str) -> str:
    month = MONTHS[lang][date.month - 1]
    day = f"{date.day} de {month} de {date.year}" if lang == PORTUGUESE else f"{month} {date.day}, {date.year}"
    if not start:
        return day

    hours = format_time(start, lang)
    if end:
        separator = " às " if lang == PORTUGUESE else " – "
        hours += separator + format_time(end, lang)

    return f"{day} · {hours}"


def load_events(config: dict) -> list[dict]:
    events = []
    for row in fetch_tab(config, "Events", "events_gid", EVENT_COLUMNS):
        require("Events", row, "date", "title")
        if bool(row["description_pt"]) != bool(row["description_en"]):
            sheet_error("Events", row, "description_pt and description_en must both be filled in, or both empty.")

        date, start, end = parse_date(row), parse_time(row, "start_time"), parse_time(row, "end_time")
        events.append(
            {
                "date": date,
                "start": start or datetime.time.min,
                "title": html.escape(row["title"]),
                "location": html.escape(row["location"]),
                "rsvp": checked_url("Events", row, "rsvp_url"),
                "instagram": checked_url("Events", row, "instagram_link"),
                "image": image_url_path("Events", row),
                "description_en": html.escape(row["description_en"]),
                "description_pt": html.escape(row["description_pt"]),
                "when_en": html.escape(format_when(date, start, end, ENGLISH)),
                "when_pt": html.escape(format_when(date, start, end, PORTUGUESE)),
            }
        )

    return events


def campus_today() -> datetime.date:
    try:
        return datetime.datetime.now(zoneinfo.ZoneInfo(CAMPUS_TIMEZONE)).date()
    except zoneinfo.ZoneInfoNotFoundError:
        return datetime.date.today()


def split_events(events: list[dict], today: datetime.date) -> tuple[list[dict], list[dict]]:
    """An event counts as upcoming through the end of its day on campus."""
    by_time = sorted(events, key=lambda event: (event["date"], event["start"]))
    upcoming = [event for event in by_time if event["date"] >= today]
    past = [event for event in reversed(by_time) if event["date"] < today]

    return upcoming, past[:PAST_EVENTS_SHOWN]


def event_values(event: dict, lang: str, is_past: bool) -> dict[str, str]:
    suffix = "pt" if lang == PORTUGUESE else "en"
    return {
        "title": event["title"],
        "location": event["location"],
        "instagram": event["instagram"],
        "image": event["image"],
        "rsvp": "" if is_past else event["rsvp"],
        "when": event[f"when_{suffix}"],
        "description": event[f"description_{suffix}"],
    }


def board_values(member: dict[str, str], lang: str) -> dict[str, str]:
    return {**member, "role": member["role_pt"] if lang == PORTUGUESE else member["role_en"]}


def link_values(config: dict) -> tuple[dict[str, str], list[str]]:
    """Unfilled links point at #TODO-NAME, so clicking one does nothing instead of hitting a 404."""
    values: dict[str, str] = {}
    unfilled: list[str] = []

    for name, value in config["links"].items():
        if value == "TODO":
            unfilled.append(name)
            values[name] = f"#TODO-{name}"
        else:
            values[name] = html.escape(value)

    email_is_set = "CONTACT_EMAIL" not in unfilled
    values["CONTACT_EMAIL_HREF"] = f"mailto:{values['CONTACT_EMAIL']}" if email_is_set else "#TODO-CONTACT_EMAIL"
    values["CONTACT_EMAIL_TEXT"] = values["CONTACT_EMAIL"] if email_is_set else display("TODO: CONTACT_EMAIL")

    return values, unfilled


def render_list(partial: str, items: list[dict[str, str]], shared: dict[str, str], lang: str) -> str:
    template = read_partial(partial, lang)
    return "\n".join(fill(template, {**shared, **item}, f"partials/{partial}.html") for item in items)


def parse_front_matter(text: str, source: str) -> tuple[dict[str, str], str]:
    match = re.match(r"\s*<!--(.*?)-->", text, flags=re.DOTALL)
    if not match:
        sys.exit(f"{source} must start with a comment holding its title and description.")

    fields = dict(line.split(":", 1) for line in match[1].splitlines() if ":" in line)
    fields = {key.strip(): value.strip() for key, value in fields.items()}
    if not fields.get("title") or not fields.get("description"):
        sys.exit(f"{source} needs both a title and a description in its first comment.")

    return fields, text[match.end():]


def page_url_path(relative: Path) -> str:
    path = "/" + relative.as_posix()
    return path.removesuffix("index.html")


def page_lang(relative: Path) -> str:
    return PORTUGUESE if relative.parts[0] == PORTUGUESE_DIR else ENGLISH


def other_language_path(relative: Path) -> Path:
    if page_lang(relative) == PORTUGUESE:
        return Path(*relative.parts[1:])

    return Path(PORTUGUESE_DIR) / relative


def check_language_pairs(pages: list[Path]) -> None:
    """The language button must never lead to a 404, so every page needs its other-language twin."""
    relative_pages = {page.relative_to(SRC) for page in pages}
    for relative in relative_pages:
        twin = other_language_path(relative)
        if twin not in relative_pages:
            sys.exit(f"src/{relative} has no other-language version: create src/{twin}")


def language_values(
    config: dict,
    shared: dict[str, str],
    lang: str,
    upcoming: list[dict],
    past: list[dict],
    board: list[dict[str, str]],
) -> dict[str, str]:
    values = {**shared, "HERO_ALT": html.escape(translated(config["hero"], "alt", lang))}
    upcoming_items = [event_values(event, lang, is_past=False) for event in upcoming]
    past_items = [event_values(event, lang, is_past=True) for event in past]
    board_items = [board_values(member, lang) for member in board]
    values["UPCOMING_EVENTS"] = render_list("event", upcoming_items, values, lang)
    values["PAST_EVENTS"] = render_list("event", past_items, values, lang)
    values["BOARD_CARDS"] = render_list("board-card", board_items, values, lang)

    return values


def open_external_links_in_new_tab(page: str) -> str:
    return re.sub(r'<a\s[^>]*href="https://[^>]*(?=>)', lambda link: f'{link[0]} target="_blank" rel="noopener"', page)


def render_page(path: Path, shared_by_lang: dict[str, dict[str, str]]) -> str:
    relative = path.relative_to(SRC)
    fields, content = parse_front_matter(path.read_text(encoding="utf-8"), str(relative))
    lang = page_lang(relative)
    shared = shared_by_lang[lang]
    url_path = page_url_path(relative)
    twin_path = page_url_path(other_language_path(relative))
    values = {
        **shared,
        "LANG": lang,
        "OG_LOCALE": "pt_BR" if lang == PORTUGUESE else "en_US",
        "TITLE": html.escape(fields["title"]),
        "DESCRIPTION": html.escape(fields["description"]),
        "PAGE_PATH": url_path,
        "LANG_SWITCH_URL": f'{shared["BASE"]}{twin_path}',
        "ENGLISH_PATH": twin_path if lang == PORTUGUESE else url_path,
        "PORTUGUESE_PATH": url_path if lang == PORTUGUESE else twin_path,
    }
    template = read_partial("layout", lang).replace("{{CONTENT}}", content)
    rendered = fill(expand_partials(template, lang), values, str(relative))
    current_link = f'href="{shared["BASE"]}{url_path}"'

    return open_external_links_in_new_tab(rendered.replace(current_link, f'{current_link} aria-current="page"'))


def tailwind_binary() -> Path:
    system = {"Darwin": "macos", "Linux": "linux", "Windows": "windows"}[platform.system()]
    arch = "arm64" if platform.machine().lower() in ("arm64", "aarch64") else "x64"
    name = f"tailwindcss-{system}-{arch}" + (".exe" if system == "windows" else "")
    binary = ROOT / ".tools" / TAILWIND_VERSION / name
    if binary.exists():
        return binary

    url = f"https://github.com/tailwindlabs/tailwindcss/releases/download/v{TAILWIND_VERSION}/{name}"
    print(f"Downloading Tailwind {TAILWIND_VERSION} (first run only)...")
    with urllib.request.urlopen(url) as response:
        data = response.read()

    checksums = (ROOT / "tailwind.sha256").read_text(encoding="utf-8")
    if f"{hashlib.sha256(data).hexdigest()}  ./{name}" not in checksums:
        sys.exit(f"The downloaded {name} does not match tailwind.sha256, so it was not used.")

    binary.parent.mkdir(parents=True, exist_ok=True)
    binary.write_bytes(data)
    binary.chmod(binary.stat().st_mode | stat.S_IEXEC)

    return binary


def warn_unfilled(unfilled: list[str]) -> None:
    if not unfilled:
        return

    message = "Still TODO in src/site.toml: " + ", ".join(unfilled)
    print(f"::warning::{message}" if os.environ.get("GITHUB_ACTIONS") else f"WARNING: {message}")


def build(base_path: str, site_url: str | None) -> None:
    config = load_config()
    domain = config["site"]["DOMAIN"]
    links, unfilled = link_values(config)
    if domain == DOMAIN_PLACEHOLDER:
        unfilled.append("DOMAIN")

    shared = {
        **links,
        "BASE": base_path.rstrip("/"),
        "SITE_URL": (site_url or f"https://{domain}").rstrip("/"),
        "YEAR": str(datetime.date.today().year),
    }
    upcoming, past = split_events(load_events(config), campus_today())
    board = load_board(config)
    shared_by_lang = {
        lang: language_values(config, shared, lang, upcoming, past, board) for lang in (ENGLISH, PORTUGUESE)
    }

    shutil.rmtree(DIST, ignore_errors=True)
    shutil.copytree(SRC / "assets", DIST / "assets", ignore=shutil.ignore_patterns(".DS_Store", ".gitkeep"))
    cname = (SRC / "CNAME").read_text(encoding="utf-8")
    (DIST / "CNAME").write_text(cname.replace(DOMAIN_PLACEHOLDER, domain), encoding="utf-8")

    pages = [path for path in SRC.rglob("*.html") if PARTIALS not in path.parents]
    check_language_pairs(pages)

    for page in pages:
        output = DIST / page.relative_to(SRC)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(render_page(page, shared_by_lang), encoding="utf-8")

    subprocess.run(
        [tailwind_binary(), "-i", SRC / "input.css", "-o", DIST / "assets" / "site.css", "--minify"],
        cwd=ROOT,
        check=True,
    )
    print(f"Built {len(pages)} pages into dist/")
    warn_unfilled(unfilled)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the BRASA at UIUC website into dist/.")
    parser.add_argument("--base-path", default="", help="URL prefix, set by CI when there is no custom domain yet")
    parser.add_argument("--site-url", default=None, help="Public site URL, set by CI (default: from site.toml)")
    args = parser.parse_args()
    build(args.base_path, args.site_url)


if __name__ == "__main__":
    main()
