"""Maschinenliste (YAML) laden und Angebote gegen die Profile pruefen."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from . import extract as ex
from .models import Listing

PASST, PRUEFEN, AUSSERHALB = "passt", "prüfen", "außerhalb Spez."
RANK = {PASST: 0, PRUEFEN: 1, AUSSERHALB: 2}


@dataclass
class Profile:
    id: str
    name: str
    gruppe: str
    hersteller: list[str] = field(default_factory=list)
    begriffe: list[str] = field(default_factory=list)
    ausschluss: list[str] = field(default_factory=list)
    spez: dict = field(default_factory=dict)
    quellen: dict[str, list[str]] = field(default_factory=dict)

    def matches(self, lst: Listing) -> bool:
        head = f"{lst.kategorie} {lst.titel}".lower()
        if any(a.lower() in head for a in self.ausschluss):
            return False
        return any(b.lower() in head for b in self.begriffe)

    def assess(self, lst: Listing) -> tuple[str, str]:
        """Passung zur Spezifikation: (Status, Begruendung)."""
        out, offen = [], []
        ymin = self.spez.get("baujahr_min")
        if ymin:
            if lst.baujahr is None:
                offen.append("Baujahr unbekannt")
            elif lst.baujahr < ymin:
                out.append(f"Baujahr {lst.baujahr} < {ymin}")
        rng = self.spez.get("kraft_kn")
        if rng:
            if lst.kraft_kn is None:
                offen.append("Kraft unbekannt")
            elif not rng[0] <= lst.kraft_kn <= rng[1]:
                out.append(f"Kraft {lst.kraft_kn:.0f} kN nicht in {rng[0]}-{rng[1]} kN")
        if out:
            return AUSSERHALB, "; ".join(out)
        if offen:
            return PRUEFEN, "; ".join(offen)
        return PASST, "Baujahr und Spezifikation im Zielbereich"


@dataclass
class Config:
    profiles: list[Profile]
    wechselkurse: dict[str, float]
    auktions_begriffe: list[str]

    @property
    def brands(self) -> list[str]:
        return sorted({h for p in self.profiles for h in p.hersteller})

    def profile(self, pid: str) -> Profile | None:
        return next((p for p in self.profiles if p.id == pid), None)


def load(path: Path) -> Config:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    profiles = [Profile(**m) for m in raw["maschinen"]]
    return Config(
        profiles=profiles,
        wechselkurse=raw.get("wechselkurse", {"EUR": 1.0}),
        auktions_begriffe=(raw.get("auktionen") or {}).get("begriffe", []),
    )


def classify(lst: Listing, cfg: Config) -> bool:
    """Ordnet ein Angebot einem Profil zu und bewertet die Passung. False = kein Treffer."""
    origin = cfg.profile(lst.herkunft_profil)
    candidates = ([origin] if origin else []) + [p for p in cfg.profiles if p is not origin]
    prof = next((p for p in candidates if p.matches(lst)), None)
    if prof is None:
        return False
    if not lst.hersteller:
        lst.hersteller, _ = ex.split_brand(lst.titel, cfg.brands)
    by_model = ex.force_from_model(lst.hersteller, f"{lst.modell} {lst.titel}")
    if by_model:  # Typbezeichnung ist verlaesslicher als Freitext
        lst.kraft_kn = by_model
    lst.profil_id = prof.id
    lst.passung, lst.passung_grund = prof.assess(lst)
    return True


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def mark_duplicates(listings: list[Listing]) -> None:
    """Gleiche Maschine auf mehreren Portalen: Hersteller + Modell + Baujahr identisch."""
    seen: dict[tuple, Listing] = {}
    for lst in listings:
        if not (lst.modell and lst.baujahr):
            continue
        name = _norm(lst.modell)
        if not name.startswith(_norm(lst.hersteller)):
            name = _norm(lst.hersteller) + name
        key = (name, lst.baujahr)
        first = seen.setdefault(key, lst)
        if first is not lst and first.quelle != lst.quelle:
            lst.moegliche_dublette = f"{first.quelle}:{first.quelle_id}"
