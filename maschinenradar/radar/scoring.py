"""Priorisierung: Punktzahl und empfohlene Aktion je Angebot (regelbasiert, nachvollziehbar)."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from .models import Auction, Listing
from .profiles import AUSSERHALB, PASST, Config

EU = {
    "Deutschland", "Österreich", "Schweiz", "Frankreich", "Italien", "Niederlande", "Belgien",
    "Polen", "Tschechien", "Spanien", "Portugal", "Dänemark", "Schweden", "Ungarn", "Slowenien",
    "Slowakei", "Luxemburg", "Finnland", "Rumänien", "Bulgarien", "Kroatien", "Irland",
}

A_VERHANDELN = "Angebot einholen und Besichtigung vereinbaren"
A_PREIS = "Preis und Verfügbarkeit anfragen"
A_DATEN = "Fehlende Daten anfragen"
A_AUKTION = "Auktion prüfen (Lose und Termin)"


@dataclass
class Action:
    punkte: int
    aktion: str
    grund: str
    listing: Listing | None = None
    auction: Auction | None = None


def score(lst: Listing, cfg: Config) -> Action | None:
    """0-100 Punkte. Außerhalb der Spezifikation und Dubletten ergeben keine Aktion."""
    if lst.passung == AUSSERHALB or lst.moegliche_dublette:
        return None
    prof = cfg.profile(lst.profil_id)
    teile = []
    punkte = 40 if lst.passung == PASST else 15
    teile.append("Spezifikation erfüllt" if lst.passung == PASST else lst.passung_grund)

    ymin = prof.spez.get("baujahr_min") if prof else None
    if lst.baujahr and ymin:
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
    if lst.land in EU:
        punkte += 15
        teile.append("Standort Europa")
    elif lst.land:
        punkte += 5
        teile.append(f"Standort {lst.land} (Transport, CE prüfen)")

    if lst.passung == PASST:
        aktion = A_VERHANDELN if lst.preis else A_PREIS
    else:
        aktion = A_DATEN
    return Action(min(punkte, 100), aktion, "; ".join(teile), listing=lst)


def rank(listings: list[Listing], auctions: list[Auction], cfg: Config, per_profile: int) -> list[Action]:
    """Aktionsliste: Auktionen mit Treffer zuerst (Fristen), dann die besten Angebote je Maschinenart."""
    out = [
        Action(100, A_AUKTION, "Treffer: " + ", ".join(a.treffer), auction=a)
        for a in auctions
        if a.treffer
    ]
    for prof in cfg.profiles:
        acts = [a for a in (score(l, cfg) for l in listings if l.profil_id == prof.id) if a]
        acts.sort(key=lambda a: (-a.punkte, -(a.listing.baujahr or 0)))
        out.extend(acts[:per_profile])
    return out
