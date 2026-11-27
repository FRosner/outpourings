"""Static Diagram: Inside etcd v0.4's In-Memory store Layout (Go Heap).

Replaces the cramped ASCII tree in Part 1 with a crisp, dark-slate structural
diagram matching the rest of the Part 1 animations and benchmark charts.

Shows:
  - Left: `store` struct (`worldLock`, `CurrentIndex`, `Root *node`,
    `WatcherHub`, and `ttlKeyHeap` with `array []*node` and `keyMap`).
  - Right: Go heap tree of `*node` structs starting at `Root` (`dir "/"`),
    illustrating how directory nodes store `Children map[string]*node`,
    leaf nodes store `Value`, `ModifiedIndex`, `ExpireTime`, and `Children: nil`,
    and `store.ttlKeyHeap.array[0]` points directly to the exact same `*node`
    struct in RAM as `/services/web/web@1`.
"""

from pathlib import Path
from typing import Iterable, List, Optional, Tuple

# Import common first so MPLCONFIGDIR and the Agg backend are configured before pyplot.
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
    draw_box,
    fig_to_rgb,
)

import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, PathPatch
from matplotlib.path import Path as MplPath
from PIL import Image

NAME = "store_memory_layout"
DESCRIPTION = "Static diagram of etcd v0.4's in-memory store struct, directory/leaf *node tree, and shared ttlKeyHeap pointer."
IS_STATIC = True


def _draw_arrow(
    ax,
    p0: Tuple[float, float],
    p1: Tuple[float, float],
    color: str,
    lw: float = 1.65,
    alpha: float = 0.92,
    linestyle: str = "-",
    head_length: float = 5.0,
    head_width: float = 3.1,
    zorder: int = 5,
):
    ax.add_patch(
        FancyArrowPatch(
            p0,
            p1,
            arrowstyle=f"-|>,head_length={head_length},head_width={head_width}",
            color=color,
            linewidth=lw,
            linestyle=linestyle,
            alpha=alpha,
            shrinkA=0.0,
            shrinkB=0.0,
            zorder=zorder,
        )
    )


def _draw_port_dot(ax, x: float, y: float, color: str, radius: float = 0.052, zorder: int = 8):
    ax.add_patch(Circle((x, y), radius * 1.75, facecolor=color, edgecolor="none", alpha=0.22, zorder=zorder - 1))
    ax.add_patch(Circle((x, y), radius, facecolor=color, edgecolor=BG_COLOR, linewidth=0.85, zorder=zorder))


def _draw_badge(
    ax,
    x: float,
    y: float,
    w: float,
    h: float,
    text: str,
    color: str,
    fontsize: float = 6.6,
    fill_mix: float = 0.20,
    zorder: int = 6,
):
    draw_box(
        ax,
        x,
        y,
        w,
        h,
        facecolor=blend_hex(BOX_INNER, color, fill_mix),
        edgecolor=blend_hex(BOX_BORDER, color, 0.72),
        lw=1.0,
        radius=0.06,
        zorder=zorder,
    )
    ax.text(
        x + w / 2.0,
        y + h / 2.0,
        text,
        color=color,
        fontsize=fontsize,
        family="monospace",
        fontweight="bold",
        ha="center",
        va="center",
        zorder=zorder + 1,
    )


