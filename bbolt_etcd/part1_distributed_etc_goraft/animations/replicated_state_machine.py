"""Animation 3: How etcd's Replicated State Machine Handles a PUT Request.

A clean, minimal conceptual animation matching the visual language of
`ttl_key_heap.py` and `event_history_ring_buffer.py`:
  - Top: A pre-plotted continuous timeline with 5 shaded step zones and a smooth
    moving playhead walking through the lifecycle of a single PUT request
    (no changing narrative paragraphs).
  - Main Stage:
      * Left: Client (`Worker 1 · locksmithd`) sending the example CAS PUT
        (`PUT .../semaphore`, `prevIndex=5`, `holders=["worker-1"]`).
      * Center: `etcd-1` (`LEADER`) with its on-disk `/var/lib/etcd/log` and
        in-memory `store` (RAM).
      * Right: `etcd-2` and `etcd-3` (`FOLLOWER`), each with the exact same
        on-disk `/var/lib/etcd/log` -> `apply` -> in-memory `store` pipeline.
  - Final hold: 8.5 seconds on the converged final state before looping.
"""

from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch

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
    ease_in_out,
    export_animation,
    fig_to_rgb,
    progress,
)

NAME = "replicated_state_machine"
DESCRIPTION = "Pre-plotted timeline + Client + 3-node etcd Replicated State Machine walking through a single PUT request."

T_MAX = 100.0
ZONE_SPLITS = (20.0, 40.0, 62.0, 82.0)

# (t_pos, label, accent_color)
TIMELINE_MILESTONES: List[Tuple[float, str, str]] = [
    (10.0, "PUT :4001\n.../semaphore", ACCENT_BLUE),
    (30.0, "append #42\nto leader log", ACCENT_AMBER),
    (51.0, "AppendEntries\n:7001 + ACK", ACCENT_TEAL),
    (72.0, "quorum 2/3\napply & 200 OK", ACCENT_GREEN),
    (91.0, "followers\napply #42", ACCENT_VIOLET),
]

# Geometry constants (16.0 x 8.5 canvas)
CLIENT_X, CLIENT_Y, CLIENT_W, CLIENT_H = 0.55, 2.18, 2.55, 2.28

NODE_W, NODE_H = 4.05, 2.48
LEADER_X, LEADER_Y = 4.95, 2.08
F2_X, F2_Y = 11.40, 3.44
F3_X, F3_Y = 11.40, 0.72


def _lerp_t(t0: float, t1: float, i: int, n: int) -> float:
    if n <= 1:
        return t1
    return t0 + (t1 - t0) * (i / float(n - 1))


def _node_state(
    log_status: str = "empty",       # "empty" | "uncommitted" | "committed"
    log_flash: float = 0.0,
    apply_pulse: float = 0.0,        # 0..1 glow on Log -> store apply arrow
    applied: bool = False,
    store_flash: float = 0.0,
) -> Dict:
    return {
        "log_status": log_status,
        "log_flash": log_flash,
        "apply_pulse": apply_pulse,
        "applied": applied,
        "store_flash": store_flash,
    }


def _make_state(
    t_now: float,
    step: int,
    active_milestone_t: Optional[float],
    client_status: str,              # "idle" | "sending" | "waiting" | "ok"
    n1: Dict,
    n2: Dict,
    n3: Dict,
    put_pkt: Optional[Tuple[float, str, str]] = None,
    reply_pkt: Optional[Tuple[float, str, str]] = None,
    rep_f2_pkt: Optional[Tuple[float, str, str]] = None,
    rep_f3_pkt: Optional[Tuple[float, str, str]] = None,
    ack_f2_pkt: Optional[Tuple[float, str, str]] = None,
    ack_f3_pkt: Optional[Tuple[float, str, str]] = None,
    commit_f2_pkt: Optional[Tuple[float, str, str]] = None,
    commit_f3_pkt: Optional[Tuple[float, str, str]] = None,
) -> Dict:
    return {
        "t_now": t_now,
        "step": step,
        "active_milestone_t": active_milestone_t,
        "client_status": client_status,
        "n1": dict(n1),
        "n2": dict(n2),
        "n3": dict(n3),
        "put_pkt": put_pkt,
        "reply_pkt": reply_pkt,
        "rep_f2_pkt": rep_f2_pkt,
        "rep_f3_pkt": rep_f3_pkt,
        "ack_f2_pkt": ack_f2_pkt,
        "ack_f3_pkt": ack_f3_pkt,
        "commit_f2_pkt": commit_f2_pkt,
        "commit_f3_pkt": commit_f3_pkt,
    }


