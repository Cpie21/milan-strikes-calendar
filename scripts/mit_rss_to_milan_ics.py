#!/usr/bin/env python3
"""
Auto-generate an iCalendar (.ics) feed for **any transport strike that may affect Milan (Milano area)**,
from the Italian Ministry of Transport (MIT) strikes RSS.

Key goals:
- HIGH RECALL (better to include more "might affect Milan" items than miss them)
- Apple Calendar subscription friendly (single .ics file served via GitHub Pages)
- English + Chinese only in event titles/descriptions (no Italian text shown)

How it decides "may affect Milan":
1) If the entry text contains any GEO_KEYWORDS (Milano/Lombardia/MI/Malpensa/Linate/Monza...)
   -> include
2) Also include NATIONAL strikes for major modes (LOCAL_PUBLIC_TRANSPORT / RAIL / AIR / HIGHWAYS)
   because national actions often impact Milan even if not explicitly mentioned.

Environment variables (optional):
  RSS_URL            : RSS URL (default: MIT RSS)
  OUTPUT_PATH        : output file path (default: docs/milan-strikes.ics)
  GEO_KEYWORDS       : comma-separated geo keywords (default covers Milan + Lombardy)
  INCLUDE_NATIONAL   : "1" to include national strikes (default: 1)
  NATIONAL_MODES     : comma-separated mode keywords (default: local transport, rail, air, highways)

Dependencies:
  pip install feedparser icalendar
"""
from __future__ import annotations

import os
import re
import urllib.request
import hashlib
from datetime import date, timedelta
from typing import Iterable, Optional, Tuple

import feedparser
from icalendar import Calendar, Event

DEFAULT_RSS_URL = "https://scioperi.mit.gov.it/mit2/public/scioperi/rss"
DEFAULT_OUTPUT_PATH = "docs/milan-strikes.ics"

DEFAULT_GEO_KEYWORDS = [
    "MILANO", "MILAN", "MI", "LOMBARDIA", "LOMBARDY", "MONZA", "BRIANZA",
    "LINATE", "MALPENSA", "BERGAMO", "ORIO AL SERIO", "VARESE", "COMO", "PAVIA", "CREMONA", "MANTOVA", "LECCO", "SONDRIO", "BRESCIA"
]

DEFAULT_NATIONAL_MODE_KEYWORDS = [
    # local public transport
    "TRASPORTO PUBBLICO LOCALE", "TPL", "AUTOBUS", "BUS", "METRO", "METROPOLITANA", "TRAM",
    # rail
    "FERROVI", "TRENI", "TRENITALIA", "RFI", "ITALO", "TRENORD",
    # air
    "AEREO", "AEROPORT", "ENAV", "HANDLING",
    # highways / roads
    "AUTOSTRAD", "TAXI"
]

DATE_PATTERNS = [
    re.compile(r'(?P<d>\d{1,2})[\/\-](?P<m>\d{1,2})[\/\-](?P<y>\d{4})'),  # dd/mm/yyyy
    re.compile(r'(?P<y>\d{4})[\/\-](?P<m>\d{1,2})[\/\-](?P<d>\d{1,2})'),  # yyyy-mm-dd
]

def _env_list(name: str, default: list[str]) -> list[str]:
    raw = os.getenv(name, "").strip()
    if raw:
        return [x.strip() for x in raw.split(",") if x.strip()]
    return default

def _rss_url() -> str:
    return os.getenv("RSS_URL", DEFAULT_RSS_URL)

def _output_path() -> str:
    return os.getenv("OUTPUT_PATH", DEFAULT_OUTPUT_PATH)

def _include_national() -> bool:
    return os.getenv("INCLUDE_NATIONAL", "1").strip() not in ("0", "false", "False", "no", "NO")

def matches_any(text: str, keywords: Iterable[str]) -> bool:
    t = (text or "").lower()
    for k in keywords:
        if k.lower() in t:
            return True
    return False

def extract_dates(text: str) -> list[date]:
    found: list[date] = []
    for pat in DATE_PATTERNS:
        for m in pat.finditer(text or ""):
            y = int(m.group("y"))
            mo = int(m.group("m"))
            d = int(m.group("d"))
            try:
                found.append(date(y, mo, d))
            except ValueError:
                pass
    return sorted({d for d in found})

def choose_event_span(dates: list[date]) -> Optional[Tuple[date, date]]:
    if not dates:
        return None
    start = min(dates)
    end = max(dates) + timedelta(days=1)  # all-day DTEND is exclusive
    return (start, end)

def make_uid(link: str, title: str) -> str:
    h = hashlib.sha1(f"{link}|{title}".encode("utf-8")).hexdigest()
    return f"mit-strike-{h}@milan"

def detect_scope(text: str) -> str:
    t = (text or "").lower()
    if "nazionale" in t:
        return "National / 全国"
    if "regionale" in t:
        return "Regional / 区域"
    if "provinc" in t:
        return "Province / 省级"
    if "locale" in t:
        return "Local / 本地"
    return "Unspecified / 未注明"

