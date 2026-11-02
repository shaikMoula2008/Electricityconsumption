import io
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")  # draw to memory, no window
import matplotlib.pyplot as plt
from flask import Blueprint, Response
from sqlalchemy import text

from db import engine
from routes.analysis import (calculate_consumption, default_factor,
                             find_high_usage, summarize)
from utils import error

charts_bp = Blueprint("charts", __name__, url_prefix="/charts")


def fig_to_png(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight")
    plt.close(fig)
    return Response(buf.getvalue(), mimetype="image/png")


@charts_bp.get("/trend/<int:meter_id>.png")
def trend_chart(meter_id):
    with engine.connect() as conn:
        code = conn.execute(
            text("SELECT meter_code FROM meters WHERE meter_id = :m"), {"m": meter_id}
        ).scalar()
        if code is None:
            return error("meter not found", 404)
        rows = conn.execute(
            text("SELECT reading_date, cumulative_kwh FROM meter_readings "
                 "WHERE meter_id = :m ORDER BY reading_date"),
            {"m": meter_id},
        ).mappings().all()

    periods = calculate_consumption(rows)
    if not periods:
        return error("not enough readings to draw a chart", 400)

    monthly = summarize(periods, "monthly")
    _, limit, flagged = find_high_usage(periods, default_factor())
    flagged_months = {p["period_start"][:7] for p in flagged}

    labels = [m["period"] for m in monthly]
    values = [m["total_kwh"] for m in monthly]
    colors = ["#d9534f" if label in flagged_months else "#4a90d9" for label in labels]
    x = list(range(len(labels)))

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(x, values, color=colors)
    if limit:
        ax.axhline(limit, linestyle="--", color="gray",
                   label=f"High-usage limit ({limit} kWh)")
        ax.legend()
    for i, m in enumerate(monthly):
        if m["reset_periods"]:
            ax.annotate("meter reset", (i, 0), ha="center", va="bottom", color="gray")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.set_title(f"Monthly consumption: meter {code}")
    ax.set_xlabel("Month")
    ax.set_ylabel("Consumption (kWh)")
    return fig_to_png(fig)


@charts_bp.get("/compare.png")
def compare_chart():
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT c.consumer_code, m.meter_id, r.reading_date, r.cumulative_kwh "
                 "FROM consumers c "
                 "JOIN meters m ON m.consumer_id = c.consumer_id "
                 "JOIN meter_readings r ON r.meter_id = m.meter_id "
                 "ORDER BY m.meter_id, r.reading_date")
        ).mappings().all()

    by_meter = defaultdict(list)
    for r in rows:
        by_meter[(r["consumer_code"], r["meter_id"])].append(
            {"reading_date": r["reading_date"], "cumulative_kwh": r["cumulative_kwh"]})

    totals = defaultdict(float)
    for (code, _), readings in by_meter.items():
        for p in calculate_consumption(readings):
            if p["status"] == "valid":
                totals[code] += p["consumption_kwh"]

    if not totals:
        return error("no consumption data to chart", 400)

    codes = sorted(totals)
    fig, ax = plt.subplots(figsize=(7, 4))
    bars = ax.bar(codes, [totals[c] for c in codes], color="#4a90d9")
    ax.bar_label(bars, fmt="%.0f")
    ax.set_title("Total valid consumption by consumer")
    ax.set_xlabel("Consumer")
    ax.set_ylabel("Consumption (kWh)")
    return fig_to_png(fig)
NAN = float("nan")


def load_meter(conn, meter_id):
    """Returns (meter_code, rows), or (None, None) if the meter is missing."""
    code = conn.execute(
        text("SELECT meter_code FROM meters WHERE meter_id = :m"), {"m": meter_id}
    ).scalar()
    if code is None:
        return None, None
    rows = conn.execute(
        text("SELECT reading_date, cumulative_kwh FROM meter_readings "
             "WHERE meter_id = :m ORDER BY reading_date"),
        {"m": meter_id},
    ).mappings().all()
    return code, rows


