#!/usr/bin/env python3
"""Web front end for chart.py.

Run:  .venv/bin/python app.py            (http://localhost:5000)
      PORT=8080 HOST=127.0.0.1 .venv/bin/python app.py
"""
import os
import re
from datetime import date as Date
from pathlib import Path
from zoneinfo import ZoneInfo, available_timezones

import markdown
import nh3
from flask import Flask, abort, jsonify, render_template, request

from chart import compute_chart

app = Flask(__name__)
ZONES = sorted(z for z in available_timezones() if "/" in z and not z.startswith(("Etc/", "SystemV/")))

# Weekly Andhra Pradesh investment reports written by the ap-investment-agent timer.
AP_REPORT_DIR = Path(os.environ.get("AP_REPORT_DIR", "/opt/ap-investment-agent/reports"))
REPORT_NAME = re.compile(r"^(\d{4}-\d{2}-\d{2})\.md$")
PERIOD_LINE = re.compile(r"^_(.+ to .+)_$", re.M)
SAFE_TAGS = {"h1", "h2", "h3", "h4", "p", "ul", "ol", "li", "strong", "em", "code", "pre",
             "blockquote", "table", "thead", "tbody", "tr", "th", "td", "a", "hr", "br"}


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


def list_reports():
    """Newest first: [{"date": "YYYY-MM-DD", "label": "22 Nov 2026", "period": "..."}]."""
    out = []
    if AP_REPORT_DIR.is_dir():
        for f in AP_REPORT_DIR.iterdir():
            m = REPORT_NAME.match(f.name)
            if not m or not f.is_file():
                continue
            try:
                d = Date.fromisoformat(m.group(1))
                head = f.read_text(encoding="utf-8", errors="replace")[:400]
            except (ValueError, OSError):
                continue
            p = PERIOD_LINE.search(head)
            out.append({"date": m.group(1), "label": d.strftime("%d %b %Y"),
                        "period": p.group(1) if p else ""})
    return sorted(out, key=lambda r: r["date"], reverse=True)


def render_report(day):
    path = AP_REPORT_DIR / f"{day}.md"
    text = path.read_text(encoding="utf-8", errors="replace")
    # Drop the agent's own title line; the page provides one.
    text = re.sub(r"\A# Andhra Pradesh investment report\s*\n", "", text)
    html = markdown.markdown(text, extensions=["tables", "sane_lists"])
    # Report text comes from web research: allow only plain formatting and http(s) links.
    return nh3.clean(html, tags=SAFE_TAGS, attributes={"a": {"href", "title"}},
                     url_schemes={"http", "https"}, link_rel="noopener noreferrer nofollow")


@app.get("/ap-reports")
@app.get("/ap-reports/<day>")
def ap_reports(day=None):
    reports = list_reports()
    if day is None:
        current = reports[0] if reports else None
    else:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
            abort(404)
        current = next((r for r in reports if r["date"] == day), None)
        if current is None:
            abort(404)
    body = render_report(current["date"]) if current else None
    return render_template("ap_reports.html", reports=reports, current=current, body=body,
                           report_dir=str(AP_REPORT_DIR))


if __name__ == "__main__":
    app.run(host=os.environ.get("HOST", "0.0.0.0"), port=int(os.environ.get("PORT", 5000)),
            debug=bool(os.environ.get("DEBUG")))
