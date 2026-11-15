"""Command line entry point: python -m photobook --input FOTOS --people PERSONEN --output FOTOBUCH"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from . import book, dedupe, geocode, scoring, select
from .scan import Photo, find_images, load_oriented, read_photo

ANALYSIS_VERSION = 1


def parse_args(argv=None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        prog="photobook",
        description="Familienfotos: Duplikate entfernen, nach Monat sortieren, Top-Fotos pro Monat "
                    "auswählen, Druckempfehlungen und ein HTML-Fotobuch mit Ortsangaben erzeugen.")
    ap.add_argument("--input", "-i", type=Path, required=True, action="append",
                    help="Ordner mit Fotos (mehrfach angebbar, Unterordner werden durchsucht)")
    ap.add_argument("--people", "-p", type=Path,
                    help="Ordner mit Referenzfotos: <people>/<Name>/*.jpg (z. B. Papa, Mama, Leo)")
    ap.add_argument("--output", "-o", type=Path, default=Path("fotobuch"))
    ap.add_argument("--top", type=int, default=25, help="Fotos pro Monat (Standard 25)")
    ap.add_argument("--print-picks", type=int, default=3, help="Druckempfehlungen pro Monat (Standard 3)")
    ap.add_argument("--title", default="Unser Familienjahr")
    ap.add_argument("--from", dest="date_from", help="Nur ab Monat JJJJ-MM")
    ap.add_argument("--to", dest="date_to", help="Nur bis Monat JJJJ-MM")
    ap.add_argument("--weight", action="append", default=[], metavar="NAME=W",
                    help="Gewicht einer Person, z. B. --weight Leo=2 (Standard 1)")
    ap.add_argument("--face-threshold", type=float, default=None,
                    help="Ähnlichkeitsschwelle Gesichtserkennung (Standard 0.363; höher = strenger)")
    ap.add_argument("--allow-without-people", action="store_true",
                    help="Fotos ohne erkannte Familienmitglieder zulassen, wenn ein Monat zu wenige hat")
    ap.add_argument("--no-geocode", action="store_true", help="Keine Ortsnamen online nachschlagen")
    ap.add_argument("--no-copy", action="store_true", help="Keine Kopien in auswahl/ und drucken/ anlegen")
    ap.add_argument("--language", default="de", help="Sprache der Ortsnamen (Standard de)")
    return ap.parse_args(argv)


def log(msg: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def progress(i: int, n: int, label: str) -> None:
    if n and (i == n or i % 50 == 0):
        print(f"  {label}: {i}/{n}", flush=True)


# --- cache -------------------------------------------------------------------------
def load_cache(path: Path) -> dict:
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("version") == ANALYSIS_VERSION:
                return data["items"]
        except (json.JSONDecodeError, KeyError):
            pass
    return {}


def save_cache(path: Path, items: dict) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"version": ANALYSIS_VERSION, "items": items}), encoding="utf-8")
    tmp.replace(path)


def cache_key(f: Path) -> str:
    st = f.stat()
    return f"{f.resolve()}|{st.st_size}|{int(st.st_mtime)}"


def photo_from_cache(d: dict) -> Photo:
    d = dict(d)
    d["taken"] = datetime.fromisoformat(d["taken"]) if d.get("taken") else None
    return Photo(**d)


def photo_to_cache(p: Photo) -> dict:
    d = asdict(p)
    d["taken"] = p.taken.isoformat() if p.taken else None
    for k in ("place", "people", "score", "duplicate_of"):
        d.pop(k)
    return d


# --- pipeline ------------------------------------------------------------------------
def main(argv=None) -> None:
    args = parse_args(argv)
    out: Path = args.output
    (out / ".cache").mkdir(parents=True, exist_ok=True)
    cache_path = out / ".cache" / "analyse.json"
    cache = load_cache(cache_path)
    t0 = time.time()

    # 1) scan
    files = [f for root in args.input for f in find_images(root)]
    if not files:
        sys.exit("Keine Bilder gefunden.")
    log(f"{len(files)} Bilddateien gefunden")
    photos: list[Photo] = []
    keys: dict[str, str] = {}
    for i, f in enumerate(files, 1):
        key = cache_key(f)
        p = photo_from_cache(cache[key]) if key in cache else read_photo(f)
        keys[p.path] = key
        photos.append(p)
        progress(i, len(files), "Metadaten")
    broken = [p for p in photos if p.error]
    photos = [p for p in photos if not p.error]
    if broken:
        log(f"{len(broken)} Dateien konnten nicht gelesen werden (siehe fehler.txt)")
        (out / "fehler.txt").write_text("\n".join(f"{p.path}: {p.error}" for p in broken), encoding="utf-8")

    if args.date_from or args.date_to:
        lo, hi = args.date_from or "0000-00", args.date_to or "9999-99"
        photos = [p for p in photos if lo <= p.month <= hi]

    # 2) exact duplicates (before the expensive analysis)
    pairs = dedupe.exact_duplicates(photos)
    unique = [p for p in photos if p.duplicate_of is None]
    log(f"{len(pairs)} exakte Duplikate, {len(unique)} eindeutige Fotos")

    # 3) faces + quality
    engine = None
    if args.people:
        from .faces import DEFAULT_THRESHOLD, FaceEngine, to_bgr  # lazy: OpenCV only when needed
        engine = FaceEngine(out / ".cache" / "models", args.face_threshold or DEFAULT_THRESHOLD)
        counts = engine.enroll(args.people)
        log("Referenzpersonen: " + ", ".join(f"{k} ({v} Fotos)" for k, v in counts.items()))
        if not engine.people:
            sys.exit("Keine Gesichter in den Referenzfotos gefunden.")
        engine.freeze()
    else:
        log("Kein --people Ordner: Auswahl nur nach Bildqualität (ohne Personenerkennung)")

    import cv2
    import numpy as np

    from .faces import ANALYSIS_MAX_SIDE
    todo = [p for p in unique if p.sharpness == 0.0 or (engine and not p.faces_done)]
    for i, p in enumerate(todo, 1):
        try:
            img = load_oriented(p.path, ANALYSIS_MAX_SIDE)
            rgb = np.asarray(img.convert("RGB"))
            gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
            if engine:
                p.faces = engine.detect_and_embed(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
                p.faces_done = True
            p.sharpness = round(scoring.sharpness(gray, p.faces), 2)
            p.exposure = round(scoring.exposure(gray), 3)
        except Exception as exc:
            p.error = f"Analyse: {exc}"
        cache[keys[p.path]] = photo_to_cache(p)
        if i % 100 == 0:
            save_cache(cache_path, cache)
        progress(i, len(todo), "Analyse")
    for p in photos:  # metadata-only entries (duplicates) are cached too
        cache.setdefault(keys[p.path], photo_to_cache(p))
    save_cache(cache_path, cache)
    unique = [p for p in unique if not p.error]

    # 4) who is in the picture
    if engine:
        for p in unique:
            engine.match(p.faces)
        added = engine.expand_references([p.faces for p in unique])
        for p in unique:
            engine.match(p.faces)
        log("Zusätzliche sichere Referenzen: " + ", ".join(f"{k} +{v}" for k, v in added.items()))
    for p in unique:
        p.people = sorted(f["person"] for f in p.faces if f.get("person"))

    # 5) score + near duplicates
    names = list(engine.people) if engine else []
    person_weights = {n: 1.0 for n in names}
    for w in args.weight:
        name, _, val = w.partition("=")
        person_weights[name] = float(val)
    weights = dict(scoring.DEFAULT_WEIGHTS)
    if not engine:
        weights["people"] = weights["faces"] = 0.0
    for p in unique:
        p.score = scoring.combined_score(p, weights, person_weights)
    near = dedupe.near_duplicates(unique)
    pairs += near
    unique = [p for p in unique if p.duplicate_of is None]
    log(f"{len(near)} weitere fast identische Fotos (Serienbilder, Re-Exporte) aussortiert")

    # 6) select per month
    months = {}
    for key, items in select.group_by_month(unique).items():
        eligible = [p for p in items if p.people] if engine else items
        if engine and args.allow_without_people and len(eligible) < args.top:
            extra = sorted((p for p in items if not p.people), key=lambda p: -p.score)
            eligible += extra[: args.top - len(eligible)]
        if not eligible:
            continue
        top = select.pick_top(eligible, args.top)
        months[key] = {"top": top, "print": select.pick_print(top, args.print_picks), "total": len(items)}
    log(f"{len(months)} Monate, {sum(len(m['top']) for m in months.values())} Fotos ausgewählt")

    # 7) places (only for selected photos -> few lookups)
    chosen = [p for m in months.values() for p in m["top"]]
    geocoder = geocode.Geocoder(out / ".cache" / "orte.json", args.language, enabled=not args.no_geocode)
    with_gps = sum(1 for p in chosen if p.lat is not None)
    log(f"Ortsnamen für {with_gps} Fotos mit GPS bestimmen ...")
    geocode.assign_places(chosen, geocoder)

    # 8) output
    book.write_duplicates(out, pairs)
    book.export_files(out, months, copy=not args.no_copy)
    index = book.write_book(out, months, args.title, {
        "selected": len(chosen), "unique": len(unique), "duplicates": len(pairs)})
    log(f"Fertig in {time.time() - t0:.0f}s → {index.resolve()}")
    for key, m in months.items():
        names_ = ", ".join(f"{Path(p.path).name}" + (f" ({p.place})" if p.place else "") for p in m["print"])
        print(f"  {book.month_title(key):>15}: {len(m['top']):>2} Fotos | drucken: {names_}")