# ---------- LINE: cumulative readings over time ----------
@charts_bp.get("/readings/<int:meter_id>.png")
def readings_line(meter_id):
    with engine.connect() as conn:
        code, rows = load_meter(conn, meter_id)
    if code is None:
        return error("meter not found", 404)
    if len(rows) < 2:
        return error("not enough readings to draw a graph", 400)

    dates = [r["reading_date"] for r in rows]
    values = [float(r["cumulative_kwh"]) for r in rows]
    resets = [i for i in range(1, len(values)) if values[i] < values[i - 1]]

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(dates, values, marker="o", color="#4a90d9", label="Meter reading")
    if resets:
        ax.scatter([dates[i] for i in resets], [values[i] for i in resets],
                   s=120, color="#d9534f", zorder=3, label="Possible meter reset")
    ax.set_title(f"Cumulative meter readings: meter {code}")
    ax.set_xlabel("Reading date")
    ax.set_ylabel("Cumulative reading (kWh)")
    ax.grid(alpha=0.3)
    ax.legend()
    fig.autofmt_xdate()
    return fig_to_png(fig)


# ---------- LINE: monthly consumption trend ----------
@charts_bp.get("/line/<int:meter_id>.png")
def consumption_line(meter_id):
    with engine.connect() as conn:
        code, rows = load_meter(conn, meter_id)
    if code is None:
        return error("meter not found", 404)

    periods = calculate_consumption(rows)
    if not periods:
        return error("not enough readings to draw a graph", 400)

    monthly = summarize(periods, "monthly")
    _, limit, flagged = find_high_usage(periods, default_factor())
    flagged_months = {p["period_start"][:7] for p in flagged}

    labels = [m["period"] for m in monthly]
    # A month with only a reset has no valid number, so the line breaks there.
    values = [m["total_kwh"] if m["valid_periods"] else NAN for m in monthly]
    x = list(range(len(labels)))

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(x, values, marker="o", color="#4a90d9", label="Monthly consumption")
    hot = [i for i, label in enumerate(labels) if label in flagged_months]
    if hot:
        ax.scatter(hot, [values[i] for i in hot], s=120, color="#d9534f",
                   zorder=3, label="High usage")
    if limit:
        ax.axhline(limit, linestyle="--", color="gray",
                   label=f"High-usage limit ({limit} kWh)")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.set_title(f"Monthly consumption trend: meter {code}")
    ax.set_xlabel("Month")
    ax.set_ylabel("Consumption (kWh)")
    ax.grid(alpha=0.3)
    ax.legend()
    return fig_to_png(fig)


# ---------- LINE: all meters on one graph ----------
@charts_bp.get("/compare-lines.png")
def compare_lines():
    with engine.connect() as conn:
        meters = conn.execute(
            text("SELECT m.meter_id, m.meter_code, c.consumer_code "
                 "FROM meters m JOIN consumers c ON c.consumer_id = m.consumer_id "
                 "ORDER BY m.meter_id")
        ).mappings().all()
        series = []
        for m in meters:
            _, rows = load_meter(conn, m["meter_id"])
            periods = calculate_consumption(rows)
            if periods:
                series.append((f"{m['meter_code']} ({m['consumer_code']})",
                               summarize(periods, "monthly")))

    if not series:
        return error("no consumption data to graph", 400)

    months = sorted({row["period"] for _, monthly in series for row in monthly})
    x = list(range(len(months)))

    fig, ax = plt.subplots(figsize=(9, 4.5))
    for label, monthly in series:
        by_month = {row["period"]: row for row in monthly}
        values = [
            by_month[mo]["total_kwh"]
            if mo in by_month and by_month[mo]["valid_periods"] else NAN
            for mo in months
        ]
        ax.plot(x, values, marker="o", label=label)
    ax.set_xticks(x)
    ax.set_xticklabels(months, rotation=45, ha="right")
    ax.set_title("Monthly consumption by meter")
    ax.set_xlabel("Month")
    ax.set_ylabel("Consumption (kWh)")
    ax.grid(alpha=0.3)
    ax.legend()
    return fig_to_png(fig)