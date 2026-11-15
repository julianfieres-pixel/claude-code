"""Face detection (YuNet) and recognition (SFace) with OpenCV - runs fully offline.

Models: OpenCV Zoo (Apache-2.0)
  https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet
  https://github.com/opencv/opencv_zoo/tree/main/models/face_recognition_sface
"""
from __future__ import annotations

import urllib.request
from pathlib import Path

import cv2
import numpy as np

from .scan import IMAGE_EXTS, load_oriented

MODEL_URLS = {
    "yunet.onnx": "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/"
    "face_detection_yunet/face_detection_yunet_2023mar.onnx",
    "sface.onnx": "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/"
    "face_recognition_sface/face_recognition_sface_2021dec.onnx",
}
# SFace cosine-similarity threshold recommended by OpenCV is 0.363. Children's faces change
# quickly, so we stay close to it; tune with --face-threshold if needed.
DEFAULT_THRESHOLD = 0.363
ANALYSIS_MAX_SIDE = 1600


def ensure_models(model_dir: Path) -> tuple[Path, Path]:
    model_dir.mkdir(parents=True, exist_ok=True)
    for name, url in MODEL_URLS.items():
        target = model_dir / name
        if not target.exists() or target.stat().st_size < 100_000:
            print(f"  Lade Modell {name} ...")
            urllib.request.urlretrieve(url, target)
    return model_dir / "yunet.onnx", model_dir / "sface.onnx"


def to_bgr(img) -> np.ndarray:
    arr = np.asarray(img.convert("RGB"))
    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)


class FaceEngine:
    def __init__(self, model_dir: Path, threshold: float = DEFAULT_THRESHOLD):
        det, rec = ensure_models(model_dir)
        self.detector = cv2.FaceDetectorYN.create(str(det), "", (320, 320), 0.8, 0.3, 5000)
        self.recognizer = cv2.FaceRecognizerSF.create(str(rec), "")
        self.threshold = threshold
        self.people: dict[str, list[np.ndarray]] = {}

    # --- detection / embedding -------------------------------------------------
    def detect(self, bgr: np.ndarray) -> np.ndarray:
        h, w = bgr.shape[:2]
        self.detector.setInputSize((w, h))
        _, faces = self.detector.detect(bgr)
        return faces if faces is not None else np.zeros((0, 15), dtype=np.float32)

    def embed(self, bgr: np.ndarray, face: np.ndarray) -> np.ndarray:
        aligned = self.recognizer.alignCrop(bgr, face)
        feat = self.recognizer.feature(aligned)
        return feat / (np.linalg.norm(feat) + 1e-9)

    # --- enrollment --------------------------------------------------------------
    def enroll(self, people_dir: Path) -> dict[str, int]:
        """people_dir/<Name>/*.jpg -> one reference embedding per photo (largest face)."""
        counts = {}
        for person_dir in sorted(p for p in people_dir.iterdir() if p.is_dir()):
            feats = []
            for f in sorted(person_dir.iterdir()):
                if f.suffix.lower() not in IMAGE_EXTS:
                    continue
                bgr = to_bgr(load_oriented(f, ANALYSIS_MAX_SIDE))
                faces = self.detect(bgr)
                if len(faces) == 0:
                    print(f"  ! Kein Gesicht gefunden in Referenzfoto {f}")
                    continue
                largest = max(faces, key=lambda r: r[2] * r[3])
                feats.append(self.embed(bgr, largest))
            if feats:
                self.people[person_dir.name] = feats
            counts[person_dir.name] = len(feats)
        return counts

    # --- analysis -----------------------------------------------------------------
    def detect_and_embed(self, bgr: np.ndarray) -> list[dict]:
        """Faces with relative bbox, detector confidence and a normalised 128-d embedding."""
        h, w = bgr.shape[:2]
        out = []
        for face in self.detect(bgr):
            x, y, fw, fh = (float(v) for v in face[:4])
            out.append({
                "box": [x / w, y / h, fw / w, fh / h],
                "det": round(float(face[14]), 3),
                "feat": [round(float(v), 5) for v in self.embed(bgr, face).ravel()],
            })
        return out

    def match(self, faces: list[dict]) -> None:
        """Assign 'person' and 'sim' in place; each person at most once per photo."""
        for f in faces:
            feat = np.asarray(f["feat"], dtype=np.float32)
            best_name, best_sim = None, -1.0
            for name, refs in self.people.items():
                sim = float(np.max(refs @ feat))
                if sim > best_sim:
                    best_name, best_sim = name, sim
            f["sim"] = round(best_sim, 3)
            f["person"] = best_name if best_sim >= self.threshold else None
        seen = set()
        for f in sorted(faces, key=lambda f: -f["sim"]):
            if f["person"] in seen:
                f["person"] = None
            elif f["person"]:
                seen.add(f["person"])

    def freeze(self) -> None:
        """Stack reference embeddings into matrices for fast matching."""
        self.people = {k: np.vstack([np.asarray(r, dtype=np.float32).ravel() for r in v])
                       for k, v in self.people.items()}

    def expand_references(self, faces_per_photo: list[list[dict]], min_sim: float = 0.55,
                          max_new: int = 200) -> dict[str, int]:
        """Add very confident matches as extra references. Helps with children whose
        faces change month by month (reference photos only cover some ages)."""
        added: dict[str, list] = {k: [] for k in self.people}
        for faces in faces_per_photo:
            for f in faces:
                if f.get("person") and f["sim"] >= min_sim and len(added[f["person"]]) < max_new:
                    added[f["person"]].append(np.asarray(f["feat"], dtype=np.float32))
        for name, feats in added.items():
            if feats:
                self.people[name] = np.vstack([self.people[name], *feats])
        return {k: len(v) for k, v in added.items()}
