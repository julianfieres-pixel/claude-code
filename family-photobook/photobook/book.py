"""Output: HTML photobook (print to PDF from the browser), month folders, print list, reports."""
from __future__ import annotations

import csv
import html
import shutil
from pathlib import Path

from .scan import Photo, load_oriented

MONTHS_DE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August",
             "September", "Oktober", "November", "Dezember"]


def month_title(key: str) -> str:
    if key == "unbekannt":
        return "Ohne Datum"
    y, m = key.split("-")
    return f"{MONTHS_DE[int(m) - 1]} {y}"


def date_de(p: Photo) -> str:
    if not p.taken:
        return ""
    d = f"{p.taken.day}. {MONTHS_DE[p.taken.month - 1]} {p.taken.year}"
    return d + (" (ungefähr)" if p.date_source == "file" else "")


def caption(p: Photo) -> str:
    parts = []
    if p.place:
        parts.append(f"📍 {p.place}")
    parts.append(date_de(p))
    if p.people:
        parts.append(" · ".join(p.people))
    return " — ".join(x for x in parts if x)


def export_name(p: Photo, idx: int) -> str:
    stamp = p.taken.strftime("%Y-%m-%d_%H%M") if p.taken else "undatiert"
    return f"{stamp}_{idx:02d}{Path(p.path).suffix.lower()}"


def make_thumb(p: Photo, target: Path, max_side: int = 1400) -> None:
    if target.exists():
        return
    img = load_oriented(p.path, max_side).convert("RGB")
    img.save(target, "JPEG", quality=85, optimize=True)


CSS = """
:root{--bg:#faf8f5;--fg:#2b2622;--muted:#7a716a;--accent:#c2643a;--card:#fff;--line:#e8e2db}
@media (prefers-color-scheme:dark){:root{--bg:#1b1917;--fg:#eee8e2;--muted:#a59b92;--accent:#e08a5f;--card:#262320;--line:#3a3531}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 Georgia,'Times New Roman',serif}
header.cover{min-height:70vh;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;padding:48px 16px}
.cover h1{font-size:clamp(2.2rem,6vw,4rem);margin:0 0 8px;font-weight:normal;letter-spacing:.02em}
.cover p{color:var(--muted);margin:4px}
nav{max-width:1100px;margin:0 auto 32px;padding:0 16px;display:flex;flex-wrap:wrap;gap:8px;justify-content:center}
nav a{color:var(--fg);text-decoration:none;border:1px solid var(--line);border-radius:999px;padding:4px 12px;font:14px system-ui,sans-serif}
section.month{max-width:1100px;margin:0 auto;padding:32px 16px 48px;break-before:page}
.month h2{font-size:2rem;font-weight:normal;border-bottom:1px solid var(--line);padding-bottom:8px;margin-bottom:4px}
.month .meta{color:var(--muted);font:14px system-ui,sans-serif;margin-bottom:24px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));grid-auto-flow:dense;gap:16px;align-items:start}
figure{margin:0;background:var(--card);border:1px solid var(--line);border-radius:6px;overflow:hidden;break-inside:avoid}
figure img{width:100%;height:240px;object-fit:cover;object-position:center 30%;display:block}
figure.print{grid-column:span 2;border-color:var(--accent);box-shadow:0 0 0 2px var(--accent)}
figure.print img{height:420px}
figcaption{padding:8px 10px;font:13px/1.4 system-ui,sans-serif;color:var(--muted)}
.badge{display:inline-block;background:var(--accent);color:#fff;border-radius:4px;padding:1px 6px;font-size:12px;margin-right:6px}
.printlist{max-width:1100px;margin:0 auto;padding:32px 16px 64px;break-before:page}
.printlist table{width:100%;border-collapse:collapse;font:14px system-ui,sans-serif}
.printlist td,.printlist th{border-bottom:1px solid var(--line);padding:6px;text-align:left;vertical-align:top}
.printlist img{width:96px;height:72px;object-fit:cover;border-radius:4px}
@media (max-width:560px){figure.print{grid-column:span 1}figure.print img{height:260px}}
@media print{nav{display:none}body{background:#fff;color:#000}figure img{height:auto;max-height:9cm}}
"""


