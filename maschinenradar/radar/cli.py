"""Kommandozeile: python -m radar --config config/maschinen.yaml --out out"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

import os

from . import dashboard, insolvency, llm, outreach, profiles, report, scoring
from .http import FetchError, Fetcher
from .models import Listing, SourceLog
from .sources import LISTING_SOURCES, netbid
from .store import Store


def run(args: argparse.Namespace) -> int:
    cfg = profiles.load(args.config)
    out = Path(args.out)
    fetcher = Fetcher(delay=args.pause, cache_dir=out / ".cache", cache_hours=args.cache_stunden)
    wanted = set(args.quellen.split(",")) if args.quellen else set(LISTING_SOURCES) | {"netbid", "indat"}
    run_id = dt.datetime.now().strftime("%Y-%m-%d %H:%M")

    found: dict[tuple[str, str], Listing] = {}
    logs: list[SourceLog] = []
    blocked: set[str] = set()
    for name, cls in LISTING_SOURCES.items():
        if name not in wanted:
            continue
        src = cls(brands=cfg.brands, max_pages=args.max_seiten)
        for prof in cfg.profiles:
            for query in prof.quellen.get(name, []):
                if name in blocked:
                    continue
                print(f"[{name}] {query} ...", end=" ", flush=True)
                try:
                    items, log = src.search(fetcher, query)
                except FetchError as e:
                    log = SourceLog(name, query, src.url_for(query), fehler=str(e))
                    items = []
                    if "HTTP 403" in str(e) or "robots" in str(e):
                        blocked.add(name)  # Sperre respektieren, Quelle nicht weiter abfragen
                print(log.fehler or f"{log.roh} Rohtreffer" + (f" ({log.hinweis})" if log.hinweis else ""))
                logs.append(log)
                for it in items:
                    it.herkunft_profil = prof.id
                    found.setdefault(it.key, it)

    listings = [l for l in found.values() if profiles.classify(l, cfg)]
    verworfen = len(found) - len(listings)
    if args.llm:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("[llm] übersprungen: ANTHROPIC_API_KEY ist nicht gesetzt")
        else:
            offen = [l for l in listings if l.passung == profiles.PRUEFEN]
            n, err = llm.enrich(offen, cfg.llm_modell, args.llm_max)
            for l in offen:
                profiles.reassess(l, cfg)
            print(f"[llm] {n} von {min(len(offen), args.llm_max)} Angeboten ergänzt" + (f" ({err})" if err else ""))
            logs.append(SourceLog("llm", cfg.llm_modell, "", roh=n, fehler=err))
    profiles.mark_duplicates(listings)

    auctions = []
    if "netbid" in wanted:
        print("[netbid] Auktionskalender ...", end=" ", flush=True)
        try:
            auctions, log = netbid.fetch(fetcher, cfg.auktions_begriffe)
        except FetchError as e:
            log = SourceLog("netbid", "Auktionskalender", netbid.URL, fehler=str(e))
        print(log.fehler or f"{log.roh} Auktionen, {sum(bool(a.treffer) for a in auctions)} mit Treffer")
        logs.append(log)

    insolvenzen = []
    if "indat" in wanted and cfg.insolvenzen:
        print("[indat] Insolvenzmeldungen ...", end=" ", flush=True)
        insolvenzen, ilogs = insolvency.fetch(fetcher, cfg.insolvenzen)
        logs.extend(ilogs)
        fehler = sum(bool(g.fehler) for g in ilogs)
        print(f"{len(insolvenzen)} relevante Firmen" + (f", {fehler} Abrufe mit Fehler" if fehler else ""))

    store = Store(out / "radar.sqlite")
    first_seen = store.upsert(listings, run_id)
    neu = sum(v == run_id for v in first_seen.values())
    store.log_run(run_id, len(listings), neu, fetcher.requests_made)

    xlsx = out / f"maschinenradar_{run_id[:10]}.xlsx"
    actions = scoring.rank(listings, auctions, cfg, cfg.aktionen_je_maschinenart, insolvenzen)
    drafts = [
        outreach.draft(a.listing, cfg)
        for a in actions
        if a.listing and a.aktion in (scoring.A_PREIS, scoring.A_DATEN)
    ]
    report.write(xlsx, cfg, listings, auctions, logs, first_seen, run_id, verworfen, actions, drafts, insolvenzen)

    print(f"\n{len(listings)} Angebote ({neu} neu), {verworfen} verworfen, "
          f"{store.not_seen_in(run_id)} frühere Angebote nicht mehr gefunden, "
          f"{fetcher.requests_made} Abrufe")
    print(f"Aktionsliste: {len(actions)} Einträge, {len(drafts)} Anfrage-Entwürfe, {len(insolvenzen)} Insolvenzen")
    data = dashboard.build(cfg, listings, auctions, logs, first_seen, run_id, actions, drafts, insolvenzen)
    dashboard.write(out / "dashboard.html", data)
    if args.dashboard_fragment:
        dashboard.write(Path(args.dashboard_fragment), data, standalone=False)
    print(f"Dashboard: {out / 'dashboard.html'}")
    print(f"Excel: {xlsx}")
    return 1 if logs and all(g.fehler for g in logs) else 0


def main(argv: list[str] | None = None) -> int:
    here = Path(__file__).resolve().parent.parent
    ap = argparse.ArgumentParser(prog="radar", description="Gebrauchtmaschinen-Radar (Phase 1)")
    ap.add_argument("--config", type=Path, default=here / "config" / "maschinen.yaml")
    ap.add_argument("--out", default=str(here / "out"))
    ap.add_argument("--quellen", help="Kommaliste, z. B. maschinensucher,resale (Standard: alle)")
    ap.add_argument("--max-seiten", type=int, default=40, help="Höchstzahl Ergebnisseiten je Suchanfrage")
    ap.add_argument("--pause", type=float, default=3.0, help="Sekunden zwischen Abrufen je Host")
    ap.add_argument("--cache-stunden", type=float, default=0, help="Seiten so lange aus dem Cache lesen")
    ap.add_argument("--dashboard-fragment", help="Dashboard zusätzlich ohne HTML-Rahmen schreiben (zum Einbetten)")
    ap.add_argument("--llm", action="store_true", help="Fehlende Felder per Claude ergänzen (braucht ANTHROPIC_API_KEY)")
    ap.add_argument("--llm-max", type=int, default=50, help="Höchstzahl Angebote für die LLM-Extraktion")
    return run(ap.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
