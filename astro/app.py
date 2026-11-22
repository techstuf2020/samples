#!/usr/bin/env python3
"""Web front end for chart.py.

Run:  .venv/bin/python app.py            (http://localhost:5000)
      PORT=8080 HOST=127.0.0.1 .venv/bin/python app.py
"""
import os
from zoneinfo import ZoneInfo, available_timezones

from flask import Flask, jsonify, render_template, request

from chart import compute_chart

app = Flask(__name__)
ZONES = sorted(z for z in available_timezones() if "/" in z and not z.startswith(("Etc/", "SystemV/")))


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/zones")
def zones():
    return jsonify(ZONES)


@app.post("/api/chart")
def chart():
    data = request.get_json(silent=True) or {}
    try:
        date = str(data["date"]).strip()
        time = str(data["time"]).strip()
        lat = float(data["lat"])
        lon = float(data["lon"])
        zone = (data.get("zone") or "").strip() or None
        tz = data.get("utc_offset")
        tz = None if tz in (None, "") else float(tz)
        if zone:
            ZoneInfo(zone)  # validate
        if zone is None and tz is None:
            raise ValueError("Choose a time zone or enter a UTC offset")
        result = compute_chart(date, time, lat, lon, tz_hours=tz, zone=zone,
                               true_node=bool(data.get("true_node")))
    except KeyError as e:
        return jsonify(error=f"Missing field: {e.args[0]}"), 400
    except Exception as e:  # bad dates, zones, numbers
        return jsonify(error=str(e)), 400
    result["input"]["name"] = str(data.get("name", ""))[:100]
    result["input"]["place"] = str(data.get("place", ""))[:200]
    return jsonify(result)


if __name__ == "__main__":
    app.run(host=os.environ.get("HOST", "0.0.0.0"), port=int(os.environ.get("PORT", 5000)),
            debug=bool(os.environ.get("DEBUG")))
