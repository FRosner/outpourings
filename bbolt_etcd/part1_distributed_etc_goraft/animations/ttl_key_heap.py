"""Animation 2: How ttlKeyHeap Tracks Ephemeral Heartbeats & Expirations.

A clean, story-driven conceptual animation with just two views:
  - Top: A continuous event timeline (t = 0s .. 60s) with pre-plotted heartbeats,
    container crash, missed renewal, and expiry moment, plus a moving playhead.
  - Main: A conceptual 3-node min-heap (`web@1`, `web@2`, `web@3`, ttl = 30s,
    renewing every 20s) with live remaining-TTL countdown bars inside each node.

Two continuous acts:
  - Act 1 (0s .. 32.5s): Register web@1, web@2, web@3 (staggered by 5s) and renew
    heartbeats on a 20s cadence — each renewal pushes the node down below the root.
  - Act 2 (32.5s .. 60s): web@2 crashes at t=35s, rises to the root when web@1 renews,
    misses its heartbeat at t=45s, and expires at t=55s; healthy web@1 renews again
    at t=60s while web@3 rises to the root.
"""

from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
import math

import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Polygon

from .common import (
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
    ease_out,
    export_animation,
    fig_to_rgb,
    progress,
)

NAME = "ttl_key_heap"
DESCRIPTION = "Conceptual min-heap + continuous timeline showing healthy heartbeats, a container crash, and automatic TTL expiration."

TTL_SECONDS = 30.0
T_MAX = 60.0
ACT2_START_T = 32.5

# Distinct accent color per web replica so the eye tracks each container effortlessly
REPLICA_COLORS: Dict[str, str] = {
    "web@1": ACCENT_TEAL,
    "web@2": ACCENT_AMBER,
    "web@3": ACCENT_VIOLET,
}

# Pre-plotted timeline events (exact 20s heartbeat cadence, 30s TTL):
# (time_sec, key, kind, short_label)
TIMELINE_EVENTS: List[Tuple[float, str, str, str]] = [
    (0.0, "web@1", "join", "web@1\njoin"),
    (5.0, "web@2", "join", "web@2\njoin"),
    (10.0, "web@3", "join", "web@3\njoin"),
    (20.0, "web@1", "renew", "web@1\nrenew"),
    (25.0, "web@2", "renew", "web@2\nrenew"),
    (30.0, "web@3", "renew", "web@3\nrenew"),
    (35.0, "web@2", "crash", "web@2\nCRASH"),
    (40.0, "web@1", "renew", "web@1\nrenew"),
    (45.0, "web@2", "miss", "web@2\nmissed"),
    (50.0, "web@3", "renew", "web@3\nrenew"),
    (55.0, "web@2", "expire", "web@2\nEXPIRE"),
    (60.0, "web@1", "renew", "web@1\nrenew"),
]

# Conceptual 3-node Min-Heap geometry inside Main Panel (x in [0.55, 15.45], y in [0.90, 5.90])
TREE_POS: List[Tuple[float, float]] = [
    (8.00, 4.18),   # [0] root (soonest to expire)
    (4.65, 2.08),   # [1] left child
    (11.35, 2.08),  # [2] right child
]
NODE_W = 3.44
NODE_H = 1.30

# Bottom act pills
ACT_PILLS = [
    (1, "Act 1: Register & Renew Heartbeats", ACCENT_TEAL),
    (2, "Act 2: Crash & Automatic Expiration", ACCENT_CORAL),
]


def _make_state(
    now: float,
    act: int,
    caption: str,
    caption_color: str,
    nodes: List[Tuple[str, float]],
    crashed: Optional[set] = None,
    swap: Optional[Tuple[int, int, float, str]] = None,
    appear: Optional[Tuple[int, float, str]] = None,
    pop_root: Optional[Tuple[str, float, float]] = None,  # (key, exp, progress 0..1)
    lift_from: Optional[Tuple[int, float, str]] = None,   # (from_idx -> 0, progress 0..1, color)
    hi_slots: Optional[Dict[int, str]] = None,
    active_event_t: Optional[float] = None,
) -> Dict:
    return {
        "now": now,
        "act": act,
        "caption": caption,
        "caption_color": caption_color,
        "nodes": list(nodes),  # list of (key, expire_t)
        "crashed": set(crashed) if crashed else set(),
        "swap": swap,
        "appear": appear,
        "pop_root": pop_root,
        "lift_from": lift_from,
        "hi_slots": dict(hi_slots) if hi_slots else {},
        "active_event_t": active_event_t,
    }


