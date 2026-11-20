"""Animation 1: Bootstrapping a CoreOS Cluster Around etcd (Distributed /etc).

Visualizes how a minimal CoreOS cluster comes online step-by-step around a central
etcd cluster, growing etcd's hierarchical keyspace in true causal bootstrapping order:
  1. Start with empty etcd (/) — a shared, fault-tolerant /etc
  2. CoreOS workers boot & join via fleetd (active scheduler + machine heartbeats)
  3. Operator submits web@1..3 & shared config — fleetd places containers on workers
  4. Running web replicas register endpoints — nginx discovers them via /services/web
  5. locksmithd shares a reboot lock so automatic OS updates reboot one host at a time
  6. Complete overview + working-set scale punchline (~30-100 keys, < 1 MB)
"""

from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import matplotlib.pyplot as plt

from .common import (
    ACCENT_AMBER,
    ACCENT_BLUE,
    ACCENT_GREEN,
    ACCENT_TEAL,
    ACCENT_VIOLET,
    BG_COLOR,
    BOX_BG,
    BOX_BORDER,
    BOX_BORDER_HI,
    BOX_INNER,
    PANEL_BG,
    TEXT_DIM,
    TEXT_MAIN,
    TEXT_SOFT,
    TEXT_SUB,
    blend_hex,
    clamp,
    draw_box,
    draw_pulse_dot,
    ease_in_out,
    ease_out,
    export_animation,
    fig_to_rgb,
    progress,
)

NAME = "coreos_cluster_bootstrap"
DESCRIPTION = "Progressive bootstrapping of a CoreOS cluster around etcd's growing directory tree."

# Frame durations per phase at 16 FPS (total = 304 frames = 19.0s loop)
PHASE_LENGTHS = [
    ("step1_etcd", 34),        # 2.1s: Empty etcd
    ("step2_fleet", 52),       # 3.25s: Workers boot & join via fleetd
    ("step3_deploy", 60),      # 3.75s: Operator submits jobs + config; containers start
    ("step4_discovery", 54),   # 3.4s: web@1..3 register endpoints; nginx discovers them
    ("step5_locksmith", 48),   # 3.0s: locksmithd coordinates rolling OS updates
    ("step6_summary", 56),     # 3.5s: Complete calm view + scale callout
]

STEP_PILLS = [
    (1, "1. etcd", ACCENT_BLUE),
    (2, "2. fleetd", ACCENT_AMBER),
    (3, "3. Deploy & Config", ACCENT_VIOLET),
    (4, "4. Discovery", ACCENT_TEAL),
    (5, "5. locksmithd", ACCENT_GREEN),
]