def build_timeline() -> Tuple[List[Dict], List[Tuple[int, str]]]:
    """Build frame-by-frame animation states and keyframe preview indices."""
    states: List[Dict] = []
    previews: List[Tuple[int, str]] = []

    def add_preview(label: str, offset_from_end: int = 2):
        idx = max(0, len(states) - offset_from_end)
        previews.append((idx, label))

    # =========================================================================
    # 0. Initial settled state: all 3 replicas start identical (idx 41)
    # =========================================================================
    n = 12
    for i in range(n):
        states.append(_make_state(
            t_now=_lerp_t(0.0, 4.0, i, n),
            step=1,
            active_milestone_t=None,
            client_status="idle",
            n1=_node_state(),
            n2=_node_state(),
            n3=_node_state(),
        ))

    # =========================================================================
    # STEP 1: Client sends PUT .../semaphore to Leader (:4001)  (t: 4 -> 20)
    # =========================================================================
    n = 28
    for i in range(n):
        pt = progress(i, 0, 22)
        pkt = (pt, "PUT semaphore", ACCENT_BLUE) if i < 22 else None
        states.append(_make_state(
            t_now=_lerp_t(4.0, 20.0, i, n),
            step=1,
            active_milestone_t=10.0,
            client_status="sending" if i < 18 else "waiting",
            n1=_node_state(),
            n2=_node_state(),
            n3=_node_state(),
            put_pkt=pkt,
        ))
    add_preview("step1_client_put", offset_from_end=16)

    # =========================================================================
    # STEP 2: Leader appends #42 to local /var/lib/etcd/log  (t: 20 -> 40)
    # =========================================================================
    n = 32
    for i in range(n):
        flash = max(0.0, 1.0 - progress(i, 4, 20)) if i >= 2 else progress(i, 0, 2)
        states.append(_make_state(
            t_now=_lerp_t(20.0, 40.0, i, n),
            step=2,
            active_milestone_t=30.0,
            client_status="waiting",
            n1=_node_state(log_status="uncommitted", log_flash=flash),
            n2=_node_state(),
            n3=_node_state(),
        ))
    add_preview("step2_leader_append", offset_from_end=18)

    # =========================================================================
    # STEP 3: Replicate via AppendEntries (:7001) & ACKs  (t: 40 -> 62)
    # =========================================================================
    # 3a. AppendEntries in flight to etcd-2 (arrives at i=20) & etcd-3 (arrives at i=24)
    n_rep = 28
    for i in range(n_rep):
        p2 = progress(i, 0, 20)
        p3 = progress(i, 0, 24)
        f2_appended = i >= 20
        f3_appended = i >= 24
        f2_flash = max(0.0, 1.0 - progress(i, 20, 10)) if f2_appended else 0.0
        f3_flash = max(0.0, 1.0 - progress(i, 24, 10)) if f3_appended else 0.0
        states.append(_make_state(
            t_now=_lerp_t(40.0, 52.0, i, n_rep),
            step=3,
            active_milestone_t=51.0,
            client_status="waiting",
            n1=_node_state(log_status="uncommitted"),
            n2=_node_state(log_status="uncommitted" if f2_appended else "empty", log_flash=f2_flash),
            n3=_node_state(log_status="uncommitted" if f3_appended else "empty", log_flash=f3_flash),
            rep_f2_pkt=(p2, "AppendEntries #42", ACCENT_TEAL) if i < 20 else None,
            rep_f3_pkt=(p3, "AppendEntries #42", ACCENT_TEAL) if i < 24 else None,
        ))
    add_preview("step3_replicate", offset_from_end=15)

    # 3b. Followers ACK back to Leader; etcd-2 lands first -> quorum (2/3) reached!
    n_ack = 22
    for i in range(n_ack):
        a2 = progress(i, 0, 16)
        a3 = progress(i, 4, 18)
        states.append(_make_state(
            t_now=_lerp_t(52.0, 62.0, i, n_ack),
            step=3,
            active_milestone_t=51.0,
            client_status="waiting",
            n1=_node_state(log_status="uncommitted"),
            n2=_node_state(log_status="uncommitted"),
            n3=_node_state(log_status="uncommitted"),
            ack_f2_pkt=(a2, "ACK #42", ACCENT_GREEN) if i < 16 else None,
            ack_f3_pkt=(a3, "ACK #42", ACCENT_GREEN) if 4 <= i < 22 else None,
        ))

    # =========================================================================
    # STEP 4: Leader commits #42, applies to RAM store & replies HTTP 200 OK
    # (t: 62 -> 82)
    # =========================================================================
    # 4a. Leader commits & applies to store
    n_apply = 24
    for i in range(n_apply):
        l_flash = max(0.0, 1.0 - progress(i, 0, 14))
        a_pulse = ease_in_out(progress(i, 4, 10)) * (1.0 - 0.55 * progress(i, 16, 8))
        applied = i >= 12
        s_flash = max(0.0, 1.0 - progress(i, 12, 12)) if applied else 0.0
        states.append(_make_state(
            t_now=_lerp_t(62.0, 72.0, i, n_apply),
            step=4,
            active_milestone_t=72.0,
            client_status="waiting",
            n1=_node_state(
                log_status="committed",
                log_flash=l_flash,
                apply_pulse=a_pulse,
                applied=applied,
                store_flash=s_flash,
            ),
            n2=_node_state(log_status="uncommitted"),
            n3=_node_state(log_status="uncommitted"),
        ))

    # 4b. Leader replies HTTP 200 OK to Client
    n_rep_cli = 24
    for i in range(n_rep_cli):
        rp = progress(i, 0, 16)
        cli_ok = i >= 16
        states.append(_make_state(
            t_now=_lerp_t(72.0, 82.0, i, n_rep_cli),
            step=4,
            active_milestone_t=72.0,
            client_status="ok" if cli_ok else "waiting",
            n1=_node_state(log_status="committed", applied=True),
            n2=_node_state(log_status="uncommitted"),
            n3=_node_state(log_status="uncommitted"),
            reply_pkt=(rp, "200 OK", ACCENT_GREEN) if i < 16 else None,
        ))
    add_preview("step4_commit_reply", offset_from_end=16)

    # =========================================================================
    # STEP 5: Leader notifies followers of commitIndex -> followers apply #42
    # (t: 82 -> 100)
    # =========================================================================
    # 5a. commit #42 sent to followers
    n_cm = 18
    for i in range(n_cm):
        cp = progress(i, 0, 15)
        states.append(_make_state(
            t_now=_lerp_t(82.0, 90.0, i, n_cm),
            step=5,
            active_milestone_t=91.0,
            client_status="ok",
            n1=_node_state(log_status="committed", applied=True),
            n2=_node_state(log_status="uncommitted"),
            n3=_node_state(log_status="uncommitted"),
            commit_f2_pkt=(cp, "commit #42", ACCENT_VIOLET) if i < 15 else None,
            commit_f3_pkt=(cp, "commit #42", ACCENT_VIOLET) if i < 15 else None,
        ))

    # 5b. Followers commit & apply #42 -> all 3 stores identical
    n_fapp = 26
    for i in range(n_fapp):
        l_flash = max(0.0, 1.0 - progress(i, 0, 12))
        a_pulse = ease_in_out(progress(i, 3, 9)) * (1.0 - progress(i, 16, 10))
        applied = i >= 10
        s_flash = max(0.0, 1.0 - progress(i, 10, 14)) if applied else 0.0
        states.append(_make_state(
            t_now=_lerp_t(90.0, 100.0, i, n_fapp),
            step=5,
            active_milestone_t=91.0,
            client_status="ok",
            n1=_node_state(log_status="committed", applied=True),
            n2=_node_state(
                log_status="committed",
                log_flash=l_flash,
                apply_pulse=a_pulse,
                applied=applied,
                store_flash=s_flash,
            ),
            n3=_node_state(
                log_status="committed",
                log_flash=l_flash,
                apply_pulse=a_pulse,
                applied=applied,
                store_flash=s_flash,
            ),
        ))

    # Final settled state (held cleanly via final_hold_ms=8500 in export_animation)
    states.append(_make_state(
        t_now=100.0,
        step=5,
        active_milestone_t=91.0,
        client_status="ok",
        n1=_node_state(log_status="committed", applied=True),
        n2=_node_state(log_status="committed", applied=True),
        n3=_node_state(log_status="committed", applied=True),
    ))
    add_preview("step5_converged", offset_from_end=1)

    return states, previews


