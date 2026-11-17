"""
OTT INFO: library-il film illenkil TMDB-yil ninnu
theatre date + OTT release date / streaming platform reply cheyyunnu.
Uses existing TMDB_API_KEY env.
"""
import os
import re
import asyncio
import logging
from datetime import date, datetime

import requests

logger = logging.getLogger(__name__)

TMDB_API_KEY = (os.environ.get("TMDB_API_KEY") or "").strip()
API = "https://api.themoviedb.org/3"
IMG = "https://image.tmdb.org/t/p/w500"
REGION = "IN"


def _norm(t):
    return re.sub(r"[^a-z0-9]", "", (t or "").lower())


def _clean_query(q):
    q = re.sub(r"\b(19|20)\d{2}\b", "", q)
    q = re.sub(r"(?i)\b(movie|film|malayalam|tamil|telugu|hindi|hd|ott)\b", "", q)
    return re.sub(r"\s+", " ", q).strip()


def _get(path, **params):
    params["api_key"] = TMDB_API_KEY
    r = requests.get(f"{API}{path}", params=params, timeout=8)
    return r.json() if r.status_code == 200 else {}


def _fmt(d):
    try:
        return datetime.fromisoformat(d[:10]).strftime("%d %b %Y")
    except Exception:
        return d[:10]


def _lookup(query):
    q = _clean_query(query)
    if len(q) < 2:
        return None
    res = (_get("/search/movie", query=q).get("results") or [])[:5]
    if not res:
        return None
    nq = _norm(q)
    # exact title match mathram (spelling thettiyal suggestion engine nokkatte)
    m = next((r for r in res if nq in (_norm(r.get("title")), _norm(r.get("original_title")))), None)
    if not m:
        return None
    # pazhaya film (2 varsham munpu) aanenkil skip
    rd = m.get("release_date") or ""
    if rd and rd[:4].isdigit() and int(rd[:4]) < date.today().year - 1:
        return None

    mid = m["id"]
    rel = _get(f"/movie/{mid}/release_dates")
    prov = _get(f"/movie/{mid}/watch/providers")

    theatre = digital = None
    for c in rel.get("results", []):
        if c.get("iso_3166_1") != REGION:
            continue
        for r in c.get("release_dates", []):
            if r.get("type") in (2, 3) and not theatre:
                theatre = r.get("release_date")
            if r.get("type") == 4 and not digital:
                digital = r.get("release_date")
    if not theatre:
        theatre = rd or None

    flat = prov.get("results", {}).get(REGION, {}).get("flatrate") or []
    platforms = ", ".join(p["provider_name"] for p in flat)

    return {
        "title": m.get("title") or q,
        "year": (rd or "")[:4],
        "poster": IMG + m["poster_path"] if m.get("poster_path") else None,
        "theatre": theatre,
        "digital": digital,
        "platforms": platforms,
    }


async def get_ott_info(query):
    """Returns (caption, poster_url) or None."""
    if not TMDB_API_KEY:
        return None
    try:
        info = await asyncio.get_event_loop().run_in_executor(None, _lookup, query)
    except Exception as e:
        logger.warning(f"ott_info error: {e}")
        return None
    if not info:
        return None

    today = date.today().isoformat()
    head = f"🎬 <b>{info['title']}</b>" + (f" ({info['year']})" if info["year"] else "")
    lines = [head, ""]
    if info["theatre"]:
        lines.append(f"🎟 <b>Theatre Release:</b> {_fmt(info['theatre'])}")
    if info["platforms"]:
        lines.append(f"📺 <b>Ippol OTT-yil undu:</b> {info['platforms']}")
    elif info["digital"] and info["digital"][:10] > today:
        lines.append(f"📅 <b>OTT Release:</b> {_fmt(info['digital'])}")
    elif info["digital"]:
        lines.append(f"📅 <b>OTT Release:</b> {_fmt(info['digital'])}")
    else:
        lines.append("📅 <b>OTT Release:</b> ithuvare announce cheythittilla")
    lines.append("")
    lines.append("ℹ️ <i>Ee film ippol library-il illa. OTT release aayal update cheyyam.</i>")
    return "\n".join(lines), info["poster"]
