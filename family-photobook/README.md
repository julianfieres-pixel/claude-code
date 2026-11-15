# Familien-Fotobuch

Lokales Tool, das aus allen Familienfotos ein digitales Fotobuch macht:

1. **Duplikate entfernen**: exakt gleiche Dateien (SHA-256) und fast gleiche Fotos (Serienbilder, WhatsApp-Kopien, Re-Exporte; Wahrnehmungs-Hash *dHash*). Behalten wird jeweils das Original mit der besten Qualität.
2. **Nach Monaten sortieren**: Aufnahmedatum aus EXIF, sonst aus dem Dateinamen (`IMG-20240312-WA0001.jpg`, `PXL_2024…`), zuletzt aus dem Dateidatum (im Buch als „ungefähr“ markiert).
3. **Personen erkennen**: du, deine Frau, euer Sohn, über Referenzfotos. Läuft komplett offline mit OpenCV (YuNet + SFace).
4. **Top 20–30 pro Monat** auswählen: Bewertung nach Familienmitgliedern im Bild, Schärfe der Gesichter, Belichtung, Gesichtsgröße und Auflösung. Ähnliche Motive desselben Moments werden übersprungen, damit der Monat abwechslungsreich bleibt.
5. **2–3 Druckempfehlungen pro Monat**: druckfähige Auflösung, möglichst ein Foto mit allen dreien, dazu Fotos von verschiedenen Tagen und Orten.
6. **Ortsangabe unter jedem Foto**: aus den GPS-Daten, z. B. „📍 Englischer Garten, München — 12. März 2026 — Mama · Leo“.

Deine Fotos verlassen den Rechner nicht. Nur für die Ortsnamen werden die GPS-Koordinaten der *ausgewählten* Fotos (auf ca. 100 m gerundet) an OpenStreetMap Nominatim geschickt. Mit `--no-geocode` lässt sich das abschalten.

## Installation (einmalig)

Voraussetzung ist Python 3.10 oder neuer.

```bash
cd family-photobook
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Die zwei Gesichtsmodelle (ca. 40 MB) werden beim ersten Lauf automatisch geladen.

## Vorbereitung: Referenzfotos

Lege pro Person einen Ordner mit **5–15 Fotos** an, auf denen die Person gut und groß zu sehen ist. Ideal ist ein Foto, auf dem *nur* diese Person zu sehen ist. Der Ordnername wird im Fotobuch als Name verwendet.

```
personen/
  Papa/   foto1.jpg foto2.jpg …
  Mama/   …
  Leo/    …   ← beim Kind Fotos aus verschiedenen Altersstufen (z. B. je 2 pro Quartal)
```

Kinder verändern sich schnell. Deshalb übernimmt das Tool zusätzlich sehr sichere Treffer automatisch als weitere Referenzen. Trotzdem gilt: je mehr Altersstufen in den Referenzfotos, desto besser.

## Ausführen

```bash
python -m photobook \
  --input ~/Bilder/Handy --input ~/Bilder/WhatsApp \
  --people ./personen \
  --output ./fotobuch \
  --top 25 --print-picks 3 \
  --weight Leo=2 \
  --title "Leos erstes Jahr"
```

| Option | Bedeutung |
|---|---|
| `--top 25` | Fotos pro Monat (20 oder 30 nach Wunsch) |
| `--print-picks 3` | Druckempfehlungen pro Monat |
| `--weight Leo=2` | Fotos mit dieser Person höher gewichten |
| `--from 2025-01 --to 2025-12` | Zeitraum eingrenzen |
| `--allow-without-people` | Monate mit wenigen Personenfotos mit den besten anderen Fotos auffüllen |
| `--face-threshold 0.42` | strengere Gesichtserkennung (bei Verwechslungen); niedriger = toleranter |
| `--no-geocode` | keine Ortsnamen online abfragen (Koordinaten bleiben sichtbar) |
| `--no-copy` | keine Kopien anlegen, nur Fotobuch und Listen |

Der zweite Lauf ist schnell, weil die Analyse in `fotobuch/.cache/` gespeichert wird. Neue Fotos werden einfach dazugenommen.

## Ergebnis

```
fotobuch/
  fotobuch.html        ← digitales Fotobuch (im Browser öffnen; Drucken → „Als PDF speichern“)
  auswahl/2026-03/…    ← Top-Fotos je Monat (Kopien, nach Datum benannt)
  drucken/2026-03/…    ← die 2–3 Druckempfehlungen je Monat
  auswahl.csv          ← Liste mit Datum, Ort, Personen, Score, Druck ja/nein
  duplikate.csv        ← welche Datei als Duplikat welcher Datei erkannt wurde
```

Im Fotobuch sind die Druckempfehlungen groß und mit „Drucken“ markiert. Am Ende steht eine Druckliste über alle Monate. Ein Klick auf ein Foto öffnet das Original.

## Wie die Bewertung funktioniert

Score 0–100, Gewichte in `photobook/scoring.py` (`DEFAULT_WEIGHTS`):

| Kriterium | Gewicht | Messung |
|---|---|---|
| Familienmitglieder im Bild | 35 % | erkannte Personen × Personengewicht |
| Schärfe | 25 % | Varianz des Laplace-Operators, gemessen auf den Gesichtern |
| Belichtung | 15 % | Helligkeit, Kontrast, ausgefressene oder abgesoffene Bereiche |
| Gesichtsgröße | 15 % | größtes Familiengesicht im Bild |
| Auflösung | 10 % | Megapixel (bis 8 MP) |

Viele fremde Gesichter (z. B. Menschenmengen) geben einen kleinen Abzug.

## Tipps

- **Fotos aus der iCloud/Google Fotos**: zuerst exportieren (Google Takeout bzw. „Originale exportieren“ in Fotos), damit EXIF-Datum und GPS erhalten bleiben. WhatsApp entfernt GPS und meist auch das EXIF-Datum.
- **Videos und RAW-Dateien** werden ignoriert. Unterstützt werden JPG, PNG, HEIC/HEIF, WebP und TIFF.
- **Falsch erkannte Person**: ein paar weitere Referenzfotos ergänzen oder `--face-threshold` erhöhen.

## Tests

```bash
python -m unittest discover -s tests
```

## Quellen

- Gesichtserkennung: OpenCV `FaceDetectorYN` / `FaceRecognizerSF`, Modelle aus dem [OpenCV Zoo](https://github.com/opencv/opencv_zoo) (YuNet, SFace; Schwellwert 0,363 laut [OpenCV-Tutorial](https://docs.opencv.org/4.x/d0/dd4/tutorial_dnn_face.html))
- Duplikate: dHash nach [Neal Krawetz, „Kind of Like That“](https://www.hackerfactor.com/blog/index.php?/archives/529-Kind-of-Like-That.html)
- Schärfe: Varianz des Laplace-Operators nach [Pertuz et al. 2013, „Analysis of focus measure operators for shape-from-focus“](https://doi.org/10.1016/j.patcog.2012.11.011)
- Ortsnamen: [OpenStreetMap Nominatim](https://nominatim.org/release-docs/latest/api/Reverse/) mit [Nutzungsrichtlinie](https://operations.osmfoundation.org/policies/nominatim/) (max. 1 Anfrage/Sekunde, Cache)
