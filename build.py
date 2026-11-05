#!/usr/bin/env python3
"""Builds the website from src/ into dist/. New here? Read README.md first."""

import argparse
import datetime
import hashlib
import html
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import urllib.request
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
    if name.startswith("TODO"):
        return "?"

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


def board_values(member: dict[str, str], lang: str) -> dict[str, str]:
    for field in ("name", "role", "major"):
        if not member.get(field):
            sys.exit(f"A [[board]] entry in src/site.toml is missing its {field}: {member}")

    photo = member.get("photo", "")
    if photo and not (SRC / "assets" / "board" / photo).exists():
        sys.exit(f"Board photo not found: put {photo} in src/assets/board/")

    return {
        "name": display(member["name"]),
        "plain_name": html.escape(member["name"]),
        "role": display(translated(member, "role", lang)),
        "major": display(translated(member, "major", lang)),
        "photo": html.escape(photo),
        "linkedin": html.escape(member.get("linkedin", "")),
        "initials": html.escape(initials(member["name"])),
    }


def event_values(event: dict[str, str], lang: str) -> dict[str, str]:
    for field in ("date", "title"):
        if not event.get(field):
            sys.exit(f"An [[events]] entry in src/site.toml is missing its {field}: {event}")

    return {field: display(translated(event, field, lang)) for field in ("date", "title", "description", "where")}


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


def language_values(config: dict, shared: dict[str, str], lang: str) -> dict[str, str]:
    values = {**shared, "HERO_ALT": html.escape(translated(config["hero"], "alt", lang))}
    events = [event_values(event, lang) for event in config.get("events", [])]
    board = [board_values(member, lang) for member in config.get("board", [])]
    values["EVENTS"] = render_list("event", events, values, lang)
    values["BOARD_CARDS"] = render_list("board-card", board, values, lang)

    return values


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

    return rendered.replace(current_link, f'{current_link} aria-current="page"')


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
    shared_by_lang = {lang: language_values(config, shared, lang) for lang in (ENGLISH, PORTUGUESE)}

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