def write_book(out: Path, months: dict[str, dict], title: str, stats: dict) -> Path:
    thumbs = out / "thumbs"
    thumbs.mkdir(parents=True, exist_ok=True)
    esc = html.escape
    parts = [f"<!doctype html><html lang='de'><head><meta charset='utf-8'>"
             f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
             f"<title>{esc(title)}</title><style>{CSS}</style></head><body>"]
    keys = list(months)
    span = f"{month_title(keys[0])} – {month_title(keys[-1])}" if keys else ""
    parts.append(f"<header class='cover'><h1>{esc(title)}</h1><p>{esc(span)}</p>"
                 f"<p>{stats['selected']} ausgewählte Fotos aus {stats['unique']} "
                 f"(nach Entfernen von {stats['duplicates']} Duplikaten)</p></header>")
    parts.append("<nav>" + "".join(f"<a href='#m{k}'>{esc(month_title(k))}</a>" for k in keys)
                 + "<a href='#druck'>Druckliste</a></nav>")

    print_rows = []
    for key, data in months.items():
        top, prints = data["top"], data["print"]
        parts.append(f"<section class='month' id='m{key}'><h2>{esc(month_title(key))}</h2>"
                     f"<div class='meta'>{len(top)} von {data['total']} Fotos · "
                     f"Druckempfehlung: {len(prints)}</div><div class='grid'>")
        for i, p in enumerate(top, 1):
            thumb = thumbs / f"{key}_{i:02d}.jpg"
            make_thumb(p, thumb)
            is_print = p in prints
            src = esc(thumb.relative_to(out).as_posix())
            badge = "<span class='badge'>Drucken</span>" if is_print else ""
            parts.append(f"<figure class='{'print' if is_print else ''}'>"
                         f"<a href='{esc(Path(p.path).resolve().as_uri())}'><img loading='lazy' src='{src}' alt=''></a>"
                         f"<figcaption>{badge}{esc(caption(p))}</figcaption></figure>")
            if is_print:
                print_rows.append((key, p, src))
        parts.append("</div></section>")

    parts.append("<section class='printlist' id='druck'><h2>Druckliste</h2><table>"
                 "<tr><th>Monat</th><th></th><th>Foto</th><th>Ort &amp; Datum</th></tr>")
    for key, p, src in print_rows:
        parts.append(f"<tr><td>{esc(month_title(key))}</td><td><img src='{src}' alt=''></td>"
                     f"<td>{esc(Path(p.path).name)}<br>{p.width}×{p.height}</td><td>{esc(caption(p))}</td></tr>")
    parts.append("</table></section></body></html>")

    index = out / "fotobuch.html"
    index.write_text("".join(parts), encoding="utf-8")
    return index


def export_files(out: Path, months: dict[str, dict], copy: bool = True) -> None:
    """auswahl/<YYYY-MM>/... (top N) and drucken/<YYYY-MM>/... (print picks)."""
    rows = []
    for key, data in months.items():
        for folder, items in (("auswahl", data["top"]), ("drucken", data["print"])):
            d = out / folder / key
            d.mkdir(parents=True, exist_ok=True)
            for i, p in enumerate(items, 1):
                if copy:
                    target = d / export_name(p, i)
                    if not target.exists():
                        shutil.copy2(p.path, target)
        for p in data["top"]:
            rows.append([key, p.path, p.taken.isoformat() if p.taken else "", p.date_source, p.place,
                         ";".join(p.people), p.score, "ja" if p in data["print"] else ""])
    with open(out / "auswahl.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["monat", "datei", "aufgenommen", "datumsquelle", "ort", "personen", "score", "drucken"])
        w.writerows(rows)


def write_duplicates(out: Path, pairs) -> None:
    with open(out / "duplikate.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["duplikat", "behalten"])
        for dup, keep in pairs:
            w.writerow([dup.path, keep.path])
