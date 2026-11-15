"""Duplicate detection.

1. Exact duplicates: identical SHA-256 (same file copied twice, e.g. WhatsApp + camera roll backup).
2. Near duplicates: perceptual dHash within a small Hamming distance (re-compressed,
   resized or re-exported copies) AND taken within a short time window.
Exact duplicates keep the highest-resolution copy. Near duplicates (burst shots,
re-exports) keep the copy with the best quality score, so run that step after analysis.
"""
from __future__ import annotations

from collections import defaultdict

from .scan import Photo


def hamming(a: int, b: int) -> int:
    return (a ^ b).bit_count()


def _quality_key(p: Photo):
    return (p.width * p.height, p.date_source == "exif", p.size_bytes)


def exact_duplicates(photos: list[Photo]) -> list[tuple[Photo, Photo]]:
    """Mark byte-identical files in place (photo.duplicate_of). Returns (duplicate, kept) pairs."""
    pairs: list[tuple[Photo, Photo]] = []
    valid = [p for p in photos if not p.error]

    # exact
    by_hash: dict[str, list[Photo]] = defaultdict(list)
    for p in valid:
        by_hash[p.sha256].append(p)
    for group in by_hash.values():
        if len(group) > 1:
            keep = max(group, key=_quality_key)
            for p in group:
                if p is not keep:
                    p.duplicate_of = keep.path
                    pairs.append((p, keep))
    return pairs


def near_duplicates(photos: list[Photo], max_distance: int = 4, max_seconds: int = 120) -> list[tuple[Photo, Photo]]:
    """Mark visually identical photos in place; keeps the one with the higher quality score."""
    pairs: list[tuple[Photo, Photo]] = []
    valid = [p for p in photos if not p.error and p.duplicate_of is None]

    def key(p: Photo):
        # prefer the camera original (EXIF date) over messenger/re-exported copies, then quality
        return (p.date_source == "exif", p.score, _quality_key(p))

    # near (only compare photos close in time -> O(n * window))
    remaining = sorted(valid, key=lambda p: p.taken)
    for i, p in enumerate(remaining):
        if p.duplicate_of:
            continue
        for q in remaining[i + 1:]:
            dt = (q.taken - p.taken).total_seconds()
            # date from file/filename is unreliable -> allow wider window only for same-day matches
            limit = max_seconds if p.date_source == q.date_source == "exif" else 86400
            if dt > 86400:
                break
            if dt > limit:
                continue
            if q.duplicate_of or hamming(p.dhash, q.dhash) > max_distance:
                continue
            keep, drop = (p, q) if key(p) >= key(q) else (q, p)
            drop.duplicate_of = keep.path
            pairs.append((drop, keep))
            if drop is p:
                break
    return pairs
