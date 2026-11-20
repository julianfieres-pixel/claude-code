"""HTML-Dashboard: eine eigenständige Datei mit eingebetteten Daten, ohne Server nutzbar."""
from __future__ import annotations

import datetime as dt
import json
from collections import Counter
from pathlib import Path
from statistics import median

from . import geo, insolvency
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
          first_seen: dict, run: str, actions: list, drafts: list,
          insolvenzen: list | None = None) -> dict:
    index = {p.id: i for i, p in enumerate(cfg.profiles)}
    profiles = []
    for p in cfg.profiles:
        ls = [x for x in listings if x.profil_id == p.id]
        prices = [e for e in (eur(x, cfg) for x in ls) if e]
        years = [x.baujahr for x in ls if x.baujahr and x.baujahr <= dt.date.today().year]
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
        "dup": bool(x.moegliche_dublette), "bg": x.baugroesse, "wm": x.wunschmodell,
    } for x in listings]

    acts = []
    for i, a in enumerate(actions, 1):
        if a.insolvenz:
            e = a.insolvenz
            acts.append({"r": i, "a": a.aktion, "pt": a.punkte, "p": -2, "h": "",
                         "m": e.firma or e.titel, "art": e.status,
                         "o": " · ".join(x for x in (e.verwalter, e.kanzlei) if x),
                         "t": e.datum_verfahren or e.datum_meldung, "g": a.grund, "q": "indat",
                         "u": e.url})
        elif a.auction:
            au = a.auction
            acts.append({"r": i, "a": a.aktion, "pt": a.punkte, "p": -1, "m": au.titel, "h": "",
                         "art": au.art, "o": au.ort, "t": au.termin, "g": a.grund, "q": au.quelle,
                         "u": au.url})
        else:
            x = a.listing
            acts.append({"r": i, "a": a.aktion, "pt": a.punkte, "p": index[x.profil_id],
                         "h": x.hersteller, "m": x.modell or x.titel, "y": x.baujahr,
                         "k": x.kraft_kn, "bh": x.betriebsstunden, "pe": eur(x, cfg), "l": x.land,
                         "o": x.ort, "g": a.grund, "q": x.quelle, "u": x.url, "ziel": a.ziel,
                         "nah": a.naehe, "bg": x.baugroesse})

    deckung = []
    for p in cfg.profiles:
        need = cfg.bedarf.get(p.id)
        if need is None:
            continue
        ls = [x for x in listings if x.profil_id == p.id and x.passung == PASST and not x.moegliche_dublette]
        if isinstance(need, dict):
            for klasse, n in need.items():
                deckung.append({"p": index[p.id], "klasse": str(klasse), "bedarf": n,
                                "passt": sum(x.baugroesse == str(klasse) for x in ls)})
        else:
            wm = sum(x.wunschmodell for x in ls)
            deckung.append({"p": index[p.id], "klasse": "", "bedarf": need, "passt": len(ls),
                            "wunsch": wm if p.wunschmodelle else None})
    regional = []
    for land, need in cfg.bedarf_regionen.items():
        region = geo.region_of(land)
        for p in cfg.profiles:
            n = need.get(p.id)
            if not n:
                continue
            ls = [x for x in listings if x.profil_id == p.id and x.passung == PASST and not x.moegliche_dublette]
            for klasse, k in (n.items() if isinstance(n, dict) else [("", n)]):
                sel = [x for x in ls if not klasse or x.baugroesse == str(klasse)]
                regional.append({
                    "land": land, "region": region, "p": index[p.id], "klasse": str(klasse), "bedarf": k,
                    "im_land": sum(x.land == land or land in geo.teilregion_laender(x.ort) for x in sel),
                    "in_region": sum(geo.region_of(x.land) == region for x in sel),
                    "welt": len(sel),
                    "wunsch": sum(x.wunschmodell and geo.region_of(x.land) == region for x in sel)
                    if p.wunschmodelle and not p.holmklassen else None,
                })
    return {
        "regional": regional,
        "deckung": deckung,
        "welt": geo.world(),
        "jahr": dt.date.today().year,
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
        "insolvenzen": [{
            "f": e.firma or e.titel, "w": e.wahrscheinlichkeit, "gr": e.gruppen, "st": e.status,
            "vw": e.verwertung, "dv": e.datum_verfahren, "dm": e.datum_meldung, "v": e.verwalter,
            "k": e.kanzlei, "kt": e.kontakt, "ind": e.indizien, "titel": e.titel, "n": e.meldungen,
            "u": e.url, "anfrage": insolvency.anfrage(e, cfg.anfrage),
        } for e in insolvenzen or []],
        "quellen": [{
            "q": q, "n": sum(x.quelle == q for x in listings) or (len(insolvenzen or []) if q == "indat" else 0),
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
