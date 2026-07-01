#!/usr/bin/env python3
"""Plot WebXR hand joint and viewer/head trajectories from JSONL logs."""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter


DEFAULT_JOINTS = [
    "wrist",
    "thumb-tip",
    "index-finger-tip",
    "middle-finger-tip",
    "ring-finger-tip",
    "pinky-finger-tip",
    "little-finger-tip",
]


def format_xyz(position: list[float] | None) -> str:
    if not position:
        return "missing"
    return f"x={position[0]: .3f}  y={position[1]: .3f}  z={position[2]: .3f}"


def format_ground_height(position: list[float] | None, display_coords: str) -> str:
    if not position:
        return "missing"
    if display_coords == "webxr":
        return f"ground=({position[0]: .3f}, {position[2]: .3f})  height={position[1]: .3f}"
    return f"ground=({position[0]: .3f}, {position[1]: .3f})  height={position[2]: .3f}"


def to_display_point(position: list[float], mode: str) -> list[float]:
    if mode == "webxr":
        return position
    return [position[0], position[2], position[1]]


def iter_frame_payloads(path: Path) -> Iterable[dict]:
    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            line = line.strip()
            if not line:
                continue

            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                print(f"skip line {line_number}: invalid JSON: {exc}")
                continue

            payload = record.get("payload", record)
            if payload.get("type") == "webxr_hand_frame":
                yield payload


def collect_tracks(path: Path, joint_names: set[str], max_frames: int | None, display_coords: str) -> tuple[dict, list]:
    joint_tracks: dict[tuple[str, str], list[tuple[int, list[float]]]] = defaultdict(list)
    viewer_track: list[tuple[int, list[float]]] = []

    for frame_count, payload in enumerate(iter_frame_payloads(path), start=1):
        if max_frames is not None and frame_count > max_frames:
            break

        frame_index = int(payload.get("frame_index", frame_count))

        viewer_pose = payload.get("viewer_pose") or {}
        viewer_position = viewer_pose.get("position")
        if viewer_pose.get("valid") and is_xyz(viewer_position):
            viewer_track.append((frame_index, to_display_point(viewer_position, display_coords)))

        for hand in payload.get("hands", []):
            handedness = hand.get("handedness", "none")
            for joint in hand.get("joints", []):
                name = joint.get("name")
                position = joint.get("position")
                if name in joint_names and is_xyz(position):
                    joint_tracks[(handedness, name)].append((frame_index, to_display_point(position, display_coords)))

    return joint_tracks, viewer_track


def collect_animation_frames(path: Path, joint_names: set[str], max_frames: int | None, display_coords: str) -> list[dict]:
    frames = []

    for frame_count, payload in enumerate(iter_frame_payloads(path), start=1):
        if max_frames is not None and frame_count > max_frames:
            break

        joints = {}
        for hand in payload.get("hands", []):
            handedness = hand.get("handedness", "none")
            for joint in hand.get("joints", []):
                name = joint.get("name")
                position = joint.get("position")
                if name in joint_names and is_xyz(position):
                    joints[(handedness, name)] = to_display_point(position, display_coords)

        viewer = None
        viewer_pose = payload.get("viewer_pose") or {}
        viewer_position = viewer_pose.get("position")
        if viewer_pose.get("valid") and is_xyz(viewer_position):
            viewer = to_display_point(viewer_position, display_coords)

        frames.append({
            "frame_index": int(payload.get("frame_index", frame_count)),
            "timestamp_ms": float(payload.get("client_time_ms", 0.0)),
            "joints": joints,
            "viewer": viewer,
        })

    return frames


def is_xyz(value: object) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 3
        and all(isinstance(item, (int, float)) for item in value)
    )


