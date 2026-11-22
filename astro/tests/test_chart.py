"""Unit tests for chart.py.  Run:  .venv/bin/python -m unittest -v tests.test_chart"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chart import (AV_TABLE, SIGNS, ashtakavarga, compute_chart, compute_transits,  # noqa: E402
                   varga_sign)


def L(sign, deg, minutes=0, seconds=0):
    """Sidereal longitude from a sign name and a degree inside it."""
    return SIGNS.index(sign) * 30 + deg + minutes / 60 + seconds / 3600


def name(lon, varga):
    return SIGNS[varga_sign(lon, varga)]


class TestNavamsa(unittest.TestCase):
    # (description, longitude, expected D9 sign) -- worked by hand from the rule
    # "movable signs count from themselves, fixed from the 9th, dual from the 5th".
    CASES = [
        ("Aries 0°  (movable, 1st part -> itself)", L("Aries", 0.5), "Aries"),
        ("Aries 29° (9th part)", L("Aries", 29), "Sagittarius"),
        ("Taurus 1° (fixed, starts at 9th = Capricorn)", L("Taurus", 1), "Capricorn"),
        ("Taurus 29° (9th part = Virgo)", L("Taurus", 29), "Virgo"),
        ("Gemini 1° (dual, starts at 5th = Libra)", L("Gemini", 1), "Libra"),
        ("Cancer 1° (movable)", L("Cancer", 1), "Cancer"),
        ("Leo 2°26' (fixed, starts Aries)", L("Leo", 2, 26), "Aries"),
        ("Sagittarius 15° (dual, starts Aries, 5th part)", L("Sagittarius", 15), "Leo"),
        ("Libra 14°59'39\" (movable, 5th part)", L("Libra", 14, 59, 39), "Aquarius"),
        ("Pisces 29°59' (last navamsa of the zodiac)", L("Pisces", 29, 59), "Pisces"),
    ]

    def test_worked_examples(self):
        for desc, lon, expected in self.CASES:
            with self.subTest(desc):
                self.assertEqual(name(lon, "D9"), expected)

    def test_part_boundary(self):
        # 3°20' starts the 2nd navamsa; just below stays in the 1st.
        self.assertEqual(name(L("Aries", 3, 19, 59), "D9"), "Aries")
        self.assertEqual(name(L("Aries", 3, 20, 1), "D9"), "Taurus")

    def test_navamsas_run_continuously_round_the_zodiac(self):
        # The 108 navamsas run Aries, Taurus, ... unbroken from 0° Aries; this is
        # what the movable/fixed/dual rule amounts to.
        for i in range(108):
            lon = i * 10 / 3 + 1.0
            self.assertEqual(varga_sign(lon, "D9"), i % 12, f"navamsa #{i}")

    def test_not_counted_from_aries_taurus_gemini(self):
        # A fixed sign does NOT start its navamsas from Taurus.
        self.assertNotEqual(name(L("Leo", 1), "D9"), "Taurus")


class TestDasamsa(unittest.TestCase):
    # Odd signs count from themselves, even signs from the 9th; 3° parts.
    CASES = [
        ("Aries 0° (odd -> itself)", L("Aries", 0.5), "Aries"),
        ("Aries 29° (10th part)", L("Aries", 29), "Capricorn"),
        ("Taurus 1° (even, starts at 9th = Capricorn)", L("Taurus", 1), "Capricorn"),
        ("Taurus 29° (10th from Capricorn)", L("Taurus", 29), "Libra"),
        ("Cancer 5° (even, starts Pisces, 2nd part)", L("Cancer", 5), "Aries"),
        ("Leo 2°26' (odd, 1st part)", L("Leo", 2, 26), "Leo"),
        ("Scorpio 23°50' (even, starts Cancer, 8th part)", L("Scorpio", 23, 50), "Aquarius"),
        ("Sagittarius 15°01' (odd, 6th part)", L("Sagittarius", 15, 1), "Taurus"),
        ("Pisces 29° (even, starts Scorpio, 10th part)", L("Pisces", 29), "Leo"),
    ]

    def test_worked_examples(self):
        for desc, lon, expected in self.CASES:
            with self.subTest(desc):
                self.assertEqual(name(lon, "D10"), expected)

    def test_part_boundary(self):
        self.assertEqual(name(L("Gemini", 2, 59, 59), "D10"), "Gemini")
        self.assertEqual(name(L("Gemini", 3, 0, 1), "D10"), "Cancer")

    def test_each_sign_gives_ten_consecutive_signs(self):
        for s in range(12):
            start = s if s % 2 == 0 else (s + 8) % 12
            got = [varga_sign(s * 30 + k * 3 + 1.5, "D10") for k in range(10)]
            self.assertEqual(got, [(start + k) % 12 for k in range(10)], SIGNS[s])


class TestOtherVargas(unittest.TestCase):
    def test_d12_counts_from_sign(self):
        self.assertEqual(name(L("Taurus", 1), "D12"), "Taurus")
        self.assertEqual(name(L("Taurus", 29), "D12"), "Aries")

    def test_d4_uses_kendras_from_sign(self):
        got = [name(L("Leo", d), "D4") for d in (1, 8, 16, 23)]
        self.assertEqual(got, ["Leo", "Scorpio", "Aquarius", "Taurus"])

    def test_d7_odd_and_even(self):
        self.assertEqual(name(L("Aries", 1), "D7"), "Aries")
        self.assertEqual(name(L("Taurus", 1), "D7"), "Scorpio")

    def test_unknown_varga(self):
        with self.assertRaises(ValueError):
            varga_sign(10, "D60")


class TestAshtakavarga(unittest.TestCase):
    EXPECTED_TOTALS = {"Sun": 48, "Moon": 49, "Mars": 39, "Mercury": 54,
                       "Jupiter": 56, "Venus": 52, "Saturn": 39}

    def test_table_totals(self):
        for planet, total in self.EXPECTED_TOTALS.items():
            self.assertEqual(sum(len(v) for v in AV_TABLE[planet].values()), total, planet)

    def test_chart_totals_are_fixed(self):
        for args in (("1978-12-30", "21:10", 16.5062, 80.6480),
                     ("2013-07-31", "12:25", 17.3850, 78.4867)):
            c = compute_chart(*args, zone="Asia/Kolkata")
            bav, sav = ashtakavarga(c)
            for planet, total in self.EXPECTED_TOTALS.items():
                self.assertEqual(sum(bav[planet]), total, planet)
            self.assertEqual(sum(sav), 337)
            self.assertTrue(all(0 <= v <= 8 for row in bav.values() for v in row))


class TestTransits(unittest.TestCase):
    def test_flags_and_ketu_opposite_rahu(self):
        c = compute_chart("1978-12-30", "21:10", 16.5062, 80.6480, zone="Asia/Kolkata")
        _, sav = ashtakavarga(c)
        rows = compute_transits(c, "2027-01", "2027-03", sav)
        self.assertEqual([r["month"] for r in rows], ["2027-01", "2027-02", "2027-03"])
        for r in rows:
            b = r["bodies"]
            self.assertEqual((b["Ketu"]["from_moon"] - b["Rahu"]["from_moon"]) % 12, 6)
            sat = b["Saturn"]["from_moon"]
            self.assertEqual(any("Kantaka" in f for f in r["flags"]), sat in (1, 4, 7, 10))
            self.assertEqual(any("Sade Sati" in f for f in r["flags"]), sat in (12, 1, 2))

    def test_bad_range(self):
        c = compute_chart("1978-12-30", "21:10", 16.5062, 80.6480, zone="Asia/Kolkata")
        with self.assertRaises(ValueError):
            compute_transits(c, "2028-01", "2027-01", [0] * 12)


if __name__ == "__main__":
    unittest.main()
