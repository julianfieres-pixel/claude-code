"""Ländernamen vereinheitlichen und Kartenpositionen bereitstellen.

Die Quellen nennen höchstens das Land (deutsch), Wotol nur die Weltregion. Für eine Karte
auf Ortsebene bräuchte es einen Geokodierdienst; hier wird je Land ein Punkt gesetzt.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

WELT = Path(__file__).parent / "templates" / "world.json"
REGIONEN = {"Europa", "Nordamerika", "Südamerika", "Asien", "Afrika", "Nahost", "Ozeanien"}

# Schreibweisen der Quellen -> einheitlicher deutscher Name
ALIAS = {
    "oesterreich": "Österreich", "austria": "Österreich", "germany": "Deutschland",
    "großbritannien": "Vereinigtes Königreich", "grossbritannien": "Vereinigtes Königreich",
    "england": "Vereinigtes Königreich", "uk": "Vereinigtes Königreich",
    "china, volksrepublik": "China", "volksrepublik china": "China",
    "tschechische republik": "Tschechien", "mazedonien": "Nordmazedonien",
    "vereinigte staaten": "USA", "usa": "USA", "holland": "Niederlande",
    "korea, republik": "Südkorea", "russische föderation": "Russland",
}
# deutscher Name -> Name im Kartendatensatz (Natural Earth über world-atlas)
KARTE = {
    "Deutschland": "Germany", "Österreich": "Austria", "Schweiz": "Switzerland", "Polen": "Poland",
    "Frankreich": "France", "Italien": "Italy", "Spanien": "Spain", "Portugal": "Portugal",
    "Niederlande": "Netherlands", "Belgien": "Belgium", "Luxemburg": "Luxembourg",
    "Dänemark": "Denmark", "Schweden": "Sweden", "Norwegen": "Norway", "Finnland": "Finland",
    "Vereinigtes Königreich": "United Kingdom", "Irland": "Ireland", "Tschechien": "Czechia",
    "Slowakei": "Slovakia", "Slowenien": "Slovenia", "Ungarn": "Hungary", "Kroatien": "Croatia",
    "Serbien": "Serbia", "Nordmazedonien": "Macedonia", "Bulgarien": "Bulgaria",
    "Rumänien": "Romania", "Griechenland": "Greece", "Türkei": "Turkey", "Estland": "Estonia",
    "Lettland": "Latvia", "Litauen": "Lithuania", "Ukraine": "Ukraine", "Russland": "Russia",
    "Bosnien und Herzegowina": "Bosnia and Herz.", "USA": "United States of America",
    "Kanada": "Canada", "Mexiko": "Mexico", "Brasilien": "Brazil", "China": "China",
    "Japan": "Japan", "Südkorea": "South Korea", "Taiwan": "Taiwan", "Indien": "India",
    "Vietnam": "Vietnam", "Singapur": "Singapore", "Indonesien": "Indonesia", "Thailand": "Thailand", "Malaysia": "Malaysia", "Israel": "Israel",
    "Vereinigte Arabische Emirate": "United Arab Emirates", "Südafrika": "South Africa",
    "Australien": "Australia", "Ägypten": "Egypt", "Marokko": "Morocco", "Tunesien": "Tunisia",
}


# Weltregion je Land (Namen wie bei Wotol), für den Abgleich von Angebot und Bedarf
_REGION_LAENDER = {
    "Nordamerika": ["USA", "Kanada", "Mexiko"],
    "Südamerika": ["Brasilien", "Argentinien", "Chile", "Kolumbien"],
    "Asien": ["China", "Japan", "Südkorea", "Taiwan", "Indien", "Vietnam", "Thailand", "Malaysia",
              "Singapur", "Indonesien", "Philippinen"],
    "Nahost": ["Israel", "Vereinigte Arabische Emirate", "Saudi-Arabien"],
    "Afrika": ["Südafrika", "Ägypten", "Marokko", "Tunesien"],
    "Ozeanien": ["Australien", "Neuseeland"],
}
WELTREGION = {land: region for region, laender in _REGION_LAENDER.items() for land in laender}


def region_of(land: str) -> str:
    """Weltregion eines Landes; unbekannte Länder mit Kartenposition zählen zu Europa."""
    if not land:
        return ""
    if land in REGIONEN:
        return land
    return WELTREGION.get(land, "Europa")


def normalize_country(name: str) -> str:
    """Vereinheitlicht den Ländernamen; unbrauchbare Werte (Zahlen, Striche) werden leer."""
    n = re.sub(r"\s+", " ", name or "").strip(" -—–,.")
    if not n or not re.search(r"[A-Za-zÄÖÜäöü]{3}", n):
        return ""
    return ALIAS.get(n.lower(), n)


def world() -> dict:
    """Kartendaten für das Dashboard: Länderumrisse und Punkte je deutschem Ländernamen."""
    data = json.loads(WELT.read_text(encoding="utf-8"))
    points = {de: data["punkte"][en] for de, en in KARTE.items() if en in data["punkte"]}
    return {"w": data["w"], "h": data["h"], "pfad": data["pfad"], "punkte": points,
            "europa": data["europa"]}
