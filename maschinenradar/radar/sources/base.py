from __future__ import annotations

from typing import Iterator

from ..http import Fetcher
from ..models import Listing, SourceLog


class Source:
    """Adapter fuer eine Quelle: Suchanfrage -> Liste von Listings."""

    name = ""

    page_cap = 99  # quellenspezifische Obergrenze fuer Ergebnisseiten

    def __init__(self, brands: list[str], max_pages: int = 2):
        self.brands = brands
        self.max_pages = min(max_pages, self.page_cap)

    def url_for(self, query: str, page: int = 1) -> str:
        raise NotImplementedError

    def parse(self, html: str) -> list[Listing]:
        raise NotImplementedError

    def has_next(self, html: str, page: int) -> bool:
        return False

    def search(self, fetcher: Fetcher, query: str) -> tuple[list[Listing], SourceLog]:
        log = SourceLog(self.name, query, self.url_for(query))
        out: list[Listing] = []
        seen: set[str] = set()
        for page in range(1, self.max_pages + 1):
            html = fetcher.get(self.url_for(query, page))
            if html is None:
                break
            items = self.parse(html)
            if items and all(it.quelle_id in seen for it in items):
                log.hinweis = f"Seite {page} wiederholt nur bekannte Angebote, abgebrochen"
                break
            seen.update(it.quelle_id for it in items)
            log.seiten += 1
            for it in items:
                it.suchanfrage = query
            out.extend(items)
            if not items or not self.has_next(html, page):
                break
            if page == self.max_pages:
                log.hinweis = f"nach {page} Seiten abgebrochen, weitere vorhanden"
        log.roh = len(out)
        return out, log
