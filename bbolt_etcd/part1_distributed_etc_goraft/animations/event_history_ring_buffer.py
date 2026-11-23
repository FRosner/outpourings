"""Animation 2: Long-Polling Watches & the EventHistory Ring Buffer.

A clean, story-driven conceptual animation matching the visual language of
`ttl_key_heap.py`:
  - Top: A continuous pre-plotted event timeline with shaded act zones and a
    smooth moving playhead, so readers always know what happened and what comes next.
  - Main Left:
      * `Writers` card (cluster PUT/Expire mutations firing visible event packets into etcd)
      * `confd` card (watching `/services/web`, tracking `next waitIndex` & responses)
  - Main Right (`etcd · WatcherHub`):
      * Compact `watchers` map slot (parked live hanging GETs)
      * `EventHistory` window & `scan()` check (`StartIndex`, `LastIndex`)
      * Circular 10-slot `EventHistory` ring buffer with `Front` and `Back` pointers
        (10 slots shown for clarity; hardcoded to 1,000 in etcd v0.4)

Consistent etcd v0.4 terminology throughout ("cleared", matching `EcodeEventIndexCleared`).
"""

from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
import math

import matplotlib.pyplot as plt
from matplotlib.patches import Arc, Circle, FancyArrowPatch, Polygon

