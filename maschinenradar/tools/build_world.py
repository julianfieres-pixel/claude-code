"""Erzeugt radar/templates/world.json aus world-atlas (Natural Earth 1:110m, gemeinfrei).

    npm install world-atlas@2.0.2
    python tools/build_world.py node_modules/world-atlas/countries-110m.json

Projektion: Equal Earth. Ausgabe: ein SVG-Pfad für alle Länder und je Land der Schwerpunkt
der größten Teilfläche, beides in Koordinaten der viewBox.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

A1, A2, A3, A4 = 1.340264, -0.081106, 0.000893, 0.003796
W = 1000.0


def project(lon: float, lat: float) -> tuple[float, float]:
    lam, phi = math.radians(lon), math.radians(lat)
    t = math.asin(math.sqrt(3) / 2 * math.sin(phi))
    x = 2 * math.sqrt(3) * lam * math.cos(t) / (3 * (9 * A4 * t**8 + 7 * A3 * t**6 + 3 * A2 * t**2 + A1))
    y = A4 * t**9 + A3 * t**7 + A2 * t**3 + A1 * t
    return x, y


def main(src: str) -> None:
    topo = json.loads(Path(src).read_text())
    sx, sy = topo["transform"]["scale"]
    tx, ty = topo["transform"]["translate"]
    arcs = []
    for arc in topo["arcs"]:
        x = y = 0
        pts = []
        for dx, dy in arc:
            x, y = x + dx, y + dy
            pts.append((x * sx + tx, y * sy + ty))
        arcs.append(pts)

    def ring(idx: list[int]) -> list[tuple[float, float]]:
        out: list[tuple[float, float]] = []
        for i in idx:
            pts = arcs[i] if i >= 0 else arcs[~i][::-1]
            out.extend(pts[1:] if out else pts)
        return out

    xmax = project(180, 0)[0]
    ytop, ybot = project(0, 84)[1], project(0, -58)[1]  # ohne Antarktis
    k = W / (2 * xmax)
    height = (ytop - ybot) * k

    def to_px(p: tuple[float, float]) -> tuple[float, float]:
        x, y = project(*p)
        return (x + xmax) * k, (ytop - y) * k

    def centroid(pts: list[tuple[float, float]]) -> tuple[float, float, float]:
        a = cx = cy = 0.0
        for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):
            f = x0 * y1 - x1 * y0
            a, cx, cy = a + f, cx + (x0 + x1) * f, cy + (y0 + y1) * f
        if abs(a) < 1e-9:
            return pts[0][0], pts[0][1], 0.0
        return cx / (3 * a), cy / (3 * a), abs(a) / 2

    path, points = [], {}
    for g in topo["objects"]["countries"]["geometries"]:
        name = g["properties"]["name"]
        if name == "Antarctica":
            continue
        polys = g["arcs"] if g["type"] == "MultiPolygon" else [g["arcs"]]
        best = (0.0, 0.0, -1.0)
        for poly in polys:
            for n, r in enumerate(poly):
                px = [to_px(p) for p in ring(r)]
                # Ringe über die Datumsgrenze an der Sprungstelle auftrennen, sonst
                # zieht sich eine Linie quer über die Karte
                parts, cur = [], [px[0]]
                for a, b in zip(px, px[1:]):
                    if abs(b[0] - a[0]) > W / 2:
                        parts.append(cur)
                        cur = []
                    cur.append(b)
                parts.append(cur)
                if len(parts) > 1:  # Anfang und Ende gehören zum selben Stück
                    parts[0] = parts.pop() + parts[0]
                for part in parts:
                    if len(part) > 2:
                        path.append("M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in part) + "Z")
                if n == 0:
                    c = centroid(px)
                    if c[2] > best[2]:
                        best = c
        points[name] = [round(best[0], 1), round(best[1], 1)]

    x0, y0 = to_px((-12, 71))
    x1, y1 = to_px((42, 34))
    out = {"w": W, "h": round(height, 1), "pfad": "".join(path), "punkte": points,
           "europa": [round(x0), round(y0), round(x1 - x0), round(y1 - y0)]}
    dst = Path(__file__).resolve().parent.parent / "radar" / "templates" / "world.json"
    dst.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(dst, dst.stat().st_size, "Bytes,", len(points), "Länder")


if __name__ == "__main__":
    main(sys.argv[1])
