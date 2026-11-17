"""Surplus Record (USA) - Kategorieseiten /machinery-equipment/<kategorie>/[<hersteller>/].

Die Suche (/search/?) ist per robots.txt gesperrt; robots.txt verlangt 10 s Pause je Abruf.
"""
from __future__ import annotations

import re
from bs4 import BeautifulSoup

from .. import extract as ex
from ..models import Listing
from .base import Source

BASE = "https://surplusrecord.com"
_CA = {"ON", "QC", "BC", "AB", "MB", "SK", "NS", "NB", "NL", "PE"}


class SurplusRecord(Source):
    name = "surplusrecord"

    page_cap = 3

    def url_for(self, query: str, page: int = 1) -> str:
        url = f"{BASE}/machinery-equipment/{query.strip('/')}/"
        return url if page == 1 else f"{url}page/{page}/"

    def has_next(self, html: str, page: int) -> bool:
        return f"/page/{page + 1}/" in html

    def parse(self, html: str) -> list[Listing]:
        soup = BeautifulSoup(html, "lxml")
        out = []
        for card in soup.select("div.listing[id^=listing-seq-id-]"):
            a = card.select_one(".listing-title a[href]")
            if not a:
                continue

            def val(cls: str) -> str:
                el = card.select_one(f".{cls} .listing-value")
                return ex.clean(el.get_text(" ")) if el else ""

            titel = ex.clean(a.get_text(" "))
            ort = val("listing-location")
            st = re.search(r",\s*([A-Z]{2})$", ort)
            land = ("Kanada" if st.group(1) in _CA else "USA") if st else ""
            price_el = card.select_one(".price-conversion-text")
            preis, waehrung = ex.parse_price(price_el.get_text()) if price_el else (None, "")
            desc_el = card.select_one(".listing-description-on-category")
            desc = ex.clean(desc_el.get_text(" ")) if desc_el else ""
            href = a["href"]
            out.append(
                Listing(
                    quelle=self.name,
                    quelle_id=card["id"].rsplit("-", 1)[-1],
                    url=href if href.startswith("http") else BASE + href,
                    titel=titel,
                    kategorie=val("listing-category"),
                    hersteller=val("listing-data-mfr"),
                    modell=val("listing-data-model"),
                    baujahr=ex.parse_year(val("listing-data-year")),
                    ort=ort,
                    land=land,
                    preis=preis,
                    waehrung=waehrung,
                    betriebsstunden=ex.parse_hours(desc),
                    kraft_kn=ex.parse_force_kn(titel),
                    verkaeufer=val("listing-data-seller"),
                    beschreibung=desc[:1500],
                )
            )
        return out
