# Unser Fotojahr – Familien-Fotobuch

Zwei Wege, dasselbe Ziel:

| | **Web-App** (`web/`) – für alle | **Kommandozeile** (`photobook/`) – für Technikaffine |
|---|---|---|
| Läuft auf | iPhone, Android, iPad, Mac, PC – im Browser | Computer mit Python |
| Fotos aus | Mediathek/Galerie, Google Fotos, Ordner | Ordnern |
| Personen | „Wer ist wer?“: Gesichtsgruppen antippen | Ordner mit Referenzfotos |
| Ergebnis | Interaktives Fotobuch, Druckfotos teilen/speichern, PDF, ZIP | HTML-Fotobuch, Ordner je Monat, CSV |

Beide arbeiten **lokal**: Die Fotos verlassen das Gerät nicht. Nur für Ortsnamen gehen GPS-Koordinaten (ohne Bild) an OpenStreetMap.

---

## Web-App „Unser Fotojahr“

### Was sie macht
1. **Fotos wählen**: direkt aus der iPhone-Mediathek oder Android-Galerie, aus Google Fotos oder einem Ordner. Weitere Fotos (z. B. vom Handy deiner Frau) lassen sich jederzeit dazunehmen; schon bekannte werden erkannt.
2. **Duplikate entfernen**: exakt gleiche Dateien sowie Serienbilder, WhatsApp-Kopien und Re-Exporte.
3. **Wer ist wer?**: Die App gruppiert ähnliche Gesichter. Ihr tippt jede Gruppe an und wählt Papa, Mama oder euren Sohn (Namen frei wählbar).
4. **Fotobuch**: pro Monat die besten 20/25/30 Fotos, mit einem großen Titelbild und Monatskapiteln. Die 2–3 Druckempfehlungen sind groß dargestellt, darunter stehen Ort und Datum.
5. **Bearbeiten**: Foto antippen, um es zum Drucken zu markieren, aus dem Buch zu nehmen (ein anderes rückt nach), den Ort einzutragen (gilt für den ganzen Tag) oder es zu teilen.
6. **Drucken & Teilen**: Druckfotos auf dem Handy über das Teilen-Menü sichern oder an einen Fotodienst schicken; am Computer als ZIP. Das ganze Buch lässt sich als PDF speichern.

Alles wird im Browser-Speicher des Geräts gespeichert (IndexedDB). Wenn ihr die App schließt und wieder öffnet, ist das Buch noch da.

### Starten
**Live-Version:** https://unser-fotojahr.vercel.app (Vercel-Projekt `unser-fotojahr`, Ordner `family-photobook/web`).

Die App besteht nur aus statischen Dateien und braucht keinen Server mit eigener Logik. Für Handys muss sie über **HTTPS** erreichbar sein:

