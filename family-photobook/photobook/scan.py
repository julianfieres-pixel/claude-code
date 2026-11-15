"""Find image files and read their metadata (capture date, GPS, size)."""
from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageOps

try:  # iPhone photos (HEIC/HEIF)
    import pillow_heif

    pillow_heif.register_heif_opener()
    HEIF_OK = True
except ImportError:  # pragma: no cover
    HEIF_OK = False

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp", ".tif", ".tiff"}

# EXIF tag ids
TAG_DATETIME = 306
TAG_DATETIME_ORIGINAL = 36867
TAG_EXIF_IFD = 0x8769
TAG_GPS_IFD = 0x8825

# e.g. IMG_20240312_101500.jpg, PXL_20240312_101500123.jpg, IMG-20240312-WA0001.jpg, 2024-03-12 10.15.00.jpg
FILENAME_DATE = re.compile(r"(20\d{2}|19\d{2})[-_.]?(0[1-9]|1[0-2])[-_.]?(0[1-9]|[12]\d|3[01])")


@dataclass
class Photo:
    path: str
    size_bytes: int
    mtime: float
    width: int = 0
    height: int = 0
    taken: datetime | None = None
    date_source: str = ""  # exif | filename | file
    lat: float | None = None
    lon: float | None = None
    sha256: str = ""
    dhash: int = 0
    # filled by later stages
    place: str = ""
    people: list[str] = field(default_factory=list)
    faces: list[dict] = field(default_factory=list)
    faces_done: bool = False
    sharpness: float = 0.0
    exposure: float = 0.0
    score: float = 0.0
    duplicate_of: str | None = None
    error: str = ""

    @property
    def month(self) -> str:
        return self.taken.strftime("%Y-%m") if self.taken else "unbekannt"

    @property
    def megapixels(self) -> float:
        return self.width * self.height / 1e6


def find_images(root: Path) -> list[Path]:
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for name in filenames:
            if not name.startswith(".") and Path(name).suffix.lower() in IMAGE_EXTS:
                files.append(Path(dirpath) / name)
    return sorted(files)


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _parse_exif_date(value) -> datetime | None:
    if not value:
        return None
    value = str(value).strip().replace("\x00", "")
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y:%m:%d %H:%M"):
        try:
            dt = datetime.strptime(value[:19], fmt)
            if dt.year >= 1990:
                return dt
        except ValueError:
            continue
    return None


def _dms_to_deg(dms, ref) -> float | None:
    try:
        d, m, s = (float(x) for x in dms)
    except (TypeError, ValueError):
        return None
    deg = d + m / 60 + s / 3600
    if ref in ("S", "W", b"S", b"W"):
        deg = -deg
    return deg


def read_exif(img: Image.Image) -> tuple[datetime | None, float | None, float | None]:
    exif = img.getexif()
    taken = None
    try:
        sub = exif.get_ifd(TAG_EXIF_IFD)
        taken = _parse_exif_date(sub.get(TAG_DATETIME_ORIGINAL))
    except Exception:
        pass
    taken = taken or _parse_exif_date(exif.get(TAG_DATETIME))

    lat = lon = None
    try:
        gps = exif.get_ifd(TAG_GPS_IFD)
        if gps and 2 in gps and 4 in gps:
            lat = _dms_to_deg(gps[2], gps.get(1))
            lon = _dms_to_deg(gps[4], gps.get(3))
            if lat is not None and lon is not None and abs(lat) < 1e-6 and abs(lon) < 1e-6:
                lat = lon = None  # 0/0 = no fix
    except Exception:
        pass
    return taken, lat, lon


def date_from_filename(name: str) -> datetime | None:
    m = FILENAME_DATE.search(name)
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), 12, 0)
    except ValueError:
        return None


def dhash(img: Image.Image, size: int = 8) -> int:
    """Difference hash: 64-bit perceptual fingerprint, robust to resizing/re-compression."""
    small = img.convert("L").resize((size + 1, size), Image.Resampling.LANCZOS)
    px = list(small.getdata())
    bits = 0
    for row in range(size):
        for col in range(size):
            left = px[row * (size + 1) + col]
            right = px[row * (size + 1) + col + 1]
            bits = (bits << 1) | (1 if left > right else 0)
    return bits


def load_oriented(path: str | Path, max_side: int | None = None) -> Image.Image:
    img = Image.open(path)
    img = ImageOps.exif_transpose(img)
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    if max_side and max(img.size) > max_side:
        img.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    return img


def read_photo(path: Path) -> Photo:
    st = path.stat()
    p = Photo(path=str(path), size_bytes=st.st_size, mtime=st.st_mtime)
    try:
        with Image.open(path) as raw:
            taken, p.lat, p.lon = read_exif(raw)
            oriented = ImageOps.exif_transpose(raw)
            p.width, p.height = oriented.size
            oriented.thumbnail((256, 256))
            p.dhash = dhash(oriented)
        p.sha256 = file_sha256(path)
    except Exception as exc:  # unreadable/corrupt file
        p.error = f"{type(exc).__name__}: {exc}"
        return p

    if taken:
        p.taken, p.date_source = taken, "exif"
    elif (fd := date_from_filename(path.name)) is not None:
        p.taken, p.date_source = fd, "filename"
    else:
        p.taken, p.date_source = datetime.fromtimestamp(st.st_mtime), "file"
    return p
