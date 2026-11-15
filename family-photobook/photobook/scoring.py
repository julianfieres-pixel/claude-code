"""Image quality metrics and the combined ranking score."""
from __future__ import annotations

import math

import cv2
import numpy as np

from .scan import Photo


def sharpness(gray: np.ndarray, faces: list[dict]) -> float:
    """Variance of the Laplacian (classic blur measure). Measured on faces if present,
    because a sharp face matters more than a sharp background."""
    h, w = gray.shape[:2]
    regions = []
    for f in faces:
        x, y, fw, fh = f["box"]
        x0, y0 = max(0, int(x * w)), max(0, int(y * h))
        x1, y1 = min(w, int((x + fw) * w)), min(h, int((y + fh) * h))
        if x1 - x0 > 16 and y1 - y0 > 16:
            regions.append(gray[y0:y1, x0:x1])
    if not regions:
        regions = [gray]
    vals = [cv2.Laplacian(r, cv2.CV_64F).var() for r in regions]
    return float(max(vals))


def exposure(gray: np.ndarray) -> float:
    """1.0 = well exposed; penalises dark/bright images and clipped highlights/shadows."""
    mean = gray.mean() / 255.0
    clipped = ((gray < 8).mean() + (gray > 247).mean())
    contrast = min(gray.std() / 64.0, 1.0)
    score = 1.0 - abs(mean - 0.5) * 1.6 - clipped * 1.5
    return float(max(0.0, min(1.0, 0.7 * score + 0.3 * contrast)))


def combined_score(p: Photo, weights: dict[str, float], person_weights: dict[str, float]) -> float:
    """0..100. Rewards photos with family members, sharp large faces, good exposure, resolution."""
    family = [f for f in p.faces if f.get("person")]
    people_part = sum(person_weights.get(f["person"], 1.0) for f in family)
    people_part = min(people_part / max(sum(person_weights.values()), 1.0), 1.0)

    face_size = max((f["box"][2] * f["box"][3] for f in family), default=0.0)
    face_part = min(math.sqrt(face_size) / 0.35, 1.0)  # face ~12% of image area = max

    sharp_part = min(math.log1p(p.sharpness) / math.log1p(800), 1.0)
    res_part = min(p.megapixels / 8.0, 1.0)

    # many strangers in the picture -> less of a family photo
    strangers = sum(1 for f in p.faces if not f.get("person") and f["box"][2] * f["box"][3] > 0.002)
    crowd_penalty = min(strangers * 0.04, 0.2)

    total = (
        weights["people"] * people_part
        + weights["faces"] * face_part
        + weights["sharpness"] * sharp_part
        + weights["exposure"] * p.exposure
        + weights["resolution"] * res_part
    ) / sum(weights.values())
    return round(100 * max(total - crowd_penalty, 0.0), 2)


DEFAULT_WEIGHTS = {"people": 0.35, "faces": 0.15, "sharpness": 0.25, "exposure": 0.15, "resolution": 0.10}
