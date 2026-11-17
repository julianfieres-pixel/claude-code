"""Tests mit kleinen, nachgebauten HTML-Ausschnitten (keine Netzwerkzugriffe)."""
from pathlib import Path

import pytest

from radar import extract as ex
from radar import profiles
from radar.models import Listing
from radar.sources import netbid
from radar.sources.maschinensucher import Maschinensucher
from radar.sources.resale import Resale
from radar.sources.surplusrecord import SurplusRecord

CFG = profiles.load(Path(__file__).resolve().parent.parent / "config" / "maschinen.yaml")


@pytest.mark.parametrize(
    "text,expected",
    [
        ("12.999 €", (12999.0, "EUR")),
        ("€29.500", (29500.0, "EUR")),
        ("$29,500", (29500.0, "USD")),
        ("EUR 1.250,00", (1250.0, "EUR")),
        ("$49,500.00 USD", (49500.0, "USD")),
        ("Preisinfo", (None, "")),
    ],
)
def test_parse_price(text, expected):
    assert ex.parse_price(text) == expected


def test_parse_year_and_hours():
    assert ex.parse_year("Baujahr 1996, 400 V") == 1996
    assert ex.parse_year("Typ 2540 x 1661") is None
    assert ex.parse_hours("Betriebsstunden: 51.573 h") == 51573


@pytest.mark.parametrize(
    "text,kn",
    [
        ("Nennkraft: 500 kN", 500),
        ("max. Druck: 200 [kN] (20 [T])", 200),
        ("Schließkraft 1.000 kN", 1000),
        ("Presskraft: 30 t", 300),
        ("20 Ton, Bruderer #BBU-190/85, high speed press", 200),
        ("Gewicht 3100 kg", None),
    ],
)
def test_parse_force(text, kn):
    assert ex.parse_force_kn(text) == kn


@pytest.mark.parametrize(
    "brand,model,kn",
    [
        ("Bruderer", "BSTA 25 EL", 250),
        ("BRUDERER", "BSTA 510-150", 510),
        ("Arburg", "Allrounder 370 S 600-100", 600),
        ("Arburg", "470 E 1000-290", 1000),
        ("Engel", "victory 330/80", None),
    ],
)
def test_force_from_model(brand, model, kn):
    assert ex.force_from_model(brand, model) == kn


def test_strip_watermarks():
    lines = ["Nennkraft 250 kN", "Hnjcufeyrf Aao T Iyfjw", "Ctiwss7sqs", "Schallschutzkabine"]
    assert ex.strip_watermarks(lines) == ["Nennkraft 250 kN", "Schallschutzkabine"]


MS_HTML = """
<section class="grid-card" id="section-14384134-1">
 <section class="grid-image"><a href="/bruderer-bsta+200m/i-14384134">Bild</a></section>
 <section class="grid-body">
  <div class="trader-location"><div class="country-name">
   <img title="Deutschland" alt="Deutschland"> Villingen-Schwenningen</div></div>
  <h2><span class="text-gray-100">Stanzautomat</span> <span class="me-1">BRUDERER</span> BSTA 200M</h2>
  <div class="text-danger h4"><span>12.999 €</span></div> VB zzgl. MwSt.
 </section>
 <section class="grid-footer"><div class="description-preview">
  Zustand: <b>gut (gebraucht)</b>, Baujahr: <b>1996</b>, Betriebsstunden: <b>51.573 h</b>,
  max. Druck: 200 [kN]. Baujahr 1999 laut Text.</div></section>
</section>"""


def test_maschinensucher_parse():
    (l,) = Maschinensucher(CFG.brands).parse(MS_HTML)
    assert (l.quelle_id, l.hersteller, l.modell, l.kategorie) == (
        "14384134", "BRUDERER", "BSTA 200M", "Stanzautomat")
    assert l.url == "https://www.maschinensucher.de/bruderer-bsta+200m/i-14384134"
    assert (l.baujahr, l.betriebsstunden, l.kraft_kn) == (1996, 51573, 200)
    assert (l.preis, l.waehrung, l.preis_hinweis) == (12999.0, "EUR", "VB zzgl. MwSt.")
    assert (l.ort, l.land, l.zustand) == ("Villingen-Schwenningen", "Deutschland", "gut (gebraucht)")


def test_maschinensucher_urls():
    s = Maschinensucher(CFG.brands)
    assert s.url_for("/Mehrspindler/ci-1137", 2) == "https://www.maschinensucher.de/Mehrspindler/ci-1137?page=2"
    assert s.url_for("Bihler") == "https://www.maschinensucher.de/mss/bihler"


