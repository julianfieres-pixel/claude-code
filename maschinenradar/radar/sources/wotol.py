"""Wotol - weltweiter Marktplatz, Kategorieseiten /cat/<pfad>?page=N (robots.txt ohne Einschränkung).

Die Listen nennen Baujahr und Region, aber keinen Preis und keinen genauen Standort.
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from .. import extract as ex
from ..models import Listing
from .base import Source

BASE = "https://www.wotol.com"
REGION = (("EUROPE", "Europa"), ("AMERICA North", "Nordamerika"), ("AMERICA South", "Südamerika"),
          ("ASIA", "Asien"), ("AFRICA", "Afrika"), ("MIDDLE", "Nahost"), ("OCEANIA", "Ozeanien"))


class Wotol(Source):
    name = "wotol"

    def url_for(self, query: str, page: int = 1) -> str:
        url = f"{BASE}/cat/{query.strip('/')}"
        return url if page == 1 else f"{url}?page={page}"

    def has_next(self, html: str, page: int) -> bool:
        return f"?page={page + 1}\"" in html

    def parse(self, html: str) -> list[Listing]:
        soup = BeautifulSoup(html, "lxml")
        h1 = soup.find("h1")
        kategorie = ex.clean(h1.get_text(" ")) if h1 else ""
        out = []
        for card in soup.select("article.rd-row-card"):
            a = card.select_one(".rd-row-card__title a[href]")
            m = re.search(r"/(\d+)$", a["href"]) if a else None
            if not m:
                continue
            titel = ex.clean(a.get_text(" "))
            desc_el = card.select_one(".rd-row-card__desc")
            desc = ex.clean(desc_el.get_text(" ")) if desc_el else ""
            year_el = card.select_one(".rd-row-card__year")
            meta_el = card.select_one(".rd-row-card__meta")
            meta = ex.clean(meta_el.get_text(" ")).lstrip("◉ ").strip() if meta_el else ""
            land = next((de for key, de in REGION if key.lower() in meta.lower()), "")
            ton = re.search(r"(\d{2,4})\s*T(?:on)?s?\s*$", titel, re.I)
            hersteller, modell = ex.split_brand(re.sub(r"\s*\d{2,4}\s*T(?:on)?s?\s*$", "", titel, flags=re.I), self.brands)
            if not hersteller and modell:
                hersteller, _, modell = modell.partition(" ")
            out.append(
                Listing(
                    quelle=self.name,
                    quelle_id=m.group(1),
                    url=BASE + a["href"],
                    titel=titel,
                    kategorie=kategorie or "Injection Molding",
                    hersteller=hersteller.strip(" ,"),
                    modell=modell.strip(" ,"),
                    baujahr=ex.parse_year(year_el.get_text()) if year_el else None,
                    ort=meta,
                    land=land,
                    betriebsstunden=ex.parse_hours(desc),
                    kraft_kn=float(ton.group(1)) * 10 if ton else ex.parse_force_kn(desc),
                    beschreibung=desc[:1500],
                )
            )
        return out
