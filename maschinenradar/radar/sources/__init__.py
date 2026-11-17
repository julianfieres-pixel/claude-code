from .maschinensucher import Maschinensucher
from .resale import Resale
from .surplusrecord import SurplusRecord

LISTING_SOURCES = {s.name: s for s in (Maschinensucher, Resale, SurplusRecord)}
