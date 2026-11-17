"""Optionale LLM-Extraktion (Claude): ergänzt Felder, die die Regeln nicht gefunden haben.

Läuft nur mit --llm und gesetztem ANTHROPIC_API_KEY. Es werden ausschließlich öffentliche
Inseratstexte gesendet, keine Daten aus der Maschinenliste.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from .models import Listing

SYSTEM = (
    "Du liest Inserate für gebrauchte Produktionsmaschinen und extrahierst technische Daten. "
    "Gib nur Werte an, die im Text stehen oder sich eindeutig aus der Typbezeichnung ergeben. "
    "Unbekannte Werte bleiben null. Tonnen rechnest du mit Faktor 10 in kN um."
)


class Extracted(BaseModel):
    baujahr: Optional[int] = Field(None, description="Baujahr der Maschine, vierstellig")
    kraft_kn: Optional[float] = Field(None, description="Presskraft oder Schließkraft in kN")
    betriebsstunden: Optional[int] = None
    hubzahl_max: Optional[int] = Field(None, description="Maximale Hubzahl pro Minute (Pressen)")
    stange_mm: Optional[float] = Field(None, description="Max. Stangendurchmesser in mm (Drehautomaten)")
    hersteller: Optional[str] = None


def enrich(listings: list[Listing], model: str, limit: int, client=None) -> tuple[int, str]:
    """Ergänzt bis zu `limit` Angebote. Liefert (Anzahl ergänzt, Fehlertext)."""
    import anthropic

    client = client or anthropic.Anthropic()
    done = 0
    for lst in listings[:limit]:
        text = f"Titel: {lst.titel}\nKategorie: {lst.kategorie}\nBeschreibung: {lst.beschreibung}"
        try:
            resp = client.messages.parse(
                model=model,
                max_tokens=2000,
                system=SYSTEM,
                messages=[{"role": "user", "content": text}],
                output_format=Extracted,
            )
        except anthropic.AuthenticationError:
            return done, "API-Schlüssel ungültig"
        except anthropic.RateLimitError:
            return done, "Rate-Limit erreicht, Rest übersprungen"
        except anthropic.APIStatusError as e:
            return done, f"API-Fehler {e.status_code}"
        except anthropic.APIConnectionError:
            return done, "API nicht erreichbar"
        data = resp.parsed_output
        if resp.stop_reason == "refusal" or data is None:
            continue
        changed = False
        for name in ("baujahr", "kraft_kn", "betriebsstunden", "hubzahl_max", "stange_mm", "hersteller"):
            new = getattr(data, name)
            if new and not getattr(lst, name):
                setattr(lst, name, new)
                changed = True
        if changed:
            lst.llm_ergaenzt = True
            done += 1
    return done, ""
