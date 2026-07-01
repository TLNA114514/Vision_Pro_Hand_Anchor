# Vision Pro WebXR Hand Anchor

**Language / 语言**: English | [中文](README.zh.md)

This is a minimal WebXR hand-anchor and trajectory capture prototype for Apple Vision Pro Safari. It serves a local HTTPS page, starts an immersive WebXR session, reads Vision Pro hand joints and viewer/head pose, streams each frame to a Python WebSocket logger, and saves the data as JSONL.

The goal is data collection, debugging, and later comparison, not a full XR application.

## Data Flow

```text
Apple Vision Pro Safari
  -> HTTPS WebXR page
  -> per-frame hand joints + viewer/head pose
  -> WebSocket JSON
  -> Python logger
  -> data/webxr_hand_*.jsonl
  -> offline/live 3D visualization
```

## Captured Data

- WebXR hand joint position, orientation, and radius
- left/right handedness
- viewer/head position, orientation, and transform matrix
- frame timing, frame index, reference space, and FPS estimate
- WebXR session diagnostic events

## Not Included

- No full visualization engine
- No assumption that WebXR joints are ground truth
- No assumption that raw WebXR XYZ directly matches MediaPipe
- No React, Three.js, Xcode, or macOS requirement
- No committed local certificates, JSONL logs, or generated images

## Requirements

- Python 3.10+
- OpenSSL
- Apple Vision Pro with Safari
- Vision Pro and desktop/laptop on the same Wi-Fi
- Python package: `websockets`
- Optional visualization package: `matplotlib`

## Setup

Use the existing conda environment if available:

```bash
source /home/luojiangrui/miniconda3/etc/profile.d/conda.sh
conda activate vphand
```

Or create your own environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install websockets matplotlib
```

Generate a local certificate with your desktop/laptop LAN IP:

```bash
bash scripts/make_self_signed_cert.sh 192.168.1.23
```

## Start Services

Start the WebSocket logger:

```bash
python3 server/ws_logger.py
```

It listens on:

```text
wss://0.0.0.0:8765
```

Start the HTTPS static server:

```bash
python3 server/https_static_server.py
```

Open on Vision Pro:

```text
https://<desktop-lan-ip>:8443
```

## Run on Apple Vision Pro

1. Put Vision Pro and desktop/laptop on the same Wi-Fi.
2. Start `server/ws_logger.py`.
3. Start `server/https_static_server.py`.
4. Open Safari on Vision Pro.
5. Visit:

   ```text
   https://<desktop-lan-ip>:8443
   ```

6. Accept the local certificate warning if Safari allows it.
7. Set WebSocket URL to:

   ```text
   wss://<desktop-lan-ip>:8765
   ```

8. Click `Connect WebSocket`.
9. Choose XR mode. Current Vision Pro Safari builds may support `immersive-vr` but not `immersive-ar`.
10. Click `Start WebXR Hand Tracking`.
11. Move both hands and the headset.
12. Check terminal FPS and JSONL files under `data/`.

## Coordinate System

Raw WebXR coordinates are typically **Y-up**:

```text
WebXR x = left/right
WebXR y = height/up
WebXR z = forward/back/depth
```

For easier everyday reading, visualization scripts default to:

```text
display X = WebXR x
display Y = WebXR z
display Z = WebXR y height
```

To inspect raw WebXR axes:

```bash
--display-coords webxr
```

## Data Format

Each JSONL line contains server timing plus the original browser payload:

```json
{
  "server_receive_time_ns": 1234567890123456789,
  "payload": {
    "type": "webxr_hand_frame",
    "source": "visionpro_safari_webxr",
    "client_time_ms": 12345.678,
    "xr_predicted_display_time_ms": 12345.678,
    "frame_index": 42,
    "session_mode": "immersive-vr",
    "reference_space": "local-floor",
    "viewer_pose": {
      "valid": true,
      "position": [0.0, 1.6, 0.0],
      "orientation": [0.0, 0.0, 0.0, 1.0],
      "matrix": [1.0, 0.0, 0.0, 0.0]
    },
    "hands": [
      {
        "handedness": "left",
        "joints": [
          {
            "name": "wrist",
            "valid": true,
            "position": [0.1, 1.2, -0.3],
            "orientation": [0.0, 0.0, 0.0, 1.0],
            "radius": 0.012
          }
        ]
      }
    ]
  }
}
```

Invalid or unavailable joint poses are omitted.

## Plot Trajectories

Static 3D plot:

```bash
python3 scripts/plot_webxr_jsonl.py data/webxr_hand_YYYYMMDD_HHMMSS.jsonl -o data/trajectory.png
```

Viewer/head only:

```bash
python3 scripts/plot_webxr_jsonl.py data/webxr_hand_YYYYMMDD_HHMMSS.jsonl \
  --viewer-only \
  -o data/viewer_trajectory.png
```

Timestamp animation as GIF:

```bash
python3 scripts/plot_webxr_jsonl.py data/webxr_hand_YYYYMMDD_HHMMSS.jsonl \
  --animate \
  --joint wrist \
  --joint index-finger-tip \
  --joint thumb-tip \
  --fps 20 \
  --trail-frames 180 \
  -o data/hand_and_viewer_motion.gif
```

The coordinate panel is enabled by default. Disable it with:

```bash
--no-coordinate-panel
```

## Live Skeleton Viewer

Live viewer for the latest log:

```bash
python3 scripts/view_webxr_skeleton.py --latest --live
```

Live viewer for a specific file:

```bash
python3 scripts/view_webxr_skeleton.py data/webxr_hand_YYYYMMDD_HHMMSS.jsonl --live
```

Offline playback:

```bash
python3 scripts/view_webxr_skeleton.py data/webxr_hand_YYYYMMDD_HHMMSS.jsonl --stride 3
```

Save playback as GIF:

```bash
python3 scripts/view_webxr_skeleton.py data/webxr_hand_YYYYMMDD_HHMMSS.jsonl \
  --stride 5 \
  --max-frames 300 \
  --save-gif data/skeleton_playback.gif
```

The viewer draws:

- viewer/head position
- viewer/head orientation as a frustum/pyramid
- red forward ray
- left/right hand joints
- hand skeleton bones
- live coordinate panel

Controls:

- mouse to rotate, zoom, and pan
- spacebar to pause/resume live or playback updates

Useful options:

```bash
--fixed-range 2.0
--fixed-height-center 1.2
--viewer-size 0.18
--joint-size 24
--interval-ms 50
--display-coords webxr
```

## Troubleshooting

If WebXR is unavailable:

- make sure the page is loaded over HTTPS
- check Safari WebXR feature flags
- update visionOS
- restart Safari
- try `immersive-vr` first

If `immersive-ar` is unavailable:

- it is likely a current visionOS/Safari WebXR capability limit
- Vision Pro hardware supports passthrough/AR, but Safari WebXR may not expose `immersive-ar`
- real-hand overlay needs browser `immersive-ar`; otherwise use `immersive-vr` or the desktop viewer

## MediaPipe Comparison Notes

WebXR hand input commonly exposes 25 joints, while MediaPipe Hands commonly exposes 21 landmarks. Do not compare raw XYZ directly.

Start with shared stable joints:

- wrist
- thumb-tip
- index-finger-tip
- middle-finger-tip
- ring-finger-tip
- pinky/little-finger-tip
- MCP-like joints

Useful metrics:

- wrist-aligned normalized MPJPE
- thumb-tip to index-finger-tip pinch distance
- fingertip distance curves over time

[中文](README.zh.md) | [Back to top](#vision-pro-webxr-hand-anchor)
