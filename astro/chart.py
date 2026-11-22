#!/usr/bin/env python3
"""Sidereal (Lahiri) birth chart with nakshatras and Vimshottari dasha.

Library:  from chart import compute_chart
CLI:
    .venv/bin/python chart.py --date 1990-05-17 --time 06:45 --lat 17.385 --lon 78.4867 --tz 5.5
    .venv/bin/python chart.py --zone America/New_York ...   # historical offset/DST from tz database
"""
import argparse
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import swisseph as swe

SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
         "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]

SIGN_LORDS = ["Mars", "Venus", "Mercury", "Moon", "Sun", "Mercury",
              "Venus", "Mars", "Jupiter", "Saturn", "Saturn", "Jupiter"]

NAKSHATRAS = ["Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
              "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni",
              "Uttara Phalguni", "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha",
              "Jyeshtha", "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana",
              "Dhanishta", "Shatabhisha", "Purva Bhadrapada", "Uttara Bhadrapada", "Revati"]

# Vimshottari order, starting from Ashwini's lord (Ketu); years per mahadasha.
DASHA_ORDER = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]
DASHA_YEARS = {"Ketu": 7, "Venus": 20, "Sun": 6, "Moon": 10, "Mars": 7,
               "Rahu": 18, "Jupiter": 16, "Saturn": 19, "Mercury": 17}
TOTAL_YEARS = 120
YEAR_DAYS = 365.25

NAK_SPAN = 360 / 27          # 13°20'
PADA_SPAN = NAK_SPAN / 4     # 3°20'

PLANETS = [("Sun", swe.SUN), ("Moon", swe.MOON), ("Mars", swe.MARS),
           ("Mercury", swe.MERCURY), ("Jupiter", swe.JUPITER), ("Venus", swe.VENUS),
           ("Saturn", swe.SATURN)]

AYANAMSAS = {"lahiri": swe.SIDM_LAHIRI}


def dms(deg):
    d = int(deg)
    m_full = (deg - d) * 60
    m = int(m_full)
    s = int(round((m_full - m) * 60))
    if s == 60:
        s, m = 0, m + 1
    if m == 60:
        m, d = 0, d + 1
    return f"{d}°{m:02d}'{s:02d}\""


