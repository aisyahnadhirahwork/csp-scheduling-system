"""Generate evaluation charts from the 500-patient load test CSV.

Produces two figures:
  1. Runtime vs number of patients (cumulative average solve time)
  2. Penalty distribution summary (bar chart by penalty type)

Usage:
    python generate_charts.py
"""

import csv
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

CSV_PATH = os.path.join(os.path.dirname(__file__), "load_test_500_results.csv")
OUT_DIR = os.path.dirname(__file__)


def load_data():
    rows = []
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            r["time_s"] = float(r["time_s"])
            r["penalty"] = int(r["penalty"]) if r["success"] == "True" else None
            r["spec_pen"] = int(r["spec_pen"])
            r["gen_pen"] = int(r["gen_pen"])
            r["time_pen"] = int(r["time_pen"])
            r["index"] = int(r["index"])
            rows.append(r)
    return rows


def chart_runtime(rows):
    """Chart 1: Average solve time (ms) as patient count grows."""
    checkpoints = [50, 100, 150, 200, 250, 300, 350, 400, 450, 500]
    avg_times = []
    for n in checkpoints:
        subset = rows[:n]
        avg_ms = sum(r["time_s"] for r in subset) / len(subset) * 1000
        avg_times.append(avg_ms)

    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.plot(checkpoints, avg_times, "s-", color="#2980b9", linewidth=2,
            markersize=7, label="CP-SAT Solver")
    ax.set_xlabel("Number of Patients Processed", fontsize=11)
    ax.set_ylabel("Average Solve Time (ms)", fontsize=11)
    ax.set_title("Solver Runtime vs Number of Patients", fontsize=13, fontweight="bold")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=10)

    # annotate first and last
    ax.annotate(f"{avg_times[0]:.1f} ms", (checkpoints[0], avg_times[0]),
                textcoords="offset points", xytext=(10, 10), fontsize=9)
    ax.annotate(f"{avg_times[-1]:.1f} ms", (checkpoints[-1], avg_times[-1]),
                textcoords="offset points", xytext=(-50, 10), fontsize=9)

    plt.tight_layout()
    path = os.path.join(OUT_DIR, "chart_runtime_vs_patients.png")
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"Saved: {path}")


def chart_penalty_summary(rows):
    """Chart 2: Penalty breakdown — perfect vs imperfect, by type."""
    matched = [r for r in rows if r["penalty"] is not None]
    perfect = sum(1 for r in matched if r["penalty"] == 0)
    imperfect = len(matched) - perfect

    spec_mismatch = sum(1 for r in matched if r["spec_pen"] > 0)
    gen_mismatch = sum(1 for r in matched if r["gen_pen"] > 0)
    time_mismatch = sum(1 for r in matched if r["time_pen"] > 0)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5))

    # Pie: perfect vs imperfect
    ax1.pie([perfect, imperfect],
            labels=[f"Perfect Match\n({perfect})", f"Imperfect Match\n({imperfect})"],
            colors=["#2ecc71", "#e74c3c"], autopct="%1.1f%%",
            startangle=90, textprops={"fontsize": 10})
    ax1.set_title("Allocation Quality", fontsize=13, fontweight="bold")

    # Bar: mismatch counts by type
    categories = ["Specialty\nMismatch", "Gender\nMismatch", "Time\nMismatch"]
    counts = [spec_mismatch, gen_mismatch, time_mismatch]
    colors = ["#e74c3c", "#f39c12", "#3498db"]
    bars = ax2.bar(categories, counts, color=colors, width=0.5)
    ax2.set_ylabel("Number of Patients", fontsize=11)
    ax2.set_title("Penalty Breakdown by Constraint Type", fontsize=13, fontweight="bold")
    ax2.grid(True, axis="y", alpha=0.3)
    for bar, count in zip(bars, counts):
        ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                 str(count), ha="center", fontsize=10, fontweight="bold")

    plt.tight_layout()
    path = os.path.join(OUT_DIR, "chart_penalty_summary.png")
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"Saved: {path}")


if __name__ == "__main__":
    data = load_data()
    print(f"Loaded {len(data)} records from CSV")
    chart_runtime(data)
    chart_penalty_summary(data)
    print("Done.")
