#!/usr/bin/env python3
"""Render steady-state write throughput and latency charts for etcd benchmarks.

Shared across series parts: renders standalone single-version charts (e.g., Part 1 v0.4.9,
Part 2 v2.3.8) as well as multi-version comparison overlays (e.g., v0.4.9 vs. v2.3.8).
Uses linear axes so scaling shape (linear vs. sub-linear saturation) reads directly.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Dict, List

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import matplotlib as mpl  # noqa: E402

mpl.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402
import numpy as np  # noqa: E402

mpl.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial", "Helvetica"]
mpl.rcParams["font.monospace"] = ["DejaVu Sans Mono", "Menlo", "Consolas"]

# Shared dark-slate palette matching the blog series animations
BG_COLOR = "#0f172a"
PANEL_BG = "#111c33"
BOX_BG = "#1e293b"
BOX_BORDER = "#334155"
BOX_BORDER_HI = "#475569"

TEXT_MAIN = "#f8fafc"
TEXT_SOFT = "#cbd5e1"
TEXT_SUB = "#94a3b8"
TEXT_DIM = "#64748b"

ACCENT_BLUE = "#38bdf8"
ACCENT_AMBER = "#f59e0b"
ACCENT_VIOLET = "#a78bfa"
ACCENT_TEAL = "#2dd4bf"
ACCENT_GREEN = "#10b981"
ACCENT_CORAL = "#fb7185"

# Points to annotate on a linear 0..256 x-axis without crowding the dense low-c cluster (1,2,4,8,16)
LABEL_CONCS = {1, 32, 64, 128, 256}


def _style_axis(ax) -> None:
    ax.set_facecolor(PANEL_BG)
    for spine in ax.spines.values():
        spine.set_color(BOX_BORDER)
        spine.set_linewidth(1.2)
    ax.tick_params(colors=TEXT_SOFT, labelsize=10.5, length=4, width=1.0)
    ax.grid(True, which="major", color=BOX_BORDER, alpha=0.45, linestyle="--", linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)


def _subtitle(datasets: List[Dict]) -> str:
    dur = int(round(datasets[0]["experiment1_concurrency_scaling"].get("measurement_seconds", 15)))
    storage = datasets[0].get("environment", {}).get("etcd_resources", {}).get("storage", "")
    storage_tag = "tmpfs" if "tmpfs" in storage.lower() else "Linux ext4"
    return (
        f"Direct-to-leader PUT /v2/keys (1,000 keys × 256 B values, HTTP keep-alive, "
        f"{dur} s per c, {storage_tag}, snapshots disabled)"
    )


def _fmt_ms(v: float) -> str:
    if v >= 20:
        return f"{v:.0f} ms"
    return f"{v:.1f} ms"


def _fmt_wps(v: float) -> str:
    if v >= 100:
        return f"{v:,.0f} w/s"
    return f"{v:.1f} w/s"


def render_write_throughput(datasets: List[Dict], out_path: Path) -> None:
    fig, ax = plt.subplots(
        figsize=(10.5, 6.2),
        dpi=180,
        facecolor=BG_COLOR,
    )
    fig.subplots_adjust(left=0.105, right=0.955, top=0.81, bottom=0.13)
    _style_axis(ax)

    single_mode = len(datasets) == 1
    line_colors = [ACCENT_BLUE, ACCENT_GREEN, ACCENT_VIOLET]

    max_conc = 0
    max_tps = 0.0

    for idx, data in enumerate(datasets):
        ver = data["version"]
        runs = data["experiment1_concurrency_scaling"]["runs"]
        concs = np.array([r["concurrency"] for r in runs], dtype=float)
        tps = np.array([r["throughput_wps"] for r in runs], dtype=float)
        max_conc = max(max_conc, int(np.max(concs)))
        max_tps = max(max_tps, float(np.max(tps)))

        color = line_colors[idx % len(line_colors)]

        if single_mode:
            ideal = tps[0] * (concs / concs[0])
            ax.plot(
                concs,
                ideal,
                color=TEXT_DIM,
                linewidth=1.5,
                linestyle="--",
                alpha=0.85,
                label=f"Ideal linear scaling (from c = {int(concs[0])})",
                zorder=3,
            )
            max_tps = max(max_tps, float(np.max(ideal)))

        if single_mode:
            ax.fill_between(concs, 0, tps, color=color, alpha=0.10, zorder=2)

        ax.plot(
            concs,
            tps,
            color=color,
            linewidth=2.6,
            marker="o",
            markersize=6.8,
            markerfacecolor=color,
            markeredgecolor=BG_COLOR,
            markeredgewidth=1.3,
            label=f"etcd {ver} throughput",
            zorder=5 + idx,
        )

        if single_mode:
            for xi, val in zip(concs, tps):
                c_int = int(xi)
                if c_int not in LABEL_CONCS:
                    continue
                if c_int == 1:
                    xytext = (0, 14)
                    ha, va = "center", "bottom"
                elif c_int == max_conc:
                    xytext = (0, -14)
                    ha, va = "center", "top"
                else:
                    xytext = (6, -13)
                    ha, va = "left", "top"
                ax.annotate(
                    _fmt_wps(val),
                    xy=(xi, val),
                    xytext=xytext,
                    textcoords="offset points",
                    ha=ha,
                    va=va,
                    color=TEXT_MAIN,
                    fontsize=9.3,
                    fontweight="bold",
                    zorder=7 + idx,
                )

    if not single_mode:
        series_maps = [
            {r["concurrency"]: r["throughput_wps"] for r in d["experiment1_concurrency_scaling"]["runs"]}
            for d in datasets
        ]
        for idx, data in enumerate(datasets):
            color = line_colors[idx % len(line_colors)]
            for r in data["experiment1_concurrency_scaling"]["runs"]:
                c_int = int(r["concurrency"])
                if c_int not in LABEL_CONCS:
                    continue
                xi = float(c_int)
                val = float(r["throughput_wps"])
                others = [m[c_int] for j, m in enumerate(series_maps) if j != idx and c_int in m]
                is_highest = all(val >= o for o in others)
                y_off = 11 if is_highest else -14
                va = "bottom" if is_highest else "top"
                ha = "left" if c_int == 1 else "center"
                x_off = 8 if c_int == 1 else 0
                ax.annotate(
                    _fmt_wps(val),
                    xy=(xi, val),
                    xytext=(x_off, y_off),
                    textcoords="offset points",
                    ha=ha,
                    va=va,
                    color=color,
                    fontsize=9.2,
                    fontweight="bold",
                    zorder=7 + idx,
                )

    xticks = [0, 32, 64, 96, 128, 160, 192, 224, 256] if max_conc <= 256 else np.linspace(0, max_conc, 9)
    ax.set_xticks(xticks)
    ax.set_xticklabels([f"{int(t)}" for t in xticks], fontsize=10.5, fontweight="bold")
    ax.set_xlim(-14, max_conc + 18)

    ax.set_ylim(0, max_tps * 1.18)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f"{int(y):,}"))

    ax.set_xlabel("Concurrent Writers (c)", color=TEXT_SOFT, fontsize=11.0, labelpad=8)
    ax.set_ylabel("Throughput (writes / sec)", color=TEXT_SOFT, fontsize=11.0, labelpad=8)

    leg = ax.legend(
        loc="upper left",
        frameon=True,
        facecolor=BOX_BG,
        edgecolor=BOX_BORDER_HI,
        labelcolor=TEXT_MAIN,
        fontsize=9.8,
    )
    leg.set_zorder(10)

    title_ver = datasets[0]["version"] if single_mode else " vs. ".join(d["version"] for d in datasets)
    fig.text(
        0.5,
        0.93,
        f"etcd {title_ver} — Steady-State Write Throughput (3-Node Cluster)",
        ha="center",
        va="center",
        color=TEXT_MAIN,
        fontsize=15.0,
        fontweight="bold",
    )
    fig.text(
        0.5,
        0.872,
        _subtitle(datasets),
        ha="center",
        va="center",
        color=TEXT_SUB,
        fontsize=9.8,
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=180, facecolor=BG_COLOR)
    plt.close(fig)
    print(f"[plot] Rendered {out_path}")


def render_write_latency(datasets: List[Dict], out_path: Path) -> None:
    fig, ax = plt.subplots(
        figsize=(10.5, 6.2),
        dpi=180,
        facecolor=BG_COLOR,
    )
    fig.subplots_adjust(left=0.095, right=0.955, top=0.81, bottom=0.13)
    _style_axis(ax)

    single_mode = len(datasets) == 1
    version_palette = [
        (ACCENT_CORAL, ACCENT_TEAL),
        (ACCENT_AMBER, ACCENT_GREEN),
    ]

    max_conc = 0
    max_lat = 0.0

    for idx, data in enumerate(datasets):
        ver = data["version"]
        runs = data["experiment1_concurrency_scaling"]["runs"]
        concs = np.array([r["concurrency"] for r in runs], dtype=float)
        p50 = np.array([r["latency_ms"]["p50"] for r in runs], dtype=float)
        p99 = np.array([r["latency_ms"]["p99"] for r in runs], dtype=float)
        max_conc = max(max_conc, int(np.max(concs)))
        max_lat = max(max_lat, float(np.max(p99)))

        c_p99, c_p50 = version_palette[idx % len(version_palette)]
        prefix = "" if single_mode else f"{ver} "
        ls_p99 = "-" if idx == 0 else "--"

        ax.fill_between(concs, p50, p99, color=c_p99, alpha=0.09 if single_mode else 0.06, zorder=2)
        ax.plot(
            concs,
            p99,
            color=c_p99,
            linewidth=2.5,
            linestyle=ls_p99,
            marker="s",
            markersize=6.6,
            markerfacecolor=c_p99,
            markeredgecolor=BG_COLOR,
            markeredgewidth=1.2,
            label=f"{prefix}p99 latency",
            zorder=6 + idx,
        )
        ax.plot(
            concs,
            p50,
            color=c_p50,
            linewidth=2.5,
            marker="o",
            markersize=6.8,
            markerfacecolor=c_p50,
            markeredgecolor=BG_COLOR,
            markeredgewidth=1.2,
            label=f"{prefix}p50 (median) latency",
            zorder=6 + idx,
        )

        if single_mode:
            y_span_est = max(max_lat * 1.24, 65.0)
            for xi, v50, v99 in zip(concs, p50, p99):
                c_int = int(xi)
                if c_int not in LABEL_CONCS:
                    continue
                ha = "center"
                x_off = 0
                ax.annotate(
                    _fmt_ms(v99),
                    xy=(xi, v99),
                    xytext=(x_off, 11),
                    textcoords="offset points",
                    ha=ha,
                    va="bottom",
                    color=c_p99,
                    fontsize=9.2,
                    fontweight="bold",
                    zorder=8,
                )
                if v50 < y_span_est * 0.11:
                    ax.annotate(
                        _fmt_ms(v50),
                        xy=(xi, v50),
                        xytext=(10, -1),
                        textcoords="offset points",
                        ha="left",
                        va="center",
                        color=c_p50,
                        fontsize=9.2,
                        fontweight="bold",
                        zorder=8,
                    )
                else:
                    ax.annotate(
                        _fmt_ms(v50),
                        xy=(xi, v50),
                        xytext=(x_off, -14),
                        textcoords="offset points",
                        ha=ha,
                        va="top",
                        color=c_p50,
                        fontsize=9.2,
                        fontweight="bold",
                        zorder=8,
                    )

    if single_mode and datasets[0]["version"].startswith("v0.4"):
        ax.axhline(
            50.0,
            color=ACCENT_AMBER,
            linestyle=":",
            linewidth=1.4,
            alpha=0.75,
            label="50 ms heartbeat interval",
            zorder=3,
        )

    xticks = [0, 32, 64, 96, 128, 160, 192, 224, 256] if max_conc <= 256 else np.linspace(0, max_conc, 9)
    ax.set_xticks(xticks)
    ax.set_xticklabels([f"{int(t)}" for t in xticks], fontsize=10.5, fontweight="bold")
    ax.set_xlim(-14, max_conc + 18)

    y_span = max(max_lat * 1.24, 65.0)
    ax.set_ylim(0, y_span)

    ax.set_xlabel("Concurrent Writers (c)", color=TEXT_SOFT, fontsize=11.0, labelpad=8)
    ax.set_ylabel("Write Latency (ms)", color=TEXT_SOFT, fontsize=11.0, labelpad=8)

    leg = ax.legend(
        loc="upper left",
        frameon=True,
        facecolor=BOX_BG,
        edgecolor=BOX_BORDER_HI,
        labelcolor=TEXT_MAIN,
        fontsize=9.8,
    )
    leg.set_zorder(10)

    title_ver = datasets[0]["version"] if single_mode else " vs. ".join(d["version"] for d in datasets)
    fig.text(
        0.5,
        0.93,
        f"etcd {title_ver} — Steady-State Write Latency (3-Node Cluster)",
        ha="center",
        va="center",
        color=TEXT_MAIN,
        fontsize=15.0,
        fontweight="bold",
    )
    fig.text(
        0.5,
        0.872,
        _subtitle(datasets),
        ha="center",
        va="center",
        color=TEXT_SUB,
        fontsize=9.8,
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=180, facecolor=BG_COLOR)
    plt.close(fig)
    print(f"[plot] Rendered {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Render etcd benchmark PNG charts.")
    parser.add_argument("--results", nargs="+", required=True, help="One or more results/<version>.json files")
    parser.add_argument(
        "--out-throughput",
        required=True,
        help="Output PNG path for steady-state write throughput",
    )
    parser.add_argument(
        "--out-latency",
        required=True,
        help="Output PNG path for steady-state write latency (p50 / p99)",
    )
    args = parser.parse_args()

    datasets = []
    for p in args.results:
        with open(p, "r", encoding="utf-8") as fh:
            datasets.append(json.load(fh))

    render_write_throughput(datasets, Path(args.out_throughput))
    render_write_latency(datasets, Path(args.out_latency))


if __name__ == "__main__":
    main()
