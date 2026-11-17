# Maschinenradar – Prototyp

Sammelt Gebrauchtmaschinen-Angebote aus mehreren Quellen, bringt sie in ein
einheitliches Schema und schreibt eine Excel-Datei mit priorisierter Aktionsliste,
Anfrage-Entwürfen und Lagebild. Input ist die
Maschinenliste in `config/maschinen.yaml`.

## Start

```bash
pip install -r requirements.txt
python -m radar                      # alle Quellen, Ergebnis in out/
python -m radar --quellen resale     # nur eine Quelle
python -m radar --cache-stunden 12   # Seiten 12 h aus dem Cache lesen (Entwicklung)
python -m radar --llm                # fehlende Felder per Claude ergänzen (ANTHROPIC_API_KEY nötig)
python -m pytest tests               # Tests ohne Netzwerk
```

Ergebnis: `out/maschinenradar_<Datum>.xlsx` und der Bestand `out/radar.sqlite`.

## Ablauf

```
config/maschinen.yaml ─► Quellen-Adapter ─► Extraktion ─► Zuordnung + Passung
                      ─► Priorisierung ─► Anfrage-Entwürfe ─► SQLite ─► Excel
```

| Schritt | Datei | Inhalt |
|---|---|---|
| Maschinenliste | `config/maschinen.yaml` | Je Maschinenart: Zielspezifikation, Hersteller, Begriffe, Seiten je Quelle |
| Abruf | `radar/http.py` | robots.txt wird beachtet, Pause je Host (Standard 3 s, mehr wenn die Quelle es verlangt) |
| Adapter | `radar/sources/` | Eine Datei je Quelle, liefert Angebote im Schema `Listing` |
| Extraktion | `radar/extract.py` | Preis, Baujahr, Betriebsstunden, Press-/Schließkraft aus Text und Typbezeichnung |
| Zuordnung | `radar/profiles.py` | Angebot → Maschinenart, Passung zur Spezifikation, Dubletten-Hinweis |
| Bestand | `radar/store.py` | „Erstmals gesehen" und „zuletzt gesehen" je Angebot |
| LLM (optional) | `radar/llm.py` | Ergänzt bei Angeboten mit Status „prüfen" fehlende Felder aus dem Inseratstext |
| Priorisierung | `radar/scoring.py` | Punktzahl 0–100 und empfohlene Aktion je Angebot |
| Anfragen | `radar/outreach.py` | Anfrage-Entwurf je Angebot mit offenen Punkten, deutsch oder englisch |
| Bericht | `radar/report.py` | Excel mit den Blättern Aktionsliste, Anfragen, Lage, Angebote, Auktionen, Lauf |

## Quellen

| Quelle | Zugriff | Einschränkung |
|---|---|---|
| Maschinensucher | Kategorieseiten und Stichwortseiten | Freie Suche ist per robots.txt gesperrt |
| Resale | Stichwortseiten | Nur die erste Ergebnisseite (maximal 50 Angebote) |
| Surplus Record (USA) | Kategorieseiten je Hersteller | 10 s Pause je Abruf, maximal 3 Seiten je Kategorie |
| NetBid | Auktionskalender | Abgleich nur über den Auktionstitel, nicht über Einzelpositionen |

Nicht angebunden: Machinio (blockt automatisierte Zugriffe) und die Suche von
gebrauchtmaschinen.de (per robots.txt gesperrt).

## Passung

- **passt**: Baujahr und Kraft liegen im Zielbereich der Spezifikation.
- **prüfen**: Das Angebot gehört zur Maschinenart, aber Baujahr oder Kraft fehlen im Inserat.
- **außerhalb Spez.**: Baujahr zu alt oder Kraft außerhalb des Bereichs.

Die Kraft wird bevorzugt aus der Typbezeichnung gelesen (Bruderer BSTA 25 = 250 kN,
Arburg 370 S 600-100 = 600 kN), sonst aus dem Beschreibungstext.

## Priorisierung

Angebote außerhalb der Spezifikation und mögliche Dubletten kommen nicht auf die
Aktionsliste. Für die übrigen gilt:

| Kriterium | Punkte |
|---|---|
| Spezifikation erfüllt / Daten fehlen | 40 / 15 |
| Baujahr (linear vom Mindest-Baujahr bis heute) | 0–25 |
| Betriebsstunden unter 20.000 / unter 40.000 | 10 / 5 |
| Preis genannt | 10 |
| Standort Europa / außerhalb | 15 / 5 |

Auktionen mit Treffer im Titel stehen wegen der Fristen oben. Je Maschinenart
erscheinen die besten 15 Angebote (einstellbar unter `aktionsliste`).

## Anfragen

Für jedes Angebot der Aktionsliste ohne Preis oder mit fehlenden Daten entsteht ein
Entwurf, der genau die offenen Punkte abfragt. Die Absenderangaben stehen als
Platzhalter unter `anfrage` in der Konfiguration. Der Radar versendet nichts.

## Neue Quelle anbinden

Eine Klasse in `radar/sources/` anlegen, die `url_for()` und `parse()` implementiert,
in `radar/sources/__init__.py` eintragen und in `config/maschinen.yaml` unter `quellen`
die Seiten je Maschinenart ergänzen.

## Grenzen des Prototyps

- Die LLM-Extraktion ist gebaut, aber nur gegen einen Test-Stub geprüft, weil in der
  Entwicklungsumgebung kein API-Schlüssel vorlag. Ohne `--llm` bleibt die Extraktion
  regelbasiert. Lehnt das Modell eine Anfrage ab, wird das Angebot übersprungen.
- Es werden nur Ergebnislisten gelesen, keine Detailseiten. Verkäufer und Kontaktweg
  fehlen deshalb bei den meisten Quellen.
- Die Wechselkurse in der Konfiguration sind Näherungen und müssen gepflegt werden.
- Kein Mailversand und keine Auswertung von Antworten; die Entwürfe müssen von Hand
  verschickt werden.