def nakshatra(lon):
    idx = int(lon // NAK_SPAN)
    pada = int((lon % NAK_SPAN) // PADA_SPAN) + 1
    return idx, pada


def _body(name, lon, retro, asc_sign):
    sign = int(lon // 30)
    nak, pada = nakshatra(lon)
    return {
        "name": name,
        "longitude": round(lon, 6),
        "sign": SIGNS[sign],
        "sign_index": sign,
        "sign_lord": SIGN_LORDS[sign],
        "degree": round(lon % 30, 6),
        "degree_dms": dms(lon % 30),
        "nakshatra": NAKSHATRAS[nak],
        "nakshatra_lord": DASHA_ORDER[nak % 9],
        "pada": pada,
        "house": (sign - asc_sign) % 12 + 1,
        "retrograde": retro,
    }


def vimshottari(moon_lon, birth_dt):
    """Return (periods, first_lord, balance_years). Dates are naive local datetimes."""
    nak, _ = nakshatra(moon_lon)
    lord_idx = nak % 9
    fraction_elapsed = (moon_lon % NAK_SPAN) / NAK_SPAN
    first_lord = DASHA_ORDER[lord_idx]
    # The mahadasha running at birth actually began before birth.
    start = birth_dt - timedelta(days=fraction_elapsed * DASHA_YEARS[first_lord] * YEAR_DAYS)

    periods = []
    for i in range(9):
        lord = DASHA_ORDER[(lord_idx + i) % 9]
        maha_days = DASHA_YEARS[lord] * YEAR_DAYS
        end = start + timedelta(days=maha_days)
        subs, s = [], start
        for j in range(9):
            sub = DASHA_ORDER[(DASHA_ORDER.index(lord) + j) % 9]
            e = s + timedelta(days=maha_days * DASHA_YEARS[sub] / TOTAL_YEARS)
            subs.append((sub, s, e))
            s = e
        periods.append((lord, start, end, subs))
        start = end
    balance_years = (1 - fraction_elapsed) * DASHA_YEARS[first_lord]
    return periods, first_lord, balance_years


def ymd(years):
    y = int(years)
    m_full = (years - y) * 12
    m = int(m_full)
    d = int(round((m_full - m) * 30.4375))
    return f"{y}y {m}m {d}d"


def resolve_offset(local_dt, zone=None, tz_hours=None):
    """UTC offset in hours: explicit tz_hours wins, else the IANA zone at that date."""
    if tz_hours is not None:
        return float(tz_hours)
    if zone:
        off = local_dt.replace(tzinfo=ZoneInfo(zone)).utcoffset()
        return off.total_seconds() / 3600
    raise ValueError("Give either a UTC offset or an IANA time zone")


def compute_chart(date, time, lat, lon, tz_hours=None, zone=None, true_node=False,
                  ephe_path=None, now=None):
    """Compute a sidereal Lahiri chart.

    date 'YYYY-MM-DD', time 'HH:MM' or 'HH:MM:SS' (local civil time at birth place),
    lat +N / lon +E in degrees, and either tz_hours (UTC offset) or zone (IANA name).
    Returns a JSON-serialisable dict.
    """
    if not -90 <= lat <= 90 or not -180 <= lon <= 180:
        raise ValueError("Latitude must be within ±90 and longitude within ±180")
    fmt = "%Y-%m-%d %H:%M:%S" if time.count(":") == 2 else "%Y-%m-%d %H:%M"
    local_dt = datetime.strptime(f"{date} {time}", fmt)
    offset = resolve_offset(local_dt, zone, tz_hours)
    utc_dt = local_dt - timedelta(hours=offset)

    if ephe_path:
        swe.set_ephe_path(ephe_path)
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    ut_hours = utc_dt.hour + utc_dt.minute / 60 + utc_dt.second / 3600
    jd_ut = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, ut_hours)
    flags = swe.FLG_SWIEPH | swe.FLG_SIDEREAL | swe.FLG_SPEED
    ayanamsa = swe.get_ayanamsa_ut(jd_ut)

    _, ascmc = swe.houses_ex(jd_ut, lat, lon, b"W", swe.FLG_SIDEREAL)
    asc_lon = ascmc[0] % 360
    asc_sign = int(asc_lon // 30)

    bodies = []
    for name, pid in PLANETS:
        xx, _ = swe.calc_ut(jd_ut, pid, flags)
        bodies.append(_body(name, xx[0] % 360, xx[3] < 0, asc_sign))
    xx, _ = swe.calc_ut(jd_ut, swe.TRUE_NODE if true_node else swe.MEAN_NODE, flags)
    rahu = xx[0] % 360
    rahu_retro = xx[3] < 0 if true_node else True
    bodies.append(_body("Rahu", rahu, rahu_retro, asc_sign))
    bodies.append(_body("Ketu", (rahu + 180) % 360, rahu_retro, asc_sign))

    moon = next(b for b in bodies if b["name"] == "Moon")
    periods, first_lord, balance = vimshottari(moon["longitude"], local_dt)
    now = now or (datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=offset))

    def iso(d):
        return d.strftime("%Y-%m-%d")

    dashas = []
    for lord, start, end, subs in periods:
        dashas.append({
            "lord": lord, "start": iso(start), "end": iso(end),
            "current": start <= now < end,
            "antardashas": [{"lord": s, "start": iso(a), "end": iso(b),
                             "current": a <= now < b, "before_birth": b <= local_dt}
                            for s, a, b in subs],
        })

    return {
        "input": {"date": date, "time": time, "lat": lat, "lon": lon,
                  "zone": zone, "utc_offset": offset, "true_node": true_node},
        "local_time": local_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "utc_time": utc_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "julian_day_ut": round(jd_ut, 6),
        "ayanamsa": {"name": "Lahiri", "value": round(ayanamsa, 6), "dms": dms(ayanamsa)},
        "house_system": "Whole sign",
        "ascendant": _body("Ascendant", asc_lon, False, asc_sign),
        "planets": bodies,
        "dasha": {
            "system": "Vimshottari", "year_days": YEAR_DAYS,
            "moon_nakshatra": moon["nakshatra"], "moon_pada": moon["pada"],
            "balance_lord": first_lord, "balance": ymd(balance),
            "balance_years": round(balance, 4), "periods": dashas,
        },
    }


def print_chart(c, place=""):
    off = c["input"]["utc_offset"]
    print(f"Birth      : {c['local_time']} (UTC{off:+g})  =  {c['utc_time']} UT")
    print(f"Place      : {place}  ({c['input']['lat']:.4f}, {c['input']['lon']:.4f})")
    print(f"Ayanamsa   : Lahiri {c['ayanamsa']['dms']}")
    print(f"Houses     : whole sign from Lagna;  nodes: {'true' if c['input']['true_node'] else 'mean'}")
    print()
    hdr = f"{'Body':<10}{'Sign':<12}{'Degree':>11}   {'Nakshatra':<18}{'Pada':>4}{'House':>7}  {'Retro':<5}"
    print(hdr)
    print("-" * len(hdr))
    for b in [c["ascendant"]] + c["planets"]:
        r = "-" if b["name"] == "Ascendant" else ("R" if b["retrograde"] else "")
        print(f"{b['name']:<10}{b['sign']:<12}{b['degree_dms']:>11}   {b['nakshatra']:<18}"
              f"{b['pada']:>4}{b['house']:>7}  {r:<5}")
    d = c["dasha"]
    print()
    print(f"Vimshottari dasha  (Moon in {d['moon_nakshatra']} pada {d['moon_pada']}; year = {d['year_days']} days)")
    print(f"Balance of {d['balance_lord']} mahadasha at birth: {d['balance']}")
    print()
    for p in d["periods"]:
        print(f"{p['lord']:<8} Mahadasha  {p['start']} – {p['end']}")
        for a in p["antardashas"]:
            mark = "  (before birth)" if a["before_birth"] else ("  <- now" if a["current"] else "")
            print(f"    {p['lord'][:3]}/{a['lord']:<8} {a['start']} – {a['end']}{mark}")
    print()
    print("Dasha dates are in local time (same zone as the birth time).")


# ---------------------------------------------------------------- divisional charts
# Sign indices: 0 = Aries ... 11 = Pisces. "Odd" signs in the Jyotish sense
# (Aries, Gemini, ...) have even indices here.
VARGA_NAMES = {"D4": "Chaturthamsa", "D7": "Saptamsa", "D9": "Navamsa",
               "D10": "Dasamsa", "D12": "Dwadasamsa"}
GRAHAS = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]


def _part(deg_in_sign, n):
    return min(int(deg_in_sign / (30 / n)), n - 1)


def varga_sign(lon, varga):
    """Sign index (0-11) of sidereal longitude `lon` in divisional chart `varga`."""
    sign, deg = int(lon // 30) % 12, lon % 30
    if varga == "D9":
        # Movable signs count from themselves, fixed from the 9th, dual from the 5th
        # (i.e. fire signs start in Aries, earth in Capricorn, air in Libra, water in Cancer).
        start = sign + (0, 8, 4)[sign % 3]
        return (start + _part(deg, 9)) % 12
    if varga == "D10":
        start = sign if sign % 2 == 0 else sign + 8        # odd: itself, even: 9th
        return (start + _part(deg, 10)) % 12
    if varga == "D12":
        return (sign + _part(deg, 12)) % 12                # from the sign itself
    if varga == "D4":
        return (sign + 3 * _part(deg, 4)) % 12             # sign, 4th, 7th, 10th
    if varga == "D7":
        start = sign if sign % 2 == 0 else sign + 6        # odd: itself, even: 7th
        return (start + _part(deg, 7)) % 12
    raise ValueError(f"Unsupported varga {varga!r}; choose from {', '.join(VARGA_NAMES)}")


def compute_varga(chart, varga):
    asc_d1 = chart["ascendant"]["sign_index"]
    lagna = varga_sign(chart["ascendant"]["longitude"], varga)
    rows = [{"name": "Ascendant", "sign": SIGNS[lagna], "sign_index": lagna, "house": 1,
             "vargottama": lagna == asc_d1}]
    for p in chart["planets"]:
        s = varga_sign(p["longitude"], varga)
        rows.append({"name": p["name"], "sign": SIGNS[s], "sign_index": s,
                     "house": (s - lagna) % 12 + 1, "vargottama": s == p["sign_index"],
                     "d1_sign": p["sign"]})
    return {"varga": varga, "name": VARGA_NAMES[varga], "lagna": SIGNS[lagna], "rows": rows}


def print_varga(v):
    print(f"\n{v['varga']} {v['name']}  (lagna {v['lagna']})")
    hdr = f"{'Body':<10}{'D1 sign':<13}{v['varga'] + ' sign':<13}{'House':>5}  Vargottama"
    print(hdr)
    print("-" * len(hdr))
    for r in v["rows"]:
        d1 = r.get("d1_sign", "")
        print(f"{r['name']:<10}{d1:<13}{r['sign']:<13}{r['house']:>5}  {'yes' if r['vargottama'] else ''}")


# ---------------------------------------------------------------- ashtakavarga
# Parashari benefic places: for each planet's BAV, the houses (counted from each
# contributor, contributor = 1st) that receive a bindu.
AV_CONTRIBUTORS = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Lagna"]
AV_TABLE = {
    "Sun": {"Sun": [1, 2, 4, 7, 8, 9, 10, 11], "Moon": [3, 6, 10, 11],
            "Mars": [1, 2, 4, 7, 8, 9, 10, 11], "Mercury": [3, 5, 6, 9, 10, 11, 12],
            "Jupiter": [5, 6, 9, 11], "Venus": [6, 7, 12],
            "Saturn": [1, 2, 4, 7, 8, 9, 10, 11], "Lagna": [3, 4, 6, 10, 11, 12]},
    "Moon": {"Sun": [3, 6, 7, 8, 10, 11], "Moon": [1, 3, 6, 7, 10, 11],
             "Mars": [2, 3, 5, 6, 9, 10, 11], "Mercury": [1, 3, 4, 5, 7, 8, 10, 11],
             "Jupiter": [1, 4, 7, 8, 10, 11, 12], "Venus": [3, 4, 5, 7, 9, 10, 11],
             "Saturn": [3, 5, 6, 11], "Lagna": [3, 6, 10, 11]},
    "Mars": {"Sun": [3, 5, 6, 10, 11], "Moon": [3, 6, 11], "Mars": [1, 2, 4, 7, 8, 10, 11],
             "Mercury": [3, 5, 6, 11], "Jupiter": [6, 10, 11, 12], "Venus": [6, 8, 11, 12],
             "Saturn": [1, 4, 7, 8, 9, 10, 11], "Lagna": [1, 3, 6, 10, 11]},
    "Mercury": {"Sun": [5, 6, 9, 11, 12], "Moon": [2, 4, 6, 8, 10, 11],
                "Mars": [1, 2, 4, 7, 8, 9, 10, 11], "Mercury": [1, 3, 5, 6, 9, 10, 11, 12],
                "Jupiter": [6, 8, 11, 12], "Venus": [1, 2, 3, 4, 5, 8, 9, 11],
                "Saturn": [1, 2, 4, 7, 8, 9, 10, 11], "Lagna": [1, 2, 4, 6, 8, 10, 11]},
    "Jupiter": {"Sun": [1, 2, 3, 4, 7, 8, 9, 10, 11], "Moon": [2, 5, 7, 9, 11],
                "Mars": [1, 2, 4, 7, 8, 10, 11], "Mercury": [1, 2, 4, 5, 6, 9, 10, 11],
                "Jupiter": [1, 2, 3, 4, 7, 8, 10, 11], "Venus": [2, 5, 6, 9, 10, 11],
                "Saturn": [3, 5, 6, 12], "Lagna": [1, 2, 4, 5, 6, 7, 9, 10, 11]},
    "Venus": {"Sun": [8, 11, 12], "Moon": [1, 2, 3, 4, 5, 8, 9, 11, 12],
              "Mars": [3, 5, 6, 9, 11, 12], "Mercury": [3, 5, 6, 9, 11],
              "Jupiter": [5, 8, 9, 10, 11], "Venus": [1, 2, 3, 4, 5, 8, 9, 10, 11],
              "Saturn": [3, 4, 5, 8, 9, 10, 11], "Lagna": [1, 2, 3, 4, 5, 8, 9, 11]},
    "Saturn": {"Sun": [1, 2, 4, 7, 8, 10, 11], "Moon": [3, 6, 11],
               "Mars": [3, 5, 6, 10, 11, 12], "Mercury": [6, 8, 9, 10, 11, 12],
               "Jupiter": [5, 6, 11, 12], "Venus": [6, 11, 12], "Saturn": [3, 5, 6, 11],
               "Lagna": [1, 3, 4, 6, 10, 11]},
}


def ashtakavarga(chart):
    """Return (bav, sav): bav[planet] = 12 bindu counts by sign (Aries..Pisces)."""
    pos = {p["name"]: p["sign_index"] for p in chart["planets"]}
    pos["Lagna"] = chart["ascendant"]["sign_index"]
    bav = {}
    for planet, table in AV_TABLE.items():
        bav[planet] = [sum(1 for c in AV_CONTRIBUTORS if (s - pos[c]) % 12 + 1 in table[c])
                       for s in range(12)]
    sav = [sum(bav[p][s] for p in bav) for s in range(12)]
    return bav, sav


def print_ashtakavarga(bav, sav, asc_sign):
    print("\nBhinnashtakavarga (bindus by sign)          house numbers are from the natal Lagna")
    hdr = f"{'':<9}" + "".join(f"{s[:3]:>5}" for s in SIGNS) + f"{'Total':>7}"
    print(hdr)
    print(f"{'House':<9}" + "".join(f"{(s - asc_sign) % 12 + 1:>5}" for s in range(12)))
    print("-" * len(hdr))
    for planet, row in bav.items():
        print(f"{planet:<9}" + "".join(f"{v:>5}" for v in row) + f"{sum(row):>7}")
    print("-" * len(hdr))
    print(f"{'SAV':<9}" + "".join(f"{v:>5}" for v in sav) + f"{sum(sav):>7}")


# ---------------------------------------------------------------- transits
TRANSIT_BODIES = ["Jupiter", "Saturn", "Rahu", "Ketu"]
SADE_SATI = {12: "Sade Sati (rising)", 1: "Sade Sati (peak)", 2: "Sade Sati (setting)"}
KANTAKA = {1, 4, 7, 10}   # Saturn in a kendra from the natal Moon


def _months(start, end):
    y, m = map(int, start.split("-")[:2])
    ey, em = map(int, end.split("-")[:2])
    if (y, m) > (ey, em):
        raise ValueError("--transit-range START must not be after END")
    while (y, m) <= (ey, em):
        yield y, m
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def transit_positions(when_local, offset, true_node=False):
    """Sidereal Jupiter, Saturn, Rahu, Ketu at a local datetime. Returns {name: (lon, retro)}."""
    utc = when_local - timedelta(hours=offset)
    jd = swe.julday(utc.year, utc.month, utc.day, utc.hour + utc.minute / 60)
    flags = swe.FLG_SWIEPH | swe.FLG_SIDEREAL | swe.FLG_SPEED
    out = {}
    for name, pid in (("Jupiter", swe.JUPITER), ("Saturn", swe.SATURN)):
        xx, _ = swe.calc_ut(jd, pid, flags)
        out[name] = (xx[0] % 360, xx[3] < 0)
    xx, _ = swe.calc_ut(jd, swe.TRUE_NODE if true_node else swe.MEAN_NODE, flags)
    out["Rahu"] = (xx[0] % 360, True)
    out["Ketu"] = ((xx[0] + 180) % 360, True)
    return out


def compute_transits(chart, start, end, sav):
    """Monthly transits (1st of each month, 12:00 birth-zone time) over START..END (YYYY-MM)."""
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    asc = chart["ascendant"]["sign_index"]
    moon = next(p["sign_index"] for p in chart["planets"] if p["name"] == "Moon")
    zone, tz = chart["input"]["zone"], chart["input"]["utc_offset"]
    rows = []
    for y, m in _months(start, end):
        when = datetime(y, m, 1, 12, 0)
        offset = resolve_offset(when, zone, None if zone else tz)
        pos = transit_positions(when, offset, chart["input"]["true_node"])
        row = {"month": f"{y}-{m:02d}", "bodies": {}}
        for name in TRANSIT_BODIES:
            lon, retro = pos[name]
            s = int(lon // 30)
            row["bodies"][name] = {
                "sign": SIGNS[s], "degree": lon % 30, "retrograde": retro,
                "from_lagna": (s - asc) % 12 + 1, "from_moon": (s - moon) % 12 + 1,
                "sav": sav[s]}
        sat_from_moon = row["bodies"]["Saturn"]["from_moon"]
        flags = []
        if sat_from_moon in SADE_SATI:
            flags.append(SADE_SATI[sat_from_moon])
        if sat_from_moon in KANTAKA:
            flags.append(f"Kantaka Shani ({sat_from_moon} from Moon)")
        row["flags"] = flags
        rows.append(row)
    return rows


def print_transits(rows, chart):
    moon = next(p for p in chart["planets"] if p["name"] == "Moon")
    print(f"\nTransits (1st of month, 12:00 local)   natal Lagna {chart['ascendant']['sign']}, "
          f"natal Moon {moon['sign']}")
    print("Cells: sign degree [R]  L=house from Lagna  M=house from Moon  SAV=bindus of that sign")
    w = 30
    hdr = f"{'Month':<9}" + "".join(f"{n:<{w}}" for n in TRANSIT_BODIES) + "Saturn flags"
    print(hdr)
    print("-" * (len(hdr) + 20))
    for r in rows:
        cells = []
        for n in TRANSIT_BODIES:
            b = r["bodies"][n]
            retro = "R" if b["retrograde"] and n in ("Jupiter", "Saturn") else " "
            cells.append(f"{b['sign'][:3]} {int(b['degree']):>2}° {retro} "
                         f"L{b['from_lagna']:<2} M{b['from_moon']:<2} SAV{b['sav']:<3}".ljust(w))
        print(f"{r['month']:<9}" + "".join(cells) + "; ".join(r["flags"]))


def main():
    ap = argparse.ArgumentParser(description="Sidereal (Lahiri) chart + Vimshottari dasha")
    ap.add_argument("--date", required=True, help="YYYY-MM-DD (local)")
    ap.add_argument("--time", required=True, help="HH:MM[:SS] (local)")
    ap.add_argument("--tz", type=float, default=None, help="UTC offset in hours (IST = 5.5)")
    ap.add_argument("--zone", default=None, help="IANA zone, e.g. Asia/Kolkata (one of --tz/--zone is required)")
    ap.add_argument("--lat", type=float, required=True, help="latitude, +N")
    ap.add_argument("--lon", type=float, required=True, help="longitude, +E")
    ap.add_argument("--place", default="", help="label for the output only")
    ap.add_argument("--true-node", action="store_true", help="use true node (default: mean node)")
    ap.add_argument("--ephe", default=None, help="path to Swiss Ephemeris .se1 files (optional)")
    ap.add_argument("--varga", default=None,
                    help="comma list of divisional charts: " + ",".join(VARGA_NAMES))
    ap.add_argument("--ashtakavarga", action="store_true",
                    help="print Bhinnashtakavarga and Sarvashtakavarga tables")
    ap.add_argument("--transit-range", nargs=2, metavar=("START", "END"),
                    help="monthly Jupiter/Saturn/Rahu/Ketu transits, YYYY-MM YYYY-MM")
    args = ap.parse_args()
    if args.tz is None and not args.zone:
        ap.error("give --tz (UTC offset in hours) or --zone (IANA time zone)")
    vargas = []
    if args.varga:
        vargas = [v.strip().upper() for v in args.varga.split(",") if v.strip()]
        bad = [v for v in vargas if v not in VARGA_NAMES]
        if bad:
            ap.error(f"unknown varga {', '.join(bad)}; choose from {', '.join(VARGA_NAMES)}")
    c = compute_chart(args.date, args.time, args.lat, args.lon, tz_hours=args.tz, zone=args.zone,
                      true_node=args.true_node, ephe_path=args.ephe)
    print_chart(c, args.place)
    for v in vargas:
        print_varga(compute_varga(c, v))
    if args.ashtakavarga or args.transit_range:
        bav, sav = ashtakavarga(c)
        if args.ashtakavarga:
            print_ashtakavarga(bav, sav, c["ascendant"]["sign_index"])
        if args.transit_range:
            try:
                rows = compute_transits(c, *args.transit_range, sav)
            except ValueError as e:
                ap.error(str(e))
            print_transits(rows, c)


if __name__ == "__main__":
    main()
