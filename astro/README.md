# Jyotish Chart

Sidereal (Lahiri) birth charts with nakshatra, pada, whole-sign houses, retrograde
status and Vimshottari dasha, computed with the Swiss Ephemeris (pyswisseph).

## Setup

```bash
python3 -m venv .venv            # needs python3-venv and python3-dev (to build pyswisseph)
.venv/bin/pip install -r requirements.txt
```

## Web app

```bash
.venv/bin/python app.py          # http://localhost:5000
PORT=8080 HOST=127.0.0.1 .venv/bin/python app.py
```

- Pick a built-in city, search online (OpenStreetMap Nominatim, called from the browser),
  or type latitude/longitude.
- The time zone is an IANA zone, so historical offsets and daylight saving are applied
  for the birth date. Use the UTC-offset override for local mean time or doubtful records.
- South or North Indian chart, positions table, all mahadashas with antardashas
  (the running period is highlighted).
- Saved charts live in the viewer's browser only; nothing is stored on the server.
- `POST /api/chart` with JSON `{date, time, lat, lon, zone | utc_offset, true_node}`
  returns the full chart as JSON.

`app.py` uses Flask's development server. For a shared deployment run it behind a
WSGI server, e.g. `pip install gunicorn && gunicorn -b 0.0.0.0:5000 app:app`.

## Command line

```bash
.venv/bin/python chart.py --date 1990-05-17 --time 06:45 --lat 17.385 --lon 78.4867 --zone Asia/Kolkata
```

## Conventions

- Ayanamsa: Lahiri. Houses: whole sign from the Lagna.
- Rahu/Ketu: mean node by default (`--true-node` / checkbox for true node); Ketu = Rahu + 180°.
- Dasha year = 365.25 days; dasha dates are in birth-place local time.
- Without `.se1` ephemeris files Swiss Ephemeris uses its built-in Moshier model
  (sub-arcminute accuracy). Pass `--ephe <dir>` / `ephe_path` to use the files.
