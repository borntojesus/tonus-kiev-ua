# tonus.kiev.ua — static export of the legacy tonus.kiev.ua WordPress site (CLIENT)

> Fleet: **CLIENT** (remote: borntojesus, repo tonus-kiev-ua). The client may review this code.
> Stack is the CLIENT'S choice — do NOT impose the fleet golden path (pnpm/homelab/Payload). See /Users/dmytro/github/ARCHITECTURE-PLAN.md §2.2.

## What this is

A flat static HTML capture/export of the legacy tonus.kiev.ua site (addiction-rehab clinic,
uk/ru). Hundreds of per-article folders, each containing an `index.html`, plus `wp-content/`,
`wp-includes/`, `wp-json/` carried over from the original WordPress. The modern Astro rebuild
lives in the sibling `tonus-astro` repo.

## Stack (client-chosen — keep as-is)

- Framework/CMS: static HTML exported from WordPress (legacy)
- Package manager: none — do not introduce one
- Deploy: Vercel static project (Cloudflare DNS in front). Prod https://tonus.kiev.ua served
  byte-identical to this repo (verified 2026-10-21). The Vercel project is NOT in the
  borntojesus-projects team; find the owning account before redeploying. `vercel.json` holds
  cleanUrls, trailingSlash=false and the uk/ru redirect map.

## Client-facing copy

Any text the client reads: no dashes as punctuation, run the `humanizer` skill before sending, no internal jargon.

## Run

```sh
# static files — serve the repo root with any static server, e.g.
python3 -m http.server 8000
```

## SEO maintenance scripts (Python 3 stdlib, run from repo root, idempotent)

```sh
python3 -I scripts/build-sitemap.py     # regenerates sitemap.xml (skips the 7 redirected root duplicates)
python3 -I scripts/build-redirects.py   # regenerates the redirects array in vercel.json
python3 -I scripts/fix-canonicals.py    # absolute canonical / hreflang / og:url in every index.html
python3 -I scripts/check-site.py        # consistency checks; run after any content change
```

Run all four after adding, moving or removing a page folder.

## URL structure

- Russian pages: `ru/<slug>/`, Russian home is the root `index.html`.
- Ukrainian pages: `uk/<slug>/`, Ukrainian home is `uk/home/`.
- 25 legitimate pages live at root level `<slug>/`; 7 more root folders are duplicates of
  ru/uk twins and are 301-redirected by vercel.json (kept on disk, excluded from sitemap,
  canonical points at the twin).
- Old WordPress root-level Russian URLs (for example `/narkotik-mefedron`) redirect to `/ru/<slug>`.

## Notes

- This is an archived/legacy export, not a live CMS. Treat as content reference for the rebuild.
- Bilingual: `uk/` and `ru/` plus localized slug folders at root.
- Do not "modernize" in place; new work happens in `tonus-astro`.
