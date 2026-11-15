"""Run: python -m unittest discover -s tests"""
import unittest
from datetime import datetime

from PIL import Image

from photobook.dedupe import exact_duplicates, hamming, near_duplicates
from photobook.geocode import format_place
from photobook.scan import Photo, date_from_filename, dhash
from photobook.select import pick_print, pick_top


def photo(name, t, score=50.0, h=0, people=(), w=4000, ht=3000, sha=None):
    p = Photo(path=name, size_bytes=1, mtime=0, width=w, height=ht, taken=t, date_source="exif",
              sha256=sha or name, dhash=h)
    p.score, p.people = score, list(people)
    return p


class TestScan(unittest.TestCase):
    def test_filename_dates(self):
        self.assertEqual(date_from_filename("IMG-20240312-WA0001.jpg").date().isoformat(), "2024-03-12")
        self.assertEqual(date_from_filename("PXL_20231101_101500123.jpg").month, 11)
        self.assertIsNone(date_from_filename("DSC0001.jpg"))

    def test_dhash_stable_under_resize(self):
        img = Image.radial_gradient("L").convert("RGB")
        self.assertLessEqual(hamming(dhash(img), dhash(img.resize((97, 61)))), 4)


class TestDedupe(unittest.TestCase):
    def test_exact_keeps_largest(self):
        a = photo("a", datetime(2024, 1, 1), sha="x", w=100, ht=100)
        b = photo("b", datetime(2024, 1, 1), sha="x")
        exact_duplicates([a, b])
        self.assertEqual(a.duplicate_of, "b")

    def test_near_keeps_best_score(self):
        a = photo("a", datetime(2024, 1, 1, 10, 0, 0), score=40, h=0b1111)
        b = photo("b", datetime(2024, 1, 1, 10, 0, 5), score=60, h=0b1110)
        c = photo("c", datetime(2024, 1, 1, 18, 0, 0), score=10, h=0b1111)  # same look, hours later
        near_duplicates([a, b, c])
        self.assertEqual(a.duplicate_of, "b")
        self.assertIsNone(c.duplicate_of)


class TestSelect(unittest.TestCase):
    def test_top_prefers_variety(self):
        t = datetime(2024, 5, 1, 12)
        burst = [photo(f"b{i}", t.replace(second=i), score=90 - i, h=0) for i in range(5)]
        other = photo("o", datetime(2024, 5, 9), score=50, h=(1 << 64) - 1)
        top = pick_top(burst + [other], 2)
        self.assertEqual({p.path for p in top}, {"b0", "o"})

    def test_print_prefers_whole_family(self):
        a = photo("a", datetime(2024, 5, 1), score=90, people=["Leo"])
        b = photo("b", datetime(2024, 5, 2), score=70, people=["Leo", "Mama", "Papa"])
        self.assertEqual(pick_print([a, b], 1)[0].path, "b")


class TestPlace(unittest.TestCase):
    def test_format(self):
        d = {"category": "leisure", "type": "park", "name": "Englischer Garten",
             "address": {"city": "München", "country": "Deutschland", "country_code": "de"}}
        self.assertEqual(format_place(d, "de"), "Englischer Garten, München")
        self.assertEqual(format_place(d, "at"), "Englischer Garten, München, Deutschland")


if __name__ == "__main__":
    unittest.main()
