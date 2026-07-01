#!/usr/bin/env python3
"""Live/playback 3D viewer for WebXR viewer pose and hand skeletons."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Iterable

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter


HAND_BONES = [
    ("wrist", "thumb-metacarpal"),
    ("thumb-metacarpal", "thumb-phalanx-proximal"),
    ("thumb-phalanx-proximal", "thumb-phalanx-distal"),
    ("thumb-phalanx-distal", "thumb-tip"),
    ("wrist", "index-finger-metacarpal"),
    ("index-finger-metacarpal", "index-finger-phalanx-proximal"),
    ("index-finger-phalanx-proximal", "index-finger-phalanx-intermediate"),
    ("index-finger-phalanx-intermediate", "index-finger-phalanx-distal"),
    ("index-finger-phalanx-distal", "index-finger-tip"),
    ("wrist", "middle-finger-metacarpal"),
    ("middle-finger-metacarpal", "middle-finger-phalanx-proximal"),
    ("middle-finger-phalanx-proximal", "middle-finger-phalanx-intermediate"),
    ("middle-finger-phalanx-intermediate", "middle-finger-phalanx-distal"),
    ("middle-finger-phalanx-distal", "middle-finger-tip"),
    ("wrist", "ring-finger-metacarpal"),
    ("ring-finger-metacarpal", "ring-finger-phalanx-proximal"),
    ("ring-finger-phalanx-proximal", "ring-finger-phalanx-intermediate"),
    ("ring-finger-phalanx-intermediate", "ring-finger-phalanx-distal"),
    ("ring-finger-phalanx-distal", "ring-finger-tip"),
    ("wrist", "pinky-finger-metacarpal"),
    ("pinky-finger-metacarpal", "pinky-finger-phalanx-proximal"),
    ("pinky-finger-phalanx-proximal", "pinky-finger-phalanx-intermediate"),
    ("pinky-finger-phalanx-intermediate", "pinky-finger-phalanx-distal"),
    ("pinky-finger-phalanx-distal", "pinky-finger-tip"),
    ("wrist", "little-finger-metacarpal"),
    ("little-finger-metacarpal", "little-finger-phalanx-proximal"),
    ("little-finger-phalanx-proximal", "little-finger-phalanx-intermediate"),
    ("little-finger-phalanx-intermediate", "little-finger-phalanx-distal"),
    ("little-finger-phalanx-distal", "little-finger-tip"),
]


PANEL_JOINTS = [
    ("left", "wrist"),
    ("left", "index-finger-tip"),
    ("left", "thumb-tip"),
    ("right", "wrist"),
    ("right", "index-finger-tip"),
    ("right", "thumb-tip"),
]


def iter_frame_payloads(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            payload = parse_jsonl_line(line, line_number)
            if payload:
                yield payload


def parse_jsonl_line(line: str, line_number: int | None = None) -> dict[str, Any] | None:
    line = line.strip()
    if not line:
        return None

    try:
        record = json.loads(line)
    except json.JSONDecodeError as exc:
        label = f"line {line_number}: " if line_number is not None else ""
        print(f"skip {label}invalid JSON: {exc}")
        return None

    payload = record.get("payload", record)
    if payload.get("type") != "webxr_hand_frame":
        return None
    return payload


def find_latest_jsonl(data_dir: Path) -> Path:
    files = sorted(data_dir.glob("webxr_hand_*.jsonl"), key=lambda path: path.stat().st_mtime)
    if not files:
        raise SystemExit(f"no webxr_hand_*.jsonl files found in {data_dir}")
    return files[-1]


def is_xyz(value: object) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 3
        and all(isinstance(item, (int, float)) for item in value)
    )


def format_xyz(position: list[float] | None) -> str:
    if not position:
        return "missing"
    return f"x={position[0]: .3f} y={position[1]: .3f} z={position[2]: .3f}"


def to_display_point(position: list[float], mode: str) -> list[float]:
    if mode == "webxr":
        return position
    return [position[0], position[2], position[1]]


def to_display_points(points: dict[tuple[str, str], list[float]], mode: str) -> dict[tuple[str, str], list[float]]:
    return {key: to_display_point(position, mode) for key, position in points.items()}


def to_display_pose(pose: dict[str, Any], mode: str) -> dict[str, Any]:
    if not pose:
        return {}
    converted = dict(pose)
    converted["position"] = to_display_point(pose["position"], mode)
    return converted


def hand_joint_map(payload: dict[str, Any]) -> dict[tuple[str, str], list[float]]:
    points = {}
    for hand in payload.get("hands", []):
        handedness = hand.get("handedness", "none")
        for joint in hand.get("joints", []):
            name = joint.get("name")
            position = joint.get("position")
            if isinstance(name, str) and is_xyz(position):
                points[(handedness, name)] = position
    return points


def viewer_pose(payload: dict[str, Any]) -> dict[str, Any]:
    pose = payload.get("viewer_pose") or {}
    if pose.get("valid") and is_xyz(pose.get("position")):
        return pose
    return {}


def basis_from_viewer_pose(pose: dict[str, Any]) -> tuple[list[float], list[float], list[float], list[float]] | None:
    position = pose.get("position")
    if not is_xyz(position):
        return None

    matrix = pose.get("matrix")
    if isinstance(matrix, list) and len(matrix) == 16:
        right = normalize([matrix[0], matrix[1], matrix[2]])
        up = normalize([matrix[4], matrix[5], matrix[6]])
        forward = normalize([-matrix[8], -matrix[9], -matrix[10]])
        return position, right, up, forward

    orientation = pose.get("orientation")
    if isinstance(orientation, list) and len(orientation) == 4:
        right = rotate_vector_by_quat([1, 0, 0], orientation)
        up = rotate_vector_by_quat([0, 1, 0], orientation)
        forward = rotate_vector_by_quat([0, 0, -1], orientation)
        return position, normalize(right), normalize(up), normalize(forward)

    return position, [1, 0, 0], [0, 1, 0], [0, 0, -1]


def basis_to_display(
    basis: tuple[list[float], list[float], list[float], list[float]],
    mode: str,
) -> tuple[list[float], list[float], list[float], list[float]]:
    if mode == "webxr":
        return basis
    position, right, up, forward = basis
    return (
        to_display_point(position, mode),
        to_display_point(right, mode),
        to_display_point(up, mode),
        to_display_point(forward, mode),
    )


def normalize(vector: list[float]) -> list[float]:
    length = sum(component * component for component in vector) ** 0.5
    if length == 0:
        return [0, 0, 0]
    return [component / length for component in vector]


def rotate_vector_by_quat(vector: list[float], quat: list[float]) -> list[float]:
    x, y, z, w = quat
    vx, vy, vz = vector
    tx = 2 * (y * vz - z * vy)
    ty = 2 * (z * vx - x * vz)
    tz = 2 * (x * vy - y * vx)
    return [
        vx + w * tx + (y * tz - z * ty),
        vy + w * ty + (z * tx - x * tz),
        vz + w * tz + (x * ty - y * tx),
    ]


def add(a: list[float], b: list[float]) -> list[float]:
    return [a[0] + b[0], a[1] + b[1], a[2] + b[2]]


def scale(vector: list[float], factor: float) -> list[float]:
    return [vector[0] * factor, vector[1] * factor, vector[2] * factor]


class JsonlTail:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.file = path.open("r", encoding="utf-8")
        self.file.seek(0, 2)

    def read_latest(self) -> dict[str, Any] | None:
        latest = None
        while True:
            line = self.file.readline()
            if not line:
                break
            payload = parse_jsonl_line(line)
            if payload:
                latest = payload
        return latest


class SkeletonViewer:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.fig = plt.figure(figsize=(12, 8))
        self.ax = self.fig.add_subplot(111, projection="3d")
        self.set_axis_labels()
        self.ax.grid(True)
        self.ax.view_init(elev=args.elev, azim=args.azim)
        self.artists = []
        self.last_payload = None
        self.start_timestamp = None
        self.paused = False
        self.animation = None
        self.coordinate_text = self.fig.text(
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
        self.fig.subplots_adjust(right=0.70)
        self.fig.canvas.mpl_connect("key_press_event", self.on_key_press)

    def set_axis_labels(self) -> None:
        if self.args.display_coords == "webxr":
            self.ax.set_xlabel("WebXR X meters")
            self.ax.set_ylabel("WebXR Y height meters")
            self.ax.set_zlabel("WebXR Z meters")
        else:
            self.ax.set_xlabel("X meters")
            self.ax.set_ylabel("Y ground/depth meters")
            self.ax.set_zlabel("Z height meters")

    def on_key_press(self, event: Any) -> None:
        if event.key == " ":
            self.paused = not self.paused
            if self.animation:
                if self.paused:
                    self.animation.event_source.stop()
                else:
                    self.animation.event_source.start()
            state = "paused" if self.paused else "running"
            print(f"viewer {state}")

    def draw_payload(self, payload: dict[str, Any]) -> None:
        self.last_payload = payload
        if self.start_timestamp is None:
            self.start_timestamp = float(payload.get("client_time_ms", 0.0))

        self.clear_artists()
        raw_hand_points = hand_joint_map(payload)
        raw_pose = viewer_pose(payload)
        hand_points = to_display_points(raw_hand_points, self.args.display_coords)
        pose = to_display_pose(raw_pose, self.args.display_coords)
        all_points = list(hand_points.values())
        if pose:
            all_points.append(pose["position"])

        self.update_axes(all_points)
        self.draw_hands(hand_points)
        self.draw_viewer(raw_pose)
        self.update_panel(payload, hand_points, pose)
        self.fig.canvas.draw_idle()

    def clear_artists(self) -> None:
        for artist in self.artists:
            artist.remove()
        self.artists = []

    def update_axes(self, points: list[list[float]]) -> None:
        if self.args.fixed_range:
            center = [0, self.args.fixed_height_center, 0]
            if self.args.display_coords == "everyday":
                center = [0, 0, self.args.fixed_height_center]
            radius = self.args.fixed_range / 2
        elif points:
            xs = [point[0] for point in points]
            ys = [point[1] for point in points]
            zs = [point[2] for point in points]
            center = [
                (min(xs) + max(xs)) / 2,
                (min(ys) + max(ys)) / 2,
                (min(zs) + max(zs)) / 2,
            ]
            span = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs), 0.5)
            radius = max(span / 2, 0.35) * 1.25
        else:
            center = [0, 1.4, 0] if self.args.display_coords == "webxr" else [0, 0, 1.4]
            radius = 1.0

        self.ax.set_xlim(center[0] - radius, center[0] + radius)
        self.ax.set_ylim(center[1] - radius, center[1] + radius)
        self.ax.set_zlim(center[2] - radius, center[2] + radius)

    def draw_hands(self, points: dict[tuple[str, str], list[float]]) -> None:
        colors = {"left": "#2f80ed", "right": "#f2994a", "none": "#9b51e0"}
        for handedness in sorted({hand for hand, _ in points}):
            color = colors.get(handedness, "#9b51e0")
            hand_positions = [position for (hand, _), position in points.items() if hand == handedness]
            if hand_positions:
                artist = self.ax.scatter(
                    [p[0] for p in hand_positions],
                    [p[1] for p in hand_positions],
                    [p[2] for p in hand_positions],
                    s=self.args.joint_size,
                    color=color,
                    depthshade=True,
                    label=f"{handedness} joints",
                )
                self.artists.append(artist)

            for start, end in HAND_BONES:
                a = points.get((handedness, start))
                b = points.get((handedness, end))
                if not a or not b:
                    continue
                line, = self.ax.plot(
                    [a[0], b[0]],
                    [a[1], b[1]],
                    [a[2], b[2]],
                    color=color,
                    linewidth=2,
                    alpha=0.9,
                )
                self.artists.append(line)

    def draw_viewer(self, pose: dict[str, Any]) -> None:
        basis = basis_from_viewer_pose(pose)
        if not basis:
            return

        basis = basis_to_display(basis, self.args.display_coords)
        position, right, up, forward = basis
        size = self.args.viewer_size
        center = add(position, scale(forward, size))
        half_width = size * 0.45
        half_height = size * 0.30
        corners = [
            add(add(center, scale(right, half_width)), scale(up, half_height)),
            add(add(center, scale(right, -half_width)), scale(up, half_height)),
            add(add(center, scale(right, -half_width)), scale(up, -half_height)),
            add(add(center, scale(right, half_width)), scale(up, -half_height)),
        ]

        viewer_dot = self.ax.scatter([position[0]], [position[1]], [position[2]], color="black", s=48, label="viewer")
        self.artists.append(viewer_dot)

        for corner in corners:
            line, = self.ax.plot(
                [position[0], corner[0]],
                [position[1], corner[1]],
                [position[2], corner[2]],
                color="black",
                linewidth=1.5,
            )
            self.artists.append(line)

        loop = corners + [corners[0]]
        base, = self.ax.plot(
            [p[0] for p in loop],
            [p[1] for p in loop],
            [p[2] for p in loop],
            color="black",
            linewidth=1.5,
        )
        self.artists.append(base)

        forward_end = add(position, scale(forward, size * 1.45))
        arrow, = self.ax.plot(
            [position[0], forward_end[0]],
            [position[1], forward_end[1]],
            [position[2], forward_end[2]],
            color="red",
            linewidth=2.2,
        )
        self.artists.append(arrow)

    def update_panel(
        self,
        payload: dict[str, Any],
        points: dict[tuple[str, str], list[float]],
        pose: dict[str, Any],
    ) -> None:
        timestamp = float(payload.get("client_time_ms", 0.0))
        elapsed = 0.0 if self.start_timestamp is None else (timestamp - self.start_timestamp) / 1000.0
        lines = [
            f"frame {payload.get('frame_index')}",
            f"t = {elapsed:.3f} s",
            f"mode = {payload.get('session_mode')}",
            "",
            "display axes:",
            "X = WebXR x" if self.args.display_coords == "everyday" else "X = WebXR x",
            "Y = WebXR z" if self.args.display_coords == "everyday" else "Y = WebXR y height",
            "Z = WebXR y height" if self.args.display_coords == "everyday" else "Z = WebXR z",
            "space = everyday" if self.args.display_coords == "everyday" else "space = raw WebXR",
            "press Space to pause",
            "",
            "viewer/head",
            f"  {format_xyz(pose.get('position')) if pose else 'missing'}",
            "",
        ]

        for key in PANEL_JOINTS:
            position = points.get(key)
            if not position:
                continue
            lines.extend([
                f"{key[0]}:{key[1]}",
                f"  {format_xyz(position)}",
            ])

        self.coordinate_text.set_text("\n".join(lines[: self.args.coordinate_lines]))


def load_playback_frames(path: Path, max_frames: int | None, stride: int) -> list[dict[str, Any]]:
    frames = []
    for index, payload in enumerate(iter_frame_payloads(path)):
        if max_frames is not None and len(frames) >= max_frames:
            break
        if index % stride == 0:
            frames.append(payload)
    return frames


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", type=Path, help="JSONL file for playback or live tail")
    parser.add_argument("--latest", action="store_true", help="Use latest data/webxr_hand_*.jsonl file")
    parser.add_argument("--live", action="store_true", help="Tail the JSONL file as it is being written")
    parser.add_argument("--data-dir", type=Path, default=Path("data"), help="Directory for --latest")
    parser.add_argument("--interval-ms", type=int, default=5, help="Live/playback update interval")
    parser.add_argument("--max-frames", type=int, help="Playback maximum source frames")
    parser.add_argument("--stride", type=int, default=5, help="Playback stride")
    parser.add_argument("--save-gif", type=Path, help="Save playback to GIF instead of opening an interactive window")
    parser.add_argument("--gif-fps", type=int, default=60, help="Saved GIF FPS")
    parser.add_argument("--fixed-range", type=float, default=2.0, help="Fixed axis cube size in meters")
    parser.add_argument("--fixed-height-center", type=float, default=1.2, help="Y center for fixed axis range")
    parser.add_argument("--viewer-size", type=float, default=0.18, help="Viewer frustum size in meters")
    parser.add_argument("--joint-size", type=float, default=9, help="Joint marker size")
    parser.add_argument("--coordinate-lines", type=int, default=30, help="Max coordinate panel lines")
    parser.add_argument("--display-coords", choices=["everyday", "webxr"], default="everyday", help="Coordinate display convention")
    parser.add_argument("--elev", type=float, default=22, help="Initial 3D view elevation")
    parser.add_argument("--azim", type=float, default=-60, help="Initial 3D view azimuth")
    return parser.parse_args()


def resolve_input(args: argparse.Namespace) -> Path:
    if args.latest:
        return find_latest_jsonl(args.data_dir)
    if args.input:
        return args.input
    return find_latest_jsonl(args.data_dir)


def main() -> None:
    args = parse_args()
    path = resolve_input(args)
    if not path.exists():
        raise SystemExit(f"input not found: {path}")

    print(f"viewing: {path}")
    viewer = SkeletonViewer(args)

    if args.live:
        tail = JsonlTail(path)

        def update_live(_step: int):
            payload = tail.read_latest()
            if payload:
                viewer.draw_payload(payload)
            return viewer.artists

        viewer.animation = FuncAnimation(viewer.fig, update_live, interval=args.interval_ms, blit=False)
        plt.show()
        return

    frames = load_playback_frames(path, args.max_frames, max(args.stride, 1))
    if not frames:
        raise SystemExit("no webxr_hand_frame payloads found")

    def update_playback(step: int):
        viewer.draw_payload(frames[step])
        return viewer.artists

    anim = FuncAnimation(
        viewer.fig,
        update_playback,
        frames=len(frames),
        interval=args.interval_ms,
        blit=False,
    )
    viewer.animation = anim

    if args.save_gif:
        args.save_gif.parent.mkdir(parents=True, exist_ok=True)
        anim.save(args.save_gif, writer=PillowWriter(fps=args.gif_fps), dpi=120)
        print(f"saved GIF: {args.save_gif}")
    else:
        plt.show()


if __name__ == "__main__":
    main()
