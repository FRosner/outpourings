"""Shared theme, drawing primitives, easing functions, and export helpers for Part 1 animations."""

import os
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import matplotlib as mpl
mpl.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyBboxPatch
import numpy as np
from PIL import Image

mpl.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial", "Helvetica"]
mpl.rcParams["font.monospace"] = ["DejaVu Sans Mono", "Menlo", "Consolas"]

# Dark-slate palette consistent with tcp_buffers and the rest of the blog
BG_COLOR = "#0f172a"       # Deep slate canvas
PANEL_BG = "#111c33"       # Subtle dark panel fill
BOX_BG = "#1e293b"         # Card fill
BOX_INNER = "#0f172a"      # Recessed inner pill fill
BOX_BORDER = "#334155"     # Default subtle border
BOX_BORDER_HI = "#475569"  # Slightly brighter border

TEXT_MAIN = "#f8fafc"      # Primary crisp white
TEXT_SOFT = "#cbd5e1"      # Secondary readable light slate
TEXT_SUB = "#94a3b8"       # Muted subtitle slate
TEXT_DIM = "#64748b"       # Faint annotation slate

# Semantic accent colors
ACCENT_BLUE = "#38bdf8"    # Sky blue (etcd core / primary)
ACCENT_AMBER = "#f59e0b"   # Amber (fleetd scheduling / operator)
ACCENT_VIOLET = "#a78bfa"  # Soft violet (app config)
ACCENT_TEAL = "#2dd4bf"    # Teal (service discovery / web + nginx)
ACCENT_GREEN = "#10b981"   # Emerald (locksmithd / OS reboot lock)
ACCENT_CORAL = "#fb7185"   # Coral (alerts / eviction / errors in future animations)


def clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def ease_in_out(t: float) -> float:
    t = clamp(t)
    return t * t * (3.0 - 2.0 * t)


def ease_out(t: float) -> float:
    t = clamp(t)
    return 1.0 - (1.0 - t) ** 3


def progress(local_f: int, start: int, duration: int) -> float:
    if duration <= 0:
        return 1.0 if local_f >= start else 0.0
    return clamp((local_f - start) / float(duration))


def blend_hex(c1: str, c2: str, t: float) -> str:
    """Linearly interpolate between two #rrggbb hex colors."""
    t = clamp(t)
    r1, g1, b1 = int(c1[1:3], 16), int(c1[3:5], 16), int(c1[5:7], 16)
    r2, g2, b2 = int(c2[1:3], 16), int(c2[3:5], 16), int(c2[5:7], 16)
    r = int(round(r1 + (r2 - r1) * t))
    g = int(round(g1 + (g2 - g1) * t))
    b = int(round(b1 + (b2 - b1) * t))
    return f"#{r:02x}{g:02x}{b:02x}"


def draw_box(
    ax,
    x: float,
    y: float,
    w: float,
    h: float,
    facecolor: str = BOX_BG,
    edgecolor: str = BOX_BORDER,
    lw: float = 1.6,
    radius: float = 0.16,
    alpha: float = 1.0,
    linestyle: str = "-",
    zorder: int = 2,
):
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle=f"round,pad=0,rounding_size={radius}",
        facecolor=facecolor,
        edgecolor=edgecolor,
        linewidth=lw,
        linestyle=linestyle,
        alpha=alpha,
        zorder=zorder,
    )
    ax.add_patch(patch)
    return patch


