"""Render the paper's figures from experiments/results/*.csv.

    pip install -r requirements-experiments.txt
    python -m experiments.plot_figures

Writes PNG (300 dpi) files to experiments/results/figures/. Colours are the first
categorical slots of a colour-vision-deficiency-validated palette; every series also
has its own marker and line style, so the figures read in greyscale print.
"""
from __future__ import annotations

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

RESULTS = Path(__file__).parent / "results"
FIGS = RESULTS / "figures"
BLUE, ORANGE, AQUA, YELLOW = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e6e5e1"

plt.rcParams.update({
    "font.family": "serif", "font.serif": ["Times New Roman", "DejaVu Serif"], "font.size": 9,
    "axes.edgecolor": MUTED, "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": GRID,
    "grid.linewidth": 0.6, "legend.frameon": False, "savefig.dpi": 300, "savefig.bbox": "tight",
})


def read(name: str) -> list[dict]:
    with (RESULTS / f"{name}.csv").open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def fig_architecture() -> None:
    fig, ax = plt.subplots(figsize=(7.0, 2.2))
    ax.set_axis_off()
    boxes = [("Simulator\n(scheduled incidents,\nhidden ground truth)", 0.0),
             ("Traces\n(PII redacted)", 1.45), ("Online evals\n(risk-based sample)", 2.75),
             ("Monitors\nratio · z-test · PSI", 4.05), ("Alerts", 5.35)]
    for label, x in boxes:
        ax.add_patch(FancyBboxPatch((x, 0.55), 1.15, 0.8, boxstyle="round,pad=0.02,rounding_size=0.06",
                                    fc="#eef4fc", ec=BLUE, lw=1))
        ax.text(x + 0.575, 0.95, label, ha="center", va="center", fontsize=7.5, color=INK)
    for i in range(len(boxes) - 1):
        x0 = boxes[i][1] + 1.15
        ax.annotate("", xy=(boxes[i + 1][1], 0.95), xytext=(x0, 0.95), arrowprops=dict(arrowstyle="->", color=MUTED, lw=1))
    ax.add_patch(FancyBboxPatch((4.05, -0.45), 2.45, 0.65, boxstyle="round,pad=0.02,rounding_size=0.06",
                                fc="#fdf0ea", ec=ORANGE, lw=1))
    ax.text(5.275, -0.12, "Monitoring evaluation: recall, delay,\nfalse alarms, negative controls", ha="center",
            va="center", fontsize=7.5, color=INK)
    ax.annotate("", xy=(5.9, 0.2), xytext=(5.9, 0.55), arrowprops=dict(arrowstyle="->", color=MUTED, lw=1))
    ax.plot([0.575, 0.575], [0.55, -0.12], color=MUTED, lw=1, ls="--")
    ax.annotate("", xy=(4.05, -0.12), xytext=(0.575, -0.12),
                arrowprops=dict(arrowstyle="->", color=MUTED, lw=1, linestyle="--"))
    ax.text(2.3, -0.02, "hidden ground truth (never read by monitors)", ha="center", va="bottom", fontsize=7, color=MUTED)
    ax.set_xlim(-0.1, 6.6)
    ax.set_ylim(-0.6, 1.45)
    fig.savefig(FIGS / "fig1_architecture.png")
    plt.close(fig)


def fig_thresholds() -> None:
    rows = read("e2_thresholds")
    fig, ax = plt.subplots(figsize=(3.4, 2.6))
    styles = {"0.0": (BLUE, "o", "-"), "0.5": (ORANGE, "s", "--"), "1.0": (AQUA, "^", "-."), "2.0": (YELLOW, "D", ":")}
    for scale, (color, marker, ls) in styles.items():
        pts = sorted(((float(r["quiet_alerts"]), float(r["recall_subtle"]), float(r["z_threshold"])) for r in rows
                      if r["min_effect_scale"] == scale), key=lambda p: p[2])
        ax.plot([p[0] + 0.01 for p in pts], [p[1] for p in pts], marker=marker, ls=ls, color=color, lw=1.5, ms=4,
                label=f"min effect ×{float(scale):g}")
    ax.set_xscale("log")
    ax.set_xlabel("False alarms per quiet run (log; +0.01 so zero is plotted)")
    ax.set_ylabel("Recall, subtle incidents")
    ax.set_ylim(0, 1.02)
    ax.legend(fontsize=7, loc="lower right")
    fig.savefig(FIGS / "fig2_threshold_tradeoff.png")
    plt.close(fig)


def fig_latency() -> None:
    rows = [r for r in read("e3_sensitivity") if r["parameter"] == "slow_fraction"]
    fig, ax = plt.subplots(figsize=(3.4, 2.4))
    for monitor, color, marker, ls in (("p95 monitor", BLUE, "o", "-"), ("mean monitor", ORANGE, "s", "--")):
        pts = sorted((float(r["value"]) * 100, float(r["detection_rate"]), float(r["ci_low"]), float(r["ci_high"]))
                     for r in rows if r["monitor"] == monitor)
        xs = [p[0] for p in pts]
        ax.fill_between(xs, [p[2] for p in pts], [p[3] for p in pts], color=color, alpha=0.12, lw=0)
        ax.plot(xs, [p[1] for p in pts], marker=marker, ls=ls, color=color, lw=1.5, ms=4, label=monitor.replace(" monitor", " latency rule"))
    ax.set_xlabel("Requests slowed by +3 s (%)")
    ax.set_ylabel("Detection rate (onset day)")
    ax.set_ylim(-0.02, 1.02)
    ax.legend(fontsize=7, loc="lower right")
    fig.savefig(FIGS / "fig3_latency_sensitivity.png")
    plt.close(fig)


def fig_sampling() -> None:
    rows = read("e4_sampling")
    fig, ax = plt.subplots(figsize=(3.4, 2.4))
    for risky, color, marker, ls, label in (("True", BLUE, "o", "-", "random + risk-based"),
                                            ("False", ORANGE, "s", "--", "random only")):
        pts = sorted((float(r["evals_per_day"]), float(r["detected_by_day7"]), float(r["sample_rate"]))
                     for r in rows if r["risk_based"] == risky)
        ax.plot([p[0] for p in pts], [p[1] for p in pts], marker=marker, ls=ls, color=color, lw=1.5, ms=4, label=label)
    ax.set_xscale("log")
    ax.set_xlabel("Online evaluations per day (log)")
    ax.set_ylabel("Model update detected\nbefore next incident")
    ax.set_ylim(-0.02, 1.02)
    ax.legend(fontsize=7, loc="lower right")
    fig.savefig(FIGS / "fig4_sampling_cost.png")
    plt.close(fig)


def main() -> int:
    FIGS.mkdir(parents=True, exist_ok=True)
    fig_architecture()
    fig_thresholds()
    fig_latency()
    fig_sampling()
    print(f"figures written to {FIGS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