def detect_mode(text: str) -> Tuple[str, str]:
    t = (text or "").lower()
    # Local public transport
    if any(x in t for x in ["trasporto pubblico locale", "tpl", "bus", "autobus", "metro", "metropolitana", "tram"]):
        return ("Local public transport strike", "城市公共交通罢工")
    # Rail
    if any(x in t for x in ["ferrovi", "treni", "trenitalia", "trenord", "rfi", "italo"]):
        return ("Rail strike", "铁路罢工")
    # Air
    if any(x in t for x in ["aereo", "aeroport", "enav", "handling"]):
        return ("Air transport strike", "航空相关罢工")
    # Highways / taxi
    if any(x in t for x in ["autostrad", "taxi"]):
        return ("Road transport strike", "公路交通相关罢工")
    return ("Transport strike", "交通罢工")

def should_include(entry_blob: str, geo_kw: list[str], include_national: bool, nat_mode_kw: list[str]) -> bool:
    if matches_any(entry_blob, geo_kw):
        return True
    if include_national:
        # include national strikes of big modes
        if "nazionale" in entry_blob.lower() and matches_any(entry_blob, nat_mode_kw):
            return True
    return False

def main() -> None:
    rss_url = _rss_url()
    out_path = _output_path()
    geo_kw = _env_list("GEO_KEYWORDS", DEFAULT_GEO_KEYWORDS)
    nat_mode_kw = _env_list("NATIONAL_MODES", DEFAULT_NATIONAL_MODE_KEYWORDS)
    include_national = _include_national()


    req = urllib.request.Request(
        rss_url,
        headers={"User-Agent": "Mozilla/5.0 (GitHub Actions)"},
    )
    raw = urllib.request.urlopen(req, timeout=30).read()

    # parse from raw bytes first (avoid broken text decoding)
    feed = feedparser.parse(raw)

    # If bozo but still has entries, continue.
    # Only fail when bozo AND no entries.
    if getattr(feed, "bozo", False) and not getattr(feed, "entries", []):
        # fallback: force UTF-8 decode then re-parse
        text = raw.decode("utf-8", errors="replace")
        feed = feedparser.parse(text.encode("utf-8"))

    if getattr(feed, "bozo", False) and not getattr(feed, "entries", []):
        raise RuntimeError(
            f"Failed to parse RSS feed (no entries). bozo_exception={getattr(feed, 'bozo_exception', 'unknown')}"
        )
       
    cal = Calendar()
    cal.add("prodid", "-//Milan Strike Feed (EN+ZH)//EN")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("x-wr-calname", "Milan transport strikes (may affect) / 可能影响米兰的交通罢工")
    cal.add("x-wr-caldesc", "Auto-generated from MIT transport strikes RSS. High-recall filter for Milan area + national modes. Verify near the date.")

    kept = 0
    for entry in getattr(feed, "entries", []):
        title = getattr(entry, "title", "") or ""
        summary = getattr(entry, "summary", "") or getattr(entry, "description", "") or ""
        link = getattr(entry, "link", "") or ""

        blob = f"{title}\n{summary}\n{link}"

        if not should_include(blob, geo_kw, include_national, nat_mode_kw):
            continue

        dates = extract_dates(blob)
        if not dates:
            pp = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
            if pp:
                dates = [date(pp.tm_year, pp.tm_mon, pp.tm_mday)]
        span = choose_event_span(dates)
        if not span:
            continue
        dtstart, dtend = span

        mode_en, mode_zh = detect_mode(blob)
        scope = detect_scope(blob)

        ev = Event()
        ev.add("uid", make_uid(link, title))
        ev.add("dtstart", dtstart)  # all-day
        ev.add("dtend", dtend)
        ev.add("summary", f"{mode_en} (may affect Milan) / {mode_zh}（可能影响米兰）")

        desc_lines = [
            "EN:",
            f"• Type: {mode_en}",
            f"• Scope: {scope.split('/')[0].strip()}",
            "• This item was included by a high-recall filter (Milan/Lombardy keywords and/or national transport action).",
            "• Always verify details close to the date via official notices.",
            "",
            "中文：",
            f"• 类型：{mode_zh}",
            f"• 范围：{scope.split('/')[1].strip() if '/' in scope else '未注明'}",
            "• 该条目由“高召回”过滤规则纳入（出现米兰/伦巴第关键词，或属于全国性交通行动）。",
            "• 请在临近日期以官方通知为准。",
        ]
        if link:
            desc_lines += ["", "Source link / 来源链接：", link]
            ev.add("url", link)

        ev.add("description", "\n".join(desc_lines))
        ev.add("categories", f"Strike,Transport,{mode_en}")
        cal.add_component(ev)
        kept += 1

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(cal.to_ical())

    print(f"OK: wrote {out_path} with {kept} event(s). RSS={rss_url}")

if __name__ == "__main__":
    main()
