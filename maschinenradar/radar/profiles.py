"""Maschinenliste (YAML) laden und Angebote gegen die Profile pruefen."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

import datetime as dt

from . import extract as ex
from . import geo
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
    hersteller_pflicht: bool = False  # nur Angebote der gelisteten Hersteller zulassen
    aktiv: bool = True
    wunschmodelle: list[str] = field(default_factory=list)  # bevorzugte Typen, z. B. "SR-20"
    holmklassen: bool = False  # Spritzguss: Angebote nach Holmklasse einordnen

    def is_wunschmodell(self, lst: Listing) -> bool:
        name = re.sub(r"[^a-z0-9]", "", f"{lst.modell} {lst.titel}".lower())
        return any(re.sub(r"[^a-z0-9]", "", w.lower()) in name for w in self.wunschmodelle)

    def matches(self, lst: Listing) -> bool:
        head = f"{lst.kategorie} {lst.titel}".lower()
        if any(a.lower() in head for a in self.ausschluss):
            return False
        if self.hersteller_pflicht:
            name = f"{lst.hersteller} {lst.titel}"
            if not any(re.search(r"(?<!\w)" + re.escape(h) + r"(?!\w)", name, re.I) for h in self.hersteller):
                return False
        return any(b.lower() in head for b in self.begriffe)

    def assess(self, lst: Listing) -> tuple[str, str]:
        """Passung zur Spezifikation: (Status, Begruendung)."""
        out, offen = [], []
        ymin = self.spez.get("baujahr_min")
        if lst.baujahr and lst.baujahr > dt.date.today().year:
            # Händler tragen bei Bestell- und Überholmaschinen das Lieferjahr als Baujahr ein
            offen.append(f"Baujahr {lst.baujahr} liegt in der Zukunft: Bestell- oder "
                         "Überholmaschine, tatsächliches Baujahr erfragen")
        elif ymin:
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
    anfrage: dict = field(default_factory=dict)
    llm_modell: str = "claude-opus-5-5"
    aktionen_je_maschinenart: int = 15
    insolvenzen: dict = field(default_factory=dict)
    bedarf: dict = field(default_factory=dict)  # Stückzahlen aus der lokalen Datei, nicht im Repository
    bedarf_regionen: dict = field(default_factory=dict)  # Zielland -> Maschinenart -> Stückzahl

    def ziele(self, profil_id: str, klasse: str = "") -> list[str]:
        """Zielländer, die diese Maschinenart (und ggf. Holmklasse) brauchen."""
        out = []
        for land, need in self.bedarf_regionen.items():
            n = need.get(profil_id)
            if isinstance(n, dict):
                n = n.get(klasse) or n.get(int(klasse)) if klasse.isdigit() else None
            if n:
                out.append(land)
        return out

    @property
    def brands(self) -> list[str]:
        return sorted({h for p in self.profiles for h in p.hersteller})

    def profile(self, pid: str) -> Profile | None:
        return next((p for p in self.profiles if p.id == pid), None)


def load(path: Path, lokal: bool = True) -> Config:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    profiles = [p for p in (Profile(**m) for m in raw["maschinen"]) if p.aktiv]
    local = Path(path).with_name("bedarf.local.yaml")  # vertrauliche Stückzahlen, per .gitignore ausgeschlossen
    daten = (yaml.safe_load(local.read_text(encoding="utf-8")) or {}) if lokal and local.exists() else {}
    regionen = daten.get("bedarf_regionen") or {}
    bedarf = dict(daten.get("bedarf") or {})
    if regionen and not bedarf:  # Gesamtbedarf aus den Zielländern summieren
        for need in regionen.values():
            for pid, n in need.items():
                if isinstance(n, dict):
                    tgt = bedarf.setdefault(pid, {})
                    for klasse, k in n.items():
                        tgt[klasse] = tgt.get(klasse, 0) + k
                else:
                    bedarf[pid] = bedarf.get(pid, 0) + n
    return Config(
        profiles=profiles,
        wechselkurse=raw.get("wechselkurse", {"EUR": 1.0}),
        auktions_begriffe=(raw.get("auktionen") or {}).get("begriffe", []),
        anfrage=raw.get("anfrage") or {},
        llm_modell=(raw.get("llm") or {}).get("modell", "claude-opus-5-5"),
        aktionen_je_maschinenart=(raw.get("aktionsliste") or {}).get("je_maschinenart", 15),
        insolvenzen=raw.get("insolvenzen") or {},
        bedarf=bedarf,
        bedarf_regionen=regionen,
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
    lst.land = geo.normalize_country(lst.land)
    if prof.holmklassen:
        lst.baugroesse, _ = ex.tiebar_class(lst.hersteller, f"{lst.modell} {lst.titel}", lst.kraft_kn)
    lst.wunschmodell = prof.is_wunschmodell(lst)
    lst.passung, lst.passung_grund = prof.assess(lst)
    return True


def reassess(lst: Listing, cfg: Config) -> None:
    prof = cfg.profile(lst.profil_id)
    if prof:
        lst.passung, lst.passung_grund = prof.assess(lst)


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
