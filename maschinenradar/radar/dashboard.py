"""HTML-Dashboard: eine eigenständige Datei mit eingebetteten Daten, ohne Server nutzbar."""
from __future__ import annotations

import datetime as dt
import json
from collections import Counter
from pathlib import Path
from statistics import median

from .models import Auction, Listing, SourceLog
from .profiles import AUSSERHALB, PASST, PRUEFEN, RANK, Config
from .report import eur

TEMPLATE = Path(__file__).parent / "templates" / "dashboard.html"
PASSUNG_CODE = {PASST: 0, PRUEFEN: 1, AUSSERHALB: 2}
HIST_START, HIST_STEP = 1980, 5


def _hist(years: list[int]) -> list[list[int]]:
    """Baujahre in 5-Jahres-Klassen; alles vor 1980 fällt in die erste Klasse."""
    end = dt.date.today().year // HIST_STEP * HIST_STEP
    buckets = Counter(max((y - HIST_START) // HIST_STEP, -1) for y in years)
    return [[HIST_START + i * HIST_STEP, buckets.get(i, 0)]
            for i in range(-1, (end - HIST_START) // HIST_STEP + 1)]


def build(cfg: Config, listings: list[Listing], auctions: list[Auction], logs: list[SourceLog],
          first_seen: dict, run: str, actions: list, drafts: list) -> dict:
    index = {p.id: i for i, p in enumerate(cfg.profiles)}
    profiles = []
    for p in cfg.profiles:
        ls = [x for x in listings if x.profil_id == p.id]
        prices = [e for e in (eur(x, cfg) for x in ls) if e]
        years = [x.baujahr for x in ls if x.baujahr]
        spec = []
        if p.spez.get("baujahr_min"):
            spec.append(f"Baujahr ab {p.spez['baujahr_min']}")
        if p.spez.get("kraft_kn"):
            spec.append("{}–{} kN".format(*p.spez["kraft_kn"]))
        profiles.append({
            "name": p.name, "gruppe": p.gruppe, "spez": " · ".join(spec),
            "ymin": p.spez.get("baujahr_min"),
            "n": [sum(x.passung == s for x in ls) for s in (PASST, PRUEFEN, AUSSERHALB)],
            "preise": len(prices),
            "pmin": min(prices) if prices else None,
            "pmed": round(median(prices)) if prices else None,
            "pmax": max(prices) if prices else None,
            "ymax": max(years) if years else None,
            "hist": _hist(years),
            "laender": Counter(x.land for x in ls if x.land).most_common(3),
        })

    listings = sorted(listings, key=lambda x: (index.get(x.profil_id, 99), RANK.get(x.passung, 9),
                                               -(x.baujahr or 0)))
    rows = [{
        "p": index[x.profil_id], "s": PASSUNG_CODE.get(x.passung, 2), "g": x.passung_grund,
        "h": x.hersteller, "m": x.modell or x.titel, "y": x.baujahr, "k": x.kraft_kn,
        "bh": x.betriebsstunden, "pr": x.preis, "w": x.waehrung, "pe": eur(x, cfg),
        "l": x.land, "o": x.ort, "z": x.zustand, "q": x.quelle, "u": x.url,
        "d": x.beschreibung[:320], "neu": first_seen.get(x.key) == run,
        "dup": bool(x.moegliche_dublette),
    } for x in listings]

    acts = []
    for i, a in enumerate(actions, 1):
        if a.auction:
            au = a.auction
            acts.append({"r": i, "a": a.aktion, "pt": a.punkte, "p": -1, "m": au.titel, "h": "",
                         "art": au.art, "o": au.ort, "t": au.termin, "g": a.grund, "q": au.quelle,
                         "u": au.url})
        else:
            x = a.listing
            acts.append({"r": i, "a": a.aktion, "pt": a.punkte, "p": index[x.profil_id],
                         "h": x.hersteller, "m": x.modell or x.titel, "y": x.baujahr,
                         "k": x.kraft_kn, "bh": x.betriebsstunden, "pe": eur(x, cfg), "l": x.land,
                         "o": x.ort, "g": a.grund, "q": x.quelle, "u": x.url})

    return {
        "lauf": run,
        "kurse": cfg.wechselkurse,
        "profile": profiles,
        "angebote": rows,
        "aktionen": acts,
        "anfragen": [{
            "p": index[d.listing.profil_id], "h": d.listing.hersteller,
            "m": d.listing.modell or d.listing.titel, "y": d.listing.baujahr, "l": d.listing.land,
            "sp": d.sprache, "offen": d.offene_punkte, "betreff": d.betreff, "text": d.text,
            "u": d.listing.url,
        } for d in drafts],
        "auktionen": [{
            "nr": a.quelle_id, "art": a.art, "titel": a.titel, "o": a.ort, "t": a.termin,
            "pos": a.positionen, "treffer": a.treffer, "u": a.url,
        } for a in sorted(auctions, key=lambda a: (not a.treffer, a.quelle_id))],
        "quellen": [{
            "q": q, "n": sum(x.quelle == q for x in listings),
            "gekappt": sum(1 for g in logs if g.quelle == q and g.hinweis),
            "fehler": sum(1 for g in logs if g.quelle == q and g.fehler),
        } for q in dict.fromkeys(g.quelle for g in logs) if q not in ("llm",)],
    }


def render(data: dict, standalone: bool = True) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    page = TEMPLATE.read_text(encoding="utf-8").replace("/*__DATA__*/null", payload)
    if not standalone:
        return page
    return ('<!doctype html>\n<html lang="de">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            "</head>\n<body>\n" + page + "\n</body>\n</html>\n")


def write(path: Path, data: dict, standalone: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(data, standalone), encoding="utf-8")
