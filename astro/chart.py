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
    args = ap.parse_args()
    if args.tz is None and not args.zone:
        ap.error("give --tz (UTC offset in hours) or --zone (IANA time zone)")
    c = compute_chart(args.date, args.time, args.lat, args.lon, tz_hours=args.tz, zone=args.zone,
                      true_node=args.true_node, ephe_path=args.ephe)
    print_chart(c, args.place)


if __name__ == "__main__":
    main()
