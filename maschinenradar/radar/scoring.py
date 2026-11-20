"""Priorisierung: Punktzahl und empfohlene Aktion je Angebot (regelbasiert, nachvollziehbar)."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from . import geo
from .models import Auction, Listing
from .profiles import AUSSERHALB, PASST, Config

EU = {
    "Deutschland", "Österreich", "Schweiz", "Frankreich", "Italien", "Niederlande", "Belgien",
    "Polen", "Tschechien", "Spanien", "Portugal", "Dänemark", "Schweden", "Ungarn", "Slowenien",
    "Slowakei", "Luxemburg", "Europa", "Finnland", "Rumänien", "Bulgarien", "Kroatien", "Irland",
}

A_VERHANDELN = "Angebot einholen und Besichtigung vereinbaren"
A_PREIS = "Preis und Verfügbarkeit anfragen"
A_DATEN = "Fehlende Daten anfragen"
A_AUKTION = "Auktion prüfen (Lose und Termin)"
A_INSOLVENZ = "Insolvenzverwaltung ansprechen (Maschinenverwertung)"


@dataclass
class Action:
    punkte: int
    aktion: str
    grund: str
    listing: Listing | None = None
    auction: Auction | None = None
    ziel: str = ""  # Zielland, dessen Bedarf das Angebot am nächsten liegt
    naehe: str = ""  # "Land", "Region" oder "fern"
    insolvenz: object | None = None


def score(lst: Listing, cfg: Config) -> Action | None:
    """0-100 Punkte. Außerhalb der Spezifikation und Dubletten ergeben keine Aktion."""
    if lst.passung == AUSSERHALB or lst.moegliche_dublette:
        return None
    prof = cfg.profile(lst.profil_id)
    teile = []
    punkte = 40 if lst.passung == PASST else 15
    teile.append("Spezifikation erfüllt" if lst.passung == PASST else lst.passung_grund)

    ymin = prof.spez.get("baujahr_min") if prof else None
    if lst.baujahr and ymin and lst.baujahr <= dt.date.today().year:
        span = max(dt.date.today().year - ymin, 1)
        alter = round(25 * min(max(lst.baujahr - ymin, 0), span) / span)
        punkte += alter
        teile.append(f"Baujahr {lst.baujahr}")
    if lst.betriebsstunden is not None:
        if lst.betriebsstunden < 20000:
            punkte += 10
            teile.append(f"{lst.betriebsstunden:,} h".replace(",", "."))
        elif lst.betriebsstunden < 40000:
            punkte += 5
    if lst.preis:
        punkte += 10
        teile.append("Preis bekannt")
    ziele = cfg.ziele(lst.profil_id, lst.baugroesse)
    ziel = naehe = ""
    if ziele and lst.land:
        region = geo.region_of(lst.land)
        if lst.land in ziele:
            ziel, naehe = lst.land, "Land"
            punkte += 15
            teile.append(f"steht im Bedarfsland {ziel}")
        else:
            nah = [z for z in ziele if geo.region_of(z) == region]
            if nah:
                ziel, naehe = nah[0], "Region"
                punkte += 10
                teile.append(f"Standort {lst.land}, gleiche Region wie der Bedarf in {', '.join(nah)}")
            else:
                ziel, naehe = ziele[0], "fern"
                punkte += 3
                teile.append(f"Standort {lst.land}, Bedarf in {', '.join(ziele)} "
                             "(Transport, Zoll, Netzspannung und Zulassung prüfen)")
    elif lst.land in EU:
        punkte += 15
        teile.append("Standort Europa")
    elif lst.land:
        punkte += 5
        teile.append(f"Standort {lst.land} (Transport, CE prüfen)")

    if lst.wunschmodell:
        punkte += 10
        teile.insert(0, "Wunschmodell")
    if lst.passung == PASST:
        aktion = A_VERHANDELN if lst.preis else A_PREIS
    else:
        aktion = A_DATEN
    return Action(min(punkte, 100), aktion, "; ".join(teile), listing=lst, ziel=ziel, naehe=naehe)


VERWERTUNG_PUNKTE = {"hoch": 30, "mittel": 15, "gering": 0, "unklar": 5}


def score_insolvenz(e) -> Action | None:
    """Insolvenzen: nur wenn Maschinen noch auf den Markt kommen können (nicht bereits verkauft)."""
    if e.verwertung == "gering" or e.wahrscheinlichkeit < 50:
        return None
    punkte = min(100, round(e.wahrscheinlichkeit * 0.7) + VERWERTUNG_PUNKTE.get(e.verwertung, 0))
    grund = (f"{e.status}; Einsatz solcher Maschinen ca. {e.wahrscheinlichkeit} % "
             f"({', '.join(e.indizien[:4])}); Meldung vom {e.datum_meldung}")
    return Action(punkte, A_INSOLVENZ, grund, insolvenz=e)


def rank(listings: list[Listing], auctions: list[Auction], cfg: Config, per_profile: int,
         insolvenzen: list | None = None) -> list[Action]:
    """Aktionsliste: Auktionen mit Treffer zuerst (Fristen), dann Insolvenzen, dann die besten
    Angebote je Maschinenart."""
    out = [
        Action(100, A_AUKTION, "Treffer: " + ", ".join(a.treffer), auction=a)
        for a in auctions
        if a.treffer
    ]
    ins = [a for a in (score_insolvenz(e) for e in insolvenzen or []) if a]
    out.extend(sorted(ins, key=lambda a: -a.punkte))
    for prof in cfg.profiles:
        acts = [a for a in (score(l, cfg) for l in listings if l.profil_id == prof.id) if a]
        acts.sort(key=lambda a: (-a.punkte, -(a.listing.baujahr or 0)))
        laender = [z for z in cfg.bedarf_regionen if cfg.bedarf_regionen[z].get(prof.id)]
        if not laender:
            out.extend(acts[:per_profile])
            continue
        # Je Zielland die besten Angebote aus dessen Nähe; zu wenige werden weltweit aufgefüllt
        used: set[tuple[str, str]] = set()
        for land in laender:
            need = cfg.bedarf_regionen[land][prof.id]
            stueck = sum(need.values()) if isinstance(need, dict) else need
            je_land = min(max(3, stueck), 10)  # so viele Vorschläge wie benötigt, höchstens zehn
            near = [a for a in acts if a.ziel == land and a.naehe != "fern" and a.listing.key not in used]
            pick = near[:je_land]
            if len(pick) < je_land:
                klassen = {str(k) for k in need} if isinstance(need, dict) else None
                # nur Angebote, die keinem anderen Zielland näher liegen
                rest = [a for a in acts if a.listing.key not in used and a not in pick
                        and a.naehe in ("fern", "")
                        and (klassen is None or a.listing.baugroesse in klassen)]
                for a in rest[: je_land - len(pick)]:
                    pick.append(Action(a.punkte, a.aktion, a.grund, listing=a.listing, ziel=land, naehe="fern"))
            for a in pick:
                used.add(a.listing.key)
                a.ziel = land
            out.extend(pick)
    return out
