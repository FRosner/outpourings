#!/usr/bin/env python3
"""
Simple, clean introductory animation showing TCP Send and Receive Buffers
as decoupling queues between applications and the network:
  Sender App -> Send Buffer (SO_SNDBUF) -> Network -> Receive Buffer (SO_RCVBUF) -> Receiver App

Outputs:
  - tcp_buffers_animation.mp4
  - tcp_buffers_animation.webp
  - tcp_buffers_animation.gif
"""

import argparse
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import imageio
import matplotlib as mpl
mpl.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import numpy as np
from PIL import Image

mpl.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial", "Helvetica"]

# Clean, minimal palette
BG_COLOR = "#0f172a"       # Dark slate background
BOX_BG = "#1e293b"         # Box fill
BOX_BORDER = "#475569"     # Box border
SLOT_EMPTY = "#0f172a"     # Empty buffer slot
SLOT_BORDER = "#334155"    # Empty slot outline
TEXT_MAIN = "#f8fafc"      # White-ish text
TEXT_SUB = "#94a3b8"       # Muted gray text
PACKET_COLOR = "#38bdf8"   # Bright sky blue for data chunks
PACKET_BORDER = "#bae6fd"  # Light sky border
ACCENT_SEND = "#f59e0b"    # Amber highlight when sender bursts
ACCENT_RECV = "#10b981"    # Emerald highlight when receiver reads


def draw_box(ax, x, y, w, h, facecolor, edgecolor="none", lw=1.8, radius=0.18, alpha=1.0, zorder=2):
    patch = FancyBboxPatch(
        (x, y), w, h,
        boxstyle=f"round,pad=0,rounding_size={radius}",
        facecolor=facecolor,
        edgecolor=edgecolor,
        linewidth=lw,
        alpha=alpha,
        zorder=zorder,
    )
    ax.add_patch(patch)
    return patch


