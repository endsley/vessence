"""Run a saved search against Facebook Marketplace and save listings.

Launches Playwright against the ``facebook_julius`` profile (stored
cookies → no 2FA), scrolls each query's results, opens surviving
candidates, applies the clean-title + suspicion filters, and writes
descriptions and photos to disk.

Idempotent per (search_name, query_slug): each refresh overwrites the
query's output directory, so cron can just call ``harvest()``.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
import os
import re
import shutil
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from . import config as _cfg

logger = logging.getLogger(__name__)

CURRENT_YEAR = 2026
_PROFILE_ID = os.environ.get("FB_PROFILE", "facebook_julius")

_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def _slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_") or "query"


def _parse_year(s: str | None) -> int | None:
    if not s:
        return None
    m = re.search(r"\b(19\d{2}|20[0-2]\d)\b", s)
    return int(m.group()) if m else None


def _is_suspicious(year: int | None, miles: int) -> tuple[bool, str]:
    if year is None or not miles:
        return False, ""
    age = CURRENT_YEAR - year
    if age <= 5:
        return False, ""
    avg = miles / max(age, 1)
    if avg < 3000:
        return True, f"implausibly low miles: {miles}mi / {age}yr = {avg:.0f}/yr"
    return False, ""


def _download(url: str, dest: Path) -> bool:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            dest.write_bytes(r.read())
        return True
    except Exception as e:
        logger.warning("photo fetch failed (%s): %s", url[:80], e)
        return False


# ── Playwright scraping ───────────────────────────────────────────────────────

_SCRIPT_SCROLL = """
(async()=>{const targetCount=60;
let prevCount=0,sameCount=0,prevHeight=0,sameHeight=0;
for(let i=0;i<180;i++){
window.scrollTo(0,document.body.scrollHeight);
await new Promise(r=>setTimeout(r,1400));
window.scrollBy(0,-220);
await new Promise(r=>setTimeout(r,250));
window.scrollTo(0,document.body.scrollHeight);
await new Promise(r=>setTimeout(r,1400));
const count=document.querySelectorAll('a[href*="/marketplace/item/"]').length;
const height=document.body.scrollHeight;
if(count===prevCount){sameCount++;}else sameCount=0;
if(height===prevHeight){sameHeight++;}else sameHeight=0;
prevCount=count;prevHeight=height;
if(count>=targetCount&&sameCount>=3)break;
if(sameCount>=10&&sameHeight>=6)break;
}
return document.querySelectorAll('a[href*="/marketplace/item/"]').length;})()
"""

_SCRIPT_EXTRACT_CARDS = r"""
(()=>{const cards=Array.from(document.querySelectorAll('a[href*="/marketplace/item/"]'));
const seen=new Set();const out=[];
for(const c of cards){
  const href=c.getAttribute('href').split('?')[0];
  if(seen.has(href))continue;seen.add(href);
  const lines=c.innerText.split('\n').map(s=>s.trim()).filter(Boolean);
  const prices=lines.filter(l=>/^\$[\d,]+/.test(l)).map(l=>parseInt(l.replace(/[^\d]/g,'')));
  const price=prices.length?Math.min(...prices):null;
  const milesLine=lines.find(l=>/miles/i.test(l));
  let miles=null;
  if(milesLine){const m=milesLine.match(/([\d.]+)\s*([kK])?\s*miles/);
    if(m){miles=parseFloat(m[1])*(m[2]?1000:1);}}
  const title=lines.find(l=>/\b(19|20)\d{2}\b/.test(l))||lines[1]||'';
  const loc=lines.find(l=>/,\s*[A-Z]{2}/.test(l))||'';
  out.push({href,price,miles,title,loc});
}return out;})()
"""

_SCRIPT_EXPAND_SEE_MORE = """
(async()=>{const btns=[...document.querySelectorAll('[role=button]')];
const sm=btns.find(b=>/see\\s*more/i.test((b.innerText||'').trim()));
if(sm){sm.click();await new Promise(r=>setTimeout(r,600));}return true;})()
"""

_SCRIPT_EXTRACT_LISTING = r"""
(()=>{const out={title:document.title, description:'', photos:[]};
const hdr=[...document.querySelectorAll('span,h2,h3')].find(e=>
  /seller.?s description|description/i.test(e.innerText));
if(hdr){let n=hdr.parentElement;
  for(let k=0;k<6&&n;k++){n=n.parentElement;
    if(n&&n.innerText.length>150){out.description=n.innerText;break;}}}
if(!out.description)out.description=document.body.innerText;
out.photos=[...new Set([...document.querySelectorAll('img')]
  .map(i=>i.getAttribute('src'))
  .filter(s=>s&&/scontent/.test(s)))];
return out;})()
"""


async def _run_query(page, query: str, filters: dict, location_id: str,
                     out_dir: Path) -> dict:
    import asyncio as _a
    q = urllib.parse.quote(query)
    search_url = (f"https://www.facebook.com/marketplace/{location_id}"
                  f"/search?query={q}")
    logger.info("query %r → %s", query, search_url)
    await page.goto(search_url, wait_until="domcontentloaded", timeout=45000)
    await _a.sleep(2.5)
    await page.evaluate(_SCRIPT_SCROLL)
    cards = await page.evaluate(_SCRIPT_EXTRACT_CARDS)

    min_price = int(filters.get("min_price") or 0)
    max_price = int(filters.get("max_price") or 0)
    max_miles = int(filters.get("max_miles") or 0)

    pre = [
        c for c in cards
        if c["miles"] is not None
        and c["miles"] < max_miles
        and c["price"] is not None
        and c["price"] >= min_price
        and c["price"] < max_price
    ]

    passed: list[dict] = []
    for c in pre:
        url = "https://www.facebook.com" + c["href"]
        listing_id = c["href"].strip("/").split("/")[-1]
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            await _a.sleep(2.5)
            await page.evaluate(_SCRIPT_EXPAND_SEE_MORE)
            detail = await page.evaluate(_SCRIPT_EXTRACT_LISTING)
        except Exception as e:
            logger.warning("listing %s failed: %s", listing_id, e)
            continue
        desc = detail["description"] or ""
        year = _parse_year(c["title"]) or _parse_year(detail.get("title", "")) \
            or _parse_year(desc)
        if filters.get("suspicion_filter", True):
            sus, reason = _is_suspicious(year, int(c["miles"] or 0))
            if sus:
                logger.info("skip %s suspicious: %s", listing_id, reason)
                continue
        lower = desc.lower()
        bad_keywords = ("salvage title","rebuilt title","reconstructed title",
                        "branded title","lemon title","rebuilt/salvage")
        has_clean = "clean title" in lower
        has_bad = any(k in lower for k in bad_keywords)
        if filters.get("require_clean_title", True):
            if not has_clean or has_bad:
                logger.info("skip %s title check (clean=%s bad=%s)",
                            listing_id, has_clean, has_bad)
                continue
        elif has_bad:
            logger.info("skip %s bad title flag", listing_id)
            continue

        ldir = out_dir / listing_id
        ldir.mkdir(parents=True, exist_ok=True)
        saved_photos: list[str] = []
        for i, u in enumerate(detail["photos"], start=1):
            mext = re.search(r"\.(png|webp|jpeg|jpg)(\?|$)", u, re.I)
            ext = "." + (mext.group(1).lower() if mext else "jpg")
            p = ldir / f"photo_{i:02d}{ext}"
            if _download(u, p):
                saved_photos.append(p.name)
        (ldir / "listing.json").write_text(json.dumps({
            "id": listing_id, "url": url, "query": query,
            "price": c["price"], "miles": c["miles"], "year": year,
            "title": c["title"], "location": c["loc"],
            "description": desc.strip(),
            "photo_urls": detail["photos"],
            "photos": saved_photos,
            "captured_at": dt.datetime.now().isoformat(timespec="seconds"),
        }, indent=2))
        passed.append({
            "id": listing_id, "url": url, "price": c["price"],
            "miles": c["miles"], "year": year,
            "title": c["title"], "location": c["loc"],
            "photos": saved_photos,
            "thumb": saved_photos[0] if saved_photos else None,
        })
    return {"query": query, "raw": len(cards), "pre_filter": len(pre),
            "passed_count": len(passed), "listings": passed}


async def _harvest_async(search_name: str) -> dict:
    from playwright.async_api import async_playwright

    # Lazy import so merely importing this module doesn't require the
    # profiles submodule being available in every environment.
    from web_automation import profiles as prof

    search = _cfg.get_search(search_name)
    if search is None:
        raise KeyError(f"no saved search named {search_name!r}")

    out_root = _cfg.search_data_dir(search_name)
    logger.info("harvesting %r → %s", search_name, out_root)

    # Wipe prior per-query directories so stale results don't linger.
    for sub in out_root.iterdir():
        if sub.is_dir():
            shutil.rmtree(sub)

    filters = search["filters"]
    location_id = search.get("location_id", _cfg.DEFAULT_LOCATION_ID)

    per_query: list[dict] = []
    async with async_playwright() as pw:
        # Marketplace pulls run headless by default. Opt into a visible
        # browser only for debugging.
        headless = os.environ.get("MARKETPLACE_HEADFUL_DEBUG", "").lower() \
            not in {"1", "true", "yes", "on"}
        browser = await pw.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        ctx_kwargs: dict[str, Any] = {"user_agent": _UA}
        try:
            ssp = prof.storage_state_path(_PROFILE_ID)
            if Path(ssp).exists() and json.loads(Path(ssp).read_text()).get("cookies"):
                ctx_kwargs["storage_state"] = ssp
                logger.info("loaded storage_state from %s", ssp)
        except prof.ProfileNotFound:
            logger.warning("profile %s missing — login will fail", _PROFILE_ID)
        ctx = await browser.new_context(**ctx_kwargs)
        page = await ctx.new_page()
        try:
            for q in search["queries"]:
                qdir = out_root / _slugify(q)
                qdir.mkdir(parents=True, exist_ok=True)
                result = await _run_query(page, q, filters, location_id, qdir)
                (qdir / "summary.json").write_text(json.dumps(result, indent=2))
                per_query.append({"slug": _slugify(q), **result})
        finally:
            await ctx.close()
            await browser.close()

    all_listings = [
        {**L, "query": pq["query"], "query_slug": pq["slug"]}
        for pq in per_query for L in pq["listings"]
    ]
    summary = {
        "search": search_name,
        "label": search.get("label", search_name),
        "last_refreshed": dt.datetime.now().isoformat(timespec="seconds"),
        "filters": filters,
        "queries": per_query,
        "passed_count": len(all_listings),
    }
    (out_root / "summary.json").write_text(json.dumps(summary, indent=2))
    return summary


def harvest(search_name: str) -> dict:
    """Blocking entry point for scripts/cron."""
    return asyncio.run(_harvest_async(search_name))


# ── Read-side helpers (used by the API) ───────────────────────────────────────

def listings_for(search_name: str) -> dict[str, Any]:
    """Return the latest saved summary + flat listings list for a search."""
    out_root = _cfg.search_data_dir(search_name)
    summary_path = out_root / "summary.json"
    if not summary_path.exists():
        return {
            "search": search_name, "last_refreshed": None,
            "passed_count": 0, "listings": [], "queries": [],
        }
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    listings = [
        {**L, "query": pq["query"], "query_slug": pq["slug"]}
        for pq in summary.get("queries", []) for L in pq.get("listings", [])
    ]
    summary["listings"] = listings
    return summary


def listing_detail(search_name: str, query_slug: str, listing_id: str) -> dict | None:
    p = _cfg.search_data_dir(search_name) / query_slug / listing_id / "listing.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def photo_path(search_name: str, query_slug: str, listing_id: str,
               photo_name: str) -> Path | None:
    # Guard against path escapes.
    for part in (query_slug, listing_id, photo_name):
        if "/" in part or ".." in part:
            return None
    p = _cfg.search_data_dir(search_name) / query_slug / listing_id / photo_name
    return p if p.exists() else None


if __name__ == "__main__":
    import argparse, logging as _log
    _log.basicConfig(level=_log.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("search_name")
    args = ap.parse_args()
    s = harvest(args.search_name)
    print(json.dumps({"passed": s["passed_count"],
                      "last_refreshed": s["last_refreshed"],
                      "queries": [{"slug": q["slug"], "query": q["query"],
                                    "passed": q["passed_count"]}
                                   for q in s["queries"]]}, indent=2))
