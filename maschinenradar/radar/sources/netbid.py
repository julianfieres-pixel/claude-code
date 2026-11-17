"""NetBid - Auktionskalender (Insolvenz- und Industrieauktionen), Abgleich ueber Auktionstitel."""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from .. import extract as ex
from ..http import Fetcher
from ..models import Auction, SourceLog

BASE = "https://www.netbid.com"
URL = f"{BASE}/en/auctions"


def parse(html: str) -> list[Auction]:
    soup = BeautifulSoup(html, "lxml")
    out, seen = [], set()
    for li in soup.select("li.auctions-list-item"):
        a = li.find("a", href=re.compile(r"/auctions/\d+"))
        parts = [ex.clean(s) for s in li.stripped_strings]
        num_i = next((i for i, p in enumerate(parts) if re.fullmatch(r"#\d+", p)), None)
        if not a or num_i is None or num_i + 1 >= len(parts):
            continue
        num = parts[num_i][1:]
        if num in seen:
            continue
        seen.add(num)
        date_i = next(
            (i for i, p in enumerate(parts) if re.match(r"\d{1,2}\. \w{3,9}\.? \d{4}", p)), None
        )
        pos = next((ex.parse_int(p) for p in parts if re.fullmatch(r"\d+ Positions?", p)), None)
        out.append(
            Auction(
                quelle="netbid",
                quelle_id=num,
                url=BASE + a["href"],
                titel=parts[num_i + 1],
                art=parts[0],
                ort=parts[date_i - 1] if date_i and date_i - 1 > num_i + 1 else "",
                termin=parts[date_i] if date_i else "",
                positionen=pos,
            )
        )
    return out


def fetch(fetcher: Fetcher, keywords: list[str]) -> tuple[list[Auction], SourceLog]:
    log = SourceLog("netbid", "Auktionskalender", URL)
    html = fetcher.get(URL)
    auctions = parse(html) if html else []
    log.seiten, log.roh = (1 if html else 0), len(auctions)
    for au in auctions:
        t = au.titel.lower()
        au.treffer = [k for k in keywords if re.search(r"(?<!\w)" + re.escape(k.lower()), t)]
    return auctions, log
