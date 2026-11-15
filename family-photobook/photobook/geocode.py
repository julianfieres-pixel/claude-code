"""Turn GPS coordinates into a readable place name ("Englischer Garten, München").

Uses the OpenStreetMap Nominatim API (https://nominatim.org/release-docs/latest/api/Reverse/).
Usage policy: max. 1 request/second, identifying User-Agent, results must be cached
(https://operations.osmfoundation.org/policies/nominatim/). Coordinates are rounded to ~100 m
and cached on disk, so each place is looked up only once. Only coordinates are sent, never photos.
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

URL = "https://nominatim.openstreetmap.org/reverse"
USER_AGENT = "family-photobook/1.0 (local photo organiser)"
POI_KEYS = ("tourism", "leisure", "amenity", "historic", "natural", "beach", "aeroway", "railway")
CITY_KEYS = ("city", "town", "village", "municipality", "hamlet")


class Geocoder:
    def __init__(self, cache_file: Path, language: str = "de", enabled: bool = True):
        self.cache_file = cache_file
        self.language = language
        self.enabled = enabled
        self.cache: dict[str, dict | None] = {}
        if cache_file.exists():
            self.cache = json.loads(cache_file.read_text(encoding="utf-8"))
        self._last = 0.0
        self._failed = False

    def _key(self, lat: float, lon: float) -> str:
        return f"{lat:.3f},{lon:.3f}"

    def lookup(self, lat: float, lon: float) -> dict | None:
        key = self._key(lat, lon)
        if key in self.cache:
            return self.cache[key]
        if not self.enabled or self._failed:
            return None
        wait = 1.1 - (time.time() - self._last)
        if wait > 0:
            time.sleep(wait)
        params = urllib.parse.urlencode({
            "lat": f"{lat:.5f}", "lon": f"{lon:.5f}", "format": "jsonv2",
            "zoom": 17, "addressdetails": 1, "accept-language": self.language,
        })
        req = urllib.request.Request(f"{URL}?{params}", headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            print(f"  ! Ortssuche nicht erreichbar ({exc}); Orte werden als Koordinaten angezeigt.")
            self._failed = True
            return None
        finally:
            self._last = time.time()
        self.cache[key] = data
        self.cache_file.write_text(json.dumps(self.cache, ensure_ascii=False), encoding="utf-8")
        return data


def format_place(data: dict | None, home_country: str | None) -> str:
    if not data or "address" not in data:
        return ""
    addr = data["address"]
    poi = None
    if data.get("category") in POI_KEYS or data.get("type") in ("park", "zoo", "beach", "attraction"):
        poi = data.get("name") or None
    poi = poi or next((addr[k] for k in POI_KEYS if k in addr), None)
    city = next((addr[k] for k in CITY_KEYS if k in addr), None) or addr.get("county") or addr.get("state")
    parts = [x for x in (poi, city) if x]
    # drop duplicates like "München, München"
    parts = list(dict.fromkeys(parts))
    country = addr.get("country")
    if country and addr.get("country_code") != home_country:
        parts.append(country)
    return ", ".join(parts)


def assign_places(photos, geocoder: Geocoder) -> None:
    raw = {}
    for p in photos:
        if p.lat is not None and p.lon is not None:
            raw[p.path] = geocoder.lookup(p.lat, p.lon)
    codes = Counter(d["address"].get("country_code") for d in raw.values() if d and "address" in d)
    home = codes.most_common(1)[0][0] if codes else None
    for p in photos:
        if p.path in raw:
            p.place = format_place(raw[p.path], home) or f"{p.lat:.4f}, {p.lon:.4f}"
