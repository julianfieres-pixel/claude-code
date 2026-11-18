"""Plasticker - Maschinenbörse der Kunststoffindustrie, Angebotslisten je Maschinenart.

robots.txt sperrt für allgemeine Crawler nur die Verwaltungsbereiche; die Listen sind erlaubt.
"""
from __future__ import annotations

import re
from urllib.parse import quote

from bs4 import BeautifulSoup

from .. import extract as ex
from ..models import Listing
from .base import Source

BASE = "https://plasticker.de"
PER_PAGE = 25


class Plasticker(Source):
    name = "plasticker"

    def url_for(self, query: str, page: int = 1) -> str:
        url = f"{BASE}/requipment/listaog.php?aog=A&art={quote(query)}"
        return url if page == 1 else f"{url}&show={page - 1}"

    def has_next(self, html: str, page: int) -> bool:
        return len(re.findall(r'_rq\d+"', html)) >= PER_PAGE

    def parse(self, html: str) -> list[Listing]:
        soup = BeautifulSoup(html, "lxml")
        out, seen = [], set()
        for a in soup.find_all("a", href=re.compile(r"_rq\d+$")):
            row = a.find_parent("tr")
            num = re.search(r"_rq(\d+)$", a["href"]).group(1)
            if row is None or num in seen:
                continue
            seen.add(num)
            ps = [ex.clean(p.get_text(" ")) for p in a.find_all("p")]
            head = a.select_one(".d14")
            kurz = ex.clean(head.get_text(" ")).rstrip(". ") if head else ""
            typ = next((p for p in ps[2:] if p), "")  # Zeile mit Hersteller und Typ
            kategorie = ps[1].replace(ex.clean(head.get_text(" ")) if head else "", "").strip() if len(ps) > 1 else ""
            text = " | ".join(row.stripped_strings)
            ort_m = re.search(r"\|\s*([^|]+?)\s*\(Anbieter\)", text)
            ort = ort_m.group(1) if ort_m else ""
            flag = row.find("img", title=re.compile("ansässig"))
            land_m = re.search(r"ist in (.+?) ansässig", flag["title"]) if flag else None
            year_m = re.search(r"Baujahr:\s*\|\s*(\d{4})", text)
            hours_m = re.search(r"Betriebsstd\.:\s*\|\s*([\d.]+)", text)
            price_m = re.search(r"(?:Preis|VB|VHB)[^|]*\|\s*([\d.,]+\s*(?:€|EUR|USD|\$))", text)
            preis, waehrung = ex.parse_price(price_m.group(1)) if price_m else (None, "")
            titel = typ or kurz
            hersteller, modell = ex.split_brand(titel, self.brands)
            out.append(
                Listing(
                    quelle=self.name,
                    quelle_id=num,
                    url=BASE + a["href"],
                    titel=f"{titel} {kurz}" if typ and kurz and kurz.lower() not in typ.lower() else titel,
                    kategorie=kategorie or "Spritzgiessmaschinen",
                    hersteller=hersteller,
                    modell=modell if hersteller else titel,
                    baujahr=ex.parse_year(year_m.group(1)) if year_m else None,
                    ort=ort,
                    land=(land_m.group(1) if land_m else ort.rsplit(",", 1)[-1].strip()),
                    preis=preis,
                    waehrung=waehrung,
                    betriebsstunden=ex.parse_int(hours_m.group(1)) if hours_m else None,
                    kraft_kn=ex.parse_force_kn(f"{titel} {kurz}"),
                    beschreibung=kurz[:1500],
                )
            )
        return out