- **Lokal am Computer testen**: `cd web && python3 -m http.server 8000`, dann http://localhost:8000 öffnen.
- **Fürs Handy veröffentlichen** (kostenlos), z. B. mit [GitHub Pages](https://docs.github.com/de/pages/getting-started-with-github-pages/creating-a-github-pages-site) (Ordner `web/` als Quelle), [Vercel](https://vercel.com/docs/deployments/overview) oder [Netlify Drop](https://app.netlify.com/drop) (den Ordner `web/` hineinziehen). Die Adresse ist öffentlich, die Fotos bleiben trotzdem auf euren Geräten.
- **Auf dem iPhone wie eine App**: Seite in Safari öffnen → Teilen → „Zum Home-Bildschirm“.

### Woher die Fotos kommen – und was mit den Orten passiert

| Quelle | Datum | Ort (GPS) |
|---|---|---|
| iPhone-Mediathek im Browser | ✓ | Safari entfernt GPS seit iOS 16.4 meist ([WebKit-Bug 257534](https://bugs.webkit.org/show_bug.cgi?id=257534), [Bug 263192](https://bugs.webkit.org/show_bug.cgi?id=263192)) |
| Android-Galerie | ✓ | meist ✓ (Android kann Ortsdaten für Apps ohne Berechtigung entfernen) |
| Google Fotos per Picker-API | ✓ | ✗: Downloads enthalten Exif „außer Ort“ ([Google-Doku](https://developers.google.com/photos/picker/guides/media-items)) |
| Google Takeout (Ordner am Computer) | ✓ | ✓ aus den JSON-Begleitdateien |
| iCloud/Mac-Export „unverändertes Original“ (Ordner) | ✓ | ✓ |

Fehlt der Ort, übernimmt die App ihn von einem Foto desselben Tages mit GPS (±4 Std.). Sonst tippt man ihn einmal pro Tag ein. Am vollständigsten sind die Orte, wenn die Fotos einmalig am Computer als Ordner eingelesen werden (Takeout oder Original-Export).

### Google Fotos direkt verbinden (optional)
Ohne Einrichtung zeigt die App eine Anleitung („In Google Fotos auswählen → Herunterladen → hier auswählen“). Für den Direkt-Button:

1. In der [Google Cloud Console](https://console.cloud.google.com/) ein Projekt anlegen und die **Google Photos Picker API** aktivieren.
2. OAuth-Zustimmungsbildschirm einrichten (Typ „Extern“, Status „Testen“) und euch beide als Testnutzer eintragen.
3. Anmeldedaten → OAuth-Client-ID → „Webanwendung“, als „Autorisierte JavaScript-Quelle“ die Adresse der App eintragen (z. B. `https://euer-name.github.io`).
4. Die Client-ID in `web/config.js` bei `googleClientId` eintragen.

Ablauf und Grenzen laut [Picker-API-Doku](https://developers.google.com/photos/picker/guides/get-started-picker): Die Auswahl erfolgt in Google Fotos selbst, und die App sieht nur die gewählten Bilder. Hinweis: Diesen Weg konnte ich ohne Google-Konto nicht live testen. Sollte das Herunterladen der Bilder im Browser blockiert werden (CORS), bleibt der Weg über „Herunterladen“ in der Google-Fotos-App.

### Technik
- Reines HTML/CSS/JavaScript (ES-Module), kein Build-Schritt; Bibliotheken liegen in `web/vendor/` (siehe `vendor/LICENSES.md`).
- Gesichter: [face-api](https://github.com/vladmandic/face-api) (SSD-MobileNet, 68-Punkte-Landmarks, 128-d-Deskriptoren, Mimik für „Lächeln“) auf TensorFlow.js/WebGL.
- Fotodaten: [exifr](https://github.com/MikeKovarik/exifr); HEIC in Chrome/Firefox über [heic2any](https://github.com/alexcorvi/heic2any).
- Bewertung: Familienmitglieder 32 %, Schärfe der Gesichter 23 %, Gesichtsgröße 13 %, Belichtung 12 %, Lächeln 12 %, Auflösung 8 % (`web/js/select.js`).
- Offline-fähig nach dem ersten Aufruf (Service Worker).

### Sicherheit
- `web/vercel.json` setzt Sicherheits-Header: eine Content-Security-Policy, die Verbindungen nur zur eigenen Adresse, zu OpenStreetMap und zu Google Fotos erlaubt, dazu Schutz gegen Einbetten in fremde Seiten. `'unsafe-eval'` ist nur wegen des HEIC-Umwandlers (heic2any) erlaubt.
- Dateinamen, Titel, Namen und Ortsangaben werden nie als HTML eingefügt.
- An OpenStreetMap gehen nur auf drei Nachkommastellen (ca. 100 m) gerundete Koordinaten; abschaltbar in den Einstellungen.
- Die Kommandozeilen-Version prüft die geladenen Gesichtsmodelle per SHA-256.

---

## Kommandozeilen-Version (Python)

Lokales Tool, das aus allen Familienfotos ein digitales Fotobuch macht:

1. **Duplikate entfernen**: exakt gleiche Dateien (SHA-256) und fast gleiche Fotos (Serienbilder, WhatsApp-Kopien, Re-Exporte; Wahrnehmungs-Hash *dHash*). Behalten wird jeweils das Original mit der besten Qualität.
2. **Nach Monaten sortieren**: Aufnahmedatum aus EXIF, sonst aus dem Dateinamen (`IMG-20240312-WA0001.jpg`, `PXL_2024…`), zuletzt aus dem Dateidatum (im Buch als „ungefähr“ markiert).
3. **Personen erkennen**: du, deine Frau, euer Sohn, über Referenzfotos. Läuft komplett offline mit OpenCV (YuNet + SFace).
4. **Top 20–30 pro Monat** auswählen: Bewertung nach Familienmitgliedern im Bild, Schärfe der Gesichter, Belichtung, Gesichtsgröße und Auflösung. Ähnliche Motive desselben Moments werden übersprungen, damit der Monat abwechslungsreich bleibt.
5. **2–3 Druckempfehlungen pro Monat**: druckfähige Auflösung, möglichst ein Foto mit allen dreien, dazu Fotos von verschiedenen Tagen und Orten.
6. **Ortsangabe unter jedem Foto**: aus den GPS-Daten, z. B. „📍 Englischer Garten, München — 12. März 2026 — Mama · Leo“.

Deine Fotos verlassen den Rechner nicht. Nur für die Ortsnamen werden die GPS-Koordinaten der *ausgewählten* Fotos (auf ca. 100 m gerundet) an OpenStreetMap Nominatim geschickt. Mit `--no-geocode` lässt sich das abschalten.

### Installation (einmalig)

Voraussetzung ist Python 3.10 oder neuer.

```bash
cd family-photobook
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Die zwei Gesichtsmodelle (ca. 40 MB) werden beim ersten Lauf automatisch geladen.

### Vorbereitung: Referenzfotos

Lege pro Person einen Ordner mit **5–15 Fotos** an, auf denen die Person gut und groß zu sehen ist. Ideal ist ein Foto, auf dem *nur* diese Person zu sehen ist. Der Ordnername wird im Fotobuch als Name verwendet.

```
personen/
  Papa/   foto1.jpg foto2.jpg …
  Mama/   …
  Leo/    …   ← beim Kind Fotos aus verschiedenen Altersstufen (z. B. je 2 pro Quartal)
```

Kinder verändern sich schnell. Deshalb übernimmt das Tool zusätzlich sehr sichere Treffer automatisch als weitere Referenzen. Trotzdem gilt: je mehr Altersstufen in den Referenzfotos, desto besser.

### Ausführen

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

### Ergebnis

```
fotobuch/
  fotobuch.html        ← digitales Fotobuch (im Browser öffnen; Drucken → „Als PDF speichern“)
  auswahl/2026-03/…    ← Top-Fotos je Monat (Kopien, nach Datum benannt)
  drucken/2026-03/…    ← die 2–3 Druckempfehlungen je Monat
  auswahl.csv          ← Liste mit Datum, Ort, Personen, Score, Druck ja/nein
  duplikate.csv        ← welche Datei als Duplikat welcher Datei erkannt wurde
```

Im Fotobuch sind die Druckempfehlungen groß und mit „Drucken“ markiert. Am Ende steht eine Druckliste über alle Monate. Ein Klick auf ein Foto öffnet das Original.

### Wie die Bewertung funktioniert

Score 0–100, Gewichte in `photobook/scoring.py` (`DEFAULT_WEIGHTS`):

| Kriterium | Gewicht | Messung |
|---|---|---|
| Familienmitglieder im Bild | 35 % | erkannte Personen × Personengewicht |
| Schärfe | 25 % | Varianz des Laplace-Operators, gemessen auf den Gesichtern |
| Belichtung | 15 % | Helligkeit, Kontrast, ausgefressene oder abgesoffene Bereiche |
| Gesichtsgröße | 15 % | größtes Familiengesicht im Bild |
| Auflösung | 10 % | Megapixel (bis 8 MP) |

Viele fremde Gesichter (z. B. Menschenmengen) geben einen kleinen Abzug.

### Tipps

- **Fotos aus der iCloud/Google Fotos**: zuerst exportieren (Google Takeout bzw. „Originale exportieren“ in Fotos), damit EXIF-Datum und GPS erhalten bleiben. WhatsApp entfernt GPS und meist auch das EXIF-Datum.
- **Videos und RAW-Dateien** werden ignoriert. Unterstützt werden JPG, PNG, HEIC/HEIF, WebP und TIFF.
- **Falsch erkannte Person**: ein paar weitere Referenzfotos ergänzen oder `--face-threshold` erhöhen.

### Tests

```bash
python -m unittest discover -s tests
```

## Quellen

- Gesichtserkennung: OpenCV `FaceDetectorYN` / `FaceRecognizerSF`, Modelle aus dem [OpenCV Zoo](https://github.com/opencv/opencv_zoo) (YuNet, SFace; Schwellwert 0,363 laut [OpenCV-Tutorial](https://docs.opencv.org/4.x/d0/dd4/tutorial_dnn_face.html))
- Duplikate: dHash nach [Neal Krawetz, „Kind of Like That“](https://www.hackerfactor.com/blog/index.php?/archives/529-Kind-of-Like-That.html)
- Schärfe: Varianz des Laplace-Operators nach [Pertuz et al. 2013, „Analysis of focus measure operators for shape-from-focus“](https://doi.org/10.1016/j.patcog.2012.11.011)
- Ortsnamen: [OpenStreetMap Nominatim](https://nominatim.org/release-docs/latest/api/Reverse/) mit [Nutzungsrichtlinie](https://operations.osmfoundation.org/policies/nominatim/) (max. 1 Anfrage/Sekunde, Cache)
