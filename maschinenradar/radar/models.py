from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class Listing:
    """Ein Angebot in einheitlichem Schema. Unbekannte Felder bleiben None bzw. leer."""

    quelle: str
    quelle_id: str
    url: str
    titel: str
    kategorie: str = ""
    hersteller: str = ""
    modell: str = ""
    baujahr: int | None = None
    ort: str = ""
    land: str = ""
    preis: float | None = None
    waehrung: str = ""
    preis_hinweis: str = ""
    zustand: str = ""
    betriebsstunden: int | None = None
    kraft_kn: float | None = None
    hubzahl_max: int | None = None
    stange_mm: float | None = None
    llm_ergaenzt: bool = False
    verkaeufer: str = ""
    beschreibung: str = ""
    suchanfrage: str = ""
    herkunft_profil: str = ""
    # wird von classify gesetzt
    profil_id: str = ""
    passung: str = ""
    passung_grund: str = ""
    moegliche_dublette: str = ""

    @property
    def key(self) -> tuple[str, str]:
        return (self.quelle, self.quelle_id)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Auction:
    quelle: str
    quelle_id: str
    url: str
    titel: str
    art: str = ""
    ort: str = ""
    termin: str = ""
    positionen: int | None = None
    treffer: list[str] = field(default_factory=list)


@dataclass
class SourceLog:
    quelle: str
    anfrage: str
    url: str
    seiten: int = 0
    roh: int = 0
    fehler: str = ""
    hinweis: str = ""
