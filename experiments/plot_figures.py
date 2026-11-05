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
    """Column-width layout: pipeline in two rows, monitoring evaluation below."""
    fig, ax = plt.subplots(figsize=(3.4, 2.7))
    ax.set_axis_off()

    def box(x, y, w, h, label, fc="#eef4fc", ec=BLUE):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.05", fc=fc, ec=ec, lw=1))
        ax.text(x + w / 2, y + h / 2, label, ha="center", va="center", fontsize=7, color=INK)

    def arrow(x0, y0, x1, y1, dashed=False):
        ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                    arrowprops=dict(arrowstyle="->", color=MUTED, lw=1, linestyle="--" if dashed else "-"))

    w, h = 1.0, 0.62
    box(0.0, 2.2, w, h, "Simulator\n(scheduled\nincidents)")
    box(1.3, 2.2, w, h, "Traces\n(PII redacted)")
    box(2.6, 2.2, w, h, "Online evals\n(risk-based\nsample)")
    box(2.6, 1.15, w, h, "Monitors\nratio · z-test\n· PSI")
    box(1.3, 1.15, w, h, "Alerts")
    box(0.0, 0.0, 3.6, 0.6, "Monitoring evaluation: recall, delay,\nfalse alarms, negative controls", fc="#fdf0ea", ec=ORANGE)
    arrow(1.0, 2.51, 1.3, 2.51)
    arrow(2.3, 2.51, 2.6, 2.51)
    arrow(3.1, 2.2, 3.1, 1.77)
    arrow(2.6, 1.46, 2.3, 1.46)
    arrow(1.8, 1.15, 1.8, 0.6)
    ax.plot([0.5, 0.5], [2.2, 0.6], color=MUTED, lw=1, ls="--")
    ax.annotate("", xy=(0.5, 0.6), xytext=(0.5, 0.75), arrowprops=dict(arrowstyle="->", color=MUTED, lw=1))
    ax.text(0.58, 1.75, "hidden ground truth\n(never read\nby monitors)", fontsize=6, color=MUTED, va="center", ha="left")
    ax.set_xlim(-0.05, 3.65)
    ax.set_ylim(-0.05, 2.87)
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
