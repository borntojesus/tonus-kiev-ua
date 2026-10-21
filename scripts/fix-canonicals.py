#!/usr/bin/env python3
"""Rewrite canonical, hreflang and og:url tags to absolute public URLs.

Run:  python3 -I scripts/fix-canonicals.py [--dry-run]
(the repo root is resolved from this file's location, not the cwd)

hreflang rules: targets must be existing page folders (`<path>.html` is read
as `<path>/` when that folder page exists), the target page's <html lang> must
match the hreflang value, the two home pages pair only with each other, every
page carries exactly one self entry, and pairs are made reciprocal (pass 2).

Idempotent: a second run reports 0 changed pages. Only the three tag kinds in
<head> are touched; everything else (body, RSS/oEmbed/JSON alternates, line
endings) is left byte-for-byte as it was.
"""
import html
import os
import posixpath
import re
import sys
from urllib.parse import quote, unquote, urlsplit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "https://tonus.kiev.ua/"
HOMES = {"", "uk/home"}
IGNORE_DIRS = {".git", "wp-content", "wp-includes", "wp-json", "cdn-cgi",
               ".claude", ".specify", "scripts"}
LANG_ORDER = ["ru", "uk"]

# Root-level duplicates that vercel.json 301s to their twin.
DUPLICATES = {
    "bytovoj-alkogolizm": "ru/bytovoj-alkogolizm",
    "kriptovaljuta-bitkojn-lovushka": "ru/kriptovaljuta-bitkojn-lovushka",
    "kto-takoj-volontjor": "ru/kto-takoj-volontjor",
    "shho-take-himichna-zalezhnist": "uk/shho-take-himichna-zalezhnist",
    "terapevtichne-seredovishhe": "uk/terapevtichne-seredovishhe",
    "test-na-narkotichni-rechovini-instrukcija-ta-vidminnosti":
        "uk/test-na-narkotichni-rechovini-instrukcija-ta-vidminnosti",
    "testi-na-narkotiki": "uk/testi-na-narkotiki",
}

ATTR_RE = re.compile(r'([a-zA-Z_:][-a-zA-Z0-9_:.]*)\s*=\s*(?:"([^"]*)"|\'([^\']*)\')')
LINK_RE = re.compile(r"<link\b[^>]*>", re.I)
META_RE = re.compile(r"<meta\b[^>]*>", re.I)
HTML_LANG_RE = re.compile(r"<html\b[^>]*?\blang\s*=\s*[\"']([^\"']+)[\"']", re.I)
DESC_RE = re.compile(r"<meta\b[^>]*\bname\s*=\s*[\"']description[\"'][^>]*>", re.I)
TRAILING_WS_RE = re.compile(r"(\r?\n[ \t]*)$")


def attrs(tag):
    return {m.group(1).lower(): (m.group(2) if m.group(2) is not None else m.group(3))
            for m in ATTR_RE.finditer(tag)}


def set_attr(tag, name, value):
    """Replace the value of attribute `name` inside `tag`, keeping its quoting."""
    pat = re.compile(r'(\b%s\s*=\s*)(?:"[^"]*"|\'[^\']*\')' % re.escape(name), re.I)
    return pat.sub(lambda m: m.group(1) + '"' + value + '"', tag, count=1)


def page_lang(text):
    m = HTML_LANG_RE.search(text)
    return m.group(1).split("-")[0].lower() if m else None


def public_url(rel):
    rel = DUPLICATES.get(rel, rel)
    return BASE if rel == "" else BASE + quote(rel, safe="/-._~")


def resolve(href, page_dir):
    """Return the site-relative folder (no slashes at ends) an href points to,
    or None when it cannot point at a page of this site."""
    h = html.unescape(href).strip()
    parts = urlsplit(h)
    if parts.scheme or parts.netloc:
        if parts.netloc.lower() not in ("tonus.kiev.ua", "www.tonus.kiev.ua"):
            return None
        path = unquote(parts.path).lstrip("/")
    else:
        path = unquote(parts.path)
        if path.startswith("/"):
            path = path.lstrip("/")
        else:
            path = posixpath.join(page_dir, path)
    path = posixpath.normpath(path) if path else "."
    if path == ".":
        path = ""
    if path == ".." or path.startswith("../"):
        return None
    if path == "index.html":
        path = ""
    elif path.endswith("/index.html"):
        path = path[: -len("/index.html")]
    elif path.endswith(".html") and os.path.isfile(
            os.path.join(ROOT, path[: -len(".html")], "index.html")):
        path = path[: -len(".html")]
    return path.strip("/")


