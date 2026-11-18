"""Regelbasierte Extraktion und Normalisierung von Feldern aus Inseratstexten."""
from __future__ import annotations

import datetime as _dt
import re

_YEAR_MAX = _dt.date.today().year + 1


def clean(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def parse_int(num: str) -> int | None:
    digits = re.sub(r"[^\d]", "", num or "")
    return int(digits) if digits else None


def parse_year(text: str | None) -> int | None:
    for m in re.finditer(r"(?<!\d)(19[5-9]\d|20[0-4]\d)(?!\d)", text or ""):
        y = int(m.group(1))
        if 1950 <= y <= _YEAR_MAX:
            return y
    return None


def parse_price(text: str | None) -> tuple[float | None, str]:
    """'12.999 €' / '€29.500' / '$29,500' / 'EUR 1.250,00' -> (Betrag, Waehrung)."""
    t = clean(text)
    cur = ""
    if "€" in t or re.search(r"\bEUR\b", t):
        cur = "EUR"
    elif "$" in t or re.search(r"\bUSD\b", t):
        cur = "USD"
    elif "£" in t or re.search(r"\bGBP\b", t):
        cur = "GBP"
    elif re.search(r"\bCHF\b", t):
        cur = "CHF"
    m = re.search(r"\d[\d.,\s ]*\d|\d", t)
    if not m or not cur:
        return None, ""
    num = re.sub(r"[\s ]", "", m.group(0))
    # Dezimalteil (genau zwei Stellen am Ende) abtrennen, Rest sind Tausendertrenner
    dec = re.search(r"[.,](\d{2})$", num)
    if dec:
        num = num[: dec.start()]
    val = parse_int(num)
    if not val or val < 100:  # Platzhalter wie "1 EUR" sind kein Preis
        return None, ""
    return float(val), cur


def parse_hours(text: str | None) -> int | None:
    m = re.search(
        r"(?:Betriebsstunden|Laufzeit|operating hours|hours)\s*:?\s*(?:ca\.?\s*)?([\d.,']{2,9})\s*(?:h|Std|hours)?\b",
        text or "",
        re.I,
    )
    return parse_int(m.group(1)) if m else None


_KN = r"(\d{1,3}(?:[.\s]\d{3})+|\d+(?:[.,]\d+)?)\s*\[?\s*kN\b"
_TON = r"(\d{1,4}(?:[.,]\d+)?)\s*\[?\s*(?:tons?|tonnen|to|t)\b"
_FORCE_WORDS = r"(?:Nennkraft|Presskraft|Pre[sß]kraft|Stanzkraft|Schlie[sß]kraft|Zuhaltekraft|Druck|clamping force|capacity)"


def _num(s: str) -> float:
    s = s.strip()
    if re.fullmatch(r"\d{1,3}(?:[.\s]\d{3})+", s):
        return float(re.sub(r"[.\s]", "", s))
    return float(s.replace(",", "."))


def force_from_model(hersteller: str, modell: str) -> float | None:
    """Kraft aus der Typbezeichnung (Herstellerkonventionen)."""
    h, m = hersteller.lower(), modell
    if "bruderer" in h or re.search(r"\bBSTA\b", m, re.I):
        mm = re.search(r"BSTA[\s-]*(\d{2,4})", m, re.I)
        if mm:
            n = int(mm.group(1))
            return float(n * 10 if n < 100 else n)  # BSTA 25 = 25 t, BSTA 510 = 510 kN
    if "arburg" in h or "allrounder" in m.lower():
        mm = re.search(r"(?<!\d)(\d{3,4})\s*-\s*\d{2,4}(?!\d)", m)  # 370 S 600-100 -> 600 kN
        if mm and 100 <= int(mm.group(1)) <= 6500:
            return float(mm.group(1))
    return None


HOLMKLASSEN = (370, 420, 470, 520, 570, 630, 720)
# Obergrenze der Schließkraft je Klasse (kN), angelehnt an die Arburg-Baureihen
_KLASSE_BIS = ((700, 370), (1000, 420), (1500, 470), (2000, 520), (2200, 570), (2600, 630), (3300, 720))


def tiebar_class(hersteller: str, modell: str, kraft_kn: float | None) -> tuple[str, bool]:
    """Holmklasse (lichte Weite in mm) -> (Klasse, geschätzt?).

    Bei Arburg steht sie in der Typbezeichnung (Allrounder 470 A = 470 mm). Bei anderen
    Herstellern wird sie aus der Schließkraft geschätzt.
    """
    if "arburg" in hersteller.lower() or "allrounder" in modell.lower():
        m = re.search(r"(?<![\d-])(" + "|".join(map(str, HOLMKLASSEN)) + r")(?!\d)", modell)
        if m:
            return m.group(1), False
    if kraft_kn:
        for bis, klasse in _KLASSE_BIS:
            if kraft_kn <= bis:
                return str(klasse), True
    return "", False


def parse_force_kn(text: str | None) -> float | None:
    """Press-/Schliesskraft in kN aus Freitext; Tonnen werden mit Faktor 10 umgerechnet."""
    t = text or ""
    for pat, factor in ((_KN, 1.0), (_TON, 10.0)):
        m = re.search(_FORCE_WORDS + r"[^\d\n]{0,25}" + pat, t, re.I)
        if m:
            return _num(m.group(1)) * factor
    m = re.search(_KN, t, re.I)
    if m:
        return _num(m.group(1))
    m = re.match(r"\s*(\d{1,4})\s*tons?\b", t, re.I)  # '20 Ton, Bruderer ...'
    if m:
        return float(m.group(1)) * 10
    return None


def split_brand(title: str, brands: list[str]) -> tuple[str, str]:
    """Hersteller am Titelanfang erkennen -> (Hersteller, Rest als Modell)."""
    t = clean(title)
    for b in sorted(brands, key=len, reverse=True):
        m = re.search(r"(?<!\w)" + re.escape(b) + r"(?!\w)", t, re.I)
        if m:
            rest = clean(t[: m.start()] + " " + t[m.end():])
            return b, rest
    return "", t


_GIBBERISH = re.compile(r"[A-Za-z0-9 ]{8,30}")


def strip_watermarks(lines: list[str]) -> list[str]:
    """Einige Portale streuen Zufallszeichenfolgen als Kopierschutz in Beschreibungen."""
    out = []
    for ln in lines:
        s = ln.strip()
        letters = re.sub(r"[^a-z]", "", s.lower())
        rare = sum(letters.count(c) for c in "jqxywf") / max(len(letters), 1)
        if (
            _GIBBERISH.fullmatch(s)
            and len(s.split()) <= 5
            and not re.search(r"\d{2}", s)
            and (rare >= 0.2 or re.search(r"[a-z]\d[a-z]", s))
        ):
            continue
        out.append(ln)
    return out
