#!/usr/bin/env python3
"""Render steady-state write throughput and latency charts for etcd benchmarks.

Designed for Part 1 (etcd v0.4.9 standalone) and Part 2 (overlaying etcd v2.3.8 onto v0.4.9).
Reuses the dark-slate palette and typography from ../animations/common.py.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Dict, List

PART1_DIR = Path(__file__).resolve().parent.parent
if str(PART1_DIR) not in sys.path:
    sys.path.insert(0, str(PART1_DIR))

from animations.common import (  # noqa: E402
    ACCENT_AMBER,
    ACCENT_BLUE,
    ACCENT_CORAL,
    ACCENT_GREEN,
    ACCENT_TEAL,
    ACCENT_VIOLET,
    BG_COLOR,
    BOX_BG,
    BOX_BORDER,
    BOX_BORDER_HI,
    PANEL_BG,
    TEXT_DIM,
    TEXT_MAIN,
    TEXT_SOFT,
    TEXT_SUB,
    plt,
)
from matplotlib.ticker import FuncFormatter, NullLocator  # noqa: E402
import numpy as np  # noqa: E402


def _style_axis(ax) -> None:
    ax.set_facecolor(PANEL_BG)
    for spine in ax.spines.values():
        spine.set_color(BOX_BORDER)
        spine.set_linewidth(1.2)
    ax.tick_params(colors=TEXT_SOFT, labelsize=10.5, length=4, width=1.0)
    ax.grid(True, which="major", color=BOX_BORDER, alpha=0.45, linestyle="--", linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)


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

    ax.set_xscale("log")
    ax.set_yscale("log")

    all_concs: List[int] = []
    all_tps: List[float] = []

    for idx, data in enumerate(datasets):
        ver = data["version"]
        runs = data["experiment1_concurrency_scaling"]["runs"]
        concs = np.array([r["concurrency"] for r in runs], dtype=float)
        tps = np.array([r["throughput_wps"] for r in runs], dtype=float)
        all_concs.extend(int(c) for c in concs)
        all_tps.extend(float(v) for v in tps)

        color = line_colors[idx % len(line_colors)]

        if idx == 0:
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
            all_tps.extend(float(v) for v in ideal)

        ax.plot(
            concs,
            tps,
            color=color,
            linewidth=2.7,
            marker="o",
            markersize=8.5,
            markerfacecolor=color,
            markeredgecolor=BG_COLOR,
            markeredgewidth=1.5,
            label=f"etcd {ver} throughput",
            zorder=5,
        )

        if single_mode:
            for xi, val in zip(concs, tps):
                label_txt = f"{val:,.0f} w/s" if val >= 100 else f"{val:.1f} w/s"
                ax.annotate(
                    label_txt,
                    xy=(xi, val),
                    xytext=(0, -15),
                    textcoords="offset points",
                    ha="center",
                    va="top",
                    color=TEXT_MAIN,
                    fontsize=9.6,
                    fontweight="bold",
                    zorder=7,
                )

    unique_concs = sorted(set(all_concs))
    ax.set_xticks(unique_concs)
    ax.set_xticklabels([str(c) for c in unique_concs], fontsize=11, fontweight="bold")
    ax.xaxis.set_minor_locator(NullLocator())
    ax.set_xlim(min(unique_concs) * 0.60, max(unique_concs) * 1.65)

    ymin = min(all_tps) * 0.42
    ymax = max(all_tps) * 2.5
    ax.set_ylim(max(ymin, 10.0), ymax)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f"{int(y):,}" if y >= 1 else f"{y:g}"))
    ax.grid(True, which="minor", axis="y", color=BOX_BORDER, alpha=0.18, linestyle=":", linewidth=0.6, zorder=0)

    ax.set_xlabel("Concurrent Writers (c, log scale)", color=TEXT_SOFT, fontsize=11.0, labelpad=8)
    ax.set_ylabel("Throughput (writes / sec, log scale)", color=TEXT_SOFT, fontsize=11.0, labelpad=8)

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
        "Direct-to-leader PUT /v2/keys (1,000 keys × 256 B values, HTTP keep-alive, 15 s per c, snapshots disabled)",
        ha="center",
        va="center",
        color=TEXT_SUB,
        fontsize=10.0,
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

    ax.set_xscale("log")

    all_concs: List[int] = []
    max_lat = 0.0

    for idx, data in enumerate(datasets):
        ver = data["version"]
        runs = data["experiment1_concurrency_scaling"]["runs"]
        concs = np.array([r["concurrency"] for r in runs], dtype=float)
        p50 = np.array([r["latency_ms"]["p50"] for r in runs], dtype=float)
        p99 = np.array([r["latency_ms"]["p99"] for r in runs], dtype=float)
        all_concs.extend(int(c) for c in concs)
        max_lat = max(max_lat, float(np.max(p99)))

        c_p99, c_p50 = version_palette[idx % len(version_palette)]
        prefix = "" if single_mode else f"{ver} "

        ax.fill_between(concs, p50, p99, color=c_p99, alpha=0.10, zorder=2)
        ax.plot(
            concs,
            p99,
            color=c_p99,
            linewidth=2.6,
            marker="s",
            markersize=7.8,
            markerfacecolor=c_p99,
            markeredgecolor=BG_COLOR,
            markeredgewidth=1.4,
            label=f"{prefix}p99 latency",
            zorder=6,
        )
        ax.plot(
            concs,
            p50,
            color=c_p50,
            linewidth=2.6,
            marker="o",
            markersize=8.0,
            markerfacecolor=c_p50,
            markeredgecolor=BG_COLOR,
            markeredgewidth=1.4,
            label=f"{prefix}p50 (median) latency",
            zorder=6,
        )

        if single_mode:
            for xi, v50, v99 in zip(concs, p50, p99):
                ax.annotate(
                    f"{v99:.0f} ms" if v99 >= 20 else f"{v99:.1f} ms",
                    xy=(xi, v99),
                    xytext=(0, 10),
                    textcoords="offset points",
                    ha="center",
                    va="bottom",
                    color=c_p99,
                    fontsize=9.4,
                    fontweight="bold",
                    zorder=7,
                )
                ax.annotate(
                    f"{v50:.0f} ms" if v50 >= 20 else f"{v50:.1f} ms",
                    xy=(xi, v50),
                    xytext=(0, -14),
                    textcoords="offset points",
                    ha="center",
                    va="top",
                    color=c_p50,
                    fontsize=9.4,
                    fontweight="bold",
                    zorder=7,
                )

    ax.axhline(
        50.0,
        color=ACCENT_AMBER,
        linestyle=":",
        linewidth=1.4,
        alpha=0.75,
        label="50 ms heartbeat interval",
        zorder=3,
    )

    unique_concs = sorted(set(all_concs))
    ax.set_xticks(unique_concs)
    ax.set_xticklabels([str(c) for c in unique_concs], fontsize=11, fontweight="bold")
    ax.xaxis.set_minor_locator(NullLocator())
    ax.set_xlim(min(unique_concs) * 0.65, max(unique_concs) * 1.55)

    y_span = max(max_lat * 1.22, 65.0)
    ax.set_ylim(0, y_span)

    ax.set_xlabel("Concurrent Writers (c, log scale)", color=TEXT_SOFT, fontsize=11.0, labelpad=8)
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
        "Direct-to-leader PUT /v2/keys (1,000 keys × 256 B values, HTTP keep-alive, 15 s per c, snapshots disabled)",
        ha="center",
        va="center",
        color=TEXT_SUB,
        fontsize=10.0,
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