from .common import (
    ACCENT_AMBER,
    ACCENT_BLUE,
    ACCENT_CORAL,
    ACCENT_GREEN,
    ACCENT_TEAL,
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

NAME = "event_history_ring_buffer"
DESCRIPTION = "Pre-plotted timeline + Writers + confd + circular 10-slot EventHistory ring buffer showing live notify, replay catch-up, and 401 cleared."

CAPACITY = 10

# Normalized timeline axis [0.0 .. 100.0] with 4 shaded zones and 8 pre-plotted milestones
T_MAX = 100.0
ZONE_SPLITS = (28.0, 54.0, 84.0)  # Act1 [0..28], Act2 [28..54], Act3 [54..84], Act4 [84..100]

# (t_pos, kind, label, accent_color)
TIMELINE_MILESTONES: List[Tuple[float, str, str, str]] = [
    (7.0,  "get",   "GET #1\npark",       ACCENT_TEAL),
    (20.0, "put",   "PUT #1\nnotify",     ACCENT_BLUE),
    (34.0, "put",   "PUT #2\n(gap)",      ACCENT_BLUE),
    (47.0, "hit",   "GET #2\nreplay",     ACCENT_GREEN),
    (59.0, "burst", "PUT #3\n(next)",     ACCENT_AMBER),
    (70.0, "burst", "PUT #10\nfull",      ACCENT_AMBER),
    (80.0, "clear", "PUT #13\n#3 cleared", ACCENT_CORAL),
    (93.0, "err",   "GET #3\n401 cleared", ACCENT_CORAL),
]

# Ring geometry (isotropic 16.0 x 8.5 canvas, right half of main panel y in [0.90, 5.88])
RING_CX = 12.18
RING_CY = 3.16
RING_R = 1.24
SLOT_R = 0.30
PTR_RX = 2.24
PTR_RY = 1.94

# Bottom act pills
ACT_PILLS = [
    (1, "1. Watch & Notify", ACCENT_TEAL),
    (2, "2. Replay Catch-Up", ACCENT_GREEN),
    (3, "3. Burst Overwrites Ring", ACCENT_AMBER),
    (4, "4. 401 Cleared", ACCENT_CORAL),
]


def _slot_angle(slot_idx: int) -> float:
    """Angle in radians for slot k (clockwise starting from 12 o'clock = pi/2)."""
    return math.pi / 2.0 - (slot_idx % CAPACITY) * (2.0 * math.pi / CAPACITY)


def _slot_xy(slot_idx: int, radius: float = RING_R) -> Tuple[float, float]:
    ang = _slot_angle(slot_idx)
    return (RING_CX + radius * math.cos(ang), RING_CY + radius * math.sin(ang))


def _make_state(
    t_now: float,
    act: int,
    slots: List[Optional[int]],
    front_slot: Optional[int],
    back_slot: Optional[int],
    start_index: int,
    last_index: int,
    writer_status: str,
    writer_color: str,
    writer_badge: Optional[str],
    confd_status: str,
    confd_color: str,
    next_wait_index: int,
    confd_log: List[Tuple[str, str]],
    active_milestone_t: Optional[float] = None,
    parked_watch: Optional[str] = None,
    watcher_flash: Optional[Tuple[str, float]] = None,
    open_conn: bool = False,
    conn_pulse: float = 0.0,
    write_packet: Optional[Tuple[float, str, str]] = None,  # (t 0..1, label, color)
    req_packet: Optional[Tuple[float, str, str]] = None,    # (t 0..1, label, color)
    resp_packet: Optional[Tuple[float, str, str]] = None,   # (t 0..1, label, color)
    scan_status: Optional[Tuple[str, str, str]] = None,     # (expr, verdict, color)
    slot_flash: Optional[Dict[int, Tuple[str, float]]] = None,
    target_slot: Optional[int] = None,
    clear_callout: Optional[Tuple[str, float]] = None,      # (text, alpha)
    scan_beam_slot: Optional[Tuple[int, str, float]] = None,
    front_angle_override: Optional[float] = None,
    back_angle_override: Optional[float] = None,
) -> Dict:
    return {
        "t_now": t_now,
        "act": act,
        "slots": list(slots),
        "front_slot": front_slot,
        "back_slot": back_slot,
        "start_index": start_index,
        "last_index": last_index,
        "writer_status": writer_status,
        "writer_color": writer_color,
        "writer_badge": writer_badge,
        "confd_status": confd_status,
        "confd_color": confd_color,
        "next_wait_index": next_wait_index,
        "confd_log": list(confd_log),
        "active_milestone_t": active_milestone_t,
        "parked_watch": parked_watch,
        "watcher_flash": watcher_flash,
        "open_conn": open_conn,
        "conn_pulse": conn_pulse,
        "write_packet": write_packet,
        "req_packet": req_packet,
        "resp_packet": resp_packet,
        "scan_status": scan_status,
        "slot_flash": dict(slot_flash) if slot_flash else {},
        "target_slot": target_slot,
        "clear_callout": clear_callout,
        "scan_beam_slot": scan_beam_slot,
        "front_angle_override": front_angle_override,
        "back_angle_override": back_angle_override,
    }


def _lerp_cw_angle(slot_from: int, slot_to: int, t: float) -> float:
    """Interpolate angle clockwise from slot_from to slot_to (decreasing radians)."""
    a0 = _slot_angle(slot_from)
    steps = (slot_to - slot_from) % CAPACITY
    a1 = a0 - steps * (2.0 * math.pi / CAPACITY)
    return a0 + (a1 - a0) * ease_in_out(t)


def _lerp_t(t0: float, t1: float, i: int, n: int) -> float:
    if n <= 1:
        return t1
    return t0 + (t1 - t0) * (i / float(n - 1))


def build_timeline() -> Tuple[List[Dict], List[Tuple[int, str]]]:
    """Build frame-by-frame animation states and keyframe preview indices."""
    states: List[Dict] = []
    previews: List[Tuple[int, str]] = []

    def add_preview(label: str, offset_from_end: int = 2):
        idx = max(0, len(states) - offset_from_end)
        previews.append((idx, label))

    slots: List[Optional[int]] = [None] * CAPACITY
    front_slot: Optional[int] = None
    back_slot: Optional[int] = None
    start_idx = 0
    last_idx = 0
    size = 0
    next_write = 0

    def push_event(ev_idx: int) -> Tuple[int, Optional[int], Optional[int], Optional[int]]:
        """Insert ev_idx into the 10-slot ring.

        Returns (written_slot, overwritten_ev, prev_front_slot, prev_back_slot).
        """
        nonlocal front_slot, back_slot, start_idx, last_idx, size, next_write
        prev_f, prev_b = front_slot, back_slot
        w_slot = next_write
        overwritten = slots[w_slot]
        slots[w_slot] = ev_idx
        next_write = (next_write + 1) % CAPACITY

        if size == 0:
            front_slot = w_slot
            back_slot = w_slot
            size = 1
        elif size < CAPACITY:
            back_slot = w_slot
            size += 1
        else:
            back_slot = w_slot
            front_slot = (front_slot + 1) % CAPACITY

        start_idx = slots[front_slot]
        last_idx = ev_idx
        return w_slot, overwritten, prev_f, prev_b

    # =========================================================================
    # ACT 1: Register Long-Poll Watch & Receive Event #1 Live  (t: 0 -> 28)
    # =========================================================================

    # 1.1 Brief empty-ring start (t: 0 -> 4)
    n = 12
    for i in range(n):
        states.append(_make_state(
            t_now=_lerp_t(0.0, 4.0, i, n),
            act=1,
            slots=slots,
            front_slot=front_slot,
            back_slot=back_slot,
            start_index=start_idx,
            last_index=last_idx,
            writer_status="Idle",
            writer_color=TEXT_SUB,
            writer_badge=None,
            confd_status="Idle",
            confd_color=TEXT_SUB,
            next_wait_index=1,
            confd_log=[],
        ))

    # 1.2 confd sends GET ?waitIndex=1 (t: 4 -> 7)
    n = 18
    for i in range(n):
        pt = progress(i, 0, 16)
        scan = ("1 > Last(0)", "Future → park watch", ACCENT_TEAL) if i >= 12 else None
        states.append(_make_state(
            t_now=_lerp_t(4.0, 7.0, i, n),
            act=1,
            slots=slots,
            front_slot=front_slot,
            back_slot=back_slot,
            start_index=start_idx,
            last_index=last_idx,
            writer_status="Idle",
            writer_color=TEXT_SUB,
            writer_badge=None,
            confd_status="Connecting...",
            confd_color=ACCENT_TEAL,
            next_wait_index=1,
            confd_log=[],
            active_milestone_t=7.0 if i >= 12 else None,
            req_packet=(pt, "GET ?waitIndex=1", ACCENT_TEAL) if pt < 1.0 else None,
            scan_status=scan,
        ))

    # 1.3 Parked in watchers["/services/web"] (t: 7 -> 14)
    n = 22
    for i in range(n):
        pulse = 0.5 + 0.5 * math.sin(i * 0.40)
        states.append(_make_state(
            t_now=_lerp_t(7.0, 14.0, i, n),
            act=1,
            slots=slots,
            front_slot=front_slot,
            back_slot=back_slot,
            start_index=start_idx,
            last_index=last_idx,
            writer_status="Idle",
            writer_color=TEXT_SUB,
            writer_badge=None,
            confd_status="Waiting (HTTP open)",
            confd_color=ACCENT_TEAL,
            next_wait_index=1,
            confd_log=[],
            active_milestone_t=7.0 if i < 12 else None,
            parked_watch="confd (waitIndex=1)",
            watcher_flash=(ACCENT_TEAL, 0.35 + 0.35 * pulse),
            open_conn=True,
            conn_pulse=pulse,
            scan_status=("1 > Last(0)", "Parked in watchers", ACCENT_TEAL),
        ))
    add_preview("1_parked")

    # 1.4 Writer sends PUT #1 -> travels to WatcherHub (t: 14 -> 20)
    n = 16
    for i in range(n):
        pt = progress(i, 0, 14)
        states.append(_make_state(
            t_now=_lerp_t(14.0, 20.0, i, n),
            act=1,
            slots=slots,
            front_slot=front_slot,
            back_slot=back_slot,
            start_index=start_idx,
            last_index=last_idx,
            writer_status="Writing #1",
            writer_color=ACCENT_BLUE,
            writer_badge="PUT /services/web/web@1",
            confd_status="Waiting (HTTP open)",
            confd_color=ACCENT_TEAL,
            next_wait_index=1,
            confd_log=[],
            active_milestone_t=20.0 if i >= 10 else None,
            parked_watch="confd (waitIndex=1)",
            watcher_flash=(ACCENT_TEAL, 0.45),
            open_conn=True,
            conn_pulse=0.8,
            write_packet=(pt, "Event #1", ACCENT_BLUE) if pt < 1.0 else None,
            scan_status=("1 > Last(0)", "Parked in watchers", ACCENT_TEAL),
        ))

    # 1.5 Event #1 lands in slot [0] & wakes parked watcher (t: 20 -> 23)
    w_slot, _, _, _ = push_event(1)
    n = 18
    for i in range(n):
        fl = max(0.0, 1.0 - progress(i, 3, 14))
        woke = i >= 6
        states.append(_make_state(
            t_now=_lerp_t(20.0, 23.0, i, n),
            act=1,
            slots=slots,
            front_slot=front_slot,
            back_slot=back_slot,
            start_index=start_idx,
            last_index=last_idx,
            writer_status="Idle",
            writer_color=TEXT_SUB,
            writer_badge="Last write: #1",
            confd_status="Waiting (HTTP open)",
            confd_color=ACCENT_TEAL,
            next_wait_index=1,
            confd_log=[],
            active_milestone_t=20.0,
            parked_watch="confd → WOKE!" if woke else "confd (waitIndex=1)",
            watcher_flash=(ACCENT_GREEN if woke else ACCENT_TEAL, 0.9 if woke else 0.4),
            open_conn=True,
            conn_pulse=1.0,
            slot_flash={w_slot: (ACCENT_BLUE, 0.35 + 0.65 * fl)},
        ))

    # 1.6 Response 200 OK (#1) delivered -> HTTP closes, confd reloads nginx (t: 23 -> 28)
    n = 24
    for i in range(n):
        pt = progress(i, 0, 15)
        arrived = i >= 15
        states.append(_make_state(
            t_now=_lerp_t(23.0, 28.0, i, n),
            act=1,
            slots=slots,
            front_slot=front_slot,
            back_slot=back_slot,
            start_index=start_idx,
            last_index=last_idx,
            writer_status="Idle",
            writer_color=TEXT_SUB,
            writer_badge="Last write: #1",
            confd_status="Reloading nginx..." if arrived else "Receiving #1...",
            confd_color=ACCENT_AMBER if arrived else ACCENT_GREEN,
            next_wait_index=2 if arrived else 1,
            confd_log=[("#1  received (live)", ACCENT_GREEN)] if arrived else [],
            active_milestone_t=20.0 if not arrived else None,
            parked_watch=None,
            open_conn=False,
            resp_packet=(pt, "200 OK (#1)", ACCENT_GREEN) if not arrived else None,
        ))
    add_preview("2_event1_delivered")

    # =========================================================================
    # ACT 2: Event #2 Arrives During Gap -> Replayed on Reconnect (t: 28 -> 54)
    # =========================================================================

    # 2.1 Writer sends PUT #2 while confd is disconnected (t: 28 -> 34)
    n = 16
    for i in range(n):
        pt = progress(i, 0, 14)
        states.append(_make_state(
            t_now=_lerp_t(28.0, 34.0, i, n),
            act=2,
            slots=slots,
            front_slot=front_slot,
            back_slot=back_slot,
            start_index=start_idx,
            last_index=last_idx,
            writer_status="Writing #2",
            writer_color=ACCENT_BLUE,
            writer_badge="PUT /services/web/web@1",
            confd_status="Reloading nginx...",
            confd_color=ACCENT_AMBER,
            next_wait_index=2,
            confd_log=[("#1  received (live)", ACCENT_GREEN)],
            active_milestone_t=34.0 if i >= 10 else None,
            write_packet=(pt, "Event #2", ACCENT_BLUE) if pt < 1.0 else None,
        ))

    # 2.2 Event #2 lands in slot [1] (watchers is empty -> buffered in ring!) (t: 34 -> 41)
    w_slot, _, _, prev_b = push_event(2)
    n = 22
    for i in range(n):
        move_t = progress(i, 0, 10)
        b_ang = _lerp_cw_angle(prev_b, back_slot, move_t) if move_t < 1.0 else None
        fl = max(0.0, 1.0 - progress(i, 3, 16))
        states.append(_make_state(
            t_now=_lerp_t(34.0, 41.0, i, n),
            act=2,
            slots=slots,
            front_slot=front_slot,
            back_slot=back_slot,
            start_index=start_idx,
            last_index=last_idx,
            writer_status="Idle",
            writer_color=TEXT_SUB,
            writer_badge="Last write: #2",
            confd_status="Reloading nginx...",
            confd_color=ACCENT_AMBER,
            next_wait_index=2,
            confd_log=[("#1  received (live)", ACCENT_GREEN)],
            active_milestone_t=34.0 if i < 14 else None,
            slot_flash={w_slot: (ACCENT_BLUE, 0.3 + 0.7 * fl)},
            back_angle_override=b_ang,
        ))

    # 2.3 confd reconnects with GET ?waitIndex=2 (t: 41 -> 47)
    n = 18
    for i in range(n):
        pt = progress(i, 0, 16)
        states.append(_make_state(
            t_now=_lerp_t(41.0, 47.0, i, n),
            act=2,
            slots=slots,
            front_slot=front_slot,
            back_slot=back_slot,
            start_index=start_idx,
            last_index=last_idx,
            writer_status="Idle",
            writer_color=TEXT_SUB,
            writer_badge="Last write: #2",
            confd_status="Reconnecting...",
            confd_color=ACCENT_TEAL,
            next_wait_index=2,
            confd_log=[("#1  received (live)", ACCENT_GREEN)],
            active_milestone_t=47.0 if i >= 12 else None,
            req_packet=(pt, "GET ?waitIndex=2", ACCENT_TEAL) if pt < 1.0 else None,
        ))

    # 2.4 EventHistory.scan(2) HIT! (t: 47 -> 50)
    n = 22
    for i in range(n):
        pulse = 0.55 + 0.45 * math.sin(i * 0.45)
        states.append(_make_state(
            t_now=_lerp_t(47.0, 50.0, i, n),
            act=2,
            slots=slots,
            front_slot=front_slot,
            back_slot=back_slot,
            start_index=start_idx,
            last_index=last_idx,
            writer_status="Idle",
            writer_color=TEXT_SUB,
            writer_badge="Last write: #2",
            confd_status="Waiting reply...",
            confd_color=ACCENT_TEAL,
            next_wait_index=2,
            confd_log=[("#1  received (live)", ACCENT_GREEN)],
            active_milestone_t=47.0,
            scan_status=("1 ≤ 2 ≤ 2", "HIT! Replay slot [1]", ACCENT_GREEN),
            slot_flash={1: (ACCENT_GREEN, 0.55 + 0.45 * pulse)},
            scan_beam_slot=(1, ACCENT_GREEN, 0.85),
        ))
    add_preview("3_scan_hit_replay")

    # 2.5 200 OK (#2) sent back -> confd enters slow busy/reloading state (t: 50 -> 54)
    n = 24
    for i in range(n):
        pt = progress(i, 0, 15)
        arrived = i >= 15
        states.append(_make_state(
            t_now=_lerp_t(50.0, 54.0, i, n),
            act=2,
            slots=slots,
            front_slot=front_slot,
            back_slot=back_slot,
            start_index=start_idx,
            last_index=last_idx,
            writer_status="Idle",
            writer_color=TEXT_SUB,
            writer_badge="Last write: #2",
            confd_status="Busy / reloading..." if arrived else "Receiving #2...",
            confd_color=ACCENT_AMBER if arrived else ACCENT_GREEN,
            next_wait_index=3 if arrived else 2,
            confd_log=(
                [("#1  received (live)", ACCENT_GREEN), ("#2  replayed (ring)", ACCENT_GREEN)]
                if arrived else
                [("#1  received (live)", ACCENT_GREEN)]
            ),
            active_milestone_t=47.0 if not arrived else None,
            resp_packet=(pt, "200 OK (#2)", ACCENT_GREEN) if not arrived else None,
            scan_status=("1 ≤ 2 ≤ 2", "HIT! Replay slot [1]", ACCENT_GREEN) if not arrived else None,
        ))

    # =========================================================================
    # ACT 3: Write Burst (#3..#13) Fills & Wraps Around Ring  (t: 54 -> 84)
    # =========================================================================

    log_after_2 = [("#1  received (live)", ACCENT_GREEN), ("#2  replayed (ring)", ACCENT_GREEN)]

    # Helper to animate a write arriving from Writers and landing in the ring
    burst_t_targets = {
        3:  (54.0, 59.0),
        4:  (59.0, 60.7),
        5:  (60.7, 62.3),
        6:  (62.3, 63.9),
        7:  (63.9, 65.5),
        8:  (65.5, 67.0),
        9:  (67.0, 68.5),
        10: (68.5, 70.5),
        11: (70.5, 74.0),
        12: (74.0, 77.2),
        13: (77.2, 84.0),
    }

    # 3.1 Events #3 .. #10 fill remaining slots (each shows packet flying from Writers!)
    for ev_num in range(3, 11):
        t0, t1 = burst_t_targets[ev_num]
        t_mid = t0 + (t1 - t0) * 0.45
        fly_n = 10 if ev_num in (3, 10) else 5
        land_n = 12 if ev_num in (3, 10) else 5

        # Fly packet from Writers -> WatcherHub
        for i in range(fly_n):
            pt = progress(i, 0, fly_n)
            states.append(_make_state(
                t_now=_lerp_t(t0, t_mid, i, fly_n),
                act=3,
                slots=slots,
                front_slot=front_slot,
                back_slot=back_slot,
                start_index=start_idx,
                last_index=last_idx,
                writer_status=f"Write burst (#{ev_num})",
                writer_color=ACCENT_AMBER,
                writer_badge=f"PUT burst: #{ev_num} / #13",
                confd_status="Busy / reloading...",
                confd_color=ACCENT_AMBER,
                next_wait_index=3,
                confd_log=log_after_2,
                active_milestone_t=(59.0 if ev_num == 3 else (70.0 if ev_num == 10 else None)),
                write_packet=(pt, f"#{ev_num}", ACCENT_AMBER),
                target_slot=2 if ev_num > 3 else None,
            ))

        # Land in ring slot
        w_slot, _, _, prev_b = push_event(ev_num)
        for i in range(land_n):
            move_t = progress(i, 0, min(5, max(1, land_n - 1)))
            b_ang = _lerp_cw_angle(prev_b, back_slot, move_t) if move_t < 1.0 else None
            fl = max(0.0, 1.0 - progress(i, 1, max(1, land_n - 1)))
            states.append(_make_state(
                t_now=_lerp_t(t_mid, t1, i, land_n),
                act=3,
                slots=slots,
                front_slot=front_slot,
                back_slot=back_slot,
                start_index=start_idx,
                last_index=last_idx,
                writer_status=f"Write burst (#{ev_num})",
                writer_color=ACCENT_AMBER,
                writer_badge=f"PUT burst: #{ev_num} / #13",
                confd_status="Busy / reloading...",
                confd_color=ACCENT_AMBER,
                next_wait_index=3,
                confd_log=log_after_2,
                active_milestone_t=(59.0 if ev_num == 3 else (70.0 if ev_num == 10 else None)),
                slot_flash={w_slot: (ACCENT_AMBER, 0.35 + 0.65 * fl)},
                target_slot=2,
                back_angle_override=b_ang,
            ))
    add_preview("4_ring_full")

    # 3.2 Wrap-around writes #11, #12, #13 clear #1, #2, and finally #3!
    for ev_num in (11, 12, 13):
        t0, t1 = burst_t_targets[ev_num]
        t_mid = t0 + (t1 - t0) * 0.35
        is_fatal = (ev_num == 13)
        fly_n = 10 if is_fatal else 7
        land_n = 22 if is_fatal else 12
        pkt_col = ACCENT_CORAL if is_fatal else ACCENT_AMBER

        # Fly packet from Writers -> WatcherHub
        for i in range(fly_n):
            pt = progress(i, 0, fly_n)
            states.append(_make_state(
                t_now=_lerp_t(t0, t_mid, i, fly_n),
                act=3,
                slots=slots,
                front_slot=front_slot,
                back_slot=back_slot,
                start_index=start_idx,
                last_index=last_idx,
                writer_status=f"Write burst (#{ev_num})",
                writer_color=pkt_col,
                writer_badge=f"PUT burst: #{ev_num} / #13",
                confd_status="Busy / reloading...",
                confd_color=ACCENT_AMBER,
                next_wait_index=3,
                confd_log=log_after_2,
                active_milestone_t=80.0 if is_fatal else None,
                write_packet=(pt, f"#{ev_num}", pkt_col),
                target_slot=2,
            ))

        # Overwrite oldest slot & advance Front
        w_slot, overwritten, prev_f, prev_b = push_event(ev_num)
        for i in range(land_n):
            move_t = progress(i, 0, 7)
            f_ang = _lerp_cw_angle(prev_f, front_slot, move_t) if move_t < 1.0 else None
            b_ang = _lerp_cw_angle(prev_b, back_slot, move_t) if move_t < 1.0 else None
            fl = max(0.0, 1.0 - progress(i, 2, max(1, land_n - 3)))
            callout_a = 1.0 if (is_fatal and i >= 2) else (0.9 * fl if i >= 1 else 0.0)
            states.append(_make_state(
                t_now=_lerp_t(t_mid, t1, i, land_n),
                act=3,
                slots=slots,
                front_slot=front_slot,
                back_slot=back_slot,
                start_index=start_idx,
                last_index=last_idx,
                writer_status="Idle" if (is_fatal and i >= 12) else f"Write burst (#{ev_num})",
                writer_color=TEXT_SUB if (is_fatal and i >= 12) else pkt_col,
                writer_badge="Last write: #13" if (is_fatal and i >= 12) else f"PUT burst: #{ev_num} / #13",
                confd_status="Busy / reloading...",
                confd_color=ACCENT_AMBER,
                next_wait_index=3,
                confd_log=log_after_2,
                active_milestone_t=80.0 if is_fatal else None,
                slot_flash={w_slot: (pkt_col, 0.4 + 0.6 * fl)},
                target_slot=None if is_fatal else 2,
                clear_callout=(f"#{overwritten} cleared!", callout_a) if callout_a > 0.05 else None,
                front_angle_override=f_ang,
                back_angle_override=b_ang,
            ))
    add_preview("5_cleared_3")

    # =========================================================================
    # ACT 4: confd Reconnects with waitIndex=3 -> 401 EcodeEventIndexCleared
    # (t: 84 -> 100)
    # =========================================================================

    # 4.1 confd reconnects asking for waitIndex=3 (t: 84 -> 90)
    n = 18
    for i in range(n):
        pt = progress(i, 0, 16)
        states.append(_make_state(
            t_now=_lerp_t(84.0, 90.0, i, n),
            act=4,
            slots=slots,
            front_slot=front_slot,
            back_slot=back_slot,
            start_index=start_idx,
            last_index=last_idx,
            writer_status="Idle",
            writer_color=TEXT_SUB,
            writer_badge="Last write: #13",
            confd_status="Reconnecting...",
            confd_color=ACCENT_TEAL,
            next_wait_index=3,
            confd_log=log_after_2,
            active_milestone_t=93.0 if i >= 12 else None,
            req_packet=(pt, "GET ?waitIndex=3", ACCENT_TEAL) if pt < 1.0 else None,
            clear_callout=("#3 cleared!", 0.85),
        ))

    # 4.2 EventHistory.scan(3) fails: 3 < StartIndex(4) (t: 90 -> 94)
    n = 24
    for i in range(n):
        pulse = 0.55 + 0.45 * math.sin(i * 0.48)
        states.append(_make_state(
            t_now=_lerp_t(90.0, 94.0, i, n),
            act=4,
            slots=slots,
            front_slot=front_slot,
            back_slot=back_slot,
            start_index=start_idx,
            last_index=last_idx,
            writer_status="Idle",
            writer_color=TEXT_SUB,
            writer_badge="Last write: #13",
            confd_status="Waiting reply...",
            confd_color=ACCENT_TEAL,
            next_wait_index=3,
            confd_log=log_after_2,
            active_milestone_t=93.0,
            scan_status=("3 < Start(4)", "401 EventIndexCleared", ACCENT_CORAL),
            slot_flash={
                2: (ACCENT_CORAL, 0.55 + 0.45 * pulse),
                front_slot: (ACCENT_AMBER, 0.45 + 0.35 * pulse),
            },
            clear_callout=("#3 cleared!", 0.95),
            scan_beam_slot=(2, ACCENT_CORAL, 0.85),
        ))
    add_preview("6_scan_401")

    # 4.3 401 Cleared response travels back to confd & final hold (t: 94 -> 100)
    log_after_401 = [
        ("#1  received (live)", ACCENT_GREEN),
        ("#2  replayed (ring)", ACCENT_GREEN),
        ("#3  401 cleared!", ACCENT_CORAL),
    ]
    n = 36
    for i in range(n):
        pt = progress(i, 0, 15)
        arrived = i >= 15
        pulse = 0.5 + 0.5 * math.sin(i * 0.32)
        states.append(_make_state(
            t_now=_lerp_t(94.0, 100.0, i, n),
            act=4,
            slots=slots,
            front_slot=front_slot,
            back_slot=back_slot,
            start_index=start_idx,
            last_index=last_idx,
            writer_status="Idle",
            writer_color=TEXT_SUB,
            writer_badge="Last write: #13",
            confd_status="401 — Must Re-Sync!" if arrived else "Waiting reply...",
            confd_color=ACCENT_CORAL if arrived else ACCENT_TEAL,
            next_wait_index=3,
            confd_log=log_after_401 if arrived else log_after_2,
            active_milestone_t=93.0,
            resp_packet=(pt, "401 Cleared!", ACCENT_CORAL) if not arrived else None,
            scan_status=("3 < Start(4)", "401 EventIndexCleared", ACCENT_CORAL),
            slot_flash={2: (ACCENT_CORAL, 0.45 + 0.30 * pulse)},
            clear_callout=("#3 cleared!", 0.95),
        ))
    add_preview("7_final_401")

    return states, previews


def _draw_packet(
    ax,
    x0: float,
    x1: float,
    y: float,
    t: float,
    label: str,
    color: str,
    pw: float = 1.68,
    zorder: int = 14,
):
    """Draw a sleek animated pill packet traveling horizontally from x0 to x1."""
    et = ease_in_out(t)
    cx = x0 + (x1 - x0) * et
    edge_fade = min(1.0, min(t, 1.0 - t) / 0.12) if 0.0 < t < 1.0 else 0.0
    if edge_fade <= 0.02:
        return
    ph = 0.36
    draw_box(
        ax, cx - pw / 2.0, y - ph / 2.0, pw, ph,
        facecolor=blend_hex(BG_COLOR, color, 0.26),
        edgecolor=color, lw=1.7, radius=0.12, alpha=0.96 * edge_fade, zorder=zorder,
    )
    ax.text(
        cx, y, label,
        color=TEXT_MAIN, fontsize=7.6, family="monospace", fontweight="bold",
        ha="center", va="center", alpha=edge_fade, zorder=zorder + 1,
    )


def _draw_pointer_badge(
    ax,
    angle: float,
    label: str,
    color: str,
    extra_dx: float = 0.0,
    zorder: int = 11,
):
    """Draw an outer ring pointer badge + short crisp arrow pointing to a slot rim."""
    bx = RING_CX + PTR_RX * math.cos(angle) + extra_dx
    by = RING_CY + PTR_RY * math.sin(angle)

    tx = RING_CX + (RING_R + SLOT_R + 0.05) * math.cos(angle)
    ty = RING_CY + (RING_R + SLOT_R + 0.05) * math.sin(angle)

    pw = 0.92
    ph = 0.30
    hw, hh = pw / 2.0, ph / 2.0

    dx, dy = tx - bx, ty - by
    if abs(dx) > 1e-6 or abs(dy) > 1e-6:
        scale = 1.0 / max(abs(dx) / hw if hw > 0 else 0.0, abs(dy) / hh if hh > 0 else 0.0)
        sx = bx + dx * scale
        sy = by + dy * scale
        arr = FancyArrowPatch(
            (sx, sy), (tx, ty),
            arrowstyle="-|>,head_length=4.8,head_width=3.2",
            color=color, linewidth=1.8, zorder=zorder,
        )
        ax.add_patch(arr)

    draw_box(
        ax, bx - hw, by - hh, pw, ph,
        facecolor=blend_hex(BG_COLOR, color, 0.22),
        edgecolor=color, lw=1.5, radius=0.09, zorder=zorder + 1,
    )
    ax.text(
        bx, by, label,
        color=color, fontsize=7.3, family="monospace", fontweight="bold",
        ha="center", va="center", zorder=zorder + 2,
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
    # Header: Clean Static Title (matching ttl_key_heap.py)
    # -------------------------------------------------------------------------
    ax.text(
        8.0, 8.12,
        "Long-Polling Watches & the EventHistory Ring Buffer",
        color=TEXT_MAIN, fontsize=15.2, fontweight="bold", ha="center", va="center",
    )

    # -------------------------------------------------------------------------
    # Top Panel: Pre-Plotted Continuous Event Timeline (matching ttl_key_heap.py)
    # -------------------------------------------------------------------------
    tl_x, tl_y, tl_w, tl_h = 0.55, 6.12, 14.90, 1.62
    draw_box(ax, tl_x, tl_y, tl_w, tl_h, facecolor=PANEL_BG, edgecolor=BOX_BORDER, lw=1.5, radius=0.16, zorder=1)

    track_x0 = 1.10
    track_x1 = 14.90
    track_y = 6.56

    def t_to_x(t_val: float) -> float:
        return track_x0 + (track_x1 - track_x0) * clamp(t_val / T_MAX, 0.0, 1.0)

    # 4 subtle shaded Act zones
    s1, s2, s3 = (t_to_x(z) for z in ZONE_SPLITS)
    zone_defs = [
        (tl_x + 0.12, s1 - 0.03, ACCENT_TEAL,  1, "1. WATCH & NOTIFY"),
        (s1 + 0.03,   s2 - 0.03, ACCENT_GREEN, 2, "2. REPLAY CATCH-UP"),
        (s2 + 0.03,   s3 - 0.03, ACCENT_AMBER, 3, "3. WRITE BURST (#3..#13)"),
        (s3 + 0.03,   tl_x + tl_w - 0.12, ACCENT_CORAL, 4, "4. 401 CLEARED"),
    ]
    for zx0, zx1, zcol, z_act, z_lbl in zone_defs:
        draw_box(
            ax, zx0, tl_y + 0.12, zx1 - zx0, tl_h - 0.24,
            facecolor=blend_hex(PANEL_BG, zcol, 0.06 if st["act"] == z_act else 0.03),
            edgecolor="none", lw=0, radius=0.09, zorder=2,
        )
        ax.text(
            (zx0 + zx1) / 2.0, tl_y + tl_h - 0.23,
            z_lbl,
            color=zcol if st["act"] == z_act else TEXT_DIM,
            fontsize=7.6, fontweight="bold", ha="center", va="center", zorder=4,
        )
    for sx_split in (s1, s2, s3):
        ax.plot(
            [sx_split, sx_split], [tl_y + 0.15, tl_y + tl_h - 0.15],
            color=BOX_BORDER_HI, lw=1.0, linestyle="--", alpha=0.65, zorder=3,
        )

    # Base track & elapsed progress bar
    ax.plot([track_x0, track_x1], [track_y, track_y], color=BOX_BORDER_HI, lw=2.8, solid_capstyle="round", zorder=3)
    now_x = t_to_x(t_now)
    if t_now > 0.2:
        ax.plot([track_x0, now_x], [track_y, track_y], color=TEXT_MAIN, lw=3.2, solid_capstyle="round", alpha=0.88, zorder=4)

    # Pre-plotted milestones
    active_mt = st["active_milestone_t"]
    for mt, kind, label, mcol in TIMELINE_MILESTONES:
        mx = t_to_x(mt)
        is_active = active_mt is not None and abs(active_mt - mt) < 0.01
        is_past = mt < t_now - 0.5
        is_future = mt > t_now + 0.5
        ev_alpha = 1.0 if is_active else (0.58 if is_past else 0.80)

        if is_active:
            ax.add_patch(Circle((mx, track_y), 0.18, facecolor=mcol, edgecolor="none", alpha=0.28, zorder=5))

        if kind in ("clear", "err"):
            r = 0.11 if is_active else 0.09
            diamond = Polygon(
                [(mx, track_y + r), (mx + r, track_y), (mx, track_y - r), (mx - r, track_y)],
                closed=True, facecolor=mcol if not is_future else BG_COLOR,
                edgecolor=mcol, lw=1.8, alpha=ev_alpha, zorder=6,
            )
            ax.add_patch(diamond)
        else:
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
            fontweight="bold" if (is_active or kind in ("clear", "err")) else "normal",
            ha="center", va="center",
            linespacing=1.12,
            alpha=1.0 if is_active else (0.72 if is_past else 0.88),
            zorder=7,
        )

    # Subtle bottom track hint under timeline
    ax.text(
        track_x0, tl_y + 0.21,
        "start (empty)", color=TEXT_DIM, fontsize=7.0, family="monospace", ha="left", va="center", zorder=4,
    )
    ax.text(
        track_x1, tl_y + 0.21,
        "re-sync required", color=ACCENT_CORAL if st["act"] == 4 else TEXT_DIM,
        fontsize=7.0, family="monospace", ha="right", va="center", zorder=4,
    )

    # Crisp moving vertical playhead
    ax.plot([now_x, now_x], [track_y - 0.15, track_y + 0.17], color=TEXT_MAIN, lw=2.4, solid_capstyle="round", zorder=10)
    ax.add_patch(Circle((now_x, track_y), 0.060, facecolor=TEXT_MAIN, edgecolor=BG_COLOR, lw=0.8, zorder=11))

    # -------------------------------------------------------------------------
    # Main Stage Left Column (x = 0.55 .. 3.92): Writers (top) + confd (bottom)
    # -------------------------------------------------------------------------
    lx = 0.55
    lw_col = 3.35

    # --- Top-Left Card: Writers (source of store mutations / events) ---
    wr_y, wr_h = 3.94, 1.94
    wr_col = st["writer_color"]
    wr_ec = blend_hex(BOX_BORDER, wr_col, 0.72) if wr_col != TEXT_SUB else BOX_BORDER
    draw_box(ax, lx, wr_y, lw_col, wr_h, facecolor=PANEL_BG, edgecolor=wr_ec, lw=1.6, radius=0.15, zorder=2)

    ax.text(
        lx + lw_col / 2.0, wr_y + wr_h - 0.30,
        "Cluster Writes",
        color=TEXT_MAIN, fontsize=11.0, fontweight="bold", ha="center", va="center", zorder=3,
    )
    ax.text(
        lx + lw_col / 2.0, wr_y + wr_h - 0.58,
        "PUT / Expire mutations → store",
        color=TEXT_SUB, fontsize=7.6, family="monospace", ha="center", va="center", zorder=3,
    )

    # Writer status pill
    ws_x, ws_y, ws_w, ws_h = lx + 0.24, wr_y + 0.66, lw_col - 0.48, 0.46
    draw_box(
        ax, ws_x, ws_y, ws_w, ws_h,
        facecolor=blend_hex(BOX_INNER, wr_col, 0.20) if wr_col != TEXT_SUB else BOX_INNER,
        edgecolor=wr_col if wr_col != TEXT_SUB else BOX_BORDER, lw=1.4, radius=0.10, zorder=3,
    )
    ax.text(
        lx + lw_col / 2.0, ws_y + ws_h / 2.0,
        st["writer_status"],
        color=wr_col if wr_col != TEXT_SUB else TEXT_DIM,
        fontsize=8.6, fontweight="bold", ha="center", va="center", zorder=4,
    )

    # Writer micro-subtitle (what key / burst count)
    ax.text(
        lx + lw_col / 2.0, wr_y + 0.32,
        st["writer_badge"] if st["writer_badge"] else "(no writes yet)",
        color=TEXT_SOFT if st["writer_badge"] else TEXT_DIM,
        fontsize=7.6, family="monospace",
        style="italic" if not st["writer_badge"] else "normal",
        ha="center", va="center", zorder=4,
    )

    # --- Bottom-Left Card: confd (Watcher) ---
    cf_y, cf_h = 0.90, 2.84
    c_col = st["confd_color"]
    cf_ec = blend_hex(BOX_BORDER, c_col, 0.70) if c_col != TEXT_SUB else BOX_BORDER
    draw_box(ax, lx, cf_y, lw_col, cf_h, facecolor=PANEL_BG, edgecolor=cf_ec, lw=1.6, radius=0.15, zorder=2)

    ax.text(
        lx + 0.24, cf_y + cf_h - 0.28,
        "confd",
        color=TEXT_MAIN, fontsize=11.0, fontweight="bold", ha="left", va="center", zorder=3,
    )
    ax.text(
        lx + lw_col - 0.24, cf_y + cf_h - 0.28,
        "watch /services/web",
        color=TEXT_SUB, fontsize=7.4, family="monospace", ha="right", va="center", zorder=3,
    )

    # confd status pill
    cs_x, cs_y, cs_w, cs_h = lx + 0.22, cf_y + cf_h - 0.92, lw_col - 0.44, 0.42
    draw_box(
        ax, cs_x, cs_y, cs_w, cs_h,
        facecolor=blend_hex(BOX_INNER, c_col, 0.18),
        edgecolor=c_col, lw=1.4, radius=0.10, zorder=3,
    )
    ax.text(
        lx + lw_col / 2.0, cs_y + cs_h / 2.0,
        st["confd_status"],
        color=c_col if c_col != TEXT_SUB else TEXT_SOFT,
        fontsize=8.4, fontweight="bold", ha="center", va="center", zorder=4,
    )

    # next waitIndex row
    wi_x, wi_y, wi_w, wi_h = lx + 0.22, cf_y + cf_h - 1.44, lw_col - 0.44, 0.40
    draw_box(ax, wi_x, wi_y, wi_w, wi_h, facecolor=BOX_INNER, edgecolor=BOX_BORDER, lw=1.1, radius=0.09, zorder=3)
    ax.text(
        wi_x + 0.16, wi_y + wi_h / 2.0,
        "next waitIndex",
        color=TEXT_SUB, fontsize=7.7, family="monospace", ha="left", va="center", zorder=4,
    )
    ax.text(
        wi_x + wi_w - 0.18, wi_y + wi_h / 2.0,
        str(st["next_wait_index"]),
        color=ACCENT_TEAL if st["act"] < 4 else ACCENT_CORAL,
        fontsize=10.8, family="monospace", fontweight="bold", ha="right", va="center", zorder=4,
    )

    # Compact watch response log
    lg_x, lg_y, lg_w, lg_h = lx + 0.22, cf_y + 0.18, lw_col - 0.44, 1.12
    draw_box(ax, lg_x, lg_y, lg_w, lg_h, facecolor=BOX_INNER, edgecolor=BOX_BORDER, lw=1.0, radius=0.09, zorder=3)
    if not st["confd_log"]:
        ax.text(
            lg_x + lg_w / 2.0, lg_y + lg_h / 2.0,
            "watch responses: (none)",
            color=TEXT_DIM, fontsize=7.5, style="italic", ha="center", va="center", zorder=4,
        )
    else:
        for row_i, (txt, rcol) in enumerate(st["confd_log"]):
            ry = lg_y + lg_h - 0.24 - row_i * 0.32
            draw_box(
                ax, lg_x + 0.10, ry - 0.12, lg_w - 0.20, 0.25,
                facecolor=blend_hex(BOX_BG, rcol, 0.15),
                edgecolor=blend_hex(BOX_BORDER, rcol, 0.60),
                lw=0.9, radius=0.06, zorder=4,
            )
            ax.text(
                lg_x + 0.22, ry,
                txt,
                color=rcol, fontsize=7.3, family="monospace", fontweight="bold",
                ha="left", va="center", zorder=5,
            )

    # -------------------------------------------------------------------------
    # Middle Channels (x = 3.90 .. 5.95): Writes (top) & Long-Poll (bottom)
    # -------------------------------------------------------------------------
    ch_x0 = lx + lw_col + 0.05
    ch_x1 = 5.95 - 0.05
    write_y = 4.90
    req_y = 2.84
    resp_y = 1.66

    # Baseline directional tracks
    for (y_line, x_s, x_e, lbl, y_off) in [
        (write_y, ch_x0, ch_x1, "store.notify()", +0.28),
        (req_y,   ch_x0, ch_x1, "HTTP GET",       +0.26),
        (resp_y,  ch_x1, ch_x0, "Response",       -0.26),
    ]:
        arr = FancyArrowPatch(
            (x_s, y_line), (x_e, y_line),
            arrowstyle="-|>,head_length=4.8,head_width=3.0",
            color=BOX_BORDER_HI, linewidth=1.2, linestyle=":", alpha=0.65, zorder=2,
        )
        ax.add_patch(arr)
        ax.text(
            (ch_x0 + ch_x1) / 2.0, y_line + y_off,
            lbl, color=TEXT_DIM, fontsize=7.1, family="monospace", ha="center", va="center", zorder=2,
        )

    # Open hanging HTTP GET connection indicator
    if st["open_conn"]:
        p = st["conn_pulse"]
        ax.plot(
            [ch_x0, ch_x1], [req_y, req_y],
            color=ACCENT_TEAL, lw=2.4, linestyle="--", alpha=0.55 + 0.35 * p, zorder=5,
        )
        draw_box(
            ax, (ch_x0 + ch_x1) / 2.0 - 0.78, req_y - 0.17, 1.56, 0.34,
            facecolor=blend_hex(BG_COLOR, ACCENT_TEAL, 0.24),
            edgecolor=ACCENT_TEAL, lw=1.3, radius=0.10, zorder=6,
        )
        ax.text(
            (ch_x0 + ch_x1) / 2.0, req_y,
            "HTTP GET open",
            color=ACCENT_TEAL, fontsize=7.3, family="monospace", fontweight="bold",
            ha="center", va="center", zorder=7,
        )

    # Animated packets
    if st["write_packet"] is not None:
        pt, plbl, pcol = st["write_packet"]
        pw_p = 1.24 if len(plbl) <= 4 else 1.50
        _draw_packet(ax, ch_x0 + 0.15, ch_x1 - 0.15, write_y, pt, plbl, pcol, pw=pw_p, zorder=15)

    if st["req_packet"] is not None:
        pt, plbl, pcol = st["req_packet"]
        _draw_packet(ax, ch_x0 + 0.15, ch_x1 - 0.15, req_y, pt, plbl, pcol, pw=1.74, zorder=15)

    if st["resp_packet"] is not None:
        pt, plbl, pcol = st["resp_packet"]
        _draw_packet(ax, ch_x1 - 0.15, ch_x0 + 0.15, resp_y, pt, plbl, pcol, pw=1.58, zorder=15)

    # -------------------------------------------------------------------------
    # Right Panel: etcd · WatcherHub (x = 5.95 .. 15.45, y = 0.90 .. 5.88)
    # -------------------------------------------------------------------------
    wx, wy, ww, wh = 5.95, 0.90, 9.50, 4.98
    draw_box(ax, wx, wy, ww, wh, facecolor=PANEL_BG, edgecolor=BOX_BORDER, lw=1.5, radius=0.16, zorder=1)

    ax.text(
        wx + 0.26, wy + wh - 0.28,
        "etcd · WatcherHub",
        color=TEXT_MAIN, fontsize=11.0, fontweight="bold", ha="left", va="center", zorder=3,
    )
    ax.text(
        wx + ww - 0.26, wy + wh - 0.28,
        "10 slots shown  (1,000 in etcd v0.4)",
        color=TEXT_SUB, fontsize=8.1, style="italic", ha="right", va="center", zorder=3,
    )

    # --- Left sub-column inside WatcherHub: watchers slot + EventHistory window ---
    sx = wx + 0.24
    sw = 2.52

    # 1) Compact watchers map slot
    wbox_y, wbox_h = 3.72, 1.62
    w_flash = st["watcher_flash"]
    ws_ec = blend_hex(BOX_BORDER, w_flash[0], 0.8 * w_flash[1]) if w_flash else BOX_BORDER
    draw_box(ax, sx, wbox_y, sw, wbox_h, facecolor=BOX_BG, edgecolor=ws_ec, lw=1.4, radius=0.12, zorder=2)
    ax.text(
        sx + 0.16, wbox_y + wbox_h - 0.24,
        "watchers",
        color=TEXT_MAIN, fontsize=9.1, family="monospace", fontweight="bold", ha="left", va="center", zorder=3,
    )
    ax.text(
        sx + 0.16, wbox_y + wbox_h - 0.48,
        '["/services/web"]',
        color=TEXT_SUB, fontsize=7.4, family="monospace", ha="left", va="center", zorder=3,
    )

    sb_y, sb_h = wbox_y + 0.18, 0.78
    if st["parked_watch"]:
        pcol = w_flash[0] if w_flash else ACCENT_TEAL
        draw_box(
            ax, sx + 0.14, sb_y, sw - 0.28, sb_h,
            facecolor=blend_hex(BOX_INNER, pcol, 0.24),
            edgecolor=pcol, lw=1.6, radius=0.10, zorder=3,
        )
        ax.text(
            sx + sw / 2.0, sb_y + sb_h / 2.0 + 0.12,
            st["parked_watch"],
            color=TEXT_MAIN, fontsize=7.8, family="monospace", fontweight="bold",
            ha="center", va="center", zorder=4,
        )
        ax.text(
            sx + sw / 2.0, sb_y + sb_h / 2.0 - 0.15,
            "live EventChan",
            color=pcol, fontsize=7.1, family="monospace", ha="center", va="center", zorder=4,
        )
    else:
        draw_box(
            ax, sx + 0.14, sb_y, sw - 0.28, sb_h,
            facecolor=BOX_INNER, edgecolor=BOX_BORDER, lw=1.1, linestyle="--", radius=0.10, zorder=3,
        )
        ax.text(
            sx + sw / 2.0, sb_y + sb_h / 2.0,
            "(empty)",
            color=TEXT_DIM, fontsize=8.0, style="italic", ha="center", va="center", zorder=4,
        )

    # 2) Compact EventHistory window & scan() check card
    eh_y, eh_h = 1.12, 2.42
    scan_st = st["scan_status"]
    eh_ec = blend_hex(BOX_BORDER, scan_st[2], 0.85) if scan_st else BOX_BORDER
    draw_box(ax, sx, eh_y, sw, eh_h, facecolor=BOX_BG, edgecolor=eh_ec, lw=1.4, radius=0.12, zorder=2)
    ax.text(
        sx + 0.16, eh_y + eh_h - 0.24,
        "EventHistory",
        color=TEXT_MAIN, fontsize=9.1, family="monospace", fontweight="bold", ha="left", va="center", zorder=3,
    )

    for row_i, (k_lbl, val_str, v_col) in enumerate([
        ("StartIndex", str(st["start_index"]) if st["start_index"] > 0 else "—", ACCENT_AMBER),
        ("LastIndex", str(st["last_index"]) if st["last_index"] > 0 else "—", ACCENT_BLUE),
    ]):
        ry = eh_y + eh_h - 0.64 - row_i * 0.44
        draw_box(
            ax, sx + 0.14, ry - 0.16, sw - 0.28, 0.34,
            facecolor=BOX_INNER, edgecolor=BOX_BORDER, lw=1.0, radius=0.08, zorder=3,
        )
        ax.text(
            sx + 0.26, ry,
            k_lbl,
            color=TEXT_SOFT, fontsize=7.6, family="monospace", ha="left", va="center", zorder=4,
        )
        ax.text(
            sx + sw - 0.26, ry,
            val_str,
            color=v_col if val_str != "—" else TEXT_DIM,
            fontsize=9.5, family="monospace", fontweight="bold", ha="right", va="center", zorder=4,
        )

    sc_y, sc_h = eh_y + 0.16, 0.86
    if scan_st is not None:
        expr, verdict, scol = scan_st
        draw_box(
            ax, sx + 0.14, sc_y, sw - 0.28, sc_h,
            facecolor=blend_hex(BOX_INNER, scol, 0.20),
            edgecolor=scol, lw=1.5, radius=0.09, zorder=3,
        )
        ax.text(
            sx + sw / 2.0, sc_y + sc_h - 0.18,
            "scan() check",
            color=TEXT_SUB, fontsize=6.8, family="monospace", ha="center", va="center", zorder=4,
        )
        ax.text(
            sx + sw / 2.0, sc_y + 0.42,
            expr,
            color=TEXT_MAIN, fontsize=8.4, family="monospace", fontweight="bold", ha="center", va="center", zorder=4,
        )
        ax.text(
            sx + sw / 2.0, sc_y + 0.16,
            verdict,
            color=scol, fontsize=7.5, fontweight="bold", ha="center", va="center", zorder=4,
        )
    else:
        draw_box(
            ax, sx + 0.14, sc_y, sw - 0.28, sc_h,
            facecolor=BOX_INNER, edgecolor=BOX_BORDER, lw=1.0, linestyle="--", radius=0.09, zorder=3,
        )
        ax.text(
            sx + sw / 2.0, sc_y + sc_h / 2.0,
            "scan() idle",
            color=TEXT_DIM, fontsize=7.7, family="monospace", style="italic", ha="center", va="center", zorder=4,
        )

    # --- Right sub-area inside WatcherHub: Circular 10-slot Ring Buffer ---
    backbone = Circle(
        (RING_CX, RING_CY), RING_R,
        facecolor="none", edgecolor=BOX_BORDER, lw=2.0, linestyle="-", alpha=0.70, zorder=2,
    )
    ax.add_patch(backbone)

    # Subtle clockwise direction arc inside the ring
    cw_arc = Arc(
        (RING_CX, RING_CY), 1.32, 1.32,
        angle=0.0, theta1=35.0, theta2=145.0,
        color=BOX_BORDER_HI, lw=1.1, linestyle="--", alpha=0.55, zorder=2,
    )
    ax.add_patch(cw_arc)
    tip_ang = math.radians(35.0)
    tip_r = 0.66
    tx = RING_CX + tip_r * math.cos(tip_ang)
    ty = RING_CY + tip_r * math.sin(tip_ang)
    ux, uy = math.sin(tip_ang), -math.cos(tip_ang)
    nx, ny = math.cos(tip_ang), math.sin(tip_ang)
    tri = Polygon(
        [
            (tx + 0.07 * ux, ty + 0.07 * uy),
            (tx - 0.05 * ux + 0.038 * nx, ty - 0.05 * uy + 0.038 * ny),
            (tx - 0.05 * ux - 0.038 * nx, ty - 0.05 * uy - 0.038 * ny),
        ],
        closed=True, facecolor=BOX_BORDER_HI, edgecolor="none", alpha=0.75, zorder=3,
    )
    ax.add_patch(tri)

    # Center ring status text
    filled_count = sum(1 for v in st["slots"] if v is not None)
    ax.text(
        RING_CX, RING_CY + 0.14,
        "Ring Buffer",
        color=TEXT_SOFT, fontsize=8.4, fontweight="bold", ha="center", va="center", zorder=3,
    )
    size_col = ACCENT_CORAL if (st["act"] == 4) else (ACCENT_AMBER if filled_count == CAPACITY else TEXT_SUB)
    size_txt = f"{filled_count} / {CAPACITY}" + (" FULL" if filled_count == CAPACITY else "")
    ax.text(
        RING_CX, RING_CY - 0.14,
        size_txt,
        color=size_col, fontsize=8.0, family="monospace", fontweight="bold", ha="center", va="center", zorder=3,
    )

    # Optional scan beam from EventHistory card to target slot (cleanly behind slots)
    if st["scan_beam_slot"] is not None:
        b_slot, b_col, b_alpha = st["scan_beam_slot"]
        tx, ty = _slot_xy(b_slot)
        arr = FancyArrowPatch(
            (sx + sw + 0.04, eh_y + 0.58),
            (tx - 0.25, ty - 0.18),
            connectionstyle="arc3,rad=0.18",
            arrowstyle="-|>,head_length=5.5,head_width=3.6",
            color=b_col, linewidth=1.9, linestyle="--", alpha=0.65 * b_alpha, zorder=3,
        )
        ax.add_patch(arr)

    # Draw all 10 circular slots
    slot_flash = st["slot_flash"]
    target_slot = st["target_slot"]
    for k in range(CAPACITY):
        x, y = _slot_xy(k)
        ev = st["slots"][k]
        is_front = (st["front_slot"] == k)
        is_back = (st["back_slot"] == k)
        fl = slot_flash.get(k)

        if ev is None:
            fc = BOX_INNER
            ec = BOX_BORDER
            lw_s = 1.2
            ls = "--"
        else:
            base_ec = ACCENT_BLUE if is_back else (ACCENT_AMBER if is_front else BOX_BORDER_HI)
            base_fc = blend_hex(BOX_BG, base_ec, 0.16 if (is_front or is_back) else 0.06)
            if fl is not None:
                fcol, fint = fl
                fc = blend_hex(base_fc, fcol, 0.38 * fint)
                ec = fcol
                lw_s = 2.2
            else:
                fc = base_fc
                ec = base_ec
                lw_s = 1.8 if (is_front or is_back) else 1.3
            ls = "-"

        if fl is not None and fl[1] > 0.08:
            ax.add_patch(Circle(
                (x, y), SLOT_R + 0.085,
                facecolor=fl[0], edgecolor="none", alpha=0.22 * fl[1], zorder=4,
            ))

        if target_slot == k and ev == 3:
            ax.add_patch(Circle(
                (x, y), SLOT_R + 0.08,
                facecolor="none", edgecolor=ACCENT_TEAL, lw=1.5, linestyle="--", alpha=0.88, zorder=5,
            ))

        ax.add_patch(Circle(
            (x, y), SLOT_R,
            facecolor=fc, edgecolor=ec, lw=lw_s, linestyle=ls, zorder=6,
        ))

        if ev is not None:
            ax.text(
                x, y + 0.04,
                f"#{ev}",
                color=TEXT_MAIN, fontsize=9.0, family="monospace", fontweight="bold",
                ha="center", va="center", zorder=7,
            )
            ax.text(
                x, y - 0.15,
                f"[{k}]",
                color=TEXT_DIM, fontsize=6.0, family="monospace",
                ha="center", va="center", zorder=7,
            )
        else:
            ax.text(
                x, y,
                f"[{k}]",
                color=TEXT_DIM, fontsize=7.0, family="monospace",
                ha="center", va="center", zorder=7,
            )

    # Cleared micro-callout centered cleanly below the ring readout
    if st["clear_callout"] is not None:
        cc_txt, cc_a = st["clear_callout"]
        ex, ey = RING_CX, RING_CY - 0.48
        pw_c, ph_c = 1.14, 0.26
        draw_box(
            ax, ex - pw_c / 2.0, ey - ph_c / 2.0, pw_c, ph_c,
            facecolor=blend_hex(BG_COLOR, ACCENT_CORAL, 0.28),
            edgecolor=ACCENT_CORAL, lw=1.2, radius=0.08, alpha=0.95 * cc_a, zorder=12,
        )
        ax.text(
            ex, ey, cc_txt,
            color=ACCENT_CORAL, fontsize=6.9, family="monospace", fontweight="bold",
            ha="center", va="center", alpha=cc_a, zorder=13,
        )

    # Draw Front (StartIndex) and Back (LastIndex) outer pointers
    if st["front_slot"] is not None and st["back_slot"] is not None:
        f_ang = st["front_angle_override"] if st["front_angle_override"] is not None else _slot_angle(st["front_slot"])
        b_ang = st["back_angle_override"] if st["back_angle_override"] is not None else _slot_angle(st["back_slot"])

        same_slot = (
            st["front_slot"] == st["back_slot"]
            and st["front_angle_override"] is None
            and st["back_angle_override"] is None
        )
        if same_slot:
            _draw_pointer_badge(ax, f_ang, f"Front #{st['start_index']}", ACCENT_AMBER, extra_dx=-0.54, zorder=11)
            _draw_pointer_badge(ax, b_ang, f"Back #{st['last_index']}", ACCENT_BLUE, extra_dx=+0.54, zorder=11)
        else:
            _draw_pointer_badge(ax, f_ang, f"Front #{st['start_index']}", ACCENT_AMBER, zorder=11)
            _draw_pointer_badge(ax, b_ang, f"Back #{st['last_index']}", ACCENT_BLUE, zorder=11)

    # -------------------------------------------------------------------------
    # Bottom Act Progress Bar + Takeaway Note
    # -------------------------------------------------------------------------
    pill_y, pill_h = 0.24, 0.42
    pill_x = 0.55
    pill_widths = [1.96, 2.04, 2.48, 1.76]
    pill_gap = 0.14

    for (act_num, label, col), pw in zip(ACT_PILLS, pill_widths):
        is_current = (st["act"] == act_num)
        is_done = (st["act"] > act_num)
        if is_current:
            fc, ec, tc, lw_p = col, col, BG_COLOR, 1.2
            p_alpha = 0.96
        elif is_done:
            fc, ec, tc, lw_p = BOX_BG, col, TEXT_SOFT, 1.1
            p_alpha = 0.85
        else:
            fc, ec, tc, lw_p = PANEL_BG, BOX_BORDER, TEXT_DIM, 1.0
            p_alpha = 0.65

        draw_box(ax, pill_x, pill_y, pw, pill_h, facecolor=fc, edgecolor=ec, lw=lw_p, radius=0.11, alpha=p_alpha, zorder=3)
        ax.text(
            pill_x + pw / 2.0, pill_y + pill_h / 2.0,
            label, color=tc, fontsize=8.1, fontweight="bold" if is_current else "normal",
            ha="center", va="center", zorder=4,
        )
        pill_x += pw + pill_gap

    ax.text(
        15.45, pill_y + pill_h / 2.0,
        "Short disconnects replay; bursts past capacity clear old events",
        color=TEXT_SUB, fontsize=8.1, style="italic", ha="right", va="center",
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
