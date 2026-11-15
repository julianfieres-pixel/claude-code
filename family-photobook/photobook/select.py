"""Per-month selection: top N photos (with variety) and 2-3 print recommendations."""
from __future__ import annotations

from collections import defaultdict

from .dedupe import hamming
from .scan import Photo

SIMILAR_HASH = 12        # bits; "same scene" (burst series, same pose)
SIMILAR_SECONDS = 180


def is_similar(a: Photo, b: Photo) -> bool:
    return (abs((a.taken - b.taken).total_seconds()) <= SIMILAR_SECONDS
            and hamming(a.dhash, b.dhash) <= SIMILAR_HASH)


def group_by_month(photos: list[Photo]) -> dict[str, list[Photo]]:
    months: dict[str, list[Photo]] = defaultdict(list)
    for p in photos:
        months[p.month].append(p)
    return dict(sorted(months.items()))


def pick_top(candidates: list[Photo], n: int) -> list[Photo]:
    """Greedy selection by score that skips near-identical shots of the same moment,
    so the month shows different scenes. Falls back to similar shots if not enough variety."""
    ranked = sorted(candidates, key=lambda p: -p.score)
    chosen: list[Photo] = []
    skipped: list[Photo] = []
    for p in ranked:
        if len(chosen) >= n:
            break
        if any(is_similar(p, c) for c in chosen):
            skipped.append(p)
        else:
            chosen.append(p)
    chosen += skipped[: n - len(chosen)]
    return sorted(chosen, key=lambda p: p.taken)


def pick_print(top: list[Photo], k: int, min_short_side: int = 1200) -> list[Photo]:
    """Print recommendations: high score, print-ready resolution (10x15 cm @ 200 dpi ~ 1200 px),
    prefer a photo with the whole family, then spread over different days/places."""
    printable = [p for p in top if min(p.width, p.height) >= min_short_side] or list(top)
    ranked = sorted(printable, key=lambda p: -p.score)
    if not ranked:
        return []
    picks: list[Photo] = []
    # 1) best photo with the most family members
    most = max(len(p.people) for p in ranked)
    picks.append(next(p for p in ranked if len(p.people) == most))
    # 2..k) best remaining, preferring other days and other places
    while len(picks) < k:
        rest = [p for p in ranked if p not in picks]
        if not rest:
            break

        def bonus(p: Photo) -> float:
            b = p.score
            if all(p.taken.date() != q.taken.date() for q in picks):
                b += 8
            if p.place and all(p.place != q.place for q in picks):
                b += 4
            if set(p.people) - {x for q in picks for x in q.people}:
                b += 4  # adds a person not yet in the print picks
            return b

        picks.append(max(rest, key=bonus))
    return sorted(picks, key=lambda p: p.taken)
