from .maschinensucher import Maschinensucher
from .resale import Resale
from .plasticker import Plasticker
from .surplusrecord import SurplusRecord
from .wotol import Wotol

LISTING_SOURCES = {s.name: s for s in (Maschinensucher, Resale, SurplusRecord, Plasticker, Wotol)}
