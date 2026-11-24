#!/usr/bin/env python3
"""Unified CLI runner for Part 1 animations.

Usage examples:
    python -m animations.render --list
    python -m animations.render coreos_cluster_bootstrap
    python -m animations.render all --formats webp mp4
"""

import argparse
from pathlib import Path
import sys
from typing import Dict

from . import (
    coreos_cluster_bootstrap,
    event_history_ring_buffer,
    replicated_state_machine,
    ttl_key_heap,
)

# Register new Part 1 animations here as they are added:
ANIMATIONS: Dict[str, object] = {
    coreos_cluster_bootstrap.NAME: coreos_cluster_bootstrap,
    ttl_key_heap.NAME: ttl_key_heap,
    event_history_ring_buffer.NAME: event_history_ring_buffer,
    replicated_state_machine.NAME: replicated_state_machine,
}


def main() -> int:
    default_out = Path(__file__).resolve().parent.parent

    parser = argparse.ArgumentParser(description="Render Part 1 etcd blog animations.")
    parser.add_argument(
        "targets",
        nargs="*",
        default=["all"],
        help="Animation name(s) to render, or 'all' (default).",
    )
    parser.add_argument("--list", action="store_true", help="List available animations and exit.")
    parser.add_argument("--out-dir", type=Path, default=default_out, help="Output directory for rendered assets.")
    parser.add_argument("--fps", type=int, default=16, help="Frames per second (default: 16).")
    parser.add_argument(
        "--formats",
        nargs="+",
        default=["webp"],
        choices=["webp", "mp4", "gif"],
        help="Output formats (default: webp).",
    )
    parser.add_argument("--save-previews", action="store_true", help="Save PNG preview frames for each act.")
    parser.add_argument("--preview-dir", type=Path, default=None, help="Optional directory for preview PNGs.")
    args = parser.parse_args()

    if args.list:
        for name, mod in ANIMATIONS.items():
            print(f"  {name}: {mod.DESCRIPTION}")
        return 0

    selected = list(ANIMATIONS.keys()) if "all" in args.targets else args.targets
    for name in selected:
        if name not in ANIMATIONS:
            print(f"Unknown animation '{name}'. Available: {', '.join(ANIMATIONS.keys())}", file=sys.stderr)
            return 1

    for name in selected:
        ANIMATIONS[name].render(
            out_dir=args.out_dir,
            fps=args.fps,
            formats=args.formats,
            save_previews=args.save_previews,
            preview_dir=args.preview_dir,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
