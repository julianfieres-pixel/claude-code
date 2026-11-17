"""Anfrage-Entwürfe für Angebote mit offenen Punkten. Es wird nichts versendet."""
from __future__ import annotations

from dataclasses import dataclass

from .models import Listing
from .profiles import Config

DACH = {"Deutschland", "Österreich", "Schweiz"}

FRAGEN = {
    "preis": ("Preis (netto, ab Standort) und Zahlungsbedingungen",
              "Price (net, ex works) and payment terms"),
    "baujahr": ("Baujahr und Seriennummer", "Year of manufacture and serial number"),
    "kraft": ("Press- bzw. Schließkraft und genaue Typbezeichnung",
              "Press force / clamping force and exact model designation"),
    "stunden": ("Betriebsstunden und Datum der letzten Wartung oder Überholung",
                "Operating hours and date of last service or overhaul"),
    "verfuegbar": ("Verfügbarkeit: Ab wann kann die Maschine abgeholt werden?",
                   "Availability: from when can the machine be collected?"),
    "zustand": ("Zustand, bekannte Mängel und Lieferumfang (Vorschub, Steuerung, Dokumentation)",
                "Condition, known defects and scope of supply (feeder, control, documentation)"),
    "besichtigung": ("Besichtigung unter Strom möglich?", "Is an inspection under power possible?"),
}


@dataclass
class Draft:
    listing: Listing
    sprache: str
    offene_punkte: list[str]
    betreff: str
    text: str


def open_points(lst: Listing, cfg: Config) -> list[str]:
    prof = cfg.profile(lst.profil_id)
    keys = []
    if not lst.preis:
        keys.append("preis")
    if not lst.baujahr:
        keys.append("baujahr")
    if prof and prof.spez.get("kraft_kn") and lst.kraft_kn is None:
        keys.append("kraft")
    if lst.betriebsstunden is None:
        keys.append("stunden")
    return keys + ["verfuegbar", "zustand", "besichtigung"]


def draft(lst: Listing, cfg: Config) -> Draft:
    de = lst.land in DACH
    keys = open_points(lst, cfg)
    name = " ".join(x for x in (lst.hersteller, lst.modell) if x) or lst.titel
    ab = cfg.anfrage
    punkte = "\n".join(f"- {FRAGEN[k][0 if de else 1]}" for k in keys)
    if de:
        betreff = f"Anfrage zu Ihrem Angebot: {name}"
        text = (
            f"Guten Tag,\n\nwir interessieren uns für die von Ihnen angebotene Maschine {name}"
            f"{f' (Baujahr {lst.baujahr})' if lst.baujahr else ''}.\n{lst.url}\n\n"
            f"Bitte senden Sie uns folgende Angaben:\n{punkte}\n\n"
            f"Vielen Dank und freundliche Grüße\n{ab.get('absender', '')}\n"
            f"{ab.get('firma', '')}\n{ab.get('email', '')}"
        )
    else:
        betreff = f"Inquiry about your listing: {name}"
        text = (
            f"Hello,\n\nwe are interested in the machine you have listed: {name}"
            f"{f' (year {lst.baujahr})' if lst.baujahr else ''}.\n{lst.url}\n\n"
            f"Could you please send us the following details:\n{punkte}\n\n"
            f"Thank you and best regards\n{ab.get('absender', '')}\n"
            f"{ab.get('firma', '')}\n{ab.get('email', '')}"
        )
    labels = [FRAGEN[k][0].split(":")[0].split(" (")[0] for k in keys[: -3]]
    return Draft(lst, "DE" if de else "EN", labels, betreff, text)