def build_timeline() -> Tuple[List[Dict], List[Tuple[int, str]]]:
    """Build frame-by-frame animation states and keyframe preview indices."""
    states: List[Dict] = []
    previews: List[Tuple[int, str]] = []

    def add_preview(label: str, offset_from_end: int = 3):
        idx = max(0, len(states) - offset_from_end)
        previews.append((idx, label))

    def push_travel(
        t0: float,
        t1: float,
        n_frames: int,
        act: int,
        caption: str,
        caption_color: str,
        nodes: List[Tuple[str, float]],
        crashed: Optional[set] = None,
    ):
        for i in range(n_frames):
            frac = i / float(max(1, n_frames))
            now = t0 + (t1 - t0) * frac
            states.append(
                _make_state(
                    now=now,
                    act=act,
                    caption=caption,
                    caption_color=caption_color,
                    nodes=nodes,
                    crashed=crashed,
                )
            )

    # =========================================================================
    # ACT 1: Register web@1..3 (ttl = 30s) & Renew Heartbeats (every 20s)
    # =========================================================================

    # 1. t=0s: web@1 joins (exp: 30s)
    n_0 = [("web@1", 30.0)]
    for i in range(16):
        a = ease_out(progress(i, 2, 10))
        states.append(
            _make_state(
                now=0.0, act=1,
                caption="Act 1 — web@1 registers with ttl = 30s (expires at t+30s)",
                caption_color=ACCENT_TEAL,
                nodes=n_0,
                appear=(0, a, ACCENT_TEAL),
                hi_slots={0: ACCENT_TEAL},
                active_event_t=0.0,
            )
        )
    add_preview("1_join1")

    # Glide 0s -> 5s
    push_travel(
        0.0, 5.0, 12, act=1,
        caption="Act 1 — Time advances; web@1's TTL counts down",
        caption_color=ACCENT_TEAL,
        nodes=n_0,
    )

    # 2. t=5s: web@2 joins (exp: 35s)
    n_5 = [("web@1", 30.0), ("web@2", 35.0)]
    for i in range(16):
        a = ease_out(progress(i, 1, 10))
        states.append(
            _make_state(
                now=5.0, act=1,
                caption="Act 1 — web@2 registers (t+35s > t+30s -> sits below web@1)",
                caption_color=ACCENT_AMBER,
                nodes=n_5,
                appear=(1, a, ACCENT_AMBER),
                hi_slots={1: ACCENT_AMBER},
                active_event_t=5.0,
            )
        )

    # Glide 5s -> 10s
    push_travel(
        5.0, 10.0, 12, act=1,
        caption="Act 1 — Time advances toward web@3's registration",
        caption_color=ACCENT_TEAL,
        nodes=n_5,
    )

    # 3. t=10s: web@3 joins (exp: 40s)
    n_10 = [("web@1", 30.0), ("web@2", 35.0), ("web@3", 40.0)]
    for i in range(18):
        a = ease_out(progress(i, 1, 10))
        states.append(
            _make_state(
                now=10.0, act=1,
                caption="Act 1 — web@3 registers (t+40s); all 3 replicas active in ttlKeyHeap",
                caption_color=ACCENT_VIOLET,
                nodes=n_10,
                appear=(2, a, ACCENT_VIOLET),
                hi_slots={2: ACCENT_VIOLET},
                active_event_t=10.0,
            )
        )
    add_preview("2_all_joined")

    # Glide 10s -> 15s and pause at 15s (consistent 5s beat even when nothing expires)
    push_travel(
        10.0, 15.0, 12, act=1,
        caption="Act 1 — Time advances; all 3 TTLs count down smoothly",
        caption_color=ACCENT_BLUE,
        nodes=n_10,
    )
    for _ in range(14):
        states.append(
            _make_state(
                now=15.0, act=1,
                caption="Act 1 — t+15s: root web@1 still has 15s left — nothing to expire",
                caption_color=ACCENT_BLUE,
                nodes=n_10,
            )
        )
    add_preview("2b_pause_15s")

    # Glide 15s -> 20s
    push_travel(
        15.0, 20.0, 12, act=1,
        caption="Act 1 — Playhead approaches web@1's first heartbeat at t+20s",
        caption_color=ACCENT_TEAL,
        nodes=n_10,
    )

    # 4. t=20s: web@1 heartbeat -> exp 30s -> 50s; swaps with web@2 (35s)
    n_20_pre = [("web@1", 50.0), ("web@2", 35.0), ("web@3", 40.0)]
    n_20_post = [("web@2", 35.0), ("web@1", 50.0), ("web@3", 40.0)]
    for i in range(28):
        if i < 8:
            nodes_cur = n_20_pre if i >= 3 else n_10
            states.append(
                _make_state(
                    now=20.0, act=1,
                    caption="Act 1 — web@1 renews heartbeat: expiry extends t+30s -> t+50s",
                    caption_color=ACCENT_TEAL,
                    nodes=nodes_cur,
                    hi_slots={0: ACCENT_TEAL},
                    active_event_t=20.0,
                )
            )
        elif i < 22:
            t = progress(i, 8, 14)
            states.append(
                _make_state(
                    now=20.0, act=1,
                    caption="Act 1 — web@1 sinks down; web@2 (t+35s) rises to the root",
                    caption_color=ACCENT_TEAL,
                    nodes=n_20_pre,
                    swap=(0, 1, t, ACCENT_TEAL),
                    active_event_t=20.0,
                )
            )
        else:
            states.append(
                _make_state(
                    now=20.0, act=1,
                    caption="Act 1 — web@2 (t+35s) is now next to expire at the root",
                    caption_color=ACCENT_TEAL,
                    nodes=n_20_post,
                    hi_slots={0: ACCENT_AMBER},
                    active_event_t=20.0,
                )
            )
    add_preview("3_hb1_swap", offset_from_end=14)

    # Glide 20s -> 25s
    push_travel(
        20.0, 25.0, 12, act=1,
        caption="Act 1 — Healthy heartbeats keep pushing the root deadline forward",
        caption_color=ACCENT_AMBER,
        nodes=n_20_post,
    )

    # 5. t=25s: web@2 heartbeat -> exp 35s -> 55s; swaps with web@3 (40s)
    n_25_pre = [("web@2", 55.0), ("web@1", 50.0), ("web@3", 40.0)]
    n_25_post = [("web@3", 40.0), ("web@1", 50.0), ("web@2", 55.0)]
    for i in range(26):
        if i < 7:
            nodes_cur = n_25_pre if i >= 2 else n_20_post
            states.append(
                _make_state(
                    now=25.0, act=1,
                    caption="Act 1 — web@2 renews heartbeat: expiry extends t+35s -> t+55s",
                    caption_color=ACCENT_AMBER,
                    nodes=nodes_cur,
                    hi_slots={0: ACCENT_AMBER},
                    active_event_t=25.0,
                )
            )
        elif i < 20:
            t = progress(i, 7, 13)
            states.append(
                _make_state(
                    now=25.0, act=1,
                    caption="Act 1 — web@2 sinks down; web@3 (t+40s) rises to the root",
                    caption_color=ACCENT_AMBER,
                    nodes=n_25_pre,
                    swap=(0, 2, t, ACCENT_AMBER),
                    active_event_t=25.0,
                )
            )
        else:
            states.append(
                _make_state(
                    now=25.0, act=1,
                    caption="Act 1 — web@3 (t+40s) is now next to expire at the root",
                    caption_color=ACCENT_AMBER,
                    nodes=n_25_post,
                    hi_slots={0: ACCENT_VIOLET},
                    active_event_t=25.0,
                )
            )

    # Glide 25s -> 30s
    push_travel(
        25.0, 30.0, 12, act=1,
        caption="Act 1 — Playhead advances to t+30s; web@3 renews on schedule",
        caption_color=ACCENT_VIOLET,
        nodes=n_25_post,
    )

    # 6. t=30s: web@3 heartbeat -> exp 40s -> 60s; swaps with web@1 (50s)
    n_30_pre = [("web@3", 60.0), ("web@1", 50.0), ("web@2", 55.0)]
    n_30_post = [("web@1", 50.0), ("web@3", 60.0), ("web@2", 55.0)]
    for i in range(26):
        if i < 7:
            nodes_cur = n_30_pre if i >= 2 else n_25_post
            states.append(
                _make_state(
                    now=30.0, act=1,
                    caption="Act 1 — web@3 renews heartbeat: expiry extends t+40s -> t+60s",
                    caption_color=ACCENT_VIOLET,
                    nodes=nodes_cur,
                    hi_slots={0: ACCENT_VIOLET},
                    active_event_t=30.0,
                )
            )
        elif i < 20:
            t = progress(i, 7, 13)
            states.append(
                _make_state(
                    now=30.0, act=1,
                    caption="Act 1 — web@3 sinks down; web@1 (t+50s) rises back to the root",
                    caption_color=ACCENT_VIOLET,
                    nodes=n_30_pre,
                    swap=(0, 1, t, ACCENT_VIOLET),
                    active_event_t=30.0,
                )
            )
        else:
            states.append(
                _make_state(
                    now=30.0, act=1,
                    caption="Act 1 — In steady state, renewals always outrun the clock",
                    caption_color=ACCENT_BLUE,
                    nodes=n_30_post,
                    hi_slots={0: ACCENT_TEAL},
                    active_event_t=30.0,
                )
            )
    add_preview("4_act1_done")

    # =========================================================================
    # ACT 2: web@2 Crashes at t=35s, Misses Renewal & Expires at t=55s; web@1 renews at t=60s
    # =========================================================================

    # Glide 30s -> 35s
    push_travel(
        30.0, 35.0, 14, act=2,
        caption="Act 2 — What happens when a container crashes?",
        caption_color=ACCENT_CORAL,
        nodes=n_30_post,
    )

    # 7. t=35s: web@2 crashes!
    crashed_w2 = {"web@2"}
    for _ in range(24):
        states.append(
            _make_state(
                now=35.0, act=2,
                caption="Act 2 — web@2 crashes! Its key stays in etcd until t+55s",
                caption_color=ACCENT_CORAL,
                nodes=n_30_post,
                crashed=crashed_w2,
                hi_slots={2: ACCENT_CORAL},
                active_event_t=35.0,
            )
        )
    add_preview("5_web2_crash")

    # Glide 35s -> 40s
    push_travel(
        35.0, 40.0, 12, act=2,
        caption="Act 2 — Healthy web@1 renews at t+40s",
        caption_color=ACCENT_CORAL,
        nodes=n_30_post,
        crashed=crashed_w2,
    )

    # 8. t=40s: web@1 heartbeat -> exp 50s -> 70s; swaps with crashed web@2 (55s) -> web@2 rises to root!
    n_40_pre = [("web@1", 70.0), ("web@3", 60.0), ("web@2", 55.0)]
    n_40_post = [("web@2", 55.0), ("web@3", 60.0), ("web@1", 70.0)]
    for i in range(28):
        if i < 7:
            nodes_cur = n_40_pre if i >= 2 else n_30_post
            states.append(
                _make_state(
                    now=40.0, act=2,
                    caption="Act 2 — web@1 renews (t+50s -> t+70s) and sinks down",
                    caption_color=ACCENT_TEAL,
                    nodes=nodes_cur,
                    crashed=crashed_w2,
                    hi_slots={0: ACCENT_TEAL},
                    active_event_t=40.0,
                )
            )
        elif i < 21:
            t = progress(i, 7, 14)
            states.append(
                _make_state(
                    now=40.0, act=2,
                    caption="Act 2 — Crashed web@2 (t+55s) rises to the root!",
                    caption_color=ACCENT_CORAL,
                    nodes=n_40_pre,
                    crashed=crashed_w2,
                    swap=(0, 2, t, ACCENT_CORAL),
                    active_event_t=40.0,
                )
            )
        else:
            states.append(
                _make_state(
                    now=40.0, act=2,
                    caption="Act 2 — web@2 is now at the root with 15s left",
                    caption_color=ACCENT_CORAL,
                    nodes=n_40_post,
                    crashed=crashed_w2,
                    hi_slots={0: ACCENT_CORAL},
                    active_event_t=40.0,
                )
            )

    # Glide 40s -> 45s
    push_travel(
        40.0, 45.0, 12, act=2,
        caption="Act 2 — Playhead reaches t+45s, when web@2 should have renewed",
        caption_color=ACCENT_CORAL,
        nodes=n_40_post,
        crashed=crashed_w2,
    )

    # 9. t=45s: web@2 misses heartbeat!
    for _ in range(20):
        states.append(
            _make_state(
                now=45.0, act=2,
                caption="Act 2 — web@2 misses its heartbeat! TTL keeps draining (10s left)",
                caption_color=ACCENT_CORAL,
                nodes=n_40_post,
                crashed=crashed_w2,
                hi_slots={0: ACCENT_CORAL},
                active_event_t=45.0,
            )
        )
    add_preview("6_missed_hb")

    # Glide 45s -> 50s
    push_travel(
        45.0, 50.0, 12, act=2,
        caption="Act 2 — Healthy web@3 renews at t+50s while web@2 nears expiry",
        caption_color=ACCENT_CORAL,
        nodes=n_40_post,
        crashed=crashed_w2,
    )

    # 10. t=50s: web@3 heartbeat -> exp 60s -> 80s (updates in place at [1]!)
    n_50 = [("web@2", 55.0), ("web@3", 80.0), ("web@1", 70.0)]
    for i in range(20):
        nodes_cur = n_50 if i >= 4 else n_40_post
        states.append(
            _make_state(
                now=50.0, act=2,
                caption="Act 2 — web@3 renews in place (t+60s -> t+80s); web@2 still at root!",
                caption_color=ACCENT_VIOLET,
                nodes=nodes_cur,
                crashed=crashed_w2,
                hi_slots={1: ACCENT_VIOLET, 0: ACCENT_CORAL},
                active_event_t=50.0,
            )
        )

    # Glide 50s -> 55s
    push_travel(
        50.0, 55.0, 14, act=2,
        caption="Act 2 — Clock reaches web@2's deadline at t+55s...",
        caption_color=ACCENT_CORAL,
        nodes=n_50,
        crashed=crashed_w2,
    )

    # 11. t=55s: EXPIRE web@2! Pop root, lift web@1 (70s) to root!
    n_55_final = [("web@1", 70.0), ("web@3", 80.0)]
    for i in range(34):
        if i < 15:
            p = progress(i, 3, 12)
            states.append(
                _make_state(
                    now=55.0, act=2,
                    caption="Act 2 — t+55s reached! Root web@2 expires & is popped from etcd",
                    caption_color=ACCENT_CORAL,
                    nodes=n_50,
                    crashed=crashed_w2,
                    pop_root=("web@2", 55.0, p),
                    hi_slots={0: ACCENT_CORAL},
                    active_event_t=55.0,
                )
            )
        elif i < 27:
            t = progress(i, 15, 12)
            states.append(
                _make_state(
                    now=55.0, act=2,
                    caption="Act 2 — web@1 (t+70s) rises to the root; t+70s > t+55s -> done!",
                    caption_color=ACCENT_GREEN,
                    nodes=[("web@2", 55.0), ("web@3", 80.0), ("web@1", 70.0)],
                    pop_root=("web@2", 55.0, 1.0),
                    lift_from=(2, t, ACCENT_TEAL),
                    hi_slots={0: ACCENT_GREEN},
                    active_event_t=55.0,
                )
            )
        else:
            states.append(
                _make_state(
                    now=55.0, act=2,
                    caption="Act 2 — web@2 removed; cluster continues with web@1 & web@3",
                    caption_color=ACCENT_GREEN,
                    nodes=n_55_final,
                    hi_slots={0: ACCENT_GREEN},
                    active_event_t=55.0,
                )
            )
    add_preview("7_expire_pop", offset_from_end=24)
    add_preview("8_post_expire")

    # Glide 55s -> 60s
    push_travel(
        55.0, 60.0, 12, act=2,
        caption="Act 2 — Healthy replicas keep renewing on their 20s cadence",
        caption_color=ACCENT_TEAL,
        nodes=n_55_final,
    )

    # 12. t=60s: web@1 renews (t+70s -> t+90s) -> swaps with web@3 (t+80s)!
    n_60_pre = [("web@1", 90.0), ("web@3", 80.0)]
    n_60_post = [("web@3", 80.0), ("web@1", 90.0)]
    for i in range(30):
        if i < 7:
            nodes_cur = n_60_pre if i >= 2 else n_55_final
            states.append(
                _make_state(
                    now=60.0, act=2,
                    caption="Act 2 — web@1 renews at t+60s: expiry extends t+70s -> t+90s",
                    caption_color=ACCENT_TEAL,
                    nodes=nodes_cur,
                    hi_slots={0: ACCENT_TEAL},
                    active_event_t=60.0,
                )
            )
        elif i < 20:
            t = progress(i, 7, 13)
            states.append(
                _make_state(
                    now=60.0, act=2,
                    caption="Act 2 — web@1 sinks down; web@3 (t+80s) rises to the root",
                    caption_color=ACCENT_TEAL,
                    nodes=n_60_pre,
                    swap=(0, 1, t, ACCENT_TEAL),
                    active_event_t=60.0,
                )
            )
        else:
            states.append(
                _make_state(
                    now=60.0, act=2,
                    caption="Healthy renewals push keys down; crashed keys rise to the root and expire",
                    caption_color=ACCENT_BLUE,
                    nodes=n_60_post,
                    hi_slots={0: ACCENT_VIOLET},
                    active_event_t=60.0,
                )
            )
    add_preview("9_final")

    return states, previews