def ease_in_out(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def build_timeline(num_frames: int = 140):
    """
    Creates a smooth, intuitive 3-act loop:
      Act 1 (frames 0..44):   Sender App writes a fast burst of 4 chunks into Send Buffer.
                              Send Buffer absorbs the burst so the app doesn't wait.
      Act 2 (frames 45..94):  Network steadily transfers chunks one-by-one from Send Buffer
                              to Receive Buffer (while Receiver App is busy).
      Act 3 (frames 95..139): Receiver App wakes up and drains the queued chunks from
                              Receive Buffer in a quick batch.
    """
    states = []

    for f in range(num_frames):
        snd_count = 0
        rcv_count = 0
        in_flight = None       # float in [0, 1] when a packet is crossing the network
        entering_snd = None    # float in [0, 1] when a chunk moves from Sender App -> Send Buffer
        leaving_rcv = None     # float in [0, 1] when a chunk moves from Receive Buffer -> Receiver App
        caption = ""
        sender_active = False
        receiver_active = False

        if f < 40:
            # Act 1: 4 chunks burst rapidly from Sender App into Send Buffer (10 frames each)
            caption = "1. Sender App writes a fast burst — Send Buffer absorbs it immediately"
            sender_active = True
            chunk_idx = f // 10
            sub_t = (f % 10) / 10.0
            snd_count = chunk_idx
            if sub_t < 0.75:
                entering_snd = ease_in_out(sub_t / 0.75)
            else:
                snd_count = chunk_idx + 1

        elif f < 100:
            # Act 2: 4 chunks travel steadily across the network (15 frames each)
            caption = "2. Network transmits at link speed — Receive Buffer holds data while Receiver is busy"
            step = f - 40
            pkt_idx = step // 15
            sub_t = (step % 15) / 15.0
            snd_count = max(0, 4 - pkt_idx - 1)
            rcv_count = pkt_idx
            if sub_t < 0.85:
                in_flight = ease_in_out(sub_t / 0.85)
            else:
                rcv_count = pkt_idx + 1

        else:
            # Act 3: Receiver App reads the 4 chunks out of Receive Buffer (10 frames each)
            caption = "3. Receiver App reads buffered chunks at its own pace"
            receiver_active = True
            step = f - 100
            read_idx = step // 10
            sub_t = (step % 10) / 10.0
            snd_count = 0
            rcv_count = max(0, 4 - read_idx - (1 if sub_t > 0.2 else 0))
            if sub_t < 0.75:
                leaving_rcv = ease_in_out(sub_t / 0.75)

        states.append({
            "snd_count": snd_count,
            "rcv_count": rcv_count,
            "in_flight": in_flight,
            "entering_snd": entering_snd,
            "leaving_rcv": leaving_rcv,
            "caption": caption,
            "sender_active": sender_active,
            "receiver_active": receiver_active,
        })

    return states


def render_frame(st, dpi=120):
    fig, ax = plt.subplots(figsize=(11, 4.6), dpi=dpi)
    fig.patch.set_facecolor(BG_COLOR)
    ax.set_facecolor(BG_COLOR)
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 5.8)
    ax.axis("off")

    # Title & Single Subtitle Caption
    ax.text(7.0, 5.25, "Why TCP Needs Send & Receive Buffers",
            color=TEXT_MAIN, fontsize=15, fontweight="bold", ha="center", va="center")
    ax.text(7.0, 4.65, st["caption"],
            color=PACKET_COLOR, fontsize=11.5, fontweight="bold", ha="center", va="center")

    # Coordinates for the 4 main stations:
    # [Sender App] ---> [Send Buffer] =====Network=====> [Receive Buffer] ---> [Receiver App]
    y_center = 2.45

    # 1. Sender App (Left)
    s_app_x, s_app_y, s_app_w, s_app_h = 0.5, y_center - 0.85, 2.0, 1.7
    s_border = ACCENT_SEND if st["sender_active"] else BOX_BORDER
    draw_box(ax, s_app_x, s_app_y, s_app_w, s_app_h, facecolor=BOX_BG, edgecolor=s_border, lw=2.2)
    ax.text(s_app_x + s_app_w / 2, y_center + 0.22, "Sender App",
            color=TEXT_MAIN, fontsize=11.5, fontweight="bold", ha="center", va="center")
    ax.text(s_app_x + s_app_w / 2, y_center - 0.28,
            "send() burst!" if st["sender_active"] else "idle",
            color=ACCENT_SEND if st["sender_active"] else TEXT_SUB,
            fontsize=9.5, family="monospace", fontweight="bold", ha="center", va="center")

    # Arrow: Sender App -> Send Buffer
    ax.annotate("", xy=(3.25, y_center), xytext=(2.6, y_center),
                arrowprops=dict(arrowstyle="->", color=TEXT_SUB, lw=2.0))

    # 2. Send Buffer (SO_SNDBUF)
    snd_x, snd_y, snd_w, snd_h = 3.35, y_center - 1.05, 2.55, 2.1
    draw_box(ax, snd_x, snd_y, snd_w, snd_h, facecolor=BOX_BG, edgecolor=BOX_BORDER, lw=2.0)
    ax.text(snd_x + snd_w / 2, snd_y + snd_h + 0.35, "Send Buffer",
            color=TEXT_MAIN, fontsize=11.5, fontweight="bold", ha="center", va="center")
    ax.text(snd_x + snd_w / 2, snd_y - 0.35, "SO_SNDBUF",
            color=TEXT_SUB, fontsize=9.5, family="monospace", ha="center", va="center")

    # 4 vertical slots inside Send Buffer (filled right-to-left so head is closest to network)
    slot_w, slot_h, gap = 0.48, 1.35, 0.08
    snd_slots_x0 = snd_x + 0.20
    slot_y = y_center - slot_h / 2
    for i in range(4):
        sx = snd_slots_x0 + i * (slot_w + gap)
        rev_idx = 3 - i  # 0 is rightmost slot
        filled = rev_idx < st["snd_count"]
        draw_box(
            ax, sx, slot_y, slot_w, slot_h,
            facecolor=PACKET_COLOR if filled else SLOT_EMPTY,
            edgecolor=PACKET_BORDER if filled else SLOT_BORDER,
            lw=1.5, radius=0.08, zorder=4 if filled else 3,
        )

    # 3. Network Pipe (Center)
    net_x1, net_x2 = 6.05, 7.95
    ax.plot([net_x1, net_x2], [y_center + 0.32, y_center + 0.32], color=BOX_BORDER, lw=2.0, ls="--")
    ax.plot([net_x1, net_x2], [y_center - 0.32, y_center - 0.32], color=BOX_BORDER, lw=2.0, ls="--")
    ax.annotate("", xy=(net_x2, y_center), xytext=(net_x1, y_center),
                arrowprops=dict(arrowstyle="->", color="#475569", lw=1.8))
    ax.text((net_x1 + net_x2) / 2, y_center + 0.65, "Network",
            color=TEXT_SUB, fontsize=10.5, fontweight="bold", ha="center", va="center")

    # 4. Receive Buffer (SO_RCVBUF)
    rcv_x, rcv_y, rcv_w, rcv_h = 8.10, y_center - 1.05, 2.55, 2.1
    draw_box(ax, rcv_x, rcv_y, rcv_w, rcv_h, facecolor=BOX_BG, edgecolor=BOX_BORDER, lw=2.0)
    ax.text(rcv_x + rcv_w / 2, rcv_y + rcv_h + 0.35, "Receive Buffer",
            color=TEXT_MAIN, fontsize=11.5, fontweight="bold", ha="center", va="center")
    ax.text(rcv_x + rcv_w / 2, rcv_y - 0.35, "SO_RCVBUF",
            color=TEXT_SUB, fontsize=9.5, family="monospace", ha="center", va="center")

    # 4 vertical slots inside Receive Buffer (filled right-to-left so head is closest to Receiver App)
    rcv_slots_x0 = rcv_x + 0.20
    for i in range(4):
        sx = rcv_slots_x0 + i * (slot_w + gap)
        rev_idx = 3 - i  # 0 is rightmost slot
        filled = rev_idx < st["rcv_count"]
        draw_box(
            ax, sx, slot_y, slot_w, slot_h,
            facecolor=PACKET_COLOR if filled else SLOT_EMPTY,
            edgecolor=PACKET_BORDER if filled else SLOT_BORDER,
            lw=1.5, radius=0.08, zorder=4 if filled else 3,
        )

    # Arrow: Receive Buffer -> Receiver App
    ax.annotate("", xy=(11.4, y_center), xytext=(10.75, y_center),
                arrowprops=dict(arrowstyle="->", color=TEXT_SUB, lw=2.0))

    # 5. Receiver App (Right)
    r_app_x, r_app_y, r_app_w, r_app_h = 11.5, y_center - 0.85, 2.0, 1.7
    r_border = ACCENT_RECV if st["receiver_active"] else BOX_BORDER
    draw_box(ax, r_app_x, r_app_y, r_app_w, r_app_h, facecolor=BOX_BG, edgecolor=r_border, lw=2.2)
    ax.text(r_app_x + r_app_w / 2, y_center + 0.22, "Receiver App",
            color=TEXT_MAIN, fontsize=11.5, fontweight="bold", ha="center", va="center")
    ax.text(r_app_x + r_app_w / 2, y_center - 0.28,
            "recv() reading!" if st["receiver_active"] else "busy...",
            color=ACCENT_RECV if st["receiver_active"] else TEXT_SUB,
            fontsize=9.5, family="monospace", fontweight="bold", ha="center", va="center")

    # -------------------------------------------------------------------------
    # Moving Chunks (Animated smooth transitions)
    # -------------------------------------------------------------------------
    # A) Chunk moving from Sender App into Send Buffer
    if st["entering_snd"] is not None:
        target_slot_i = 3 - st["snd_count"]
        target_x = snd_slots_x0 + target_slot_i * (slot_w + gap)
        start_x = s_app_x + s_app_w - 0.3
        cur_x = start_x + st["entering_snd"] * (target_x - start_x)
        draw_box(ax, cur_x, slot_y, slot_w, slot_h,
                 facecolor=PACKET_COLOR, edgecolor=PACKET_BORDER, lw=1.8, radius=0.08, zorder=8)

    # B) Chunk flying across the Network from Send Buffer to Receive Buffer
    if st["in_flight"] is not None:
        start_x = snd_slots_x0 + 3 * (slot_w + gap)
        target_slot_i = 3 - st["rcv_count"]
        target_x = rcv_slots_x0 + target_slot_i * (slot_w + gap)
        cur_x = start_x + st["in_flight"] * (target_x - start_x)
        # Slightly smaller height while in network pipe, expanding as it lands
        scale_h = 0.55 + 0.45 * abs(2.0 * st["in_flight"] - 1.0)
        cur_h = slot_h * scale_h
        draw_box(ax, cur_x, y_center - cur_h / 2, slot_w, cur_h,
                 facecolor=PACKET_COLOR, edgecolor=PACKET_BORDER, lw=1.8, radius=0.08, zorder=8)

    # C) Chunk moving from Receive Buffer into Receiver App
    if st["leaving_rcv"] is not None:
        start_x = rcv_slots_x0 + 3 * (slot_w + gap)
        target_x = r_app_x + 0.2
        cur_x = start_x + st["leaving_rcv"] * (target_x - start_x)
        alpha = 1.0 - 0.5 * st["leaving_rcv"]
        draw_box(ax, cur_x, slot_y, slot_w, slot_h,
                 facecolor=PACKET_COLOR, edgecolor=PACKET_BORDER, lw=1.8, radius=0.08, alpha=alpha, zorder=8)

    # Bottom summary line
    ax.text(7.0, 0.45,
            "Buffers decouple application speed from network speed — absorbing write bursts and read delays.",
            color=TEXT_SUB, fontsize=10, ha="center", va="center")

    fig.tight_layout(pad=0)
    fig.canvas.draw()
    rgba = np.asarray(fig.canvas.buffer_rgba())
    rgb = rgba[:, :, :3].copy()
    plt.close(fig)
    return rgb