RESALE_HTML = """
<div class="rsk-card-wrap"><a class="card-link-wrap" href="/citizen-l20/Nr-1">
 <article class="product-card" data-id="1">
  <h3 class="card-title" title="Citizen Cincom L20"><span>Citizen Cincom L20</span></h3>
  <div class="card-category"><span class="cat-level">Drehmaschinen</span>
   <span class="cat-level">Langdrehautomaten</span></div>
  <p class="card-meta">2012 · Deutschland</p><p class="card-desc">CNC Langdreher</p>
  <div class="card-footer"><span class="card-price">€29.500</span></div>
 </article></a></div>"""


def test_resale_parse():
    (l,) = Resale(CFG.brands).parse(RESALE_HTML)
    assert (l.hersteller, l.modell, l.baujahr, l.land) == ("Citizen", "Cincom L20", 2012, "Deutschland")
    assert (l.preis, l.waehrung, l.kategorie) == (29500.0, "EUR", "Langdrehautomaten")


SR_HTML = """
<div class="listing" id="listing-seq-id-176380">
 <h3 class="listing-title"><a href="/listing/x-176380/">20 Ton, Bruderer #BBU-190/85, high speed press, 1983</a></h3>
 <div class="listing-data listing-category"><span class="listing-value">High Speed and Automatic Presses</span></div>
 <div class="listing-data listing-data-seller"><span class="listing-value">D &amp; D Industries Inc</span></div>
 <div class="listing-data listing-location"><span class="listing-value">Monclova, OH</span></div>
 <div class="listing-data listing-data-mfr"><span class="listing-value">Bruderer</span></div>
 <div class="listing-data listing-data-model"><span class="listing-value">BBU-190/85</span></div>
 <div class="listing-data listing-data-year"><span class="listing-value">1983</span></div>
 <span class="price-conversion-text">$29,500</span>
</div>"""


def test_surplusrecord_parse():
    (l,) = SurplusRecord(CFG.brands).parse(SR_HTML)
    assert (l.quelle_id, l.hersteller, l.baujahr, l.land) == ("176380", "Bruderer", 1983, "USA")
    assert (l.preis, l.waehrung, l.kraft_kn) == (29500.0, "USD", 200)
    assert l.url == "https://surplusrecord.com/listing/x-176380/"


NETBID_HTML = """
<ul><li class="auctions-list-item"><a href="/en/auctions/1-2-punching"></a>
 <span>Insolvency Auction</span><span>#18444</span>
 <span>2 Online auctions of tools, punching machines and peripherals</span>
 <span>Musterstr. 1</span><span>58511 Lüdenscheid</span><span>18. Nov 2026, 10:00 AM</span>
 <span>160 Positions</span><a href="/en/auctions/1-2-punching">View</a></li></ul>"""


def test_netbid_parse():
    (a,) = netbid.parse(NETBID_HTML)
    assert (a.quelle_id, a.art, a.positionen) == ("18444", "Insolvency Auction", 160)
    assert a.titel.startswith("2 Online auctions") and a.ort == "58511 Lüdenscheid"
    assert a.termin.startswith("18. Nov 2026")


def _listing(**kw) -> Listing:
    base = dict(quelle="t", quelle_id="1", url="u", titel="")
    return Listing(**{**base, **kw})


def test_classify_and_assess():
    ok = _listing(titel="Stanzautomat Bruderer BSTA 510-125", kategorie="Stanzautomat",
                  hersteller="Bruderer", modell="BSTA 510-125", baujahr=2015)
    assert profiles.classify(ok, CFG)
    assert (ok.profil_id, ok.kraft_kn, ok.passung) == ("stanzautomat", 510, profiles.PASST)

    old = _listing(titel="Stanzautomat Bruderer BSTA 25", kategorie="Stanzautomat",
                   hersteller="Bruderer", modell="BSTA 25", baujahr=1985)
    assert profiles.classify(old, CFG) and old.passung == profiles.AUSSERHALB

    unknown = _listing(titel="Spritzgießmaschine Engel victory", kategorie="Spritzgießmaschine")
    assert profiles.classify(unknown, CFG) and unknown.passung == profiles.PRUEFEN
    assert unknown.hersteller == "Engel"

    noise = _listing(titel="Walzenvorschub Bruderer BBV 190", kategorie="Vorschub")
    assert not profiles.classify(noise, CFG)


def test_mark_duplicates():
    a = _listing(quelle="a", hersteller="Index", modell="MS 22C", baujahr=2015)
    b = _listing(quelle="b", quelle_id="9", hersteller="INDEX", modell="MS22C", baujahr=2015)
    profiles.mark_duplicates([a, b])
    assert a.moegliche_dublette == "" and b.moegliche_dublette == "a:1"