def _draw_packet_xy(
    ax,
    p0: Tuple[float, float],
    p1: Tuple[float, float],
    t: float,
    label: str,
    color: str,
    pw: float = 1.48,
    ph: float = 0.30,
    zorder: int = 16,
):
    """Draw a smooth traveling pill packet along p0 -> p1."""
    if t <= 0.0 or t >= 1.0:
        return
    et = ease_in_out(t)
    cx = p0[0] + (p1[0] - p0[0]) * et
    cy = p0[1] + (p1[1] - p0[1]) * et
    fade = min(1.0, min(t, 1.0 - t) / 0.14)

    draw_box(
        ax, cx - pw / 2.0, cy - ph / 2.0, pw, ph,
        facecolor=blend_hex(BG_COLOR, color, 0.28),
        edgecolor=color, lw=1.6, radius=0.10, alpha=0.96 * fade, zorder=zorder,
    )
    ax.text(
        cx, cy, label,
        color=TEXT_MAIN, fontsize=7.2, family="monospace", fontweight="bold",
        ha="center", va="center", alpha=fade, zorder=zorder + 1,
    )


def _draw_etcd_node(
    ax,
    x: float,
    y: float,
    name: str,
    is_leader: bool,
    nst: Dict,
):
    """Draw one etcd replica card (On-Disk Log -> apply -> In-Memory store)."""
    w, h = NODE_W, NODE_H
    role_col = ACCENT_BLUE if is_leader else TEXT_SUB
    card_ec = blend_hex(BOX_BORDER, ACCENT_BLUE, 0.65) if is_leader else BOX_BORDER
    if nst["applied"] and nst["store_flash"] > 0.05:
        card_ec = blend_hex(card_ec, ACCENT_GREEN, 0.75 * nst["store_flash"])

    draw_box(ax, x, y, w, h, facecolor=PANEL_BG, edgecolor=card_ec, lw=1.6, radius=0.15, zorder=2)

    # Header row
    hdr_y = y + h - 0.21
    ax.text(
        x + 0.18, hdr_y,
        name,
        color=TEXT_MAIN, fontsize=10.5, family="monospace", fontweight="bold",
        ha="left", va="center", zorder=4,
    )
    badge_txt = "LEADER" if is_leader else "FOLLOWER"
    bw, bh = 0.92 if is_leader else 1.06, 0.25
    bx, by = x + w - bw - 0.16, hdr_y - bh / 2.0
    draw_box(
        ax, bx, by, bw, bh,
        facecolor=blend_hex(BOX_INNER, role_col, 0.24) if is_leader else BOX_INNER,
        edgecolor=role_col if is_leader else BOX_BORDER_HI,
        lw=1.2, radius=0.07, zorder=3,
    )
    ax.text(
        bx + bw / 2.0, hdr_y,
        badge_txt,
        color=ACCENT_BLUE if is_leader else TEXT_SUB,
        fontsize=7.1, family="monospace", fontweight="bold",
        ha="center", va="center", zorder=4,
    )

    # -------------------------------------------------------------------------
    # Sub-box 1: On-Disk Log (/var/lib/etcd/log)
    # -------------------------------------------------------------------------
    log_x = x + 0.16
    log_w = w - 0.32
    log_h = 0.78
    log_y = y + h - 0.38 - log_h

    l_status = nst["log_status"]
    l_flash = nst["log_flash"]
    if l_status == "committed":
        log_ec = blend_hex(BOX_BORDER_HI, ACCENT_GREEN, 0.55 + 0.45 * l_flash)
    elif l_status == "uncommitted":
        log_ec = blend_hex(BOX_BORDER_HI, ACCENT_AMBER, 0.55 + 0.45 * l_flash)
    else:
        log_ec = BOX_BORDER

    draw_box(ax, log_x, log_y, log_w, log_h, facecolor=BOX_BG, edgecolor=log_ec, lw=1.3, radius=0.10, zorder=3)
    ax.text(
        log_x + 0.12, log_y + log_h - 0.16,
        "On-Disk Log",
        color=TEXT_SOFT, fontsize=7.7, fontweight="bold", ha="left", va="center", zorder=4,
    )
    ax.text(
        log_x + log_w - 0.12, log_y + log_h - 0.16,
        "/var/lib/etcd/log",
        color=TEXT_DIM, fontsize=6.8, family="monospace", ha="right", va="center", zorder=4,
    )

    # Horizontal append-only log slots: [... #41 ✓] [ #42 CAS semaphore ]
    slot_y = log_y + 0.10
    slot_h = 0.38
    # Prior committed entry #41
    s41_x, s41_w = log_x + 0.11, 0.86
    draw_box(ax, s41_x, slot_y, s41_w, slot_h, facecolor=BOX_INNER, edgecolor=BOX_BORDER, lw=1.0, radius=0.07, zorder=4)
    ax.text(
        s41_x + s41_w / 2.0, slot_y + slot_h / 2.0,
        "… #41 ✓",
        color=TEXT_DIM, fontsize=7.2, family="monospace", ha="center", va="center", zorder=5,
    )

    # New entry #42
    s42_x = s41_x + s41_w + 0.09
    s42_w = log_x + log_w - 0.11 - s42_x
    if l_status == "empty":
        draw_box(
            ax, s42_x, slot_y, s42_w, slot_h,
            facecolor=BOX_INNER, edgecolor=BOX_BORDER, lw=1.0, linestyle="--", radius=0.07, zorder=4,
        )
        ax.text(
            s42_x + s42_w / 2.0, slot_y + slot_h / 2.0,
            "(next log entry)",
            color=TEXT_DIM, fontsize=7.1, family="monospace", style="italic", ha="center", va="center", zorder=5,
        )
    else:
        scol = ACCENT_GREEN if l_status == "committed" else ACCENT_AMBER
        fc = blend_hex(BOX_INNER, scol, 0.22 + 0.20 * l_flash)
        draw_box(ax, s42_x, slot_y, s42_w, slot_h, facecolor=fc, edgecolor=scol, lw=1.5, radius=0.07, zorder=4)
        ax.text(
            s42_x + 0.10, slot_y + slot_h / 2.0,
            "#42 CAS semaphore",
            color=TEXT_MAIN, fontsize=7.2, family="monospace", fontweight="bold", ha="left", va="center", zorder=5,
        )
        tag_txt = "✓" if l_status == "committed" else "pending"
        ax.text(
            s42_x + s42_w - 0.09, slot_y + slot_h / 2.0,
            tag_txt,
            color=scol, fontsize=6.9 if tag_txt != "✓" else 8.6, family="monospace", fontweight="bold",
            ha="right", va="center", zorder=5,
        )

    # -------------------------------------------------------------------------
    # Middle Arrow: Log -> In-Memory store (apply)
    # -------------------------------------------------------------------------
    st_x = x + 0.16
    st_w = w - 0.32
    st_h = 0.78
    st_y = y + 0.14

    arr_x = x + w / 2.0
    ap = nst["apply_pulse"]
    arr_col = blend_hex(BOX_BORDER_HI, ACCENT_GREEN, max(ap, 0.45 if nst["applied"] else 0.0))
    arr_lw = 1.6 + 1.4 * ap
    arr = FancyArrowPatch(
        (arr_x, log_y - 0.03),
        (arr_x, st_y + st_h + 0.03),
        arrowstyle="-|>,head_length=5.0,head_width=3.2",
        color=arr_col, linewidth=arr_lw, zorder=5,
    )
    ax.add_patch(arr)
    ax.text(
        arr_x + 0.15, (log_y + st_y + st_h) / 2.0,
        "apply",
        color=ACCENT_GREEN if (ap > 0.15 or nst["applied"]) else TEXT_DIM,
        fontsize=7.3, family="monospace", fontweight="bold" if ap > 0.15 else "normal",
        ha="left", va="center", zorder=5,
    )

    # -------------------------------------------------------------------------
    # Sub-box 2: In-Memory store (RAM)
    # -------------------------------------------------------------------------
    applied = nst["applied"]
    s_flash = nst["store_flash"]
    st_ec = blend_hex(BOX_BORDER_HI, ACCENT_GREEN, 0.55 + 0.45 * s_flash) if applied else BOX_BORDER
    draw_box(ax, st_x, st_y, st_w, st_h, facecolor=BOX_BG, edgecolor=st_ec, lw=1.3, radius=0.10, zorder=3)

    ax.text(
        st_x + 0.12, st_y + st_h - 0.16,
        "In-Memory store (RAM)",
        color=TEXT_SOFT, fontsize=7.7, fontweight="bold", ha="left", va="center", zorder=4,
    )
    idx_val = "42" if applied else "41"
    ax.text(
        st_x + st_w - 0.12, st_y + st_h - 0.16,
        f"CurrentIndex: {idx_val}",
        color=ACCENT_GREEN if applied else TEXT_SUB,
        fontsize=7.2, family="monospace", fontweight="bold" if applied else "normal",
        ha="right", va="center", zorder=4,
    )

    # Key-value state row
    kv_y, kv_h = st_y + 0.10, 0.38
    kv_fc = blend_hex(BOX_INNER, ACCENT_GREEN, 0.18 + 0.22 * s_flash) if applied else BOX_INNER
    kv_ec = ACCENT_GREEN if applied else BOX_BORDER
    draw_box(ax, st_x + 0.11, kv_y, st_w - 0.22, kv_h, facecolor=kv_fc, edgecolor=kv_ec, lw=1.2 if applied else 1.0, radius=0.07, zorder=4)

    val_txt = 'semaphore: ["worker-1"]' if applied else "semaphore: []"
    mod_txt = "idx 42" if applied else "idx 5"
    ax.text(
        st_x + 0.22, kv_y + kv_h / 2.0,
        val_txt,
        color=TEXT_MAIN if applied else TEXT_SOFT,
        fontsize=7.5, family="monospace", fontweight="bold" if applied else "normal",
        ha="left", va="center", zorder=5,
    )
    ax.text(
        st_x + st_w - 0.22, kv_y + kv_h / 2.0,
        mod_txt,
        color=ACCENT_GREEN if applied else TEXT_DIM,
        fontsize=7.2, family="monospace", fontweight="bold" if applied else "normal",
        ha="right", va="center", zorder=5,
    )


