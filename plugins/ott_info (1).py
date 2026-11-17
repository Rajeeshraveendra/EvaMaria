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
MIN_DAYS = 28  # theatre release kazhinju ithra divasam vare TMDB platform list kaanikkilla


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
    m = next((r for r in res if nq in (_norm(r.get("title")), _norm(r.get("original_title")))), None)
    if not m:
        return None
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

    # platform names: "with Ads" / "Amazon Channel" duplicates ozhivakkunnu
    names = []
    for p in prov.get("results", {}).get(REGION, {}).get("flatrate") or []:
        n = re.sub(r"(?i)\s*(standard\s+)?with ads|\s*amazon channel", "", p.get("provider_name", "")).strip()
        if n and n.lower() not in [x.lower() for x in names]:
            names.append(n)

    today = date.today()
    t_date = _d(theatre)
    d_date = _d(digital)
    # theatre release kazhinju MIN_DAYS aakathe platform kaanikkilla (TMDB data thettaan saadhyatha)
    fresh = t_date is not None and (today - t_date).days < MIN_DAYS
    if fresh and not (d_date and d_date <= today):
        names = []

    return {
        "title": m.get("title") or q,
        "year": (rd or "")[:4],
        "poster": IMG + m["poster_path"] if m.get("poster_path") else None,
        "theatre": theatre,
        "digital": digital,
        "platforms": ", ".join(names),
        "upcoming": t_date is not None and t_date > today,
    }


def _d(s):
    try:
        return datetime.fromisoformat(s[:10]).date() if s else None
    except Exception:
        return None


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

    head = f"🎬 <b>{info['title']}</b>" + (f" ({info['year']})" if info["year"] else "")
    lines = [head, ""]
    if info["theatre"]:
        lbl = "തിയേറ്റർ റിലീസ് / Theatre Release"
        lines.append(f"🎟 <b>{lbl}:</b> {_fmt(info['theatre'])}")
    if info["platforms"]:
        lines.append(f"📺 <b>ഇപ്പോൾ OTT-യിൽ / Now Streaming:</b> {info['platforms']}")
    elif info["digital"]:
        lines.append(f"📅 <b>OTT റിലീസ് / OTT Release:</b> {_fmt(info['digital'])}")
    else:
        lines.append("📅 <b>OTT റിലീസ് / OTT Release:</b> ഇതുവരെ പ്രഖ്യാപിച്ചിട്ടില്ല / Not announced yet")
    lines.append("")
    if info["upcoming"]:
        lines.append("ℹ️ <i>ഈ സിനിമ ഇതുവരെ റിലീസ് ആയിട്ടില്ല.\nThis movie has not released yet.</i>")
    else:
        lines.append("ℹ️ <i>ഈ സിനിമ ഇപ്പോൾ ഞങ്ങളുടെ ലൈബ്രറിയിൽ ഇല്ല. OTT റിലീസ് ആയാൽ അപ്ഡേറ്റ് ചെയ്യാം.\nThis movie is not in our library yet. We'll update once it's on OTT.</i>")
    return "\n".join(lines), info["poster"]
