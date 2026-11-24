#!/usr/bin/env python3
"""Render steady-state concurrency scaling and compaction stall charts for etcd benchmarks.

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
import numpy as np  # noqa: E402


def _style_axis(ax) -> None:
    ax.set_facecolor(PANEL_BG)
    for spine in ax.spines.values():
        spine.set_color(BOX_BORDER)
        spine.set_linewidth(1.2)
    ax.tick_params(colors=TEXT_SOFT, labelsize=10.5, length=4, width=1.0)
    ax.grid(True, which="major", color=BOX_BORDER, alpha=0.42, linestyle="--", linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)


def render_concurrency_scaling(datasets: List[Dict], out_path: Path) -> None:
    fig, (ax_tps, ax_lat) = plt.subplots(
        1,
        2,
        figsize=(16.0, 6.8),
        dpi=180,
        facecolor=BG_COLOR,
    )
    fig.subplots_adjust(left=0.065, right=0.975, top=0.81, bottom=0.14, wspace=0.19)

    _style_axis(ax_tps)
    _style_axis(ax_lat)

    single_mode = len(datasets) == 1
    version_palette = [
        (ACCENT_BLUE, ACCENT_CORAL, ACCENT_TEAL),
        (ACCENT_GREEN, ACCENT_AMBER, ACCENT_VIOLET),
    ]

    for idx, data in enumerate(datasets):
        ver = data["version"]
        runs = data["experiment1_concurrency_scaling"]["runs"]
        concs = [r["concurrency"] for r in runs]
        x = np.arange(len(concs), dtype=float)
        tps = np.array([r["throughput_wps"] for r in runs], dtype=float)
        mean_lat = np.array([r["latency_ms"]["mean"] for r in runs], dtype=float)
        p50 = np.array([r["latency_ms"]["p50"] for r in runs], dtype=float)
        p95 = np.array([r["latency_ms"]["p95"] for r in runs], dtype=float)
        p99 = np.array([r["latency_ms"]["p99"] for r in runs], dtype=float)

        c_tps, c_p99, c_p50 = version_palette[idx % len(version_palette)]
        prefix = "" if single_mode else f"{ver} "

        # Left subplot: Throughput vs concurrency
        ax_tps.fill_between(x, 0, tps, color=c_tps, alpha=0.12, zorder=2)
        ax_tps.plot(
            x,
            tps,
            color=c_tps,
            linewidth=2.7,
            marker="o",
            markersize=8.5,
            markerfacecolor=c_tps,
            markeredgecolor=BG_COLOR,
            markeredgewidth=1.5,
            label=f"{ver} throughput" if not single_mode else "Throughput (writes/s)",
            zorder=5,
        )

        tps_max = float(np.max(tps))
        tps_ylim = tps_max * 1.25
        ax_tps.set_ylim(0, tps_ylim)
        ax_tps.set_xlim(-0.38, len(concs) - 0.55)
        ax_tps.set_xticks(x)
        ax_tps.set_xticklabels([str(c) for c in concs], fontsize=11, fontweight="bold")

        if single_mode:
            for xi, val in zip(x, tps):
                label_txt = f"{val:,.0f} w/s" if val >= 100 else f"{val:.1f} w/s"
                y_off = tps_ylim * 0.032
                ax_tps.text(
                    xi,
                    val + y_off,
                    label_txt,
                    ha="center",
                    va="bottom",
                    color=TEXT_MAIN,
                    fontsize=9.6,
                    fontweight="bold",
                    bbox=dict(
                        boxstyle="round,pad=0.22",
                        facecolor=BOX_BG,
                        edgecolor=BOX_BORDER_HI,
                        linewidth=0.9,
                        alpha=0.95,
                    ),
                    zorder=7,
                )

            # Callout 1 in open mid-left space (no overlap with c=1,4,16 pills)
            ax_tps.annotate(
                f"c = 1 floor ({tps[0]:.1f} writes/s, {mean_lat[0]:.1f} ms mean)\n"
                f"50 ms Peer.heartbeat() polling (~25 ms avg wait)",
                xy=(x[0], tps[0] + tps_ylim * 0.015),
                xytext=(0.05, tps_ylim * 0.48),
                color=TEXT_SOFT,
                fontsize=9.4,
                ha="left",
                va="center",
                bbox=dict(boxstyle="round,pad=0.38", facecolor=BOX_BG, edgecolor=ACCENT_AMBER, linewidth=1.1),
                arrowprops=dict(arrowstyle="->", color=ACCENT_AMBER, lw=1.4, connectionstyle="arc3,rad=0.16"),
                zorder=8,
            )

            # Callout 2 in upper-left/center space, right edge safely left of x=4 pill
            peak_i = int(np.argmax(tps))
            ax_tps.annotate(
                f"Sub-linear scaling at high c ({tps[peak_i]:,.0f} w/s at c = {concs[peak_i]})\n"
                f"4× more clients (64 → 256) yields ~{tps[-1]/tps[-2]:.1f}× throughput\n"
                f"under serialized Log.mutex & unbatched syscalls",
                xy=(x[peak_i] - 0.06, tps[peak_i]),
                xytext=(3.20, tps_ylim * 0.84),
                color=TEXT_SOFT,
                fontsize=9.3,
                ha="right",
                va="center",
                bbox=dict(boxstyle="round,pad=0.38", facecolor=BOX_BG, edgecolor=ACCENT_BLUE, linewidth=1.1),
                arrowprops=dict(arrowstyle="->", color=ACCENT_BLUE, lw=1.4, connectionstyle="arc3,rad=0.12"),
                zorder=8,
            )

        # Right subplot: Latency (p50, p95, p99) vs concurrency
        ax_lat.fill_between(x, p50, p99, color=c_p99, alpha=0.10, zorder=2)
        ax_lat.plot(
            x,
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
        if single_mode:
            ax_lat.plot(
                x,
                p95,
                color=ACCENT_AMBER,
                linewidth=1.8,
                linestyle="--",
                marker="^",
                markersize=6.5,
                markerfacecolor=ACCENT_AMBER,
                markeredgecolor=BG_COLOR,
                markeredgewidth=1.1,
                label="p95 latency",
                zorder=5,
            )
        ax_lat.plot(
            x,
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

        lat_max = float(np.max(p99))
        y_span = max(lat_max * 1.25, 65.0)
        ax_lat.set_ylim(0, y_span)
        ax_lat.set_xlim(-0.38, len(concs) - 0.55)
        ax_lat.set_xticks(x)
        ax_lat.set_xticklabels([str(c) for c in concs], fontsize=11, fontweight="bold")

        if single_mode:
            # 25 ms half-heartbeat reference line with label centered in open valley (between c=1 and c=64)
            ax_lat.axhline(
                25.0,
                color=ACCENT_AMBER,
                linestyle=":",
                linewidth=1.4,
                alpha=0.85,
                zorder=3,
            )
            ax_lat.text(
                1.50,
                25.0 - y_span * 0.022,
                "25 ms (½ × 50 ms heartbeat avg wait)",
                ha="center",
                va="top",
                color=ACCENT_AMBER,
                fontsize=8.9,
                fontstyle="italic",
                zorder=4,
            )

            # Value callouts on p50 and p99 points cleanly separated
            for xi, v50, v99 in zip(x, p50, p99):
                ax_lat.text(
                    xi,
                    v99 + y_span * 0.028,
                    f"{v99:.0f} ms" if v99 >= 20 else f"{v99:.1f} ms",
                    ha="center",
                    va="bottom",
                    color=ACCENT_CORAL,
                    fontsize=9.2,
                    fontweight="bold",
                    zorder=7,
                )
                ax_lat.text(
                    xi,
                    v50 - y_span * 0.032,
                    f"{v50:.0f} ms" if v50 >= 20 else f"{v50:.1f} ms",
                    ha="center",
                    va="top",
                    color=ACCENT_TEAL,
                    fontsize=9.2,
                    fontweight="bold",
                    zorder=7,
                )

            # Callout for c=1 floor positioned safely between legend and curves
            ax_lat.annotate(
                f"c = 1: mean = {mean_lat[0]:.1f} ms (p50 = {p50[0]:.1f} ms, p99 = {p99[0]:.1f} ms)\n"
                f"Bounded by 50 ms stop-and-wait heartbeat ticks",
                xy=(x[0], p99[0] + y_span * 0.07),
                xytext=(0.05, y_span * 0.56),
                color=TEXT_SOFT,
                fontsize=9.2,
                ha="left",
                va="center",
                bbox=dict(boxstyle="round,pad=0.38", facecolor=BOX_BG, edgecolor=ACCENT_TEAL, linewidth=1.1),
                arrowprops=dict(arrowstyle="->", color=ACCENT_TEAL, lw=1.35, connectionstyle="arc3,rad=0.14"),
                zorder=8,
            )

            # Callout for high-concurrency queueing, right-aligned left of x=4
            ax_lat.annotate(
                f"c = {concs[-1]}: p50 = {p50[-1]:.0f} ms, p99 = {p99[-1]:.0f} ms\n"
                f"Contention on Log.mutex + fsync queues writers",
                xy=(x[-1] - 0.06, p99[-1]),
                xytext=(3.42, y_span * 0.87),
                color=TEXT_SOFT,
                fontsize=9.2,
                ha="right",
                va="center",
                bbox=dict(boxstyle="round,pad=0.38", facecolor=BOX_BG, edgecolor=ACCENT_CORAL, linewidth=1.1),
                arrowprops=dict(arrowstyle="->", color=ACCENT_CORAL, lw=1.35, connectionstyle="arc3,rad=-0.12"),
                zorder=8,
            )

    ax_tps.set_title("Aggregate Write Throughput", color=TEXT_MAIN, fontsize=13.0, fontweight="bold", pad=12)
    ax_tps.set_xlabel("Concurrent Writers (c)", color=TEXT_SOFT, fontsize=11.0, labelpad=8)
    ax_tps.set_ylabel("Throughput (writes / sec)", color=TEXT_SOFT, fontsize=11.0, labelpad=8)

    ax_lat.set_title("Per-Request Write Latency (p50 / p95 / p99)", color=TEXT_MAIN, fontsize=13.0, fontweight="bold", pad=12)
    ax_lat.set_xlabel("Concurrent Writers (c)", color=TEXT_SOFT, fontsize=11.0, labelpad=8)
    ax_lat.set_ylabel("Write Latency (ms)", color=TEXT_SOFT, fontsize=11.0, labelpad=8)
    leg = ax_lat.legend(
        loc="upper left",
        frameon=True,
        facecolor=BOX_BG,
        edgecolor=BOX_BORDER_HI,
        labelcolor=TEXT_MAIN,
        fontsize=9.5,
    )
    leg.set_zorder(10)

    if not single_mode:
        leg_tps = ax_tps.legend(
            loc="upper left",
            frameon=True,
            facecolor=BOX_BG,
            edgecolor=BOX_BORDER_HI,
            labelcolor=TEXT_MAIN,
            fontsize=9.5,
        )
        leg_tps.set_zorder(10)

    title_ver = datasets[0]["version"] if single_mode else " vs. ".join(d["version"] for d in datasets)
    fig.text(
        0.5,
        0.935,
        f"etcd {title_ver} — Steady-State Write Concurrency Scaling (3-Node Cluster)",
        ha="center",
        va="center",
        color=TEXT_MAIN,
        fontsize=16.0,
        fontweight="bold",
    )
    fig.text(
        0.5,
        0.888,
        "Direct-to-leader PUT /v2/keys (1,000 keys × 256 B values, persistent HTTP keep-alive, 15 s window per c, snapshots disabled)",
        ha="center",
        va="center",
        color=TEXT_SUB,
        fontsize=10.8,
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=180, facecolor=BG_COLOR)
    plt.close(fig)
    print(f"[plot] Rendered {out_path}")


def _rolling_percentile(values: np.ndarray, window: int, q: float) -> np.ndarray:
    n = len(values)
    out = np.empty(n, dtype=float)
    half = max(1, window // 2)
    for i in range(n):
        lo = max(0, i - half)
        hi = min(n, i + half + 1)
        out[i] = np.percentile(values[lo:hi], q)
    return out


def render_compaction_stall(datasets: List[Dict], out_path: Path) -> None:
    fig, (ax_lat, ax_log) = plt.subplots(
        2,
        1,
        figsize=(16.0, 7.8),
        dpi=180,
        sharex=True,
        gridspec_kw={"height_ratios": [1.32, 1.0], "hspace": 0.16},
        facecolor=BG_COLOR,
    )
    fig.subplots_adjust(left=0.07, right=0.975, top=0.83, bottom=0.10)

    _style_axis(ax_lat)
    _style_axis(ax_log)

    single_mode = len(datasets) == 1

    for idx, data in enumerate(datasets):
        ver = data["version"]
        run = data["experiment2_compaction_stall"]["run"]
        snap_thr = data["experiment2_compaction_stall"].get("snapshot_count", 10000)

        writes = run["writes"]
        disk = run["disk_samples"]
        snap_events = run.get("snapshot_events", [])
        leader_name = run.get("leader_name", "etcd-1")

        w_seq = np.array([w["write_seq"] for w in writes], dtype=float)
        w_lat = np.array([w["latency_ms"] for w in writes], dtype=float)
        w_elapsed_s = np.array([w["elapsed_ms"] / 1000.0 for w in writes], dtype=float)

        d_seq = np.array([d["completed_writes"] for d in disk], dtype=float)
        d_mb = np.array([d["log_bytes"] / (1024.0 * 1024.0) for d in disk], dtype=float)

        roll_p50 = _rolling_percentile(w_lat, window=200, q=50.0)
        roll_p99 = _rolling_percentile(w_lat, window=200, q=99.0)

        if single_mode:
            ax_lat.scatter(
                w_seq,
                w_lat,
                s=8,
                color=ACCENT_BLUE,
                alpha=0.20,
                edgecolors="none",
                label="Individual PUT latency",
                zorder=3,
                rasterized=True,
            )
            ax_lat.plot(
                w_seq,
                roll_p99,
                color=ACCENT_CORAL,
                linewidth=2.3,
                label="Rolling p99 (200-write window)",
                zorder=6,
            )
            ax_lat.plot(
                w_seq,
                roll_p50,
                color=ACCENT_TEAL,
                linewidth=2.1,
                label="Rolling p50 (200-write window)",
                zorder=5,
            )

            ax_log.fill_between(d_seq, 0, d_mb, color=ACCENT_AMBER, alpha=0.15, zorder=2)
            ax_log.plot(
                d_seq,
                d_mb,
                color=ACCENT_AMBER,
                linewidth=2.6,
                label=f"Leader ({leader_name}) /var/lib/etcd/log size (MB)",
                zorder=5,
            )

            # Threshold marker at 10,000 commits
            ax_lat.axvline(snap_thr, color=TEXT_DIM, linestyle=":", linewidth=1.3, alpha=0.9, zorder=2)
            ax_log.axvline(snap_thr, color=TEXT_DIM, linestyle=":", linewidth=1.3, alpha=0.9, zorder=2)

            # Find exact compaction drop on leader log
            drop_idx = None
            for i in range(1, len(d_mb)):
                if d_mb[i - 1] > 1.0 and d_mb[i] < d_mb[i - 1] * 0.5:
                    drop_idx = i
                    break

            compact_seq = float(run.get("compaction_write_seq", 0))
            if drop_idx is not None:
                compact_seq = float(d_seq[drop_idx])
                pre_mb = float(d_mb[drop_idx - 1])
                post_mb = float(d_mb[drop_idx])
            else:
                pre_mb = float(np.max(d_mb))
                post_mb = float(np.min(d_mb[-10:])) if len(d_mb) >= 10 else float(np.min(d_mb))

            # Locate peak latency specifically within the compaction window around compact_seq
            if compact_seq > 0:
                win_mask = (w_seq >= compact_seq - 650) & (w_seq <= compact_seq + 650)
            else:
                win_mask = w_seq >= (snap_thr * 0.95)
            if np.any(win_mask):
                sub_indices = np.where(win_mask)[0]
                peak_local = sub_indices[int(np.argmax(w_lat[win_mask]))]
            else:
                peak_local = int(np.argmax(w_lat))

            peak_seq = float(w_seq[peak_local])
            peak_lat = float(w_lat[peak_local])
            peak_time_s = float(w_elapsed_s[peak_local])

            if compact_seq > 0:
                span_lo = min(compact_seq, peak_seq) - 260
                span_hi = max(compact_seq, peak_seq) + 260
                ax_lat.axvspan(span_lo, span_hi, color=ACCENT_CORAL, alpha=0.12, zorder=1)
                ax_log.axvspan(span_lo, span_hi, color=ACCENT_CORAL, alpha=0.12, zorder=1)
                ax_lat.axvline(compact_seq, color=ACCENT_CORAL, linestyle="--", linewidth=1.5, alpha=0.85, zorder=4)
                ax_log.axvline(compact_seq, color=ACCENT_CORAL, linestyle="--", linewidth=1.5, alpha=0.85, zorder=4)

            overall_max = float(np.max(w_lat))
            lat_ylim = max(overall_max * 1.42, peak_lat * 1.50, 198.0)
            ax_lat.set_ylim(0, lat_ylim)

            log_ylim = max(pre_mb * 1.30, 1.0)
            ax_log.set_ylim(0, log_ylim)
            max_x = float(w_seq[-1])
            ax_log.set_xlim(0, max_x * 1.01)

            # Label snapshot_count = 10,000 threshold cleanly on left of 10k line
            ax_log.text(
                snap_thr - 240,
                log_ylim * 0.88,
                f"snapshot-count = {snap_thr:,}\nthreshold crossed",
                ha="right",
                va="top",
                color=TEXT_SUB,
                fontsize=9.2,
                bbox=dict(boxstyle="round,pad=0.30", facecolor=BOX_BG, edgecolor=BOX_BORDER_HI, linewidth=0.9),
                zorder=7,
            )

            # Steady-state baseline annotation over the flat pre-compaction span (writes 2,400–8,500)
            pre_p50 = run["steady_pre_compact_latency_ms"]["p50"]
            pre_p99 = run["steady_pre_compact_latency_ms"]["p99"]
            ax_lat.text(
                max_x * 0.125,
                lat_ylim * 0.83,
                f"Pre-compaction steady state (writes 1–{snap_thr:,}):\n"
                f"median p50 = {pre_p50:.1f} ms  ·  tail p99 = {pre_p99:.1f} ms",
                ha="left",
                va="top",
                color=TEXT_SOFT,
                fontsize=9.4,
                bbox=dict(boxstyle="round,pad=0.36", facecolor=BOX_BG, edgecolor=ACCENT_TEAL, linewidth=1.0),
                zorder=8,
            )

            # Annotate compaction stall spike cleanly below upper-right legend strip and above curves
            comp_ann_x = compact_seq - 450 if compact_seq > max_x * 0.62 else compact_seq + 500
            comp_ha = "right" if compact_seq > max_x * 0.62 else "left"
            comp_rad = -0.16 if comp_ha == "right" else 0.14
            ax_lat.annotate(
                f"Compaction stall: {peak_lat:.1f} ms (write #{int(peak_seq):,}, t = {peak_time_s:.1f} s)\n"
                f"TakeSnapshot() + Log.compact() blocks Log.mutex",
                xy=(peak_seq, peak_lat),
                xytext=(comp_ann_x, lat_ylim * 0.64),
                color=TEXT_MAIN,
                fontsize=9.4,
                ha=comp_ha,
                va="top",
                bbox=dict(boxstyle="round,pad=0.38", facecolor=BOX_BG, edgecolor=ACCENT_CORAL, linewidth=1.2),
                arrowprops=dict(
                    arrowstyle="->",
                    color=ACCENT_CORAL,
                    lw=1.5,
                    connectionstyle=f"arc3,rad={comp_rad}",
                ),
                zorder=9,
            )

            leader_snaps = [s for s in snap_events if s["node"] == leader_name]
            snap_note = ""
            if leader_snaps:
                s0 = leader_snaps[0]
                snap_mb = s0["bytes"] / (1024.0 * 1024.0)
                snap_note = f"\nWrites snapshot/{s0['filename']} ({snap_mb:.2f} MB) + fsync"

            if compact_seq > 0:
                log_ann_x = compact_seq + 520
                ax_log.annotate(
                    f"Log.compact() rewrites log.new → log\n"
                    f"{pre_mb:.2f} MB → {post_mb:.2f} MB (200-entry tail kept){snap_note}",
                    xy=(compact_seq + 40, post_mb + (pre_mb - post_mb) * 0.16),
                    xytext=(log_ann_x, log_ylim * 0.73),
                    color=TEXT_MAIN,
                    fontsize=9.3,
                    ha="left",
                    va="center",
                    bbox=dict(boxstyle="round,pad=0.38", facecolor=BOX_BG, edgecolor=ACCENT_AMBER, linewidth=1.15),
                    arrowprops=dict(arrowstyle="->", color=ACCENT_AMBER, lw=1.4, connectionstyle="arc3,rad=-0.16"),
                    zorder=8,
                )
        else:
            c_line = ACCENT_CORAL if idx == 0 else ACCENT_GREEN
            c_disk = ACCENT_AMBER if idx == 0 else ACCENT_BLUE
            ax_lat.plot(w_seq, roll_p99, color=c_line, linewidth=2.2, label=f"{ver} rolling p99 latency")
            ax_log.plot(d_seq, d_mb, color=c_disk, linewidth=2.4, label=f"{ver} leader WAL/log size (MB)")

    ax_lat.set_ylabel("Write Latency (ms)", color=TEXT_SOFT, fontsize=11.0, labelpad=8)
    ax_lat.set_title("Per-Request & Rolling Tail Write Latency", color=TEXT_MAIN, fontsize=12.6, fontweight="bold", pad=9)
    leg_top = ax_lat.legend(
        loc="upper right",
        ncol=3,
        frameon=True,
        facecolor=BOX_BG,
        edgecolor=BOX_BORDER_HI,
        labelcolor=TEXT_MAIN,
        fontsize=9.2,
        columnspacing=1.1,
    )
    leg_top.set_zorder(10)

    ax_log.set_ylabel("Leader Log Size (MB)", color=TEXT_SOFT, fontsize=11.0, labelpad=8)
    ax_log.set_xlabel("Committed Client Writes (PUT sequence #)", color=TEXT_SOFT, fontsize=11.2, labelpad=8)
    ax_log.set_title("On-Disk Raft Log Growth & Compaction Truncation (/var/lib/etcd/log)", color=TEXT_MAIN, fontsize=12.6, fontweight="bold", pad=9)
    leg_bot = ax_log.legend(
        loc="lower right",
        frameon=True,
        facecolor=BOX_BG,
        edgecolor=BOX_BORDER_HI,
        labelcolor=TEXT_MAIN,
        fontsize=9.4,
    )
    leg_bot.set_zorder(10)

    max_writes = int(datasets[0]["experiment2_compaction_stall"]["run"]["total_writes"])
    xticks = np.arange(0, max_writes + 1, 2500)
    ax_log.set_xticks(xticks)
    ax_log.set_xticklabels([f"{int(t):,}" for t in xticks], fontsize=10.5)

    run0 = datasets[0]["experiment2_compaction_stall"]["run"]
    dur_s = run0["duration_s"]
    avg_wps = run0["throughput_wps"]
    title_ver = datasets[0]["version"] if single_mode else " vs. ".join(d["version"] for d in datasets)

    fig.text(
        0.5,
        0.94,
        f"etcd {title_ver} — Snapshot & Log-Rewrite Compaction Stall (snapshot-count = 10,000)",
        ha="center",
        va="center",
        color=TEXT_MAIN,
        fontsize=16.0,
        fontweight="bold",
    )
    fig.text(
        0.5,
        0.895,
        f"Sustained writes (c = {run0['concurrency']}, {run0['total_writes']:,} PUTs in {dur_s:.1f} s ≈ {avg_wps:,.0f} writes/s, 1,000 keys × 256 B, Linux ext4 volumes)",
        ha="center",
        va="center",
        color=TEXT_SUB,
        fontsize=10.8,
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=180, facecolor=BG_COLOR)
    plt.close(fig)
    print(f"[plot] Rendered {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Render etcd benchmark PNG charts.")
    parser.add_argument("--results", nargs="+", required=True, help="One or more results/<version>.json files")
    parser.add_argument(
        "--out-scaling",
        default=str(PART1_DIR / "v04_concurrency_scaling.png"),
        help="Output PNG path for Experiment 1 (concurrency scaling)",
    )
    parser.add_argument(
        "--out-compaction",
        default=str(PART1_DIR / "v04_compaction_stall.png"),
        help="Output PNG path for Experiment 2 (compaction stall)",
    )
    args = parser.parse_args()

    datasets = []
    for p in args.results:
        with open(p, "r", encoding="utf-8") as fh:
            datasets.append(json.load(fh))

    render_concurrency_scaling(datasets, Path(args.out_scaling))
    render_compaction_stall(datasets, Path(args.out_compaction))


if __name__ == "__main__":
    main()