def _draw_dir_node(
    ax,
    x: float,
    cy: float,
    w: float,
    h: float,
    segment: str,
    child_key: str,
    color: str,
    highlight: bool = False,
):
    """Draw a compact directory *node card showing segment name and outgoing Children[key]."""
    y = cy - h / 2.0
    if highlight:
        draw_box(
            ax, x - 0.05, y - 0.05, w + 0.10, h + 0.10,
            facecolor="none", edgecolor=color, lw=2.8, radius=0.16, alpha=0.20, zorder=2,
        )
    fc = blend_hex(BOX_BG, color, 0.08 if highlight else 0.03)
    ec = blend_hex(BOX_BORDER_HI, color, 0.85 if highlight else 0.50)
    lw = 1.9 if highlight else 1.35
    draw_box(ax, x, y, w, h, facecolor=fc, edgecolor=ec, lw=lw, radius=0.12, zorder=3)

    # Left colored accent strip
    draw_box(
        ax, x + 0.05, y + 0.10, 0.05, h - 0.20,
        facecolor=color, edgecolor="none", lw=0, radius=0.02, alpha=0.90 if highlight else 0.70, zorder=4,
    )

    # Top row: DIR badge + segment name
    top_y = y + h - 0.23
    _draw_badge(ax, x + 0.15, top_y - 0.10, 0.38, 0.20, "DIR", color, fontsize=6.2, zorder=5)
    seg_fs = 7.6 if len(segment) >= 11 else 8.0
    ax.text(
        x + 0.60,
        top_y,
        f'"{segment}"',
        color=TEXT_MAIN if highlight else TEXT_SOFT,
        fontsize=seg_fs,
        family="monospace",
        fontweight="bold",
        ha="left",
        va="center",
        zorder=5,
    )

    # Bottom row: recessed Children[key] pill
    pill_x = x + 0.15
    pill_y = y + 0.11
    pill_w = w - 0.26
    pill_h = 0.27
    draw_box(
        ax,
        pill_x,
        pill_y,
        pill_w,
        pill_h,
        facecolor=BOX_INNER,
        edgecolor=blend_hex(BOX_BORDER, color, 0.45 if highlight else 0.22),
        lw=0.95,
        radius=0.06,
        zorder=4,
    )
    pill_txt = f'Children["{child_key}"]'
    pill_fs = 5.9 if len(child_key) >= 10 else 6.4
    ax.text(
        pill_x + 0.08,
        pill_y + pill_h / 2.0,
        pill_txt,
        color=blend_hex(TEXT_SUB, color, 0.58 if highlight else 0.28),
        fontsize=pill_fs,
        family="monospace",
        ha="left",
        va="center",
        zorder=5,
    )

    # Port dot on right edge at vertical center of card
    _draw_port_dot(ax, x + w, cy, color, radius=0.046, zorder=7)


def _draw_leaf_node(
    ax,
    x: float,
    cy: float,
    w: float,
    h: float,
    name: str,
    value_str: str,
    mod_idx: int,
    color: str,
    expire_str: Optional[str] = None,
    highlight: bool = False,
):
    """Draw a leaf *node card with Value, ModifiedIndex, Children: nil, and optional ExpireTime."""
    y = cy - h / 2.0
    if highlight:
        draw_box(
            ax, x - 0.06, y - 0.06, w + 0.12, h + 0.12,
            facecolor="none", edgecolor=color, lw=3.2, radius=0.17, alpha=0.26, zorder=2,
        )
    fc = blend_hex(BOX_BG, color, 0.11 if highlight else 0.05)
    ec = color if highlight else blend_hex(BOX_BORDER_HI, color, 0.72)
    lw = 2.1 if highlight else 1.5
    draw_box(ax, x, y, w, h, facecolor=fc, edgecolor=ec, lw=lw, radius=0.13, zorder=3)

    # Top header row
    top_y = y + h - 0.22
    _draw_badge(ax, x + 0.14, top_y - 0.105, 0.48, 0.21, "LEAF", color, fontsize=6.4, fill_mix=0.26, zorder=5)
    ax.text(
        x + 0.71,
        top_y,
        f'"{name}"',
        color=TEXT_MAIN,
        fontsize=8.6,
        family="monospace",
        fontweight="bold",
        ha="left",
        va="center",
        zorder=5,
    )

    # Subtle divider under header
    div_y = y + h - 0.40
    ax.plot([x + 0.14, x + w - 0.14], [div_y, div_y], color=BOX_BORDER, lw=0.9, alpha=0.75, zorder=4)

    # Value line
    val_y = div_y - 0.19
    ax.text(
        x + 0.15,
        val_y,
        "Value:",
        color=TEXT_DIM,
        fontsize=7.2,
        family="monospace",
        ha="left",
        va="center",
        zorder=5,
    )
    ax.text(
        x + 0.72,
        val_y,
        value_str,
        color=TEXT_MAIN if highlight else TEXT_SOFT,
        fontsize=7.3,
        family="monospace",
        fontweight="bold" if highlight else "normal",
        ha="left",
        va="center",
        zorder=5,
    )

    # Metadata line: ModifiedIndex + Children: nil
    meta_y = val_y - 0.24
    ax.text(
        x + 0.15,
        meta_y,
        f"ModifiedIndex: {mod_idx}",
        color=color if not highlight else TEXT_SOFT,
        fontsize=7.0,
        family="monospace",
        fontweight="bold" if mod_idx == 5 else "normal",
        ha="left",
        va="center",
        zorder=5,
    )
    ax.text(
        x + w - 0.15,
        meta_y,
        "Children: nil",
        color=TEXT_DIM,
        fontsize=6.9,
        family="monospace",
        ha="right",
        va="center",
        zorder=5,
    )

    # Optional ExpireTime pill (for ephemeral TTL keys)
    if expire_str is not None:
        ep_x = x + 0.14
        ep_y = y + 0.11
        ep_w = w - 0.28
        ep_h = 0.26
        draw_box(
            ax,
            ep_x,
            ep_y,
            ep_w,
            ep_h,
            facecolor=blend_hex(BOX_INNER, color, 0.20),
            edgecolor=color,
            lw=1.15,
            radius=0.07,
            zorder=4,
        )
        ax.text(
            ep_x + ep_w / 2.0,
            ep_y + ep_h / 2.0,
            f"ExpireTime: {expire_str}",
            color=color,
            fontsize=7.3,
            family="monospace",
            fontweight="bold",
            ha="center",
            va="center",
            zorder=5,
        )