def leading_ws(head, pos, default="\n  "):
    m = TRAILING_WS_RE.search(head[:pos])
    return m.group(1) if m else default


def collect_pages(root):
    pages = []
    for d, dirs, files in os.walk(root):
        if d == root:
            dirs[:] = [x for x in dirs if x not in IGNORE_DIRS]
        dirs.sort()
        if "index.html" in files:
            rel = os.path.relpath(d, root).replace(os.sep, "/")
            pages.append("" if rel == "." else rel)
    return sorted(pages)


def is_tag(m, rel_value):
    return attrs(m.group(0)).get("rel", "").lower().split() == [rel_value]


def lang_key(l):
    return (LANG_ORDER.index(l) if l in LANG_ORDER else len(LANG_ORDER), l)


def main():
    dry = "--dry-run" in sys.argv
    root = ROOT
    for dup, twin in DUPLICATES.items():
        for p in (dup, twin):
            if not os.path.isfile(os.path.join(root, p, "index.html")):
                sys.exit("missing page for duplicate mapping: %s" % p)

    pages = collect_pages(root)
    page_set = set(pages)
    texts, langs = {}, {}
    for rel in pages:
        with open(os.path.join(root, rel, "index.html"), "rb") as fh:
            texts[rel] = fh.read().decode("utf-8")
        langs[rel] = page_lang(texts[rel])
    # public URL -> the page that owns it (twins own the duplicates' URLs)
    url_owner = {public_url(r): r for r in pages if r not in DUPLICATES}

    st = dict(pages=len(pages), changed=0, canon_rewritten=0, canon_inserted=0,
              canon_removed_dupes=0, hl_rewritten=0, hl_dropped_missing=0,
              hl_dropped_self_wrong_lang=0, hl_dropped_target_lang=0,
              hl_dropped_home_pairing=0, hl_dropped_external=0,
              hl_dropped_dupe=0, hl_added_self=0, hl_added_reciprocal=0,
              og_rewritten=0)
    dropped_log, warn_log, added_log = [], [], []
    work = {}  # rel -> dict(head, rest, chosen{lang: (url, original_href)})

    # ---- pass 1: canonical, og:url, filtered hreflang per page -----------
    for rel in pages:
        text = texts[rel]
        lang = langs[rel]
        if lang is None:
            warn_log.append("%s: no <html lang>, skipped" % (rel or "/"))
            continue
        hend = text.lower().find("</head>")
        if hend < 0:
            warn_log.append("%s: no </head>, skipped" % (rel or "/"))
            continue
        head, rest = text[:hend], text[hend:]
        self_url = public_url(rel)
        page_is_home = rel in HOMES

        canon = [m for m in LINK_RE.finditer(head) if is_tag(m, "canonical")]
        if canon:
            for m in reversed(canon[1:]):
                s = m.start() - len(leading_ws(head, m.start(), ""))
                head = head[:s] + head[m.end():]
                st["canon_removed_dupes"] += 1
            m = canon[0]
            if attrs(m.group(0)).get("href") != self_url:
                head = head[:m.start()] + set_attr(m.group(0), "href", self_url) + head[m.end():]
                st["canon_rewritten"] += 1
        else:
            tag = '<link rel="canonical" href="%s">' % self_url
            d = DESC_RE.search(head)
            if d:
                head = head[:d.end()] + leading_ws(head, d.start()) + tag + head[d.end():]
            else:
                head = head + leading_ws(head, len(head), "\n") + tag + "\n"
            st["canon_inserted"] += 1

        og = [m for m in META_RE.finditer(head)
              if attrs(m.group(0)).get("property", "").lower() == "og:url"]
        if not og:
            warn_log.append("%s: no og:url meta" % (rel or "/"))
        for m in reversed(og):
            if attrs(m.group(0)).get("content") != self_url:
                head = head[:m.start()] + set_attr(m.group(0), "content", self_url) + head[m.end():]
                st["og_rewritten"] += 1

        alts = [m for m in LINK_RE.finditer(head)
                if "hreflang" in attrs(m.group(0)) and is_tag(m, "alternate")]
        entries = []  # (lang, url, original_href)
        for m in alts:
            a = attrs(m.group(0))
            hl = a["hreflang"].strip().lower()
            href = a.get("href", "")
            target = resolve(href, rel)
            where = "%s: hreflang=%s href=%s" % (rel or "/", hl, href)
            if target is None:
                st["hl_dropped_external"] += 1
                dropped_log.append(where + "  [unresolvable/external]")
                continue
            if target not in page_set:
                st["hl_dropped_missing"] += 1
                dropped_log.append(where + "  [target missing: /%s]" % target)
                continue
            url = public_url(target)
            if url == self_url and hl != lang:
                st["hl_dropped_self_wrong_lang"] += 1
                dropped_log.append(where + "  [points to self but page is %s]" % lang)
                continue
            owner = url_owner[url]
            if langs.get(owner) and hl.split("-")[0] != langs[owner]:
                st["hl_dropped_target_lang"] += 1
                dropped_log.append(where + "  [target page lang is %s]" % langs[owner])
                continue
            if url != self_url and (owner in HOMES) != page_is_home:
                st["hl_dropped_home_pairing"] += 1
                dropped_log.append(where + "  [home pages pair only with home pages]")
                continue
            entries.append((hl, url, href))

        chosen = {}
        for hl, url, href in entries:
            if hl == lang and url != self_url:
                st["hl_dropped_dupe"] += 1
                dropped_log.append("%s: hreflang=%s href=%s  [own language must be self]"
                                   % (rel or "/", hl, href))
                continue
            if hl in chosen:
                st["hl_dropped_dupe"] += 1
                dropped_log.append("%s: hreflang=%s href=%s  [duplicate language]"
                                   % (rel or "/", hl, href))
                continue
            chosen[hl] = (url, href)
        if lang not in chosen:
            chosen[lang] = (self_url, None)
            st["hl_added_self"] += 1
        for hl, (url, href) in chosen.items():
            if href is not None and href != url:
                st["hl_rewritten"] += 1
        work[rel] = dict(head=head, rest=rest, chosen=chosen, has_alts=bool(alts))

    # ---- pass 2: reciprocity --------------------------------------------
    # A (lang LA) -> B in slot LB  =>  B gets slot LA -> A when B has no LA.
    # A's URL is its public URL, so a duplicate contributes its twin's URL.
    conflicts = []
    for a_rel in pages:
        if a_rel not in work:
            continue
        a_lang, a_url = langs[a_rel], public_url(a_rel)
        for hl, (b_url, _) in sorted(work[a_rel]["chosen"].items()):
            if b_url == a_url:
                continue
            b_rel = url_owner[b_url]
            if b_rel not in work or b_rel == url_owner.get(a_url):
                continue
            b_chosen = work[b_rel]["chosen"]
            if a_lang not in b_chosen:
                b_chosen[a_lang] = (a_url, None)
                st["hl_added_reciprocal"] += 1
                added_log.append("/%s: hreflang=%s -> %s  [reciprocal of /%s]"
                                 % (b_rel, a_lang, a_url, a_rel))
            elif b_chosen[a_lang][0] != a_url:
                conflicts.append("/%s says %s -> %s, but /%s has %s -> %s"
                                 % (a_rel, hl, b_url, b_rel, a_lang, b_chosen[a_lang][0]))

    # ---- pass 3: write hreflang blocks ------------------------------------
    for rel in pages:
        if rel not in work:
            continue
        w = work[rel]
        head, chosen = w["head"], w["chosen"]
        tags = ['<link rel="alternate" href="%s" hreflang="%s">' % (chosen[l][0], l)
                for l in sorted(chosen, key=lang_key)]
        alts = [m for m in LINK_RE.finditer(head)
                if "hreflang" in attrs(m.group(0)) and is_tag(m, "alternate")]
        if alts:
            sep = head[alts[0].end():alts[1].start()] if len(alts) > 1 else None
            if sep is None or sep.strip():
                sep = leading_ws(head, alts[0].start())
            block = sep.join(tags)
            for m in reversed(alts[1:]):
                s = m.start() - len(leading_ws(head, m.start(), ""))
                head = head[:s] + head[m.end():]
            m0 = alts[0]
            head = head[:m0.start()] + block + head[m0.end():]
        else:
            c = next(m for m in LINK_RE.finditer(head) if is_tag(m, "canonical"))
            ws = leading_ws(head, c.start())
            head = head[:c.start()] + ws.join(tags) + ws + head[c.start():]

        new = head + w["rest"]
        if new != texts[rel]:
            st["changed"] += 1
            if not dry:
                with open(os.path.join(root, rel, "index.html"), "wb") as fh:
                    fh.write(new.encode("utf-8"))

    print(("DRY RUN " if dry else "") + "fix-canonicals summary")
    for k, v in st.items():
        print("  %-28s %d" % (k, v))
    for title, log in (("Dropped hreflang entries", dropped_log),
                       ("Added reciprocal hreflang entries", added_log),
                       ("Reciprocity conflicts (left as is)", conflicts),
                       ("Warnings", warn_log)):
        if log:
            print("\n%s (%d):" % (title, len(log)))
            for line in log:
                print("  " + line)


if __name__ == "__main__":
    main()
