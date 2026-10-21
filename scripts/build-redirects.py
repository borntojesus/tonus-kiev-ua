#!/usr/bin/env python3
"""Regenerate the `redirects` array in vercel.json.

Recreates the legacy WordPress redirects lost in the static export: old
root-level article URLs (`/<slug>`) are sent to their language folder
(`/ru/<slug>` or `/uk/<slug>`). All other vercel.json keys are kept as is.

Run from the repo root:  python3 -I scripts/build-redirects.py
The output is deterministic (sorted by source), so the script is idempotent.
"""

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(ROOT, "vercel.json")

IGNORED = {
    ".git", "wp-content", "wp-includes", "wp-json", "cdn-cgi",
    ".claude", ".specify", "scripts",
}
SLUG_RE = re.compile(r"^[a-z0-9-]+$")

# Root-level folders that are near-identical duplicates of a ru/ or uk/ twin.
DUPLICATES = {
    "bytovoj-alkogolizm": "ru",
    "kriptovaljuta-bitkojn-lovushka": "ru",
    "kto-takoj-volontjor": "ru",
    "shho-take-himichna-zalezhnist": "uk",
    "terapevtichne-seredovishhe": "uk",
    "test-na-narkotichni-rechovini-instrukcija-ta-vidminnosti": "uk",
    "testi-na-narkotiki": "uk",
}

# Language roots have no index.html of their own.
FIXED = {
    "/uk": "/uk/home",
    "/ru": "/",
}


def page_slugs(base):
    """Folder names directly under `base` that contain an index.html."""
    path = os.path.join(ROOT, base) if base else ROOT
    slugs = set()
    for name in os.listdir(path):
        if not base and name in IGNORED:
            continue
        if os.path.isfile(os.path.join(path, name, "index.html")):
            slugs.add(name)
    return slugs


def check_slug(slug, where):
    if not SLUG_RE.match(slug):
        sys.exit(f"error: unsafe slug {where}/{slug!r} (allowed: [a-z0-9-])")


def root_path_taken(slug):
    """True if `/<slug>` is already served by something at the repo root."""
    return (
        os.path.exists(os.path.join(ROOT, slug))
        or os.path.exists(os.path.join(ROOT, slug + ".html"))
    )


def main():
    with open(CONFIG, encoding="utf-8") as fh:
        config = json.load(fh)

    root = page_slugs("")
    ru = page_slugs("ru")
    uk = page_slugs("uk")
    for where, slugs in (("", root), ("ru", ru), ("uk", uk)):
        for slug in slugs:
            check_slug(slug, where or ".")

    redirects = {}
    counts = {"duplicates": 0, "ru": 0, "uk": 0, "fixed": 0}

    def add(source, destination, rule):
        if source in redirects:
            sys.exit(f"error: duplicate source {source}")
        redirects[source] = destination
        counts[rule] += 1

    # Rule 1: duplicate root folders go to their twin.
    for slug, lang in sorted(DUPLICATES.items()):
        twin = ru if lang == "ru" else uk
        if slug not in root:
            sys.exit(f"error: duplicate root folder {slug}/ not found")
        if slug not in twin:
            sys.exit(f"error: twin {lang}/{slug}/ not found")
        add(f"/{slug}", f"/{lang}/{slug}", "duplicates")

    # Rule 2: ru slugs without a root page.
    for slug in sorted(ru):
        if slug in DUPLICATES or root_path_taken(slug):
            continue
        add(f"/{slug}", f"/ru/{slug}", "ru")

    # Rule 3: uk slugs without a root page and without a ru twin.
    for slug in sorted(uk):
        if slug in DUPLICATES or slug in ru or root_path_taken(slug):
            continue
        add(f"/{slug}", f"/uk/{slug}", "uk")

    # Rule 4: language roots.
    for source, destination in FIXED.items():
        add(source, destination, "fixed")

    config["redirects"] = [
        {"source": s, "destination": redirects[s], "permanent": True}
        for s in sorted(redirects)
    ]

    if len(config["redirects"]) >= 1024:
        sys.exit(f"error: {len(config['redirects'])} redirects exceeds Vercel limit")

    with open(CONFIG, "w", encoding="utf-8") as fh:
        json.dump(config, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    print(
        f"{len(config['redirects'])} redirects "
        f"(duplicates {counts['duplicates']}, ru {counts['ru']}, "
        f"uk {counts['uk']}, language roots {counts['fixed']})"
    )


if __name__ == "__main__":
    main()