def set_axes_equal(ax) -> None:
    x_limits = ax.get_xlim3d()
    y_limits = ax.get_ylim3d()
    z_limits = ax.get_zlim3d()

    x_range = abs(x_limits[1] - x_limits[0])
    y_range = abs(y_limits[1] - y_limits[0])
    z_range = abs(z_limits[1] - z_limits[0])
    max_range = max(x_range, y_range, z_range)

    x_middle = sum(x_limits) / 2
    y_middle = sum(y_limits) / 2
    z_middle = sum(z_limits) / 2
    radius = max_range / 2

    ax.set_xlim3d(x_middle - radius, x_middle + radius)
    ax.set_ylim3d(y_middle - radius, y_middle + radius)
    ax.set_zlim3d(z_middle - radius, z_middle + radius)


def set_axes_from_points(ax, points: list[list[float]]) -> None:
    if not points:
        return

    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    zs = [point[2] for point in points]
    ax.set_xlim(min(xs), max(xs))
    ax.set_ylim(min(ys), max(ys))
    ax.set_zlim(min(zs), max(zs))
    set_axes_equal(ax)


def set_axis_labels(ax, display_coords: str) -> None:
    if display_coords == "webxr":
        ax.set_xlabel("WebXR X meters")
        ax.set_ylabel("WebXR Y height meters")
        ax.set_zlabel("WebXR Z meters")
    else:
        ax.set_xlabel("X meters")
        ax.set_ylabel("Y ground/depth meters")
        ax.set_zlabel("Z height meters")


def plot_tracks(joint_tracks: dict, viewer_track: list, args: argparse.Namespace) -> None:
    fig = plt.figure(figsize=(11, 8))
    ax = fig.add_subplot(111, projection="3d")

    if not args.viewer_only:
        for (handedness, joint_name), samples in sorted(joint_tracks.items()):
            if len(samples) < 1:
                continue
            xs = [position[0] for _, position in samples]
            ys = [position[1] for _, position in samples]
            zs = [position[2] for _, position in samples]
            ax.plot(xs, ys, zs, linewidth=1.2, label=f"{handedness}:{joint_name}")
            ax.scatter(xs[-1], ys[-1], zs[-1], s=20)

    if args.viewer and viewer_track:
        xs = [position[0] for _, position in viewer_track]
        ys = [position[1] for _, position in viewer_track]
        zs = [position[2] for _, position in viewer_track]
        ax.plot(xs, ys, zs, color="black", linewidth=2.0, label="viewer/head")
        ax.scatter(xs[0], ys[0], zs[0], color="green", s=35, label="viewer start")
        ax.scatter(xs[-1], ys[-1], zs[-1], color="red", s=35, label="viewer end")

    ax.set_title(args.title or f"WebXR trajectories: {args.input.name}")
    set_axis_labels(ax, args.display_coords)
    ax.grid(True)
    set_axes_equal(ax)
    ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1.0), borderaxespad=0)
    fig.tight_layout()

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(args.output, dpi=args.dpi, bbox_inches="tight")
        print(f"saved plot: {args.output}")

    if args.show or not args.output:
        plt.show()


