"""Resale.de - Stichwortseiten /<slug>/ (die Suche resalesuche2.php ist per robots.txt gesperrt)."""
from __future__ import annotations

from bs4 import BeautifulSoup

from .. import extract as ex
from ..models import Listing
from .base import Source

BASE = "https://www.resale.de"


class Resale(Source):
    name = "resale"

    def url_for(self, query: str, page: int = 1) -> str:
        return f"{BASE}/{query.strip('/')}/"

    def parse(self, html: str) -> list[Listing]:
        soup = BeautifulSoup(html, "lxml")
        out = []
        for wrap in soup.select(".rsk-card-wrap"):
            link = wrap.select_one("a.card-link-wrap[href]")
            art = wrap.select_one("article[data-id]")
            title_el = wrap.select_one(".card-title")
            if not (link and art and title_el):
                continue
            titel = ex.clean(title_el.get("title") or title_el.get_text(" "))
            cats = [ex.clean(c.get_text()) for c in wrap.select(".cat-level")]
            meta = wrap.select_one(".card-meta")
            meta_parts = [p.strip() for p in ex.clean(meta.get_text(" ")).split("·")] if meta else []
            baujahr = next((ex.parse_year(p) for p in meta_parts if ex.parse_year(p)), None)
            land = next((p for p in meta_parts if p and not ex.parse_year(p)), "")
            price_el = wrap.select_one(".card-price")
            preis, waehrung = ex.parse_price(price_el.get_text()) if price_el else (None, "")
            desc_el = wrap.select_one(".card-desc")
            desc = ex.clean(desc_el.get_text(" ")) if desc_el else ""
            hersteller, modell = ex.split_brand(titel, self.brands)
            out.append(
                Listing(
                    quelle=self.name,
                    quelle_id=art["data-id"],
                    url=BASE + link["href"],
                    titel=titel,
                    kategorie=cats[-1] if cats else "",
                    hersteller=hersteller,
                    modell=modell,
                    baujahr=baujahr,
                    land=land,
                    preis=preis,
                    waehrung=waehrung,
                    betriebsstunden=ex.parse_hours(desc),
                    kraft_kn=ex.parse_force_kn(desc),
                    beschreibung=desc[:1500],
                )
            )
        return out
