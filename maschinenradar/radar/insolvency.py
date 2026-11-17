"""Insolvenz-Monitor: Meldungen von Insolvenzkanzleien (INDat) nach Betrieben durchsuchen,
die wahrscheinlich Maschinen der gesuchten Art einsetzen.

Quelle ist die offene WordPress-Schnittstelle von der-indat.de. Das amtliche Portal
insolvenzbekanntmachungen.de untersagt automatisierte Zugriffe per robots.txt und wird
deshalb nicht abgefragt. Alle Felder werden regelbasiert aus Freitext gelesen und sind
als Hinweis zu verstehen, nicht als geprüfte Angabe.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import re
from dataclasses import dataclass, field
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from .http import Fetcher
from .models import SourceLog

API = "https://www.der-indat.de/wp-json/wp/v2/posts"
FIELDS = "id,date,link,title,content"
GEWICHT = {"stark": 0.55, "mittel": 0.30, "schwach": 0.12}

RECHTSFORM = r"(?:GmbH\s*&\s*Co\.?\s*KGaA|GmbH\s*&\s*Co\.?\s*KG|GmbH|AG|SE|KG|OHG|UG|e\.\s?K\.)"
FIRMA_RE = re.compile(
    r"((?:(?:[A-ZÄÖÜ0-9][\w&.+\-]*|und|&)\s+){0,6}?[A-ZÄÖÜ0-9][\w&.+\-]*\s+" + RECHTSFORM + r")(?![\w])"
)
FIRMA_VORSPANN = re.compile(
    r"^(?:(?:\d[\d.]*|Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|"
    r"Dezember|Die|Der|Das|Bei|Für|Insolvente[nr]?|Über|Vermögen|der|des|die|von|Verkauf|"
    r"Insolvenzverwalter|und|an|beim|mit|in|Sanierung|Investorenprozess|Zukunft|&)\s+)+")
KANZLEIEN = [
    "PLUTA", "Schultze & Braun", "Brinkmann & Partner", "Dr. Beck & Partner", "White & Case",
    "GÖRG", "anchor Rechtsanwälte", "HWW", "dhpg", "BBL", "REIMER", "Jaffé", "Flöther & Wissing",
    "CMS", "Kebekus et Zimmermann", "Niering Stock Tömp", "WallnerWeiß", "SGP Schneider Geiwitz",
    "Pohlmann Hofmann", "VOIGT SALUS", "Müller-Heydenreich Bierbach & Kollegen", "Menold Bezler",
    "LIESER Rechtsanwälte", "GRUB BRUGGER", "Schiebe und Collegen", "Mönning Feser Partner",
    "Kübler", "STAPPER", "Wellensiek", "Baker Tilly", "BRL", "Eckert Rechtsanwälte", "RSW",
    "Dr. Dälken Rechtsanwälte", "SZA Schilling, Zutt & Anschütz", "Kulitzscher & Ettelt", "ANURE",
    "Abel und Kollegen", "Ebner Stolz", "dkp", "Buchalik Brömmekamp", "Tiefenbacher", "FRH",
]
BERATER = re.compile(
    r"rechtsanw|kanzlei|partner|corporate finance|treuhand|steuerberat|wirtschaftspr|consult|"
    r"capital|advis|beratung|restrukturierung|pluta|falkensteg|indat|m&a", re.I)
TITEL = r"(?:(?:Rechtsanwalt|Rechtsanwältin|RA|RAin|Dr\.|Prof\.|jur\.|Dipl\.-\w+\.?|Diplom-\w+)\s+)*"
NAME = r"((?:Dr\.\s+)?[A-ZÄÖÜ][a-zäöüß]+(?:-[A-ZÄÖÜ][a-zäöüß]+)?(?:\s+(?:von|van|de)\s+)?(?:\s+[A-ZÄÖÜ][a-zäöüß]+(?:-[A-ZÄÖÜ][a-zäöüß]+)?){1,2})"
ROLLE = r"(?:vorläufige[rn]?\s+)?(?:Insolvenzverwalter(?:in)?|Sachwalter(?:in)?)"
VERWALTER_RES = [
    re.compile(ROLLE + r"\s+" + TITEL + NAME),
    re.compile(TITEL + NAME + r"[^.\n]{0,140}?\bzu[mr]\s+" + ROLLE),
    re.compile(TITEL + NAME + r"[^.\n]{0,80}?\bals\s+" + ROLLE),
    re.compile(TITEL + NAME + r"\s*\([^)]{2,60}\)\s+zu[mr]\s+" + ROLLE),
]
KEIN_NAME = re.compile(
    r"^(Der|Die|Das|Den|Dem|Ein|Eine|Herr|Frau|General\w*|Sanierungs\w*|Mit|Nach|Für|Ziel|Bei|Als|Im|In|Am|Zum|Zur|Und|Über|Seit|Von|"
    r"Insolvenz\w*|Sachwalter\w*|Rechtsanw\w*|Kanzlei|Amtsgericht|Geschäfts\w*|Gläubiger\w*|"
    r"Verfahren\w*|Unternehmen\w*|Eröffnung|Sanierung\w*|Eigenverwaltung)\b")
KANZLEI_RES = [
    re.compile(r"(?:von|aus) der (?:Kanzlei|Sozietät|Wirtschaftskanzlei)\s+([A-ZÄÖÜ][\w&.\- ]{2,60}?)(?=\s+(?:in|zum|zur|als|bestellt|ist|hat|wurde|und|mit)\b|[,.;)\n])"),
    re.compile(r"(?:Kanzlei|Sozietät)\s+([A-ZÄÖÜ][\w&.\- ]{2,60}?)(?=\s+(?:in|zum|zur|als|bestellt|ist|hat|wurde|zählt|gehört)\b|[,.;:)\n])"),
]
STATUS = [  # Reihenfolge = Vorrang; (Status, Muster, Chance auf Maschinenverwertung)
    ("Stilllegung / Abwicklung",
     r"geschäftsbetrieb(?:s)? (?:wird |wurde |ist )?eingestellt|betriebsstilllegung|stilllegung|"
     r"betrieb wird (?:geschlossen|eingestellt)|ausproduktion|abwicklung des|kein investor|"
     r"schließung des (?:werks|standorts|betriebs)|werk(?:s)?schließung", "hoch"),
    ("Verkauft / Investor gefunden",
     r"veräußert|verkauft|übernimmt|übernahme durch|übernommen|investor gefunden|erwirbt|erworben|"
     r"übertragende sanierung|neuer eigentümer|kaufvertrag|sanierung (?:erfolgreich )?abgeschlossen|"
     r"zukunft (?:\w+ ){0,3}gesichert|insolvenzplan (?:\w+ ){0,4}(?:angenommen|bestätigt|zugestimmt)", "gering"),
    ("Investorensuche",
     r"investorensuche|investorenprozess|sucht (?:einen )?investor|m&a-prozess|suche nach (?:einem )?investor|"
     r"interessenten", "mittel"),
    ("Verfahren eröffnet",
     r"insolvenzverfahren (?:wurde |ist )?(?:am [^.]{0,30})?eröffnet|verfahren (?:wurde |ist )?eröffnet|"
     r"eröffnung des insolvenzverfahrens|mit eröffnung", "mittel"),
    ("Eigenverwaltung / Schutzschirm", r"eigenverwaltung|schutzschirm", "gering"),
    ("Antrag / vorläufiges Verfahren",
     r"insolvenzantrag|beantragt (?:\w+ ){0,3}insolvenz|muss insolvenz|vorläufige[rn]? insolvenzverwalter|vorläufige[rn]? sachwalter|antrag auf eröffnung|"
     r"insolvenz angemeldet|vorläufige insolvenzverwaltung", "mittel"),
]
MONAT = "Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember"
DATUM_RE = re.compile(
    r"(?:insolvenzantrag|antrag|eröffnet|eröffnung|insolvenz angemeldet)[^.\n]{0,90}?"
    r"((?:am\s+)?\d{1,2}\.\s?(?:" + MONAT + r")\s+\d{4}|(?:im|Anfang|Mitte|Ende)\s+(?:" + MONAT + r")\s+\d{4}|"
    r"\d{1,2}\.\d{1,2}\.\d{4})", re.I)
_DATUM = (r"((?:am\s+)?\d{1,2}\.\s?(?:" + MONAT + r")\s+\d{4}|(?:im|Anfang|Mitte|Ende)\s+(?:" + MONAT
          + r")\s+\d{4}|\d{1,2}\.\d{1,2}\.\d{4})")
DATUM_VOR_RE = re.compile(
    _DATUM + r"[^.\n]{0,60}?(?:insolvenzantrag|insolvenz angemeldet|insolvenzverfahren eröffnet|eröffnet)", re.I)
MAIL_RE = re.compile(r"[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+")
TEL_RE = re.compile(r"(?:Tel(?:efon)?\.?|Fon|T)\s*[:.]?\s*(\+?[\d(][\d\s/()\-]{7,20}\d)")
WEB_RE = re.compile(r"\bwww\.[\w\-]+(?:\.[\w\-]+)+", re.I)


@dataclass
class Insolvenz:
    quelle_id: str
    url: str
    titel: str
    datum_meldung: str
    firma: str = ""
    status: str = ""
    verwertung: str = ""  # Chance, dass Maschinen auf den Markt kommen
    datum_verfahren: str = ""
    verwalter: str = ""
    kanzlei: str = ""
    kontakt: str = ""
    wahrscheinlichkeit: int = 0  # Prozent, Schätzung aus Stichworten
    gruppen: list[str] = field(default_factory=list)
    indizien: list[str] = field(default_factory=list)
    auszug: str = ""
    meldungen: int = 1


def _text(rendered: str) -> str:
    return BeautifulSoup(rendered, "lxml").get_text("\n", strip=True)


def probability(titel: str, text: str, indizien: dict) -> tuple[int, list[str], list[str]]:
    """Schätzt aus Stichworten, wie wahrscheinlich der Betrieb solche Maschinen einsetzt."""
    low, tlow = text.lower(), titel.lower()
    miss, groups, found = 1.0, [], []
    for gruppe, stufen in indizien.items():
        for stufe, terms in stufen.items():
            for term in terms:
                t = term.lower()
                if t in low or t in tlow:
                    w = GEWICHT.get(stufe, 0.1) * (1.3 if t in tlow else 1.0)
                    miss *= 1 - min(w, 0.8)
                    found.append(term)
                    if gruppe != "allgemein" and gruppe not in groups and stufe != "schwach":
                        groups.append(gruppe)
    return min(95, 5 * round((1 - miss) * 20)), groups, found


def find_status(titel: str, text: str) -> tuple[str, str]:
    for scope in (titel.lower(), text.lower()):
        for name, pat, chance in STATUS:
            if re.search(pat, scope):
                return name, chance
    return "unklar", "unklar"


def find_verwalter(text: str) -> str:
    for rx in VERWALTER_RES:
        for m in rx.finditer(text):
            name = re.sub(r"\s+", " ", m.group(1)).strip()
            name = re.sub(r"\s+\w*(?:ung|ungen|keit|heit|schaft|tion|tionen|nisse?)$", "", name)
            if not KEIN_NAME.match(name) and len(name.split()) >= 2:
                return name
    return ""


def find_kanzlei(text: str, verwalter: str) -> str:
    if verwalter:
        m = re.search(re.escape(verwalter) + r"\s*\(([^)]{3,60})\)", text)
        if m and not re.search(r"\d{4}|Foto|Bild", m.group(1)):
            return m.group(1).strip()
        m = re.search(re.escape(verwalter) + r"\s+von\s+(?:der\s+)?(?:Kanzlei\s+)?([A-ZÄÖÜ][\w&.\- ]{2,50}?)(?=\s+(?:in|zum|zur|als|bestellt|ist|hat|wurde)\b|[,.;)\n])", text)
        if m:
            return re.sub(r"\s+(?:und|erzielt|sieht|prüft|begleitet|findet)\b.*$", "", m.group(1)).strip()
    low = text.lower()
    known = [(low.count(k.lower()), k) for k in KANZLEIEN if re.search(r"(?<!\w)" + re.escape(k.lower()) + r"(?!\w)", low)]
    if known:
        return max(known)[1]
    for rx in KANZLEI_RES:
        m = rx.search(text)
        if m:
            return re.sub(r"\s+(?:und|erzielt|sieht|prüft|begleitet|findet)\b.*$", "", m.group(1)).strip()
    return ""


def find_firma(titel: str, text: str) -> str:
    counts: dict[str, int] = {}
    for src, weight in ((titel, 3), (text[:1500], 1)):
        for m in FIRMA_RE.finditer(src):
            name = re.sub(r"\s+", " ", m.group(1)).strip()
            name = FIRMA_VORSPANN.sub("", name)
            if name and not BERATER.search(name) and len(name) > 5:
                counts[name] = counts.get(name, 0) + weight
    return max(counts, key=lambda n: (counts[n], -len(n))) if counts else ""


def find_kontakt(text: str, kanzlei: str) -> str:
    tail = text[-1800:]
    parts = list(dict.fromkeys(MAIL_RE.findall(tail)))[:2]
    parts += [re.sub(r"\s+", " ", t) for t in dict.fromkeys(TEL_RE.findall(tail))][:1]
    webs = list(dict.fromkeys(w.lower() for w in WEB_RE.findall(tail)))
    if kanzlei:  # Website der Kanzlei bevorzugen
        key = re.sub(r"[^a-z]", "", kanzlei.lower())[:5]
        webs.sort(key=lambda w: key not in re.sub(r"[^a-z]", "", w))
    return " · ".join(parts + webs[:1])


def analyse(post: dict, indizien: dict, min_prozent: int) -> Insolvenz | None:
    titel = html.unescape(BeautifulSoup(post["title"]["rendered"], "lxml").get_text())
    text = _text(post["content"]["rendered"])
    if not re.search(r"insolvenz|eigenverwaltung|schutzschirm", f"{titel} {text}", re.I):
        return None
    p, gruppen, found = probability(titel, text, indizien)
    if p < min_prozent:
        return None
    status, chance = find_status(titel, text)
    verwalter = find_verwalter(text)
    kanzlei = find_kanzlei(text, verwalter)
    d = DATUM_RE.search(text) or DATUM_VOR_RE.search(text)
    return Insolvenz(
        quelle_id=str(post["id"]), url=post["link"], titel=titel.strip(),
        datum_meldung=post["date"][:10], firma=find_firma(titel, text), status=status,
        verwertung=chance, datum_verfahren=re.sub(r"^am\s+", "", d.group(1)) if d else "",
        verwalter=verwalter, kanzlei=kanzlei, kontakt=find_kontakt(text, kanzlei),
        wahrscheinlichkeit=p, gruppen=gruppen, indizien=found, auszug=text[:400],
    )


def _firm_key(e: Insolvenz) -> str:
    base = re.sub(RECHTSFORM, "", e.firma or e.titel)
    return re.sub(r"[^a-z0-9]", "", base.lower())[:24]


def merge(entries: list[Insolvenz]) -> list[Insolvenz]:
    """Mehrere Meldungen zur selben Firma: die jüngste zählt, ältere füllen Lücken."""
    by: dict[str, Insolvenz] = {}
    for e in sorted(entries, key=lambda e: e.datum_meldung, reverse=True):
        cur = by.setdefault(_firm_key(e), e)
        if cur is e:
            continue
        cur.meldungen += 1
        for f in ("verwalter", "kanzlei", "kontakt", "datum_verfahren"):
            if not getattr(cur, f):
                setattr(cur, f, getattr(e, f))
        cur.wahrscheinlichkeit = max(cur.wahrscheinlichkeit, e.wahrscheinlichkeit)
    out = sorted(by.values(), key=lambda e: e.datum_meldung, reverse=True)
    return sorted(out, key=lambda e: -e.wahrscheinlichkeit)


def fetch(fetcher: Fetcher, cfg: dict) -> tuple[list[Insolvenz], list[SourceLog]]:
    since = (dt.date.today() - dt.timedelta(days=30 * cfg.get("monate", 18))).isoformat() + "T00:00:00"
    urls = [(f"aktuelle Meldungen, Seite {n}", f"{API}?per_page=100&page={n}&after={since}&_fields={FIELDS}")
            for n in range(1, cfg.get("seiten_aktuell", 3) + 1)]
    urls += [(f"Suche: {term}", f"{API}?search={quote_plus(term)}&per_page=50&after={since}&_fields={FIELDS}")
             for term in cfg.get("suchbegriffe", [])]
    posts: dict[int, dict] = {}
    logs = []
    for label, url in urls:
        log = SourceLog("indat", label, url)
        try:
            raw = fetcher.get(url)
            items = json.loads(raw) if raw else []
            if not isinstance(items, list):
                items = []
            log.seiten, log.roh = 1, len(items)
            for p in items:
                posts[p["id"]] = p
        except Exception as e:  # Netzwerk- oder Formatfehler: Quelle protokollieren, Lauf fortsetzen
            log.fehler = str(e)[:200]
        logs.append(log)
    found = [x for x in (analyse(p, cfg.get("indizien", {}), cfg.get("min_prozent", 30))
                         for p in posts.values()) if x and (x.firma or x.wahrscheinlichkeit >= 50)]
    return merge(found), logs


def anfrage(e: Insolvenz, absender: dict) -> str:
    """Entwurf einer Anfrage an die Insolvenzverwaltung (wird nicht versendet)."""
    anrede = f"Sehr geehrte Damen und Herren{', z. Hd. ' + e.verwalter if e.verwalter else ''},"
    return (
        f"{anrede}\n\nwir haben erfahren, dass Sie im Verfahren {e.firma or e.titel} tätig sind. "
        "Wir suchen gebrauchte Produktionsmaschinen (Stanzautomaten, Drehautomaten, "
        "Spritzgießmaschinen) und sind an einer Übernahme einzelner Maschinen oder des "
        "Maschinenparks interessiert.\n\nBitte teilen Sie uns mit:\n"
        "- ob eine Verwertung des Anlagevermögens geplant ist und über wen sie läuft\n"
        "- ob eine Maschinenliste oder ein Gutachten vorliegt\n"
        "- welche Fristen und Besichtigungstermine gelten\n\n"
        f"Vielen Dank und freundliche Grüße\n{absender.get('absender', '')}\n"
        f"{absender.get('firma', '')}\n{absender.get('email', '')}"
    )