def animate_tracks(frames: list[dict], args: argparse.Namespace) -> None:
    if not frames:
        raise SystemExit("no frames to animate")

    stride = args.stride
    if stride is None:
        stride = max(1, math.ceil(len(frames) / args.animation_max_frames))

    animation_indices = list(range(0, len(frames), stride))
    if animation_indices[-1] != len(frames) - 1:
        animation_indices.append(len(frames) - 1)

    all_points = []
    track_keys = set()
    for frame in frames:
        if args.viewer and frame["viewer"]:
            all_points.append(frame["viewer"])
        if not args.viewer_only:
            for key, position in frame["joints"].items():
                track_keys.add(key)
                all_points.append(position)

    if not all_points:
        raise SystemExit("no plottable positions found for animation")

    fig = plt.figure(figsize=(11, 8))
    ax = fig.add_subplot(111, projection="3d")
    set_axis_labels(ax, args.display_coords)
    ax.grid(True)
    set_axes_from_points(ax, all_points)

    joint_artists = {}
    for key in sorted(track_keys):
        line, = ax.plot([], [], [], linewidth=1.1, alpha=0.65, label=f"{key[0]}:{key[1]}")
        dot = ax.scatter([], [], [], s=28)
        joint_artists[key] = (line, dot)

    viewer_line = None
    viewer_dot = None
    if args.viewer:
        viewer_line, = ax.plot([], [], [], color="black", linewidth=2.0, label="viewer/head")
        viewer_dot = ax.scatter([], [], [], color="red", s=42)

    if joint_artists or args.viewer:
        ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1.0), borderaxespad=0)

    coordinate_text = None
    if args.coordinate_panel:
        coordinate_text = fig.text(
            0.74,
            0.52,
            "",
            ha="left",
            va="center",
            family="monospace",
            fontsize=8,
            bbox={
                "boxstyle": "round,pad=0.5",
                "facecolor": "white",
                "edgecolor": "0.75",
                "alpha": 0.92,
            },
        )
        fig.subplots_adjust(right=0.70)

    start_timestamp = frames[0]["timestamp_ms"]

    def set_line(line, positions: list[list[float]]) -> None:
        if positions:
            line.set_data([p[0] for p in positions], [p[1] for p in positions])
            line.set_3d_properties([p[2] for p in positions])
        else:
            line.set_data([], [])
            line.set_3d_properties([])

    def set_dot(dot, position: list[float] | None) -> None:
        if position:
            dot._offsets3d = ([position[0]], [position[1]], [position[2]])
        else:
            dot._offsets3d = ([], [], [])

    def positions_for_key(key, current_frame_index: int) -> list[list[float]]:
        start = max(0, current_frame_index - args.trail_frames + 1)
        return [
            frames[index]["joints"][key]
            for index in range(start, current_frame_index + 1)
            if key in frames[index]["joints"]
        ]

    def viewer_positions(current_frame_index: int) -> list[list[float]]:
        start = max(0, current_frame_index - args.trail_frames + 1)
        return [
            frames[index]["viewer"]
            for index in range(start, current_frame_index + 1)
            if frames[index]["viewer"]
        ]

    def update(animation_step: int):
        frame_index = animation_indices[animation_step]
        frame = frames[frame_index]
        elapsed_s = (frame["timestamp_ms"] - start_timestamp) / 1000.0
        ax.set_title(
            args.title
            or f"WebXR motion frame={frame['frame_index']} t={elapsed_s:.2f}s"
        )

        for key, (line, dot) in joint_artists.items():
            positions = positions_for_key(key, frame_index)
            set_line(line, positions)
            set_dot(dot, positions[-1] if positions else None)

        if args.viewer and viewer_line and viewer_dot:
            positions = viewer_positions(frame_index)
            set_line(viewer_line, positions)
            set_dot(viewer_dot, positions[-1] if positions else None)

        if coordinate_text:
            lines = [
                f"frame {frame['frame_index']}",
                f"t = {elapsed_s:.3f} s",
                "",
                "display axes:",
                "X = WebXR x" if args.display_coords == "everyday" else "X = WebXR x",
                "Y = WebXR z" if args.display_coords == "everyday" else "Y = WebXR y height",
                "Z = WebXR y height" if args.display_coords == "everyday" else "Z = WebXR z",
                "space = everyday" if args.display_coords == "everyday" else "space = raw WebXR",
                "",
            ]
            if args.viewer:
                lines.extend([
                    "viewer/head",
                    f"  {format_xyz(frame['viewer'])}",
                    f"  {format_ground_height(frame['viewer'], args.display_coords)}",
                    "",
                ])
            if not args.viewer_only:
                for key in sorted(track_keys):
                    position = frame["joints"].get(key)
                    if position is None:
                        continue
                    lines.extend([
                        f"{key[0]}:{key[1]}",
                        f"  {format_xyz(position)}",
                    ])
                if not any(frame["joints"].get(key) for key in track_keys):
                    lines.append("no selected joints")
            coordinate_text.set_text("\n".join(lines[:args.coordinate_lines]))

        artists = []
        for line, dot in joint_artists.values():
            artists.extend([line, dot])
        if viewer_line and viewer_dot:
            artists.extend([viewer_line, viewer_dot])
        if coordinate_text:
            artists.append(coordinate_text)
        return artists

    anim = FuncAnimation(
        fig,
        update,
        frames=len(animation_indices),
        interval=1000 / args.fps,
        blit=False,
    )

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        writer = PillowWriter(fps=args.fps)
        anim.save(args.output, writer=writer, dpi=args.dpi)
        print(f"saved animation: {args.output}")
        print(f"source frames={len(frames)} rendered frames={len(animation_indices)} stride={stride}")

    if args.show or not args.output:
        plt.show()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Input webxr_hand_*.jsonl file")
    parser.add_argument("--output", "-o", type=Path, help="Output image path, for example data/trajectory.png")
    parser.add_argument("--joint", action="append", dest="joints", help="Joint name to plot; can be repeated")
    parser.add_argument("--all-joints", action="store_true", help="Plot every joint found in the file")
    parser.add_argument("--viewer-only", action="store_true", help="Only plot viewer/head trajectory")
    parser.add_argument("--no-viewer", action="store_false", dest="viewer", help="Do not plot viewer/head trajectory")
    parser.add_argument("--animate", action="store_true", help="Export or show a timestamp animation")
    parser.add_argument("--fps", type=int, default=20, help="Animation playback FPS")
    parser.add_argument("--trail-frames", type=int, default=120, help="Number of source frames kept as motion trail")
    parser.add_argument("--stride", type=int, help="Use every Nth source frame for animation")
    parser.add_argument("--animation-max-frames", type=int, default=400, help="Auto-downsample animation to this many frames")
    parser.add_argument("--coordinate-panel", action=argparse.BooleanOptionalAction, default=True, help="Show current coordinates in animation")
    parser.add_argument("--coordinate-lines", type=int, default=34, help="Maximum coordinate panel text lines")
    parser.add_argument("--display-coords", choices=["everyday", "webxr"], default="everyday", help="Coordinate display convention")
    parser.add_argument("--max-frames", type=int, help="Read at most this many hand frames")
    parser.add_argument("--dpi", type=int, default=160, help="Output image DPI")
    parser.add_argument("--title", help="Plot title")
    parser.add_argument("--show", action="store_true", help="Open an interactive matplotlib window")
    parser.set_defaults(viewer=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.input.exists():
        raise SystemExit(f"input not found: {args.input}")

    joint_names = set(args.joints or DEFAULT_JOINTS)
    if args.all_joints:
        joint_names = {
            joint.get("name")
            for payload in iter_frame_payloads(args.input)
            for hand in payload.get("hands", [])
            for joint in hand.get("joints", [])
            if isinstance(joint.get("name"), str)
        }

    joint_tracks, viewer_track = collect_tracks(args.input, joint_names, args.max_frames, args.display_coords)
    if args.viewer_only:
        args.viewer = True

    if args.animate:
        frames = collect_animation_frames(args.input, joint_names, args.max_frames, args.display_coords)
        if args.viewer_only and not any(frame["viewer"] for frame in frames):
            raise SystemExit("no viewer_pose samples found; refresh the web page and collect a new log")
        animate_tracks(frames, args)
        return

    if args.viewer_only and not viewer_track:
        raise SystemExit("no viewer_pose samples found; refresh the web page and collect a new log")
    if not joint_tracks and not viewer_track:
        raise SystemExit("no plottable hand frames found; collect a new log with the updated web client")

    print(f"joint tracks: {len(joint_tracks)}")
    print(f"viewer samples: {len(viewer_track)}")
    plot_tracks(joint_tracks, viewer_track, args)


if __name__ == "__main__":
    main()
