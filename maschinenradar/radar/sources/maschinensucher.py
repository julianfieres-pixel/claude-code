"""Maschinensucher.de - Kategorieseiten (/Name/ci-123) und Stichwortseiten (/mss/<begriff>).

Die freie Suche (/main/search) ist per robots.txt gesperrt. Stichwortseiten gibt es nur
fuer vom Portal angelegte Begriffe; unbekannte Begriffe liefern 404 (= keine Treffer).
"""
from __future__ import annotations

import re
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from .. import extract as ex
from ..models import Listing
from .base import Source

BASE = "https://www.maschinensucher.de"


class Maschinensucher(Source):
    name = "maschinensucher"

    def url_for(self, query: str, page: int = 1) -> str:
        if query.startswith("/"):
            url = BASE + query
        else:
            url = f"{BASE}/mss/{quote_plus(query.lower())}"
        return url if page == 1 else f"{url}?page={page}"

    def has_next(self, html: str, page: int) -> bool:
        return f"?page={page + 1}" in html

    def parse(self, html: str) -> list[Listing]:
        soup = BeautifulSoup(html, "lxml")
        out = []
        for card in soup.select("section.grid-card"):
            m = re.match(r"section-(\d+)", card.get("id", ""))
            link = card.find("a", href=re.compile(r"/i-\d+"))
            h2 = card.find("h2")
            if not (m and link and h2):
                continue
            cat = h2.select_one("span.text-gray-100")
            brand = h2.select_one("span.me-1")
            kategorie = ex.clean(cat.get_text()) if cat else ""
            hersteller = ex.clean(brand.get_text()) if brand else ""
            titel = ex.clean(h2.get_text(" "))
            modell = titel
            for part in (kategorie, hersteller):
                if part and modell.startswith(part):
                    modell = modell[len(part):].strip()

            loc = card.select_one(".country-name")
            flag = loc.find("img") if loc else None
            price_el = card.select_one("div.text-danger")
            body = card.select_one(".grid-body")
            body_text = ex.clean(body.get_text(" ")) if body else ""
            preis, waehrung = ex.parse_price(price_el.get_text()) if price_el else (None, "")
            hinweis = ""
            if preis:
                hinweis = " ".join(
                    w for w in ("VB", "Festpreis", "zzgl. MwSt.") if w in body_text
                )

            desc_el = card.select_one(".description-preview")
            lines = ex.strip_watermarks(
                list(desc_el.stripped_strings) if desc_el else []
            )
            desc = ex.clean(" ".join(lines))
            attr = lambda label: re.search(label + r"\s*:\s*([^,]+?)\s*,", desc)  # noqa: E731
            zustand = attr("Zustand")
            baujahr = attr("Baujahr")
            out.append(
                Listing(
                    quelle=self.name,
                    quelle_id=m.group(1),
                    url=BASE + link["href"].split("?")[0],
                    titel=titel,
                    kategorie=kategorie,
                    hersteller=hersteller,
                    modell=modell,
                    baujahr=ex.parse_year(baujahr.group(1)) if baujahr else None,
                    ort=ex.clean(loc.get_text()) if loc else "",
                    land=(flag.get("title") or "") if flag else "",
                    preis=preis,
                    waehrung=waehrung,
                    preis_hinweis=hinweis,
                    zustand=ex.clean(zustand.group(1)) if zustand else "",
                    betriebsstunden=ex.parse_hours(desc),
                    kraft_kn=ex.parse_force_kn(desc),
                    beschreibung=desc[:1500],
                )
            )
        return out