def build_timeline() -> Tuple[List[Dict], List[Tuple[int, str]]]:
    """Generate per-frame state dictionaries and keyframe preview indices."""
    states: List[Dict] = []
    previews: List[Tuple[int, str]] = []
    cursor = 0

    for phase, length in PHASE_LENGTHS:
        # Capture a representative settled frame near the end of each phase
        previews.append((cursor + length - 6, phase))

        for lf in range(length):
            st: Dict = {
                "phase": phase,
                "active_step": 1,
                "caption": "",
                "caption_color": ACCENT_BLUE,
                # Visibility alphas [0..1]
                "etcd_glow": 0.0,
                "workers_alpha": 0.0,
                "fleetd_alpha": 0.0,
                "operator_alpha": 0.0,
                "apps_alpha": 0.0,
                "nginx_hi": 0.0,
                "locksmith_alpha": 0.0,
                # Keyspace group alphas [0..1]
                "k_fleet_base": 0.0,
                "k_fleet_jobs": 0.0,
                "k_config": 0.0,
                "k_services": 0.0,
                "k_locksmith": 0.0,
                # Active highlight group in keyspace panel
                "active_tree_groups": set(),
                # Active accent for bus lines & highlights
                "bus_color": BOX_BORDER_HI,
                "bus_hi": 0.0,
                "op_link_hi": 0.0,
                # Traveling pulses: list of (src_key, dst_key, t, color)
                "pulses": [],
                # Summary scale footer alpha
                "summary_alpha": 0.0,
                "key_badge": "0 keys",
            }

            if phase == "step1_etcd":
                st["active_step"] = 1
                st["caption"] = "1. Start with etcd — a shared, fault-tolerant distributed /etc"
                st["caption_color"] = ACCENT_BLUE
                st["etcd_glow"] = 0.65 + 0.25 * ease_in_out(progress(lf, 0, 16))
                st["key_badge"] = "0 keys"

            elif phase == "step2_fleet":
                st["active_step"] = 2
                st["caption"] = "2. CoreOS workers join via fleetd — picking a scheduler & reporting liveness"
                st["caption_color"] = ACCENT_AMBER
                st["workers_alpha"] = ease_out(progress(lf, 0, 12))
                st["fleetd_alpha"] = ease_out(progress(lf, 4, 12))
                st["bus_color"] = ACCENT_AMBER
                st["bus_hi"] = ease_out(progress(lf, 10, 10))
                # Pulses from workers up to etcd
                p_up = progress(lf, 12, 16)
                if 0.0 < p_up < 1.0:
                    st["pulses"] = [
                        ("w1", "etcd1", p_up, ACCENT_AMBER),
                        ("w2", "etcd2", clamp(p_up * 1.05), ACCENT_AMBER),
                        ("w3", "etcd3", clamp(p_up * 0.95), ACCENT_AMBER),
                    ]
                st["k_fleet_base"] = ease_out(progress(lf, 24, 10))
                if st["k_fleet_base"] > 0.05:
                    st["active_tree_groups"] = {"fleet_base"}
                    st["key_badge"] = "4 keys"
                else:
                    st["key_badge"] = "0 keys"

            elif phase == "step3_deploy":
                st["active_step"] = 3
                st["caption"] = "3. Admin deploys web@1..3, nginx & config — fleetd places containers on workers"
                st["caption_color"] = ACCENT_VIOLET
                st["workers_alpha"] = 1.0
                st["fleetd_alpha"] = 1.0
                st["k_fleet_base"] = 1.0
                st["operator_alpha"] = ease_out(progress(lf, 0, 10))
                st["op_link_hi"] = ease_out(progress(lf, 6, 10))
                st["bus_color"] = ACCENT_VIOLET
                st["bus_hi"] = ease_out(progress(lf, 22, 10))

                # Phase A: Admin -> etcd writes job definitions & /config/web
                p_op = progress(lf, 8, 14)
                if 0.0 < p_op < 1.0:
                    st["pulses"].append(("op", "etcd_left", p_op, ACCENT_VIOLET))
                st["k_fleet_jobs"] = ease_out(progress(lf, 19, 10))
                st["k_config"] = ease_out(progress(lf, 21, 10))
                if st["k_fleet_jobs"] > 0.05:
                    st["active_tree_groups"] = {"fleet_jobs", "config"}
                    st["key_badge"] = "9 keys"
                else:
                    st["key_badge"] = "4 keys"

                # Phase B: etcd -> workers (fleetd starts web@1..3 & nginx, reading config)
                p_down = progress(lf, 26, 16)
                if 0.0 < p_down < 1.0:
                    st["pulses"].extend([
                        ("etcd1", "w1", p_down, ACCENT_VIOLET),
                        ("etcd2", "w2", clamp(p_down * 1.04), ACCENT_VIOLET),
                        ("etcd3", "w3", clamp(p_down * 0.96), ACCENT_VIOLET),
                    ])
                st["apps_alpha"] = ease_out(progress(lf, 36, 12))

            elif phase == "step4_discovery":
                st["active_step"] = 4
                st["caption"] = "4. Running web containers register endpoints — nginx discovers them via etcd"
                st["caption_color"] = ACCENT_TEAL
                st["workers_alpha"] = 1.0
                st["fleetd_alpha"] = 1.0
                st["operator_alpha"] = 1.0
                st["apps_alpha"] = 1.0
                st["k_fleet_base"] = 1.0
                st["k_fleet_jobs"] = 1.0
                st["k_config"] = 1.0
                st["bus_color"] = ACCENT_TEAL
                st["bus_hi"] = ease_out(progress(lf, 2, 10))

                # Phase A: web@1..3 register IP:port up to etcd
                p_reg = progress(lf, 4, 15)
                if 0.0 < p_reg < 1.0:
                    st["pulses"].extend([
                        ("w1", "etcd1", p_reg, ACCENT_TEAL),
                        ("w2", "etcd2", clamp(p_reg * 1.04), ACCENT_TEAL),
                        ("w3", "etcd3", clamp(p_reg * 0.96), ACCENT_TEAL),
                    ])
                st["k_services"] = ease_out(progress(lf, 16, 10))
                if st["k_services"] > 0.05:
                    st["active_tree_groups"] = {"services"}
                    st["key_badge"] = "12 keys"
                else:
                    st["key_badge"] = "9 keys"

                # Phase B: etcd notifies nginx on Worker 3
                p_watch = progress(lf, 25, 14)
                if 0.0 < p_watch < 1.0:
                    st["pulses"].append(("etcd3", "w3", p_watch, ACCENT_TEAL))
                st["nginx_hi"] = ease_out(progress(lf, 33, 10))

            elif phase == "step5_locksmith":
                st["active_step"] = 5
                st["caption"] = "5. locksmithd shares a reboot lock so OS updates reboot one host at a time"
                st["caption_color"] = ACCENT_GREEN
                st["workers_alpha"] = 1.0
                st["fleetd_alpha"] = 1.0
                st["operator_alpha"] = 1.0
                st["apps_alpha"] = 1.0
                st["k_fleet_base"] = 1.0
                st["k_fleet_jobs"] = 1.0
                st["k_config"] = 1.0
                st["k_services"] = 1.0
                st["locksmith_alpha"] = ease_out(progress(lf, 0, 10))
                st["bus_color"] = ACCENT_GREEN
                st["bus_hi"] = ease_out(progress(lf, 8, 10))

                p_lock = progress(lf, 10, 15)
                if 0.0 < p_lock < 1.0:
                    st["pulses"].extend([
                        ("w1", "etcd1", p_lock, ACCENT_GREEN),
                        ("w2", "etcd2", clamp(p_lock * 1.04), ACCENT_GREEN),
                        ("w3", "etcd3", clamp(p_lock * 0.96), ACCENT_GREEN),
                    ])
                st["k_locksmith"] = ease_out(progress(lf, 21, 10))
                if st["k_locksmith"] > 0.05:
                    st["active_tree_groups"] = {"locksmith"}
                    st["key_badge"] = "13 keys"
                else:
                    st["key_badge"] = "12 keys"

            elif phase == "step6_summary":
                st["active_step"] = 6
                st["caption"] = "Workers never talk directly — all state & coordination flow through etcd"
                st["caption_color"] = ACCENT_BLUE
                st["etcd_glow"] = 0.7
                st["workers_alpha"] = 1.0
                st["fleetd_alpha"] = 1.0
                st["operator_alpha"] = 1.0
                st["apps_alpha"] = 1.0
                st["locksmith_alpha"] = 1.0
                st["k_fleet_base"] = 1.0
                st["k_fleet_jobs"] = 1.0
                st["k_config"] = 1.0
                st["k_services"] = 1.0
                st["k_locksmith"] = 1.0
                st["bus_color"] = ACCENT_BLUE
                st["bus_hi"] = 0.35
                st["summary_alpha"] = ease_out(progress(lf, 2, 12))
                st["key_badge"] = "13 keys"

            states.append(st)
        cursor += length

    return states, previews