def _draw_rounded_ortho_arrow(
    ax,
    p_start: Tuple[float, float],
    lane_y: float,
    p_end: Tuple[float, float],
    color: str,
    r: float = 0.18,
    lw: float = 2.0,
    zorder: int = 6,
):
    """Draw a smooth orthogonal pointer: down from p_start -> right along lane_y -> up into p_end."""
    x0, y0 = p_start
    x1, y1 = p_end

    verts = [
        (x0, y0),
        (x0, lane_y + r),
        (x0, lane_y),          # corner 1 control point
        (x0 + r, lane_y),
        (x1 - r, lane_y),
        (x1, lane_y),          # corner 2 control point
        (x1, lane_y + r),
        (x1, y1 - 0.12),
    ]
    codes = [
        MplPath.MOVETO,
        MplPath.LINETO,
        MplPath.CURVE3,
        MplPath.CURVE3,
        MplPath.LINETO,
        MplPath.CURVE3,
        MplPath.CURVE3,
        MplPath.LINETO,
    ]
    path = MplPath(verts, codes)
    # Soft glow underlay
    ax.add_patch(
        PathPatch(
            path,
            facecolor="none",
            edgecolor=color,
            linewidth=lw + 3.0,
            alpha=0.14,
            capstyle="round",
            zorder=zorder - 1,
        )
    )
    # Crisp main dashed line
    ax.add_patch(
        PathPatch(
            path,
            facecolor="none",
            edgecolor=color,
            linewidth=lw,
            linestyle=(0, (5.5, 2.8)),
            alpha=0.95,
            capstyle="round",
            zorder=zorder,
        )
    )
    # Crisp arrowhead at target entry
    _draw_arrow(
        ax,
        (x1, y1 - 0.18),
        (x1, y1),
        color=color,
        lw=lw,
        head_length=5.6,
        head_width=3.6,
        zorder=zorder + 1,
    )