def _arc_interp(
    p0: Tuple[float, float],
    p1: Tuple[float, float],
    t: float,
    arc_sign: float = 1.0,
    arc_amp: float = 0.85,
) -> Tuple[float, float]:
    """Smooth perpendicular arc interpolation from p0 -> p1."""
    et = ease_in_out(t)
    x = p0[0] + (p1[0] - p0[0]) * et
    y = p0[1] + (p1[1] - p0[1]) * et
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    dist = math.hypot(dx, dy)
    if dist > 1e-6:
        nx, ny = -dy / dist, dx / dist
        lift = math.sin(math.pi * et) * arc_amp * arc_sign
        x += nx * lift
        y += ny * lift
    return x, y


def _draw_node_card(
    ax,
    cx: float,
    cy: float,
    key: str,
    expire_t: float,
    now: float,
    is_crashed: bool = False,
    alpha: float = 1.0,
    hi_color: Optional[str] = None,
    zorder: int = 6,
):
    """Draw a large, readable conceptual heap node with live TTL countdown bar."""
    if alpha <= 0.01:
        return
    base_col = ACCENT_CORAL if is_crashed else REPLICA_COLORS[key]
    x = cx - NODE_W / 2.0
    y = cy - NODE_H / 2.0

    # Soft outer glow ring when active
    if hi_color is not None:
        draw_box(
            ax, x - 0.07, y - 0.07, NODE_W + 0.14, NODE_H + 0.14,
            facecolor="none", edgecolor=hi_color, lw=3.6, radius=0.20, alpha=0.28 * alpha, zorder=zorder - 1,
        )

    edge_col = hi_color if hi_color is not None else blend_hex(BOX_BORDER_HI, base_col, 0.65)
    fc = blend_hex(BOX_BG, hi_color, 0.12) if hi_color is not None else BOX_BG
    lw = 2.4 if hi_color is not None else 1.7
    draw_box(ax, x, y, NODE_W, NODE_H, facecolor=fc, edgecolor=edge_col, lw=lw, radius=0.16, alpha=alpha, zorder=zorder)

    # Top row: role dot + replica name (left) + status pill (right)
    top_y = y + NODE_H - 0.31
    ax.add_patch(Circle((x + 0.28, top_y), 0.095, facecolor=base_col, edgecolor="none", alpha=alpha, zorder=zorder + 1))
    ax.text(
        x + 0.49, top_y,
        key,
        color=TEXT_MAIN, fontsize=12.4, family="monospace", fontweight="bold",
        ha="left", va="center", alpha=alpha, zorder=zorder + 2,
    )

    st_text = "CRASHED" if is_crashed else "healthy"
    st_col = ACCENT_CORAL if is_crashed else base_col
    pw, ph = 1.04, 0.30
    px, py = x + NODE_W - pw - 0.17, top_y - ph / 2.0
    draw_box(
        ax, px, py, pw, ph,
        facecolor=blend_hex(BOX_INNER, st_col, 0.18),
        edgecolor=blend_hex(BOX_BORDER, st_col, 0.70),
        lw=1.1, radius=0.08, alpha=alpha, zorder=zorder + 1,
    )
    ax.text(
        px + pw / 2.0, top_y,
        st_text,
        color=st_col, fontsize=7.9, family="monospace", fontweight="bold",
        ha="center", va="center", alpha=alpha, zorder=zorder + 2,
    )

    # Middle row: expiration deadline + remaining seconds
    rem = max(0.0, expire_t - now)
    mid_y = y + 0.58
    ax.text(
        x + 0.22, mid_y,
        f"expires at t+{int(round(expire_t))}s",
        color=TEXT_SOFT, fontsize=9.4, family="monospace", fontweight="bold",
        ha="left", va="center", alpha=alpha, zorder=zorder + 2,
    )
    rem_col = ACCENT_CORAL if (is_crashed or rem <= 5.0) else base_col
    ax.text(
        x + NODE_W - 0.20, mid_y,
        f"{int(round(rem))}s left",
        color=rem_col, fontsize=9.0, family="monospace", fontweight="bold",
        ha="right", va="center", alpha=alpha, zorder=zorder + 2,
    )

    # Bottom row: remaining TTL progress bar
    bar_x = x + 0.20
    bar_y = y + 0.19
    bar_w = NODE_W - 0.40
    bar_h = 0.17
    draw_box(ax, bar_x, bar_y, bar_w, bar_h, facecolor=BOX_INNER, edgecolor=BOX_BORDER, lw=0.9, radius=0.06, alpha=alpha, zorder=zorder + 1)
    fill_frac = clamp(rem / TTL_SECONDS, 0.0, 1.0)
    if fill_frac > 0.02:
        fw = max(0.10, bar_w * fill_frac)
        bar_col = ACCENT_CORAL if (is_crashed and rem <= 15.0) else base_col
        draw_box(ax, bar_x, bar_y, fw, bar_h, facecolor=bar_col, edgecolor="none", lw=0.0, radius=0.06, alpha=0.88 * alpha, zorder=zorder + 2)