def render_frame(st: Dict, dpi: int = 125):
    fig, ax = plt.subplots(figsize=(12.8, 6.8), dpi=dpi)
    fig.patch.set_facecolor(BG_COLOR)
    ax.set_facecolor(BG_COLOR)
    ax.set_xlim(0.0, 16.0)
    ax.set_ylim(0.0, 8.5)
    ax.axis("off")

    # -------------------------------------------------------------------------
    # Header: Title + Active Step Caption
    # -------------------------------------------------------------------------
    ax.text(
        8.0, 8.10,
        "How a CoreOS Cluster Bootstraps Around etcd",
        color=TEXT_MAIN, fontsize=15.5, fontweight="bold", ha="center", va="center",
    )
    ax.text(
        8.0, 7.62,
        st["caption"],
        color=st["caption_color"], fontsize=11.0, fontweight="bold", ha="center", va="center",
    )

    # -------------------------------------------------------------------------
    # Left Pane Geometry: Operator + etcd Cluster Hub + 3 CoreOS Workers
    # -------------------------------------------------------------------------
    # etcd Cluster Hub (always visible from Step 1)
    ex, ey, ew, eh = 3.05, 5.10, 5.35, 1.72
    etcd_edge = blend_hex(BOX_BORDER_HI, ACCENT_BLUE, max(0.45, st["etcd_glow"]))
    draw_box(ax, ex, ey, ew, eh, facecolor=BOX_BG, edgecolor=etcd_edge, lw=2.2, radius=0.18, zorder=3)
    ax.text(
        ex + ew / 2, ey + eh - 0.34,
        "etcd Cluster",
        color=TEXT_MAIN, fontsize=12.0, fontweight="bold", ha="center", va="center", zorder=4,
    )
    ax.text(
        ex + ew / 2, ey + eh - 0.68,
        "Shared, fault-tolerant /etc",
        color=ACCENT_BLUE, fontsize=9.0, ha="center", va="center", zorder=4,
    )

    # 3 subtle node pills inside etcd box (hints at redundancy without Raft jargon)
    node_w, node_h, node_gap = 1.48, 0.50, 0.22
    nodes_x0 = ex + (ew - (3 * node_w + 2 * node_gap)) / 2
    for idx, label in enumerate(("etcd-1", "etcd-2", "etcd-3")):
        nx = nodes_x0 + idx * (node_w + node_gap)
        ny = ey + 0.24
        draw_box(
            ax, nx, ny, node_w, node_h,
            facecolor=BOX_INNER, edgecolor=ACCENT_BLUE, lw=1.2, radius=0.10, alpha=0.88, zorder=4,
        )
        ax.text(
            nx + node_w / 2, ny + node_h / 2,
            label, color=TEXT_SOFT, fontsize=8.8, family="monospace", fontweight="bold",
            ha="center", va="center", zorder=5,
        )

    # Admin (fleetctl / etcdctl) box — appears in Step 3
    op_x, op_y, op_w, op_h = 0.45, 5.28, 1.85, 1.36
    if st["operator_alpha"] > 0.01:
        oa = st["operator_alpha"]
        op_edge = blend_hex(BOX_BORDER_HI, ACCENT_VIOLET, st["op_link_hi"])
        draw_box(ax, op_x, op_y, op_w, op_h, facecolor=BOX_BG, edgecolor=op_edge, lw=1.8, radius=0.15, alpha=oa, zorder=3)
        ax.text(
            op_x + op_w / 2, op_y + op_h - 0.32,
            "Admin (CLI)", color=TEXT_MAIN, fontsize=9.8, fontweight="bold",
            ha="center", va="center", alpha=oa, zorder=4,
        )
        ax.text(
            op_x + op_w / 2, op_y + op_h - 0.68,
            "fleetctl / etcdctl", color=ACCENT_AMBER, fontsize=7.6, family="monospace", fontweight="bold",
            ha="center", va="center", alpha=oa, zorder=4,
        )
        ax.text(
            op_x + op_w / 2, op_y + 0.28,
            "jobs & config", color=TEXT_SUB, fontsize=8.0,
            ha="center", va="center", alpha=oa, zorder=4,
        )
        # Connector Operator -> etcd
        link_col = blend_hex(BOX_BORDER_HI, ACCENT_VIOLET, st["op_link_hi"])
        ax.annotate(
            "",
            xy=(ex - 0.04, op_y + op_h / 2),
            xytext=(op_x + op_w + 0.04, op_y + op_h / 2),
            arrowprops=dict(arrowstyle="->", color=link_col, lw=1.8, alpha=oa),
            zorder=5,
        )

    # Anchor points for hub-and-spoke connectors and pulse animations
    w_w, w_h, w_gap = 2.46, 2.86, 0.28
    w_y = 1.05
    worker_xs = [0.45 + i * (w_w + w_gap) for i in range(3)]
    etcd_ports = [
        (ex + 1.15, ey),
        (ex + ew / 2, ey),
        (ex + ew - 1.15, ey),
    ]
    worker_tops = [(wx + w_w / 2, w_y + w_h) for wx in worker_xs]

    anchors = {
        "op": (op_x + op_w + 0.05, op_y + op_h / 2),
        "etcd_left": (ex - 0.05, op_y + op_h / 2),
        "w1": worker_tops[0],
        "w2": worker_tops[1],
        "w3": worker_tops[2],
        "etcd1": etcd_ports[0],
        "etcd2": etcd_ports[1],
        "etcd3": etcd_ports[2],
    }

    # 3 CoreOS Worker cards + hub-and-spoke lines to etcd
    if st["workers_alpha"] > 0.01:
        wa = st["workers_alpha"]
        bus_col = blend_hex(BOX_BORDER_HI, st["bus_color"], st["bus_hi"])
        bus_lw = 1.6 + 0.7 * st["bus_hi"]

        for i in range(3):
            wx = worker_xs[i]
            # Hub-and-spoke line Worker i <-> etcd (NO horizontal lines between workers)
            p_w = worker_tops[i]
            p_e = etcd_ports[i]
            ax.plot(
                [p_w[0], p_e[0]], [p_w[1] + 0.02, p_e[1] - 0.02],
                color=bus_col, lw=bus_lw, alpha=0.85 * wa, zorder=2,
            )

            # Worker card container
            draw_box(
                ax, wx, w_y, w_w, w_h,
                facecolor=BOX_BG, edgecolor=BOX_BORDER_HI, lw=1.7, radius=0.16, alpha=wa, zorder=3,
            )
            ax.text(
                wx + 0.16, w_y + w_h - 0.28,
                f"Worker {i + 1}",
                color=TEXT_MAIN, fontsize=10.2, fontweight="bold", ha="left", va="center", alpha=wa, zorder=4,
            )
            ax.text(
                wx + w_w - 0.16, w_y + w_h - 0.28,
                "CoreOS",
                color=TEXT_DIM, fontsize=7.8, family="monospace", ha="right", va="center", alpha=wa, zorder=4,
            )

            # Row 1: fleetd pill (Step 2+)
            if st["fleetd_alpha"] > 0.01:
                fa = st["fleetd_alpha"] * wa
                is_sched = (i == 1)
                f_edge = ACCENT_AMBER if (is_sched or st["active_step"] == 2) else BOX_BORDER_HI
                f_lw = 1.7 if is_sched else 1.2
                py = w_y + 1.88
                ph = 0.56
                draw_box(
                    ax, wx + 0.14, py, w_w - 0.28, ph,
                    facecolor=BOX_INNER, edgecolor=f_edge, lw=f_lw, radius=0.10, alpha=fa, zorder=4,
                )
                ax.text(
                    wx + w_w / 2, py + ph * 0.66,
                    "fleetd ★" if is_sched else "fleetd",
                    color=ACCENT_AMBER if is_sched else TEXT_MAIN,
                    fontsize=8.9, family="monospace", fontweight="bold",
                    ha="center", va="center", alpha=fa, zorder=5,
                )
                ax.text(
                    wx + w_w / 2, py + ph * 0.26,
                    "active scheduler" if is_sched else "agent",
                    color=ACCENT_AMBER if is_sched else TEXT_SUB,
                    fontsize=7.4, ha="center", va="center", alpha=fa, zorder=5,
                )

            # Row 2: App containers (Step 3+, highlighted in Step 4)
            if st["apps_alpha"] > 0.01:
                aa = st["apps_alpha"] * wa
                py = w_y + 1.06
                ph = 0.64
                app_edge = ACCENT_TEAL if st["active_step"] == 4 else (
                    ACCENT_VIOLET if st["active_step"] == 3 else BOX_BORDER_HI
                )
                if i < 2:
                    draw_box(
                        ax, wx + 0.14, py, w_w - 0.28, ph,
                        facecolor=BOX_INNER, edgecolor=app_edge, lw=1.4, radius=0.10, alpha=aa, zorder=4,
                    )
                    ax.text(
                        wx + w_w / 2, py + ph * 0.64,
                        f"web@{i + 1}",
                        color=TEXT_MAIN, fontsize=9.2, family="monospace", fontweight="bold",
                        ha="center", va="center", alpha=aa, zorder=5,
                    )
                    ax.text(
                        wx + w_w / 2, py + ph * 0.26,
                        f"10.0.1.{i + 1}:8080",
                        color=ACCENT_TEAL if st["active_step"] == 4 else TEXT_SUB,
                        fontsize=7.3, family="monospace", ha="center", va="center", alpha=aa, zorder=5,
                    )
                else:
                    # Worker 3: web@3 + nginx side by side
                    sub_gap = 0.10
                    sub_w = (w_w - 0.28 - sub_gap) / 2
                    # web@3
                    draw_box(
                        ax, wx + 0.14, py, sub_w, ph,
                        facecolor=BOX_INNER, edgecolor=app_edge, lw=1.4, radius=0.10, alpha=aa, zorder=4,
                    )
                    ax.text(
                        wx + 0.14 + sub_w / 2, py + ph * 0.64,
                        "web@3",
                        color=TEXT_MAIN, fontsize=8.6, family="monospace", fontweight="bold",
                        ha="center", va="center", alpha=aa, zorder=5,
                    )
                    ax.text(
                        wx + 0.14 + sub_w / 2, py + ph * 0.26,
                        ":8080",
                        color=ACCENT_TEAL if st["active_step"] == 4 else TEXT_SUB,
                        fontsize=7.3, family="monospace", ha="center", va="center", alpha=aa, zorder=5,
                    )
                    # nginx proxy
                    nx_x = wx + 0.14 + sub_w + sub_gap
                    ng_edge = blend_hex(app_edge, ACCENT_TEAL, st["nginx_hi"])
                    ng_lw = 1.4 + 0.8 * st["nginx_hi"]
                    draw_box(
                        ax, nx_x, py, sub_w, ph,
                        facecolor=BOX_INNER, edgecolor=ng_edge, lw=ng_lw, radius=0.10, alpha=aa, zorder=4,
                    )
                    ax.text(
                        nx_x + sub_w / 2, py + ph * 0.64,
                        "nginx",
                        color=ACCENT_TEAL if st["nginx_hi"] > 0.3 else TEXT_MAIN,
                        fontsize=8.6, family="monospace", fontweight="bold",
                        ha="center", va="center", alpha=aa, zorder=5,
                    )
                    ax.text(
                        nx_x + sub_w / 2, py + ph * 0.26,
                        "proxy",
                        color=ACCENT_TEAL if st["nginx_hi"] > 0.3 else TEXT_SUB,
                        fontsize=7.3, ha="center", va="center", alpha=aa, zorder=5,
                    )

            # Row 3: locksmithd pill (Step 5+)
            if st["locksmith_alpha"] > 0.01:
                la = st["locksmith_alpha"] * wa
                l_edge = ACCENT_GREEN if st["active_step"] == 5 else BOX_BORDER_HI
                py = w_y + 0.22
                ph = 0.62
                draw_box(
                    ax, wx + 0.14, py, w_w - 0.28, ph,
                    facecolor=BOX_INNER, edgecolor=l_edge, lw=1.5 if st["active_step"] == 5 else 1.2,
                    radius=0.10, alpha=la, zorder=4,
                )
                ax.text(
                    wx + w_w / 2, py + ph * 0.64,
                    "locksmithd",
                    color=ACCENT_GREEN if st["active_step"] == 5 else TEXT_MAIN,
                    fontsize=8.8, family="monospace", fontweight="bold",
                    ha="center", va="center", alpha=la, zorder=5,
                )
                ax.text(
                    wx + w_w / 2, py + ph * 0.26,
                    "A/B OS updates",
                    color=TEXT_SUB, fontsize=7.4, ha="center", va="center", alpha=la, zorder=5,
                )

    # Draw traveling pulses on top of connectors
    for src_k, dst_k, t_p, p_col in st["pulses"]:
        draw_pulse_dot(ax, anchors[src_k], anchors[dst_k], t_p, p_col)

    # -------------------------------------------------------------------------
    # Bridge Connector: Left etcd Hub -> Right etcd Keyspace Panel
    # -------------------------------------------------------------------------
    rx, ry, rw, rh = 8.92, 1.05, 6.66, 5.77
    ax.annotate(
        "",
        xy=(rx - 0.05, ey + eh / 2),
        xytext=(ex + ew + 0.05, ey + eh / 2),
        arrowprops=dict(arrowstyle="->", color=ACCENT_BLUE, lw=1.8, ls=":", alpha=0.88),
        zorder=3,
    )

    # -------------------------------------------------------------------------
    # Right Pane: Live Growing etcd Directory Tree
    # -------------------------------------------------------------------------
    draw_box(
        ax, rx, ry, rw, rh,
        facecolor=PANEL_BG, edgecolor=ACCENT_BLUE if st["active_step"] in (1, 6) else BOX_BORDER_HI,
        lw=1.9, radius=0.18, zorder=3,
    )

    # Panel title header bar
    header_y = ry + rh - 0.56
    ax.plot([rx + 0.16, rx + rw - 0.16], [header_y, header_y], color=BOX_BORDER, lw=1.1, zorder=4)
    ax.text(
        rx + 0.28, ry + rh - 0.29,
        "Inside etcd: Shared Keyspace",
        color=TEXT_MAIN, fontsize=10.6, fontweight="bold", ha="left", va="center", zorder=4,
    )
    # Key counter badge (top-right inside panel)
    badge_w, badge_h = 1.62, 0.34
    draw_box(
        ax, rx + rw - badge_w - 0.22, ry + rh - 0.46, badge_w, badge_h,
        facecolor=BOX_INNER, edgecolor=BOX_BORDER_HI, lw=1.1, radius=0.09, zorder=4,
    )
    ax.text(
        rx + rw - badge_w / 2 - 0.22, ry + rh - 0.29,
        st["key_badge"],
        color=ACCENT_BLUE, fontsize=8.3, family="monospace", fontweight="bold",
        ha="center", va="center", zorder=5,
    )

    # Build exact dynamic ASCII tree lines (strictly top-to-bottom, zero reflow!)
    has_fleet = st["k_fleet_base"] > 0.02
    has_jobs = st["k_fleet_jobs"] > 0.02
    has_cfg = st["k_config"] > 0.02
    has_svc = st["k_services"] > 0.02
    has_lock = st["k_locksmith"] > 0.02

    p_fleet = "├──" if has_cfg else "└──"
    c_fleet = "│" if has_cfg else " "
    p_mach = "├──" if has_jobs else "└──"

    p_cfg = "├──" if has_svc else "└──"
    c_cfg = "│" if has_svc else " "

    p_svc = "├──" if has_lock else "└──"
    c_svc = "│" if has_lock else " "

    # (text, alpha, group_name, accent_color)
    tree_rows = [
        ("/" + ("   (empty)" if not has_fleet else ""), 1.0, "root", ACCENT_BLUE),
        (f"{p_fleet} _coreos.com/fleet/", st["k_fleet_base"], "fleet_base", ACCENT_AMBER),
        (f'{c_fleet}   ├── lease/engine-leader = "worker-2"', st["k_fleet_base"], "fleet_base", ACCENT_AMBER),
        (f"{c_fleet}   {p_mach} machines/worker-1..3  (heartbeats)", st["k_fleet_base"], "fleet_base", ACCENT_AMBER),
        (f"{c_fleet}   └── job/web@1..3, nginx  (4 units)", st["k_fleet_jobs"], "fleet_jobs", ACCENT_VIOLET),
        (f"{p_cfg} config/web/", st["k_config"], "config", ACCENT_VIOLET),
        (f'{c_cfg}   └── rate_limit = "100rps"', st["k_config"], "config", ACCENT_VIOLET),
        (f"{p_svc} services/web/", st["k_services"], "services", ACCENT_TEAL),
        (f'{c_svc}   ├── web@1 = "10.0.1.1:8080"', st["k_services"], "services", ACCENT_TEAL),
        (f'{c_svc}   ├── web@2 = "10.0.1.2:8080"', st["k_services"], "services", ACCENT_TEAL),
        (f'{c_svc}   └── web@3 = "10.0.1.3:8080"', st["k_services"], "services", ACCENT_TEAL),
        ("└── coreos.com/updateengine/", st["k_locksmith"], "locksmith", ACCENT_GREEN),
        ("    └── rebootlock/semaphore  (max: 1)", st["k_locksmith"], "locksmith", ACCENT_GREEN),
    ]

    top_line_y = header_y - 0.29
    line_dy = 0.322
    active_groups = st["active_tree_groups"]

    for idx, (text, alpha, grp, accent) in enumerate(tree_rows):
        if alpha <= 0.01:
            continue
        ly = top_line_y - idx * line_dy
        is_active = grp in active_groups
        if is_active:
            draw_box(
                ax, rx + 0.16, ly - 0.135, rw - 0.32, 0.28,
                facecolor=accent, edgecolor="none", radius=0.06, alpha=0.14 * alpha, zorder=4,
            )
            txt_col = TEXT_MAIN if idx > 0 else ACCENT_BLUE
            # Add thin left accent bar for newly introduced rows
            draw_box(
                ax, rx + 0.16, ly - 0.125, 0.06, 0.26,
                facecolor=accent, edgecolor="none", radius=0.02, alpha=0.95 * alpha, zorder=5,
            )
        else:
            if grp == "root":
                txt_col = ACCENT_BLUE
            elif text.strip().endswith("/"):
                txt_col = blend_hex(TEXT_SOFT, accent, 0.55)
            else:
                txt_col = TEXT_SOFT

        ax.text(
            rx + 0.32, ly,
            text,
            color=txt_col,
            fontsize=9.2,
            family="monospace",
            fontweight="bold" if (is_active or grp == "root" or text.strip().endswith("/")) else "normal",
            ha="left", va="center",
            alpha=alpha,
            zorder=6,
        )

    # Summary scale banner inside bottom of right panel (Step 6)
    if st["summary_alpha"] > 0.01:
        sa = st["summary_alpha"]
        draw_box(
            ax, rx + 0.22, ry + 0.18, rw - 0.44, 0.44,
            facecolor=BOX_BG, edgecolor=ACCENT_BLUE, lw=1.4, radius=0.10, alpha=sa, zorder=5,
        )
        ax.text(
            rx + rw / 2, ry + 0.40,
            "Tiny working set: dozens of keys in practice (< 1 MB) · low write rate",
            color=ACCENT_BLUE, fontsize=8.3, fontweight="bold", ha="center", va="center", alpha=sa, zorder=6,
        )

    # -------------------------------------------------------------------------
    # Bottom Progress Bar + Hub-and-Spoke Reminder
    # -------------------------------------------------------------------------
    pill_y, pill_h = 0.30, 0.40
    pill_x = 0.45
    pill_widths = [1.20, 1.38, 2.22, 1.62, 1.78]
    pill_gap = 0.15

    for (step_num, label, col), pw in zip(STEP_PILLS, pill_widths):
        is_current = (st["active_step"] == step_num)
        is_done = (st["active_step"] > step_num)
        if is_current:
            fc, ec, tc, lw = col, col, BG_COLOR, 1.2
            p_alpha = 0.95
        elif is_done:
            fc, ec, tc, lw = BOX_BG, col, TEXT_SOFT, 1.1
            p_alpha = 0.85
        else:
            fc, ec, tc, lw = PANEL_BG, BOX_BORDER, TEXT_DIM, 1.0
            p_alpha = 0.65

        draw_box(ax, pill_x, pill_y, pw, pill_h, facecolor=fc, edgecolor=ec, lw=lw, radius=0.11, alpha=p_alpha, zorder=3)
        ax.text(
            pill_x + pw / 2, pill_y + pill_h / 2,
            label, color=tc, fontsize=8.4, fontweight="bold" if is_current else "normal",
            ha="center", va="center", zorder=4,
        )
        pill_x += pw + pill_gap

    # Right-aligned bottom architectural note
    ax.text(
        15.55, pill_y + pill_h / 2,
        "Hub-and-spoke: daemons never talk peer-to-peer",
        color=TEXT_SUB if st["workers_alpha"] > 0.5 else TEXT_DIM,
        fontsize=8.6, style="italic", ha="right", va="center",
    )

    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    return fig_to_rgb(fig)


def render(
    out_dir: Path,
    fps: int = 16,
    formats: Iterable[str] = ("webp",),
    save_previews: bool = False,
    preview_dir: Optional[Path] = None,
) -> List[Path]:
    states, previews = build_timeline()
    print(f"[{NAME}] Rendering {len(states)} frames at {fps} FPS...")
    frames_rgb = [render_frame(st) for st in states]
    written = export_animation(
        frames_rgb=frames_rgb,
        out_dir=out_dir,
        stem=NAME,
        fps=fps,
        formats=formats,
        preview_frames=previews if save_previews else None,
        preview_dir=preview_dir,
        final_hold_ms=7500,  # ~10s total calm hold on the final complete diagram before looping
    )
    for p in written:
        size_kb = p.stat().st_size / 1024.0
        print(f"[{NAME}] Wrote {p} ({size_kb:.1f} KB)")
    return written
