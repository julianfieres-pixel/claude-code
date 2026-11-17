"""Excel-Export: Lage je Maschinenart, Angebotsliste, Auktionen, Laufprotokoll."""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from statistics import median

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .models import Auction, Listing, SourceLog
from .profiles import AUSSERHALB, PASST, PRUEFEN, RANK, Config

HEAD_FILL = PatternFill("solid", fgColor="1F3864")
HEAD_FONT = Font(bold=True, color="FFFFFF")
FILLS = {
    PASST: PatternFill("solid", fgColor="C6EFCE"),
    PRUEFEN: PatternFill("solid", fgColor="FFEB9C"),
    AUSSERHALB: PatternFill("solid", fgColor="F2F2F2"),
}


def _sheet(wb: Workbook, title: str, header: list[str], widths: list[int]):
    ws = wb.create_sheet(title)
    ws.append(header)
    for i, w in enumerate(widths, 1):
        c = ws.cell(row=1, column=i)
        c.fill, c.font = HEAD_FILL, HEAD_FONT
        c.alignment = Alignment(vertical="center", wrap_text=True)
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A2"
    return ws


def _finish(ws) -> None:
    ws.auto_filter.ref = ws.dimensions


def _link(cell, url: str) -> None:
    cell.hyperlink = url
    cell.font = Font(color="0563C1", underline="single")


def eur(lst: Listing, cfg: Config) -> float | None:
    rate = cfg.wechselkurse.get(lst.waehrung)
    return round(lst.preis * rate) if lst.preis and rate else None


def write(
    path: Path,
    cfg: Config,
    listings: list[Listing],
    auctions: list[Auction],
    logs: list[SourceLog],
    first_seen: dict[tuple[str, str], str],
    run: str,
    verworfen: int,
) -> None:
    wb = Workbook()
    wb.remove(wb.active)
    order = {p.id: i for i, p in enumerate(cfg.profiles)}
    names = {p.id: p for p in cfg.profiles}

    # -- Lage -----------------------------------------------------------
    ws = _sheet(
        wb,
        "Lage",
        ["Gruppe", "Maschinenart", "Zielspezifikation", "Angebote", "passt", "prüfen",
         "außerhalb Spez.", "mit Preis", "Preis min EUR (ca.)", "Preis Median EUR (ca.)",
         "Preis max EUR (ca.)", "Baujahr Median", "jüngstes Baujahr", "Länder (Top 3)",
         "neu in diesem Lauf"],
        [12, 30, 34, 10, 8, 8, 12, 10, 14, 14, 14, 10, 10, 34, 10],
    )
    for p in cfg.profiles:
        ls = [x for x in listings if x.profil_id == p.id]
        prices = [e for e in (eur(x, cfg) for x in ls) if e]
        years = [x.baujahr for x in ls if x.baujahr]
        lands = Counter(x.land for x in ls if x.land).most_common(3)
        spec = []
        if p.spez.get("baujahr_min"):
            spec.append(f"Baujahr ab {p.spez['baujahr_min']}")
        if p.spez.get("kraft_kn"):
            spec.append("Kraft {}-{} kN".format(*p.spez["kraft_kn"]))
        ws.append([
            p.gruppe, p.name, ", ".join(spec), len(ls),
            sum(x.passung == PASST for x in ls), sum(x.passung == PRUEFEN for x in ls),
            sum(x.passung == AUSSERHALB for x in ls), len(prices),
            min(prices) if prices else None, round(median(prices)) if prices else None,
            max(prices) if prices else None, round(median(years)) if years else None,
            max(years) if years else None, ", ".join(f"{l} ({n})" for l, n in lands),
            sum(first_seen.get(x.key) == run for x in ls),
        ])
    _finish(ws)

    # -- Angebote -------------------------------------------------------
    ws = _sheet(
        wb,
        "Angebote",
        ["Gruppe", "Maschinenart", "Passung", "Begründung", "Hersteller", "Modell", "Baujahr",
         "Kraft kN", "Betriebsstunden", "Preis", "Währung", "Preis EUR (ca.)", "Preisstatus",
         "Land", "Ort", "Zustand", "Verkäufer", "Quelle", "Link", "erstmals gesehen",
         "mögliche Dublette", "Kategorie lt. Quelle", "Beschreibung"],
        [11, 26, 14, 34, 14, 24, 9, 9, 12, 11, 8, 12, 14, 14, 22, 20, 24, 15, 12, 13, 22, 26, 80],
    )
    listings = sorted(
        listings,
        key=lambda x: (order.get(x.profil_id, 99), RANK.get(x.passung, 9), -(x.baujahr or 0)),
    )
    for x in listings:
        p = names[x.profil_id]
        status = (x.preis_hinweis or "Preis genannt") if x.preis else "auf Anfrage"
        ws.append([
            p.gruppe, p.name, x.passung, x.passung_grund, x.hersteller, x.modell, x.baujahr,
            x.kraft_kn, x.betriebsstunden, x.preis, x.waehrung, eur(x, cfg), status, x.land,
            x.ort, x.zustand, x.verkaeufer, x.quelle, "öffnen", first_seen.get(x.key, run),
            x.moegliche_dublette, x.kategorie, x.beschreibung[:500],
        ])
        r = ws.max_row
        ws.cell(row=r, column=3).fill = FILLS.get(x.passung, FILLS[AUSSERHALB])
        _link(ws.cell(row=r, column=19), x.url)
        for col in (10, 12):
            ws.cell(row=r, column=col).number_format = "#,##0"
    _finish(ws)

    # -- Auktionen ------------------------------------------------------
    ws = _sheet(
        wb,
        "Auktionen",
        ["Treffer-Begriffe", "Art", "Nr.", "Titel", "Ort", "Termin", "Positionen", "Quelle", "Link"],
        [26, 22, 9, 70, 26, 22, 11, 10, 10],
    )
    for a in sorted(auctions, key=lambda a: (not a.treffer, a.quelle_id)):
        ws.append([", ".join(a.treffer), a.art, a.quelle_id, a.titel, a.ort, a.termin,
                   a.positionen, a.quelle, "öffnen"])
        r = ws.max_row
        if a.treffer:
            ws.cell(row=r, column=1).fill = FILLS[PRUEFEN]
        _link(ws.cell(row=r, column=9), a.url)
    _finish(ws)

    # -- Lauf -----------------------------------------------------------
    ws = _sheet(wb, "Lauf", ["Quelle", "Suchanfrage", "Seiten", "Rohtreffer", "Fehler", "Hinweis", "URL"],
                [16, 40, 8, 11, 50, 44, 70])
    for g in logs:
        ws.append([g.quelle, g.anfrage, g.seiten, g.roh, g.fehler, g.hinweis, g.url])
    ws.append([])
    ws.append(["Lauf", run])
    ws.append(["Angebote nach Filter", len(listings)])
    ws.append(["verworfen (kein Profil passt)", verworfen])
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