def render_diagram(dpi: int = 180):
    fig, ax = plt.subplots(figsize=(13.2, 7.36), dpi=dpi)
    fig.patch.set_facecolor(BG_COLOR)
    ax.set_facecolor(BG_COLOR)
    ax.set_xlim(0.0, 16.5)
    ax.set_ylim(0.0, 9.2)
    ax.axis("off")

    # -------------------------------------------------------------------------
    # Header
    # -------------------------------------------------------------------------
    ax.text(
        8.25,
        8.78,
        "Inside etcd v0.4: In-Memory store Layout (Go Heap)",
        color=TEXT_MAIN,
        fontsize=15.0,
        fontweight="bold",
        ha="center",
        va="center",
    )
    ax.text(
        8.25,
        8.38,
        "Directory nodes hold Children map[string]*node; leaf nodes hold values; ttlKeyHeap shares *node pointers",
        color=TEXT_SUB,
        fontsize=9.3,
        ha="center",
        va="center",
    )

    # -------------------------------------------------------------------------
    # Left Panel: `store` Struct
    # -------------------------------------------------------------------------
    sx, sy, sw, sh = 0.30, 0.72, 2.74, 7.32
    draw_box(
        ax, sx, sy, sw, sh,
        facecolor=PANEL_BG, edgecolor=blend_hex(BOX_BORDER_HI, ACCENT_BLUE, 0.55),
        lw=1.7, radius=0.16, zorder=1,
    )
    s_hdr_y = sy + sh - 0.50
    ax.plot([sx + 0.15, sx + sw - 0.15], [s_hdr_y, s_hdr_y], color=BOX_BORDER, lw=1.0, zorder=2)
    ax.text(
        sx + 0.18, sy + sh - 0.25,
        "store",
        color=ACCENT_BLUE, fontsize=11.4, family="monospace", fontweight="bold",
        ha="left", va="center", zorder=3,
    )
    ax.text(
        sx + sw - 0.18, sy + sh - 0.25,
        "struct",
        color=TEXT_DIM, fontsize=8.2, family="monospace",
        ha="right", va="center", zorder=3,
    )

    fx = sx + 0.15
    fw = sw - 0.30

    # Field 1: worldLock
    wl_y, wl_h = 6.72, 0.66
    draw_box(ax, fx, wl_y, fw, wl_h, facecolor=BOX_BG, edgecolor=BOX_BORDER, lw=1.2, radius=0.10, zorder=2)
    ax.text(fx + 0.12, wl_y + 0.44, "worldLock", color=TEXT_MAIN, fontsize=8.5, family="monospace", fontweight="bold", ha="left", va="center", zorder=3)
    ax.text(fx + fw - 0.11, wl_y + 0.44, "RWMutex", color=TEXT_SUB, fontsize=7.0, family="monospace", ha="right", va="center", zorder=3)
    ax.text(fx + 0.12, wl_y + 0.18, "RLock (read) / Lock (write)", color=TEXT_DIM, fontsize=6.7, ha="left", va="center", zorder=3)

    # Field 2: CurrentIndex
    ci_y, ci_h = 5.92, 0.64
    draw_box(ax, fx, ci_y, fw, ci_h, facecolor=BOX_BG, edgecolor=BOX_BORDER, lw=1.2, radius=0.10, zorder=2)
    ax.text(fx + 0.12, ci_y + 0.42, "CurrentIndex", color=TEXT_MAIN, fontsize=8.3, family="monospace", fontweight="bold", ha="left", va="center", zorder=3)
    _draw_badge(ax, fx + fw - 0.44, ci_y + 0.30, 0.33, 0.24, "5", ACCENT_BLUE, fontsize=7.6, fill_mix=0.22, zorder=4)
    ax.text(fx + 0.12, ci_y + 0.17, "global monotonic uint64", color=TEXT_DIM, fontsize=6.7, ha="left", va="center", zorder=3)

    # Field 3: Root *node (highlighted blue)
    rt_y, rt_h = 4.90, 0.86
    rt_cy = rt_y + rt_h / 2.0
    draw_box(
        ax, fx, rt_y, fw, rt_h,
        facecolor=blend_hex(BOX_BG, ACCENT_BLUE, 0.12),
        edgecolor=ACCENT_BLUE, lw=1.65, radius=0.10, zorder=2,
    )
    ax.text(fx + 0.12, rt_y + 0.60, "Root", color=ACCENT_BLUE, fontsize=9.1, family="monospace", fontweight="bold", ha="left", va="center", zorder=3)
    ax.text(fx + 0.12, rt_y + 0.35, '*node  (dir "/")', color=TEXT_SOFT, fontsize=7.4, family="monospace", ha="left", va="center", zorder=3)
    ax.text(fx + 0.12, rt_y + 0.14, "entry point for all lookups", color=TEXT_DIM, fontsize=6.6, ha="left", va="center", zorder=3)
    _draw_port_dot(ax, fx + fw, rt_cy, ACCENT_BLUE, radius=0.054, zorder=8)

    # Field 4: WatcherHub
    wh_y, wh_h = 4.08, 0.66
    draw_box(ax, fx, wh_y, fw, wh_h, facecolor=BOX_BG, edgecolor=BOX_BORDER, lw=1.15, radius=0.10, zorder=2)
    ax.text(fx + 0.12, wh_y + 0.44, "WatcherHub", color=TEXT_SOFT, fontsize=8.3, family="monospace", fontweight="bold", ha="left", va="center", zorder=3)
    ax.text(fx + 0.12, wh_y + 0.18, "watches + EventHistory[1000]", color=TEXT_DIM, fontsize=6.5, ha="left", va="center", zorder=3)

    # Field 5: ttlKeyHeap (highlighted teal, bottom sub-card)
    th_y, th_h = 1.54, 2.36
    draw_box(
        ax, fx, th_y, fw, th_h,
        facecolor=blend_hex(BOX_BG, ACCENT_TEAL, 0.08),
        edgecolor=blend_hex(BOX_BORDER_HI, ACCENT_TEAL, 0.78),
        lw=1.55, radius=0.11, zorder=2,
    )
    ax.text(fx + 0.12, th_y + th_h - 0.24, "ttlKeyHeap", color=ACCENT_TEAL, fontsize=8.8, family="monospace", fontweight="bold", ha="left", va="center", zorder=3)
    ax.text(fx + fw - 0.11, th_y + th_h - 0.24, "min-heap", color=TEXT_DIM, fontsize=6.9, family="monospace", ha="right", va="center", zorder=3)

    # keyMap note pill
    km_y, km_h = th_y + 1.48, 0.36
    draw_box(ax, fx + 0.10, km_y, fw - 0.20, km_h, facecolor=BOX_INNER, edgecolor=BOX_BORDER, lw=0.9, radius=0.07, zorder=3)
    ax.text(fx + 0.18, km_y + km_h / 2.0, "keyMap: map[*node]int", color=TEXT_SUB, fontsize=6.7, family="monospace", ha="left", va="center", zorder=4)

    # array []*node label + 3-cell horizontal slice strip
    ax.text(fx + 0.12, th_y + 1.24, "array []*node (soonest first)", color=TEXT_SOFT, fontsize=6.6, family="monospace", ha="left", va="center", zorder=3)

    arr_y, arr_h = th_y + 0.20, 0.84
    arr_x = fx + 0.10
    arr_w = fw - 0.20
    cell_gap = 0.07
    cell_w = (arr_w - 2 * cell_gap) / 3.0

    heap_cells = [
        ("[0]", "*node", "+30s", True),
        ("[1]", "web@2", "+35s", False),
        ("[2]", "web@3", "+40s", False),
    ]
    cell0_bot_x = arr_x + cell_w / 2.0
    for idx_c, (c_idx, c_lbl, c_ttl, is_root_cell) in enumerate(heap_cells):
        cx_cell = arr_x + idx_c * (cell_w + cell_gap)
        c_fc = blend_hex(BOX_INNER, ACCENT_TEAL, 0.22) if is_root_cell else BOX_INNER
        c_ec = ACCENT_TEAL if is_root_cell else BOX_BORDER
        draw_box(ax, cx_cell, arr_y, cell_w, arr_h, facecolor=c_fc, edgecolor=c_ec, lw=1.4 if is_root_cell else 0.95, radius=0.07, zorder=3)
        ax.text(
            cx_cell + cell_w / 2.0, arr_y + arr_h - 0.18,
            c_idx, color=ACCENT_TEAL if is_root_cell else TEXT_DIM,
            fontsize=7.2, family="monospace", fontweight="bold", ha="center", va="center", zorder=4,
        )
        ax.text(
            cx_cell + cell_w / 2.0, arr_y + 0.40,
            c_lbl, color=TEXT_MAIN if is_root_cell else TEXT_SUB,
            fontsize=6.8, family="monospace", fontweight="bold" if is_root_cell else "normal",
            ha="center", va="center", zorder=4,
        )
        ax.text(
            cx_cell + cell_w / 2.0, arr_y + 0.16,
            c_ttl, color=ACCENT_TEAL if is_root_cell else TEXT_DIM,
            fontsize=6.4, family="monospace", ha="center", va="center", zorder=4,
        )

    _draw_port_dot(ax, cell0_bot_x, arr_y, ACCENT_TEAL, radius=0.054, zorder=8)

    # -------------------------------------------------------------------------
    # Right Panel: Go Heap (Tree of *node Structs)
    # -------------------------------------------------------------------------
    hx, hy, hw, hh = 3.42, 0.72, 12.78, 7.32
    draw_box(
        ax, hx, hy, hw, hh,
        facecolor=PANEL_BG, edgecolor=BOX_BORDER, lw=1.5, radius=0.16, zorder=1,
    )
    h_hdr_y = hy + hh - 0.50
    ax.plot([hx + 0.18, hx + hw - 0.18], [h_hdr_y, h_hdr_y], color=BOX_BORDER, lw=1.0, zorder=2)
    ax.text(
        hx + 0.22, hy + hh - 0.25,
        "Go Heap: Tree of *node Structs",
        color=TEXT_MAIN, fontsize=10.6, fontweight="bold", ha="left", va="center", zorder=3,
    )

    # Compact inline legend in Go Heap header (top-right)
    leg_y = hy + hh - 0.25
    _draw_badge(ax, 10.66, leg_y - 0.105, 0.44, 0.21, "DIR", TEXT_SOFT, fontsize=6.3, fill_mix=0.16, zorder=4)
    ax.text(11.18, leg_y, "Directory (Children map)", color=TEXT_SUB, fontsize=7.6, ha="left", va="center", zorder=4)
    _draw_badge(ax, 13.44, leg_y - 0.105, 0.50, 0.21, "LEAF", ACCENT_TEAL, fontsize=6.3, fill_mix=0.22, zorder=4)
    ax.text(14.02, leg_y, "Leaf (Value, Children: nil)", color=TEXT_SUB, fontsize=7.6, ha="left", va="center", zorder=4)

    # -------------------------------------------------------------------------
    # Row Vertical Centers (4 branches cleanly stacked with generous header clearance)
    # -------------------------------------------------------------------------
    ROW_Y = {
        "fleet":     6.36,
        "config":    5.08,
        "locksmith": 3.78,
        "services":  2.28,
    }

    # -------------------------------------------------------------------------
    # Column 2: Root *node (`dir "/"`) with explicit `Children map[string]*node`
    # -------------------------------------------------------------------------
    rx, rw = 3.64, 2.18
    ry_bot = 1.60
    ry_top = 7.46
    rh = ry_top - ry_bot
    draw_box(
        ax, rx, ry_bot, rw, rh,
        facecolor=blend_hex(BOX_BG, ACCENT_BLUE, 0.06),
        edgecolor=blend_hex(BOX_BORDER_HI, ACCENT_BLUE, 0.72),
        lw=1.75, radius=0.13, zorder=3,
    )
    _draw_badge(ax, rx + 0.13, ry_top - 0.33, 0.40, 0.21, "DIR", ACCENT_BLUE, fontsize=6.4, fill_mix=0.24, zorder=5)
    ax.text(
        rx + 0.60, ry_top - 0.225,
        'Root ("/")',
        color=TEXT_MAIN, fontsize=9.0, family="monospace", fontweight="bold",
        ha="left", va="center", zorder=5,
    )
    ax.plot([rx + 0.13, rx + rw - 0.13], [ry_top - 0.44, ry_top - 0.44], color=BOX_BORDER, lw=0.9, zorder=4)
    ax.text(
        rx + 0.15, ry_top - 0.62,
        "Children map[string]*node",
        color=TEXT_SUB, fontsize=6.6, family="monospace", ha="left", va="center", zorder=4,
    )

    # Connect store.Root -> Root *node card
    _draw_arrow(ax, (fx + fw + 0.05, rt_cy), (rx - 0.03, rt_cy), color=ACCENT_BLUE, lw=2.0, head_length=5.5, head_width=3.5, zorder=6)

    # Root Children map entries (aligned vertically with the 4 rows)
    root_entries = [
        ("fleet",     "_coreos.com", ACCENT_AMBER,  False),
        ("config",    "config",      ACCENT_VIOLET, False),
        ("locksmith", "coreos.com",  ACCENT_GREEN,  False),
        ("services",  "services",    ACCENT_TEAL,   True),
    ]
    slot_x = rx + 0.13
    slot_w = rw - 0.26
    slot_h = 0.44
    for rkey, seg, col, is_hi in root_entries:
        cy = ROW_Y[rkey]
        sy_slot = cy - slot_h / 2.0
        s_fc = blend_hex(BOX_INNER, col, 0.16 if is_hi else 0.07)
        s_ec = col if is_hi else blend_hex(BOX_BORDER, col, 0.55)
        draw_box(ax, slot_x, sy_slot, slot_w, slot_h, facecolor=s_fc, edgecolor=s_ec, lw=1.35 if is_hi else 1.0, radius=0.08, zorder=4)
        ax.text(
            slot_x + 0.10, cy,
            f'"{seg}"',
            color=TEXT_MAIN if is_hi else TEXT_SOFT,
            fontsize=7.7, family="monospace", fontweight="bold" if is_hi else "normal",
            ha="left", va="center", zorder=5,
        )
        ax.text(
            slot_x + slot_w - 0.18, cy,
            "*node",
            color=col if is_hi else TEXT_DIM,
            fontsize=6.4, family="monospace", ha="right", va="center", zorder=5,
        )
        _draw_port_dot(ax, rx + rw, cy, col, radius=0.050, zorder=8)

    # -------------------------------------------------------------------------
    # Columns 3, 4, 5 (Directory Nodes) and Column 6 (Leaf Nodes)
    # -------------------------------------------------------------------------
    c1_x, c1_w = 6.18, 1.96
    c2_x, c2_w = 8.48, 2.02
    c3_x, c3_w = 10.84, 1.88
    leaf_x, leaf_w = 13.06, 2.94
    dir_h = 0.84

    # --- Row 1: _coreos.com -> fleet -> machines -> ... (Amber) ---
    y1 = ROW_Y["fleet"]
    _draw_arrow(ax, (rx + rw + 0.05, y1), (c1_x - 0.03, y1), ACCENT_AMBER, lw=1.55)
    _draw_dir_node(ax, c1_x, y1, c1_w, dir_h, "_coreos.com", "fleet", ACCENT_AMBER)
    _draw_arrow(ax, (c1_x + c1_w + 0.05, y1), (c2_x - 0.03, y1), ACCENT_AMBER, lw=1.55)
    _draw_dir_node(ax, c2_x, y1, c2_w, dir_h, "fleet", "machines", ACCENT_AMBER)
    _draw_arrow(ax, (c2_x + c2_w + 0.05, y1), (c3_x - 0.03, y1), ACCENT_AMBER, lw=1.55)
    _draw_dir_node(ax, c3_x, y1, c3_w, dir_h, "machines", "worker-1", ACCENT_AMBER)
    _draw_arrow(ax, (c3_x + c3_w + 0.05, y1), (leaf_x - 0.03, y1), ACCENT_AMBER, lw=1.55, linestyle="--")

    # Truncated fleet subtree card
    fl_h = 0.84
    draw_box(
        ax, leaf_x, y1 - fl_h / 2.0, leaf_w, fl_h,
        facecolor=BOX_INNER, edgecolor=blend_hex(BOX_BORDER, ACCENT_AMBER, 0.55),
        lw=1.3, radius=0.12, linestyle="--", zorder=3,
    )
    ax.text(
        leaf_x + leaf_w / 2.0, y1 + 0.14,
        "worker-1 .. worker-3",
        color=ACCENT_AMBER, fontsize=8.2, family="monospace", fontweight="bold",
        ha="center", va="center", zorder=4,
    )
    ax.text(
        leaf_x + leaf_w / 2.0, y1 - 0.16,
        "+ lease/ & job/ subtrees (omitted)",
        color=TEXT_DIM, fontsize=7.1, style="italic",
        ha="center", va="center", zorder=4,
    )

    # --- Row 2: config -> web -> rate_limit (Violet) ---
    y2 = ROW_Y["config"]
    _draw_arrow(ax, (rx + rw + 0.05, y2), (c1_x - 0.03, y2), ACCENT_VIOLET, lw=1.55)
    _draw_dir_node(ax, c1_x, y2, c1_w, dir_h, "config", "web", ACCENT_VIOLET)
    _draw_arrow(ax, (c1_x + c1_w + 0.05, y2), (c2_x - 0.03, y2), ACCENT_VIOLET, lw=1.55)
    _draw_dir_node(ax, c2_x, y2, c2_w, dir_h, "web", "rate_limit", ACCENT_VIOLET)
    _draw_arrow(ax, (c2_x + c2_w + 0.05, y2), (leaf_x - 0.03, y2), ACCENT_VIOLET, lw=1.65)
    _draw_leaf_node(
        ax, leaf_x, y2, leaf_w, 0.98,
        name="rate_limit",
        value_str='"100rps"',
        mod_idx=3,
        color=ACCENT_VIOLET,
    )

    # --- Row 3: coreos.com -> updateengine -> rebootlock -> semaphore (Green) ---
    y3 = ROW_Y["locksmith"]
    _draw_arrow(ax, (rx + rw + 0.05, y3), (c1_x - 0.03, y3), ACCENT_GREEN, lw=1.55)
    _draw_dir_node(ax, c1_x, y3, c1_w, dir_h, "coreos.com", "updateengine", ACCENT_GREEN)
    _draw_arrow(ax, (c1_x + c1_w + 0.05, y3), (c2_x - 0.03, y3), ACCENT_GREEN, lw=1.55)
    _draw_dir_node(ax, c2_x, y3, c2_w, dir_h, "updateengine", "rebootlock", ACCENT_GREEN)
    _draw_arrow(ax, (c2_x + c2_w + 0.05, y3), (c3_x - 0.03, y3), ACCENT_GREEN, lw=1.55)
    _draw_dir_node(ax, c3_x, y3, c3_w, dir_h, "rebootlock", "semaphore", ACCENT_GREEN)
    _draw_arrow(ax, (c3_x + c3_w + 0.05, y3), (leaf_x - 0.03, y3), ACCENT_GREEN, lw=1.65)
    _draw_leaf_node(
        ax, leaf_x, y3, leaf_w, 0.98,
        name="semaphore",
        value_str='{"semaphore":1,...}',
        mod_idx=5,
        color=ACCENT_GREEN,
    )

    # --- Row 4: services -> web -> web@1 (Teal, highlighted lookup & TTL target!) ---
    y4 = ROW_Y["services"]
    _draw_arrow(ax, (rx + rw + 0.05, y4), (c1_x - 0.03, y4), ACCENT_TEAL, lw=2.0, head_length=5.5, head_width=3.5)
    _draw_dir_node(ax, c1_x, y4, c1_w, dir_h, "services", "web", ACCENT_TEAL, highlight=True)
    _draw_arrow(ax, (c1_x + c1_w + 0.05, y4), (c2_x - 0.03, y4), ACCENT_TEAL, lw=2.0, head_length=5.5, head_width=3.5)
    _draw_dir_node(ax, c2_x, y4, c2_w, dir_h, "web", "web@1", ACCENT_TEAL, highlight=True)
    _draw_arrow(ax, (c2_x + c2_w + 0.05, y4), (leaf_x - 0.03, y4), ACCENT_TEAL, lw=2.0, head_length=5.5, head_width=3.5)
    leaf4_h = 1.36
    _draw_leaf_node(
        ax, leaf_x, y4, leaf_w, leaf4_h,
        name="web@1",
        value_str='"10.0.1.1:8080"',
        mod_idx=4,
        color=ACCENT_TEAL,
        expire_str="t + 30s",
        highlight=True,
    )

    # -------------------------------------------------------------------------
    # Bottom Shared *node Pointer: store.ttlKeyHeap.array[0] -> web@1 leaf
    # -------------------------------------------------------------------------
    lane_y = 1.06
    target_x = leaf_x + leaf_w / 2.0
    target_y = y4 - leaf4_h / 2.0 - 0.03
    _draw_rounded_ortho_arrow(
        ax,
        p_start=(cell0_bot_x, arr_y - 0.05),
        lane_y=lane_y,
        p_end=(target_x, target_y),
        color=ACCENT_TEAL,
        r=0.20,
        lw=2.0,
        zorder=7,
    )

    # Label pill centered cleanly along the horizontal bottom pointer lane
    lbl_cx = 8.40
    lbl_w, lbl_h = 5.65, 0.34
    draw_box(
        ax, lbl_cx - lbl_w / 2.0, lane_y - lbl_h / 2.0, lbl_w, lbl_h,
        facecolor=BG_COLOR, edgecolor=blend_hex(BOX_BORDER, ACCENT_TEAL, 0.78),
        lw=1.2, radius=0.09, zorder=8,
    )
    ax.text(
        lbl_cx, lane_y,
        "ttlKeyHeap.array[0]  →  shared *node pointer (same struct in RAM)",
        color=ACCENT_TEAL, fontsize=7.5, family="monospace", fontweight="bold",
        ha="center", va="center", zorder=9,
    )

    # -------------------------------------------------------------------------
    # Footer Takeaway
    # -------------------------------------------------------------------------
    ax.text(
        8.25,
        0.34,
        'Reading /services/web/web@1: acquire worldLock.RLock(), then walk Root.Children["services"].Children["web"].Children["web@1"]',
        color=TEXT_SUB,
        fontsize=8.3,
        style="italic",
        ha="center",
        va="center",
    )

    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    return fig_to_rgb(fig)


def render(
    out_dir: Path,
    fps: int = 16,
    formats: Iterable[str] = ("png",),
    save_previews: bool = False,
    preview_dir: Optional[Path] = None,
) -> List[Path]:
    del fps, formats, save_previews, preview_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"[{NAME}] Rendering static diagram...")
    rgb = render_diagram(dpi=180)
    out_path = out_dir / f"{NAME}.png"
    Image.fromarray(rgb).save(out_path, optimize=True)
    size_kb = out_path.stat().st_size / 1024.0
    print(f"[{NAME}] Wrote {out_path} ({size_kb:.1f} KB)")
    return [out_path]


if __name__ == "__main__":
    default_out = Path(__file__).resolve().parent.parent
    render(default_out)