def render_frame(st: Dict, dpi: int = 125):
    fig, ax = plt.subplots(figsize=(12.8, 6.8), dpi=dpi)
    fig.patch.set_facecolor(BG_COLOR)
    ax.set_facecolor(BG_COLOR)
    ax.set_xlim(0.0, 16.0)
    ax.set_ylim(0.0, 8.5)
    ax.axis("off")

    t_now = st["t_now"]

    # -------------------------------------------------------------------------
    # Header: Clean Static Title Only
    # -------------------------------------------------------------------------
    ax.text(
        8.0, 8.12,
        "How etcd's Replicated State Machine Handles a PUT Request",
        color=TEXT_MAIN, fontsize=15.0, fontweight="bold", ha="center", va="center",
    )

    # -------------------------------------------------------------------------
    # Top Panel: Pre-Plotted Continuous Timeline (matching ttl_key_heap & event_history)
    # -------------------------------------------------------------------------
    tl_x, tl_y, tl_w, tl_h = 0.55, 6.12, 14.90, 1.62
    draw_box(ax, tl_x, tl_y, tl_w, tl_h, facecolor=PANEL_BG, edgecolor=BOX_BORDER, lw=1.5, radius=0.16, zorder=1)

    track_x0 = 1.10
    track_x1 = 14.90
    track_y = 6.54

    def t_to_x(t_val: float) -> float:
        return track_x0 + (track_x1 - track_x0) * clamp(t_val / T_MAX, 0.0, 1.0)

    s1, s2, s3, s4 = (t_to_x(z) for z in ZONE_SPLITS)
    zone_defs = [
        (tl_x + 0.12, s1 - 0.03, ACCENT_BLUE,   1, "1. CLIENT PUT"),
        (s1 + 0.03,   s2 - 0.03, ACCENT_AMBER,  2, "2. APPEND LOG"),
        (s2 + 0.03,   s3 - 0.03, ACCENT_TEAL,   3, "3. REPLICATE"),
        (s3 + 0.03,   s4 - 0.03, ACCENT_GREEN,  4, "4. COMMIT & REPLY"),
        (s4 + 0.03,   tl_x + tl_w - 0.12, ACCENT_VIOLET, 5, "5. FOLLOWERS APPLY"),
    ]
    for zx0, zx1, zcol, z_step, z_lbl in zone_defs:
        is_cur = (st["step"] == z_step)
        draw_box(
            ax, zx0, tl_y + 0.12, zx1 - zx0, tl_h - 0.24,
            facecolor=blend_hex(PANEL_BG, zcol, 0.07 if is_cur else 0.025),
            edgecolor="none", lw=0, radius=0.09, zorder=2,
        )
        ax.text(
            (zx0 + zx1) / 2.0, tl_y + tl_h - 0.23,
            z_lbl,
            color=zcol if is_cur else TEXT_DIM,
            fontsize=7.6, fontweight="bold", ha="center", va="center", zorder=4,
        )
    for sx_split in (s1, s2, s3, s4):
        ax.plot(
            [sx_split, sx_split], [tl_y + 0.15, tl_y + tl_h - 0.15],
            color=BOX_BORDER_HI, lw=1.0, linestyle="--", alpha=0.65, zorder=3,
        )

    # Base track + elapsed progress highlight
    ax.plot([track_x0, track_x1], [track_y, track_y], color=BOX_BORDER_HI, lw=2.8, solid_capstyle="round", zorder=3)
    now_x = t_to_x(t_now)
    if t_now > 0.2:
        ax.plot([track_x0, now_x], [track_y, track_y], color=TEXT_MAIN, lw=3.2, solid_capstyle="round", alpha=0.88, zorder=4)

    # Pre-plotted milestones
    active_mt = st["active_milestone_t"]
    for mt, label, mcol in TIMELINE_MILESTONES:
        mx = t_to_x(mt)
        is_active = active_mt is not None and abs(active_mt - mt) < 0.01
        is_past = mt < t_now - 0.5
        is_future = mt > t_now + 0.5
        ev_alpha = 1.0 if is_active else (0.58 if is_past else 0.80)

        if is_active:
            ax.add_patch(Circle((mx, track_y), 0.18, facecolor=mcol, edgecolor="none", alpha=0.28, zorder=5))

        fc = mcol if not is_future else BG_COLOR
        ax.add_patch(Circle(
            (mx, track_y), 0.095 if is_active else 0.080,
            facecolor=fc, edgecolor=mcol, lw=1.8, alpha=ev_alpha, zorder=6,
        ))

        lbl_col = mcol if is_active else (TEXT_SOFT if not is_future else blend_hex(TEXT_DIM, mcol, 0.48))
        ax.text(
            mx, track_y + 0.42,
            label,
            color=lbl_col,
            fontsize=7.6 if is_active else 7.2,
            family="monospace",
            fontweight="bold" if is_active else "normal",
            ha="center", va="center",
            linespacing=1.12,
            alpha=1.0 if is_active else (0.72 if is_past else 0.88),
            zorder=7,
        )

    # Moving vertical playhead
    ax.plot([now_x, now_x], [track_y - 0.15, track_y + 0.17], color=TEXT_MAIN, lw=2.4, solid_capstyle="round", zorder=10)
    ax.add_patch(Circle((now_x, track_y), 0.060, facecolor=TEXT_MAIN, edgecolor=BG_COLOR, lw=0.8, zorder=11))

    # -------------------------------------------------------------------------
    # Main Stage Left: Client (Worker 1 · locksmithd)
    # -------------------------------------------------------------------------
    cx, cy, cw, ch = CLIENT_X, CLIENT_Y, CLIENT_W, CLIENT_H
    cst = st["client_status"]
    cli_col = ACCENT_GREEN if cst == "ok" else (ACCENT_BLUE if cst in ("sending", "waiting") else BOX_BORDER)
    cli_ec = blend_hex(BOX_BORDER, cli_col, 0.78) if cli_col != BOX_BORDER else BOX_BORDER
    draw_box(ax, cx, cy, cw, ch, facecolor=PANEL_BG, edgecolor=cli_ec, lw=1.6, radius=0.15, zorder=2)

    ax.text(
        cx + cw / 2.0, cy + ch - 0.26,
        "Client",
        color=TEXT_MAIN, fontsize=10.8, fontweight="bold", ha="center", va="center", zorder=4,
    )
    ax.text(
        cx + cw / 2.0, cy + ch - 0.50,
        "Worker 1 · locksmithd",
        color=TEXT_SUB, fontsize=7.6, family="monospace", ha="center", va="center", zorder=4,
    )

    # Example PUT request box
    req_x, req_y, req_w, req_h = cx + 0.18, cy + 0.84, cw - 0.36, 0.78
    draw_box(
        ax, req_x, req_y, req_w, req_h,
        facecolor=blend_hex(BOX_INNER, ACCENT_BLUE, 0.14) if cst != "idle" else BOX_INNER,
        edgecolor=ACCENT_BLUE if cst == "sending" else BOX_BORDER_HI,
        lw=1.3, radius=0.09, zorder=3,
    )
    ax.text(
        cx + cw / 2.0, req_y + req_h - 0.18,
        "PUT .../semaphore",
        color=ACCENT_BLUE, fontsize=7.9, family="monospace", fontweight="bold", ha="center", va="center", zorder=4,
    )
    ax.text(
        cx + cw / 2.0, req_y + 0.36,
        "prevIndex=5",
        color=TEXT_SOFT, fontsize=7.3, family="monospace", ha="center", va="center", zorder=4,
    )
    ax.text(
        cx + cw / 2.0, req_y + 0.15,
        'holders=["worker-1"]',
        color=TEXT_SOFT, fontsize=7.2, family="monospace", ha="center", va="center", zorder=4,
    )

    # Response status box
    res_x, res_y, res_w, res_h = cx + 0.18, cy + 0.18, cw - 0.36, 0.50
    if cst == "ok":
        res_fc, res_ec, res_tc = blend_hex(BOX_INNER, ACCENT_GREEN, 0.22), ACCENT_GREEN, ACCENT_GREEN
        res_txt = "HTTP 200 OK (idx 42)"
    elif cst in ("sending", "waiting"):
        res_fc, res_ec, res_tc = BOX_INNER, BOX_BORDER_HI, TEXT_SOFT
        res_txt = "waiting for reply…"
    else:
        res_fc, res_ec, res_tc = BOX_INNER, BOX_BORDER, TEXT_DIM
        res_txt = "(ready)"
    draw_box(ax, res_x, res_y, res_w, res_h, facecolor=res_fc, edgecolor=res_ec, lw=1.3 if cst == "ok" else 1.0, radius=0.09, zorder=3)
    ax.text(
        cx + cw / 2.0, res_y + res_h / 2.0,
        res_txt,
        color=res_tc, fontsize=7.5, family="monospace",
        fontweight="bold" if cst == "ok" else "normal",
        style="italic" if cst == "idle" else "normal",
        ha="center", va="center", zorder=4,
    )

    # -------------------------------------------------------------------------
    # Main Stage: 3 etcd Replicas (Leader + 2 Followers)
    # -------------------------------------------------------------------------
    _draw_etcd_node(ax, LEADER_X, LEADER_Y, "etcd-1", True, st["n1"])
    _draw_etcd_node(ax, F2_X, F2_Y, "etcd-2", False, st["n2"])
    _draw_etcd_node(ax, F3_X, F3_Y, "etcd-3", False, st["n3"])

    # -------------------------------------------------------------------------
    # Network Arrows: Client <-> Leader (:4001) and Leader <-> Followers (:7001)
    # -------------------------------------------------------------------------
    c_put_y = 3.72
    c_rep_y = 2.66
    c_x0 = CLIENT_X + CLIENT_W + 0.05
    c_x1 = LEADER_X - 0.05

    for (ys, xs, xe, lbl, yoff) in [
        (c_put_y, c_x0, c_x1, "HTTP :4001", +0.26),
        (c_rep_y, c_x1, c_x0, "Response",   -0.26),
    ]:
        ax.add_patch(FancyArrowPatch(
            (xs, ys), (xe, ys),
            arrowstyle="-|>,head_length=4.8,head_width=3.0",
            color=BOX_BORDER_HI, linewidth=1.3, linestyle=":", alpha=0.70, zorder=2,
        ))
        ax.text(
            (c_x0 + c_x1) / 2.0, ys + yoff,
            lbl, color=TEXT_DIM, fontsize=7.1, family="monospace", ha="center", va="center", zorder=2,
        )

    # Leader <-> Follower log-level link coordinates
    l_rx = LEADER_X + NODE_W + 0.05
    f_lx = F2_X - 0.05
    l_log_y = LEADER_Y + NODE_H - 0.77
    f2_log_y = F2_Y + NODE_H - 0.77
    f3_log_y = F3_Y + NODE_H - 0.77

    # Outbound replication tracks (Leader -> Followers)
    for (p0, p1) in [
        ((l_rx, l_log_y + 0.10), (f_lx, f2_log_y + 0.08)),
        ((l_rx, l_log_y - 0.14), (f_lx, f3_log_y + 0.08)),
    ]:
        ax.add_patch(FancyArrowPatch(
            p0, p1,
            arrowstyle="-|>,head_length=4.8,head_width=3.0",
            color=BOX_BORDER_HI, linewidth=1.3, linestyle=":", alpha=0.70, zorder=2,
        ))

    # Return ACK tracks (Followers -> Leader)
    for (p0, p1) in [
        ((f_lx, f2_log_y - 0.24), (l_rx, l_log_y - 0.04)),
        ((f_lx, f3_log_y - 0.24), (l_rx, l_log_y - 0.30)),
    ]:
        ax.add_patch(FancyArrowPatch(
            p0, p1,
            arrowstyle="-|>,head_length=4.5,head_width=2.8",
            color=BOX_BORDER, linewidth=1.1, linestyle=":", alpha=0.55, zorder=2,
        ))

    ax.text(
        (l_rx + f_lx) / 2.0, 3.32,
        "Raft :7001",
        color=TEXT_DIM, fontsize=7.1, family="monospace", ha="center", va="center", zorder=2,
    )

    # Animated packets (endpoints inset so pill never overlaps card borders)
    if st["put_pkt"] is not None:
        pt, plbl, pcol = st["put_pkt"]
        pw = 1.28
        _draw_packet_xy(ax, (c_x0 + pw / 2.0, c_put_y), (c_x1 - pw / 2.0, c_put_y), pt, plbl, pcol, pw=pw)

    if st["reply_pkt"] is not None:
        pt, plbl, pcol = st["reply_pkt"]
        pw = 0.96
        _draw_packet_xy(ax, (c_x1 - pw / 2.0, c_rep_y), (c_x0 + pw / 2.0, c_rep_y), pt, plbl, pcol, pw=pw)

    if st["rep_f2_pkt"] is not None:
        pt, plbl, pcol = st["rep_f2_pkt"]
        _draw_packet_xy(ax, (l_rx + 0.56, l_log_y + 0.14), (f_lx - 0.56, f2_log_y + 0.04), pt, plbl, pcol, pw=1.56)

    if st["rep_f3_pkt"] is not None:
        pt, plbl, pcol = st["rep_f3_pkt"]
        _draw_packet_xy(ax, (l_rx + 0.56, l_log_y - 0.18), (f_lx - 0.56, f3_log_y + 0.12), pt, plbl, pcol, pw=1.56)

    if st["ack_f2_pkt"] is not None:
        pt, plbl, pcol = st["ack_f2_pkt"]
        _draw_packet_xy(ax, (f_lx - 0.42, f2_log_y - 0.22), (l_rx + 0.42, l_log_y - 0.06), pt, plbl, pcol, pw=1.00)

    if st["ack_f3_pkt"] is not None:
        pt, plbl, pcol = st["ack_f3_pkt"]
        _draw_packet_xy(ax, (f_lx - 0.42, f3_log_y - 0.22), (l_rx + 0.42, l_log_y - 0.28), pt, plbl, pcol, pw=1.00)

    if st["commit_f2_pkt"] is not None:
        pt, plbl, pcol = st["commit_f2_pkt"]
        _draw_packet_xy(ax, (l_rx + 0.48, l_log_y + 0.14), (f_lx - 0.48, f2_log_y + 0.04), pt, plbl, pcol, pw=1.18)

    if st["commit_f3_pkt"] is not None:
        pt, plbl, pcol = st["commit_f3_pkt"]
        _draw_packet_xy(ax, (l_rx + 0.48, l_log_y - 0.18), (f_lx - 0.48, f3_log_y + 0.12), pt, plbl, pcol, pw=1.18)

    # -------------------------------------------------------------------------
    # Subtle Static Bottom Takeaway
    # -------------------------------------------------------------------------
    ax.text(
        8.0, 0.34,
        "Same ordered log + same deterministic store  →  identical RAM state across all three nodes",
        color=TEXT_SUB, fontsize=8.5, style="italic", ha="center", va="center",
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
        final_hold_ms=8500,
    )
    for p in written:
        size_kb = p.stat().st_size / 1024.0
        print(f"[{NAME}] Wrote {p} ({size_kb:.1f} KB)")
    return written
