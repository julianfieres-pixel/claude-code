"""SQLite-Bestand: merkt sich, wann ein Angebot erstmals und zuletzt gesehen wurde."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .models import Listing

SCHEMA = """
CREATE TABLE IF NOT EXISTS listings (
    quelle TEXT NOT NULL, quelle_id TEXT NOT NULL,
    erstmals_gesehen TEXT NOT NULL, zuletzt_gesehen TEXT NOT NULL,
    preis_erst REAL, daten TEXT NOT NULL,
    PRIMARY KEY (quelle, quelle_id)
);
CREATE TABLE IF NOT EXISTS laeufe (
    lauf TEXT PRIMARY KEY, angebote INTEGER, neu INTEGER, anfragen INTEGER
);
"""


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.executescript(SCHEMA)

    def upsert(self, listings: list[Listing], run: str) -> dict[tuple[str, str], str]:
        """Speichert die Angebote; liefert je Angebot das Datum 'erstmals gesehen'."""
        first: dict[tuple[str, str], str] = {}
        for lst in listings:
            row = self.db.execute(
                "SELECT erstmals_gesehen FROM listings WHERE quelle=? AND quelle_id=?", lst.key
            ).fetchone()
            data = json.dumps(lst.to_dict(), ensure_ascii=False)
            if row:
                first[lst.key] = row[0]
                self.db.execute(
                    "UPDATE listings SET zuletzt_gesehen=?, daten=? WHERE quelle=? AND quelle_id=?",
                    (run, data, *lst.key),
                )
            else:
                first[lst.key] = run
                self.db.execute(
                    "INSERT INTO listings VALUES (?,?,?,?,?,?)", (*lst.key, run, run, lst.preis, data)
                )
        self.db.commit()
        return first

    def log_run(self, run: str, angebote: int, neu: int, anfragen: int) -> None:
        self.db.execute("INSERT OR REPLACE INTO laeufe VALUES (?,?,?,?)", (run, angebote, neu, anfragen))
        self.db.commit()

    def not_seen_in(self, run: str) -> int:
        """Anzahl frueher gesehener Angebote, die im aktuellen Lauf fehlen (evtl. verkauft)."""
        return self.db.execute(
            "SELECT COUNT(*) FROM listings WHERE zuletzt_gesehen < ?", (run,)
        ).fetchone()[0]