def draw_pulse_dot(
    ax,
    p0: Tuple[float, float],
    p1: Tuple[float, float],
    t: float,
    color: str,
    radius: float = 0.11,
    zorder: int = 12,
):
    """Draw a glowing traveling packet dot along segment p0 -> p1 for t in [0, 1]."""
    if t <= 0.0 or t >= 1.0:
        return
    et = ease_in_out(t)
    x = p0[0] + (p1[0] - p0[0]) * et
    y = p0[1] + (p1[1] - p0[1]) * et
    # Fade softly at endpoints
    edge_fade = min(1.0, min(t, 1.0 - t) / 0.12)
    halo = Circle((x, y), radius * 1.9, facecolor=color, edgecolor="none", alpha=0.25 * edge_fade, zorder=zorder)
    core = Circle((x, y), radius, facecolor=color, edgecolor="#ffffff", linewidth=0.9, alpha=0.95 * edge_fade, zorder=zorder + 1)
    ax.add_patch(halo)
    ax.add_patch(core)


def fig_to_rgb(fig) -> np.ndarray:
    fig.canvas.draw()
    rgba = np.asarray(fig.canvas.buffer_rgba())
    rgb = rgba[:, :, :3].copy()
    plt.close(fig)
    return rgb


def export_animation(
    frames_rgb: Sequence[np.ndarray],
    out_dir: Path,
    stem: str,
    fps: int = 16,
    formats: Iterable[str] = ("webp",),
    preview_frames: Optional[List[Tuple[int, str]]] = None,
    preview_dir: Optional[Path] = None,
    final_hold_ms: int = 0,
) -> List[Path]:
    """Export rendered RGB frames to .webp (and optionally .mp4 / .gif) plus optional preview PNGs."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written: List[Path] = []
    pil_frames = [Image.fromarray(f) for f in frames_rgb]
    duration_ms = int(round(1000.0 / fps))

    if preview_frames:
        pdir = preview_dir if preview_dir is not None else out_dir
        pdir.mkdir(parents=True, exist_ok=True)
        for idx, label in preview_frames:
            safe_idx = min(max(0, idx), len(pil_frames) - 1)
            p_path = pdir / f"preview_{stem}_{label}.png"
            pil_frames[safe_idx].save(p_path)
            written.append(p_path)

    fmt_set = {f.lower() for f in formats}

    # Deduplicate consecutive identical frames for webp/gif using per-frame durations
    dedup_pil: List[Image.Image] = []
    dedup_durations: List[int] = []
    if "webp" in fmt_set or "gif" in fmt_set:
        prev_arr: Optional[np.ndarray] = None
        for arr, im in zip(frames_rgb, pil_frames):
            if prev_arr is not None and np.array_equal(arr, prev_arr):
                dedup_durations[-1] += duration_ms
            else:
                dedup_pil.append(im)
                dedup_durations.append(duration_ms)
                prev_arr = arr
        if final_hold_ms > 0 and dedup_durations:
            dedup_durations[-1] += final_hold_ms

    if "webp" in fmt_set:
        webp_path = out_dir / f"{stem}.webp"
        dedup_pil[0].save(
            webp_path,
            save_all=True,
            append_images=dedup_pil[1:],
            duration=dedup_durations,
            loop=0,
            quality=86,
            method=4,
        )
        written.append(webp_path)

    if "mp4" in fmt_set:
        import imageio

        mp4_path = out_dir / f"{stem}.mp4"
        writer = imageio.get_writer(
            str(mp4_path),
            fps=fps,
            codec="libx264",
            quality=8,
            pixelformat="yuv420p",
            macro_block_size=1,
        )
        for frame in frames_rgb:
            writer.append_data(frame)
        if final_hold_ms > 0 and frames_rgb:
            extra = int(round(final_hold_ms / 1000.0 * fps))
            for _ in range(extra):
                writer.append_data(frames_rgb[-1])
        writer.close()
        written.append(mp4_path)

    if "gif" in fmt_set:
        gif_path = out_dir / f"{stem}.gif"
        quantized = [im.quantize(colors=64, method=Image.Quantize.MEDIANCUT) for im in dedup_pil]
        quantized[0].save(
            gif_path,
            save_all=True,
            append_images=quantized[1:],
            duration=dedup_durations,
            loop=0,
            optimize=True,
        )
        written.append(gif_path)

    return written
