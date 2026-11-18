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

Ergebnis: das Dashboard `out/dashboard.html` (im Browser öffnen, kein Server nötig),
die Excel-Datei `out/maschinenradar_<Datum>.xlsx` und der Bestand `out/radar.sqlite`.

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
| Dashboard | `radar/dashboard.py`, `radar/templates/dashboard.html` | Eine HTML-Datei mit eingebetteten Daten: Marktlage, Aktionsliste, Angebote mit Filtern, Anfragen, Auktionen |
| Bericht | `radar/report.py` | Excel mit den Blättern Aktionsliste, Anfragen, Lage, Angebote, Auktionen, Lauf |

## Quellen

| Quelle | Zugriff | Einschränkung |
|---|---|---|
| Maschinensucher | Kategorieseiten und Stichwortseiten | Freie Suche ist per robots.txt gesperrt |
| Resale | Stichwortseiten | Nur die erste Ergebnisseite (maximal 50 Angebote) |
| Surplus Record (USA) | Kategorieseiten je Hersteller | 10 s Pause je Abruf, maximal 3 Seiten je Kategorie |
| INDat | Offene Schnittstelle der Meldungen | Nur Verfahren mit Pressemeldung einer Kanzlei |
| NetBid | Auktionskalender | Abgleich nur über den Auktionstitel, nicht über Einzelpositionen |

Nicht angebunden: Machinio (blockt automatisierte Zugriffe) und die Suche von
gebrauchtmaschinen.de (per robots.txt gesperrt).

## Bedarf und Vertraulichkeit

`config/maschinen.yaml` enthält nur generische Maschinenklassen und wird versioniert.
Stückzahlen stehen in `config/bedarf.local.yaml`, die per `.gitignore` ausgeschlossen ist
(Vorlage: `config/bedarf.beispiel.yaml`). Liegt die Datei vor, zeigt das Dashboard je
Maschinenart die Bedarfsdeckung: benötigte Stückzahl gegen passende Angebote.

Spritzgießmaschinen werden nach Holmklasse eingeordnet (lichte Holmweite 370 bis 720 mm).
Bei Arburg steht die Klasse in der Typbezeichnung (Allrounder 470 A), bei anderen Herstellern
wird sie aus der Schließkraft geschätzt. `wunschmodelle` im Profil geben 10 Punkte Bonus
(z. B. Star SR-20/SB-20, Winema Flex-Master, Arburg Allrounder).

## Karte

Die Ansicht „Karte" zeigt je Land einen Kreis, dessen Fläche der Zahl der Angebote entspricht,
wahlweise für Europa oder die Welt. Die Quellen nennen den Standort nur als Text, deshalb
arbeitet die Karte auf Länderebene; Wotol nennt nur die Weltregion und erscheint in der Liste
neben der Karte. Die Umrisse stammen aus Natural Earth (gemeinfrei) und liegen in
`radar/templates/world.json`; `tools/build_world.py` erzeugt die Datei neu.

## Passung

- **passt**: Baujahr und Kraft liegen im Zielbereich der Spezifikation.
- **prüfen**: Das Angebot gehört zur Maschinenart, aber Baujahr oder Kraft fehlen im Inserat.
- **außerhalb Spez.**: Baujahr zu alt oder Kraft außerhalb des Bereichs.

Liegt das Baujahr in der Zukunft, gilt das Angebot als „prüfen": Händler tragen bei Bestell-
und Überholmaschinen das Lieferjahr ein. Solche Angebote erhalten keine Alterspunkte.

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

## Insolvenz-Monitor

`radar/insolvency.py` liest Meldungen der Insolvenzkanzleien bei INDat (der-indat.de) über
deren offene Schnittstelle: die jüngsten 300 Meldungen und gezielte Suchen nach
Branchenbegriffen, jeweils für die letzten 18 Monate. Je Firma entstehen:

| Feld | Herkunft |
|---|---|
| Wahrscheinlichkeit | Schätzung aus Stichworten der Meldung (stark 55 %, mittel 30 %, schwach 12 %, kombiniert); kein statistisch geeichter Wert |
| Status | Antrag, Verfahren eröffnet, Eigenverwaltung, Investorensuche, verkauft oder Stilllegung, aus Titel und Text |
| Chance Verwertung | hoch bei Stilllegung, gering bei Verkauf oder Eigenverwaltung, sonst mittel |
| Datum | Datum der Meldung und, wenn im Text genannt, Datum von Antrag oder Eröffnung |
| Verwalter, Kanzlei, Kontakt | aus dem Meldungstext; der Kontakt kann die Pressestelle oder ein Berater sein |

Mehrere Meldungen zur selben Firma werden zusammengeführt, die jüngste bestimmt den Status.
Auf die Aktionsliste kommen Firmen ab 50 % Wahrscheinlichkeit, deren Maschinen noch auf den
Markt kommen können. Stichworte und Schwellen stehen unter `insolvenzen` in der Konfiguration.

Nicht abgefragt wird das amtliche Portal insolvenzbekanntmachungen.de: Es untersagt
automatisierte Zugriffe per robots.txt. Kleine Verfahren ohne Pressemeldung fehlen deshalb.

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