def generate_animations(out_dir: Path, fps: int = 20, save_previews: bool = False):
    states = build_timeline(140)
    total = len(states)
    print(f"Rendering {total} frames at {fps} FPS...")

    frames_rgb = [render_frame(st) for st in states]

    if save_previews:
        for idx, name in [(15, "act1"), (62, "act2"), (112, "act3")]:
            Image.fromarray(frames_rgb[idx]).save(out_dir / f"preview_{name}.png")

    mp4_path = out_dir / "tcp_buffers_animation.mp4"
    writer = imageio.get_writer(
        str(mp4_path),
        fps=fps,
        codec="libx264",
        quality=8,
        pixelformat="yuv420p",
        macro_block_size=1,
    )
    for f in frames_rgb:
        writer.append_data(f)
    writer.close()

    webp_path = out_dir / "tcp_buffers_animation.webp"
    pil_frames = [Image.fromarray(f) for f in frames_rgb]
    duration_ms = int(1000 / fps)
    pil_frames[0].save(
        webp_path,
        save_all=True,
        append_images=pil_frames[1:],
        duration=duration_ms,
        loop=0,
        quality=85,
        method=4,
    )

    gif_path = out_dir / "tcp_buffers_animation.gif"
    quantized = [im.quantize(colors=64, method=Image.Quantize.MEDIANCUT) for im in pil_frames]
    quantized[0].save(
        gif_path,
        save_all=True,
        append_images=quantized[1:],
        duration=duration_ms,
        loop=0,
        optimize=True,
    )
    print("Done!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate simple TCP Buffers intro animation.")
    parser.add_argument("--out-dir", type=Path, default=Path(__file__).parent)
    parser.add_argument("--fps", type=int, default=20)
    parser.add_argument("--save-previews", action="store_true")
    args = parser.parse_args()
    generate_animations(args.out_dir, fps=args.fps, save_previews=args.save_previews)