def render_frame(st: Dict, dpi: int = 125):
    fig, ax = plt.subplots(figsize=(12.8, 6.8), dpi=dpi)
    fig.patch.set_facecolor(BG_COLOR)
    ax.set_facecolor(BG_COLOR)
    ax.set_xlim(0.0, 16.0)
    ax.set_ylim(0.0, 8.5)
    ax.axis("off")

    now = st["now"]

    # -------------------------------------------------------------------------
    # Header: Clean Static Title Only
    # -------------------------------------------------------------------------
    ax.text(
        8.0, 8.12,
        "How ttlKeyHeap Tracks Ephemeral Heartbeats & Expirations",
        color=TEXT_MAIN, fontsize=15.4, fontweight="bold", ha="center", va="center",
    )

    # -------------------------------------------------------------------------
    # Top Panel: Clean Continuous Event Timeline (t = 0s .. 60s)
    # -------------------------------------------------------------------------
    tl_x, tl_y, tl_w, tl_h = 0.55, 6.12, 14.90, 1.62
    draw_box(ax, tl_x, tl_y, tl_w, tl_h, facecolor=PANEL_BG, edgecolor=BOX_BORDER, lw=1.5, radius=0.16, zorder=1)

    track_x0 = 1.15
    track_x1 = 14.85
    track_y = 6.68

    def t_to_x(t_sec: float) -> float:
        return track_x0 + (track_x1 - track_x0) * clamp(t_sec / T_MAX, 0.0, 1.0)

    # Subtle shaded Act 1 & Act 2 zones
    split_x = t_to_x(ACT2_START_T)
    draw_box(
        ax, tl_x + 0.12, tl_y + 0.12, split_x - (tl_x + 0.16), tl_h - 0.24,
        facecolor=blend_hex(PANEL_BG, ACCENT_TEAL, 0.05), edgecolor="none", lw=0, radius=0.10, zorder=2,
    )
    draw_box(
        ax, split_x + 0.04, tl_y + 0.12, (tl_x + tl_w - 0.12) - (split_x + 0.04), tl_h - 0.24,
        facecolor=blend_hex(PANEL_BG, ACCENT_CORAL, 0.06), edgecolor="none", lw=0, radius=0.10, zorder=2,
    )
    ax.plot([split_x, split_x], [tl_y + 0.15, tl_y + tl_h - 0.15], color=BOX_BORDER_HI, lw=1.1, linestyle="--", alpha=0.7, zorder=3)

    # Act zone header labels
    ax.text(
        tl_x + 0.28, tl_y + tl_h - 0.23,
        "ACT 1: REGISTER & RENEW HEARTBEATS (ttl = 30s, renew every 20s)",
        color=ACCENT_TEAL if st["act"] == 1 else TEXT_DIM,
        fontsize=8.1, fontweight="bold", ha="left", va="center", zorder=4,
    )
    ax.text(
        split_x + 0.20, tl_y + tl_h - 0.23,
        "ACT 2: web@2 CRASHES & EXPIRES",
        color=ACCENT_CORAL if st["act"] == 2 else TEXT_DIM,
        fontsize=8.1, fontweight="bold", ha="left", va="center", zorder=4,
    )

    # Base timeline track bar + elapsed progress highlight
    ax.plot([track_x0, track_x1], [track_y, track_y], color=BOX_BORDER_HI, lw=3.0, solid_capstyle="round", zorder=3)
    now_x = t_to_x(now)
    if now > 0.05:
        ax.plot([track_x0, now_x], [track_y, track_y], color=TEXT_MAIN, lw=3.4, solid_capstyle="round", alpha=0.88, zorder=4)

    # Time ticks every 5s cleanly below axis
    for ts in range(0, 65, 5):
        tx = t_to_x(float(ts))
        is_current_tick = abs(float(ts) - now) < 0.35
        is_past = ts <= now + 0.01
        ax.plot([tx, tx], [track_y - 0.10, track_y + 0.05], color=TEXT_MAIN if is_current_tick else BOX_BORDER_HI, lw=1.3 if is_current_tick else 1.0, alpha=0.85 if is_current_tick else 0.65, zorder=3)
        ax.text(
            tx, track_y - 0.29,
            f"{ts}s",
            color=TEXT_MAIN if is_current_tick else (TEXT_SOFT if is_past else TEXT_DIM),
            fontsize=8.2 if is_current_tick else 7.7,
            family="monospace",
            fontweight="bold" if is_current_tick else "normal",
            ha="center", va="center", zorder=4,
        )

    # Plot all 12 pre-scheduled events
    active_et = st["active_event_t"]
    for et, ek, kind, label in TIMELINE_EVENTS:
        ex = t_to_x(et)
        is_active = active_et is not None and abs(active_et - et) < 0.01
        is_past = et < now - 0.05
        is_future = et > now + 0.05

        ecol = ACCENT_CORAL if kind in ("crash", "miss", "expire") else REPLICA_COLORS[ek]
        ev_alpha = 1.0 if is_active else (0.58 if is_past else 0.75)

        if is_active:
            ax.add_patch(Circle((ex, track_y), 0.19, facecolor=ecol, edgecolor="none", alpha=0.28, zorder=5))

        if kind == "crash":
            r = 0.115 if is_active else 0.095
            diamond = Polygon(
                [(ex, track_y + r), (ex + r, track_y), (ex, track_y - r), (ex - r, track_y)],
                closed=True, facecolor=ecol if not is_future else BG_COLOR,
                edgecolor=ecol, lw=1.8, alpha=ev_alpha, zorder=6,
            )
            ax.add_patch(diamond)
        elif kind == "miss":
            ax.add_patch(Circle((ex, track_y), 0.09, facecolor=BG_COLOR, edgecolor=ecol, lw=1.6, linestyle="--", alpha=ev_alpha, zorder=6))
        elif kind == "expire":
            ax.add_patch(Circle((ex, track_y), 0.11, facecolor=ecol if not is_future else BG_COLOR, edgecolor=ecol, lw=2.0, alpha=ev_alpha, zorder=6))
        else:
            fc = ecol if not is_future else BG_COLOR
            ax.add_patch(Circle((ex, track_y), 0.095 if is_active else 0.082, facecolor=fc, edgecolor=ecol, lw=1.8, alpha=ev_alpha, zorder=6))

        lbl_col = ecol if is_active else (TEXT_SOFT if not is_future else blend_hex(TEXT_DIM, ecol, 0.45))
        ax.text(
            ex, track_y + 0.40,
            label,
            color=lbl_col,
            fontsize=7.6 if is_active else 7.2,
            family="monospace",
            fontweight="bold" if (is_active or kind in ("crash", "expire")) else "normal",
            ha="center", va="center",
            linespacing=1.12,
            alpha=1.0 if is_active else (0.72 if is_past else 0.85),
            zorder=7,
        )

    # Crisp moving vertical playhead marker (no pills needed)
    ax.plot([now_x, now_x], [track_y - 0.16, track_y + 0.18], color=TEXT_MAIN, lw=2.5, solid_capstyle="round", zorder=10)
    ax.add_patch(Circle((now_x, track_y), 0.062, facecolor=TEXT_MAIN, edgecolor=BG_COLOR, lw=0.8, zorder=11))

    # -------------------------------------------------------------------------
    # Main Panel: Conceptual Min-Heap (ttlKeyHeap)
    # -------------------------------------------------------------------------
    mx, my, mw, mh = 0.55, 0.90, 14.90, 5.00
    draw_box(ax, mx, my, mw, mh, facecolor=PANEL_BG, edgecolor=BOX_BORDER, lw=1.5, radius=0.16, zorder=1)
    ax.text(
        mx + 0.28, my + mh - 0.29,
        "ttlKeyHeap  (Min-Heap ordered by expiration time)",
        color=TEXT_MAIN, fontsize=11.2, fontweight="bold", ha="left", va="center", zorder=3,
    )
    ax.text(
        mx + mw - 0.28, my + mh - 0.29,
        "Soonest-to-expire key always sits at the top",
        color=TEXT_SUB, fontsize=8.9, ha="right", va="center", zorder=3,
    )

    nodes = st["nodes"]
    crashed = st["crashed"]
    swap = st["swap"]
    appear = st["appear"]
    pop_root = st["pop_root"]
    lift_from = st["lift_from"]

    # Draw tree edges (0->1, 0->2) for visible children
    for c_idx in (1, 2):
        if c_idx >= len(nodes):
            continue
        if lift_from is not None and lift_from[0] == c_idx:
            e_alpha = max(0.0, 1.0 - lift_from[1] * 1.4)
        elif appear is not None and appear[0] == c_idx:
            e_alpha = appear[1]
        else:
            e_alpha = 1.0
        if e_alpha <= 0.02:
            continue
        p0, p1 = TREE_POS[0], TREE_POS[c_idx]
        is_swap_edge = swap is not None and ({swap[0], swap[1]} == {0, c_idx})
        ecol = swap[3] if is_swap_edge else BOX_BORDER_HI
        elw = 2.8 if is_swap_edge else 1.8
        ax.plot(
            [p0[0], p1[0]],
            [p0[1] - NODE_H / 2.0, p1[1] + NODE_H / 2.0],
            color=ecol, lw=elw, alpha=0.85 * e_alpha, zorder=3,
        )

    # Render static (non-moving) nodes
    swapping_set = {swap[0], swap[1]} if swap is not None else set()
    for idx, (k, exp_t) in enumerate(nodes):
        if idx in swapping_set:
            continue
        if pop_root is not None and idx == 0:
            continue
        if lift_from is not None and idx == lift_from[0]:
            continue
        alpha = appear[1] if (appear is not None and appear[0] == idx) else 1.0
        hi_col = st["hi_slots"].get(idx)
        _draw_node_card(
            ax, TREE_POS[idx][0], TREE_POS[idx][1], k, exp_t, now,
            is_crashed=(k in crashed), alpha=alpha, hi_color=hi_col, zorder=6,
        )

    # Render smooth swap pair along wide opposite perpendicular arcs
    if swap is not None:
        ia, ib, t, scol = swap
        ka, exp_a = nodes[ia]
        kb, exp_b = nodes[ib]
        pos_a = _arc_interp(TREE_POS[ia], TREE_POS[ib], t, arc_sign=1.0, arc_amp=0.88)
        pos_b = _arc_interp(TREE_POS[ib], TREE_POS[ia], t, arc_sign=1.0, arc_amp=0.88)
        hi_a = ACCENT_CORAL if ka in crashed else REPLICA_COLORS[ka]
        hi_b = ACCENT_CORAL if kb in crashed else REPLICA_COLORS[kb]
        _draw_node_card(
            ax, pos_a[0], pos_a[1], ka, exp_a, now,
            is_crashed=(ka in crashed), hi_color=hi_a, zorder=10,
        )
        _draw_node_card(
            ax, pos_b[0], pos_b[1], kb, exp_b, now,
            is_crashed=(kb in crashed), hi_color=hi_b, zorder=16,
        )

    # Render popping root fading upward during expiration
    if pop_root is not None:
        pk, pexp, pt = pop_root
        if pt < 0.99:
            et = ease_in_out(pt)
            px = TREE_POS[0][0]
            py = TREE_POS[0][1] + 0.42 * et
            alpha = max(0.0, 1.0 - et)
            _draw_node_card(
                ax, px, py, pk, pexp, now,
                is_crashed=True, alpha=alpha, hi_color=ACCENT_CORAL, zorder=14,
            )

    # Render surviving node lifting smoothly to root after expiration
    if lift_from is not None:
        from_idx, lt, lcol = lift_from
        lk, lexp = nodes[from_idx]
        lpos = _arc_interp(TREE_POS[from_idx], TREE_POS[0], lt, arc_sign=1.0, arc_amp=0.20)
        _draw_node_card(
            ax, lpos[0], lpos[1], lk, lexp, now,
            is_crashed=False, hi_color=lcol, zorder=12,
        )

    # -------------------------------------------------------------------------
    # Bottom Act Progress Bar + Takeaway Note
    # -------------------------------------------------------------------------
    pill_y, pill_h = 0.24, 0.42
    pill_x = 0.55
    pill_widths = [3.35, 3.45]
    pill_gap = 0.20

    for (act_num, label, col), pw in zip(ACT_PILLS, pill_widths):
        is_current = (st["act"] == act_num)
        is_done = (st["act"] > act_num)
        if is_current:
            fc, ec, tc, lw = col, col, BG_COLOR, 1.2
            p_alpha = 0.96
        elif is_done:
            fc, ec, tc, lw = BOX_BG, col, TEXT_SOFT, 1.1
            p_alpha = 0.85
        else:
            fc, ec, tc, lw = PANEL_BG, BOX_BORDER, TEXT_DIM, 1.0
            p_alpha = 0.65

        draw_box(ax, pill_x, pill_y, pw, pill_h, facecolor=fc, edgecolor=ec, lw=lw, radius=0.11, alpha=p_alpha, zorder=3)
        ax.text(
            pill_x + pw / 2.0, pill_y + pill_h / 2.0,
            label, color=tc, fontsize=8.6, fontweight="bold" if is_current else "normal",
            ha="center", va="center", zorder=4,
        )
        pill_x += pw + pill_gap

    ax.text(
        15.45, pill_y + pill_h / 2.0,
        "Healthy heartbeats keep pushing keys down; crashed keys rise to the root & expire",
        color=TEXT_SUB, fontsize=8.5, style="italic", ha="right", va="center",
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
        final_hold_ms=6500,
    )
    for p in written:
        size_kb = p.stat().st_size / 1024.0
        print(f"[{NAME}] Wrote {p} ({size_kb:.1f} KB)")
    return written
