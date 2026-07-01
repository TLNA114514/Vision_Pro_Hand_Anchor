# Vision Pro WebXR Hand Stream

## What this is

A minimal WebXR hand-joint streaming prototype for Apple Vision Pro Safari. It serves a local HTTPS page, starts an immersive WebXR session, reads rough hand joint poses, streams them over WebSocket, and logs the messages as JSONL on a desktop or laptop.

This is intentionally small: plain JavaScript, Python, and one Python dependency for the WebSocket server.

## What it captures

- WebXR hand joint positions, orientations, and radius values when Safari exposes `inputSource.hand`.
- Viewer/head pose position, orientation, and transform matrix when `frame.getViewerPose()` is available.
- One JSON message per XR frame.
- Left and right hand data when available.
- Client timing, XR predicted display time, frame index, user agent metadata, and reference-space name.

## What it does not capture

- It does not provide a full visualization engine.
- It does not assume WebXR joints are ground truth.
- It does not make raw coordinates comparable with MediaPipe without alignment.
- It does not require a Mac, Xcode, React, Three.js, or a frontend build step.

## Requirements

- Python 3.10+
- OpenSSL for generating a local certificate
- Apple Vision Pro with Safari
- Desktop/laptop and Vision Pro on the same Wi-Fi
- Python package: `websockets`
- Optional plotting package: `matplotlib`

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install websockets
```

For offline trajectory plots:

```bash
pip install matplotlib
```

Find your desktop/laptop LAN IP, for example `192.168.1.23`, then create a local certificate:

```bash
bash scripts/make_self_signed_cert.sh 192.168.1.23
```

## Start WebSocket logger

```bash
python3 server/ws_logger.py
```

The logger listens on:

```text
wss://0.0.0.0:8765
```

If `certs/localhost.pem` and `certs/localhost-key.pem` are missing, it falls back to `ws://`. To force plain WebSocket for local desktop testing:

```bash
python3 server/ws_logger.py --no-tls
```

It writes files like:

```text
data/webxr_hand_YYYYMMDD_HHMMSS.jsonl
```

While frames are arriving, the logger prints a live status line about once per second with server receive FPS, client-estimated FPS, joint count, input-source count, and active XR mode.

## Start HTTPS web server

Preferred:

```bash
python3 server/https_static_server.py
```

It serves:

```text
https://0.0.0.0:8443
```

You can also run a plain HTTP test server for desktop debugging only, but WebXR hand tracking requires HTTPS:

```bash
python3 -m http.server 8443 --directory web
```

## Run on Apple Vision Pro

1. Put the desktop/laptop and Vision Pro on the same Wi-Fi.
2. Find the desktop/laptop LAN IP, for example `192.168.1.23`.
3. Start the Python WebSocket logger:
   `python3 server/ws_logger.py`
4. Start the HTTPS static server:
   `python3 server/https_static_server.py`
5. On Vision Pro, open Safari.
6. Visit:
   `https://192.168.1.23:8443`
7. Accept the local certificate warning if Safari allows it.
8. Click Connect WebSocket.
9. Choose `AR: align dots with real hands` if you want joint dots overlaid on the real hand view.
10. Click Start WebXR Hand Tracking.
11. Grant permissions if prompted.
12. Move both hands in view.
13. Check the desktop terminal and `data/` folder for JSONL output.

The WebSocket URL defaults to:

```text
wss://<current-host>:8765
```

For quick LAN testing with `python3 server/ws_logger.py --no-tls`, you can edit it to:

```text
ws://<desktop-ip>:8765
```

Note: some browsers block insecure WebSocket connections from HTTPS pages. If `ws://` fails from an HTTPS page, use a trusted local TLS setup or tunnel for the WebSocket server.

## Troubleshooting

If the page says WebXR is unavailable:

- update visionOS if possible
- check Safari WebXR feature flags
- restart Safari
- make sure the page is loaded over HTTPS
- try immersive-vr before immersive-ar

Other notes:

- WebXR APIs require an HTTPS secure context.
- Vision Pro Safari behavior differs by visionOS version.
- WebXR hand tracking may be unavailable until an immersive session starts.
- AR mode is the best choice for visually checking whether rendered joint dots line up with your real hands.
- `inputSource.hand` may be undefined if hand tracking permission is missing or not granted.
- `getJointPose()` can return null for occluded or unavailable joints.
- `handedness` may be `"left"`, `"right"`, or `"none"` depending on implementation.
- The coordinate frame is WebXR reference-space dependent.
- Do not compare raw XYZ directly with MediaPipe.
- For MediaPipe comparison, first align by wrist and normalize by palm scale or wrist-to-middle-MCP length.

## Data format

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

Invalid or unavailable joint poses are omitted in this first prototype.

`viewer_pose` is the WebXR viewer/head pose in the same reference space as the hand joints. In `local-floor`, values are approximately meters relative to the session's local floor-space origin. Treat this as a browser-defined tracking space, not a global room coordinate system.

## Plot trajectories

After collecting a log with hand frames, create a 3D plot:

```bash
python3 scripts/plot_webxr_jsonl.py data/webxr_hand_YYYYMMDD_HHMMSS.jsonl -o data/trajectory.png
```

Plot specific joints:

```bash
python3 scripts/plot_webxr_jsonl.py data/webxr_hand_YYYYMMDD_HHMMSS.jsonl \
  --joint wrist \
  --joint index-finger-tip \
  --joint thumb-tip \
  -o data/fingertips.png
```

Plot every joint found in the file:

```bash
python3 scripts/plot_webxr_jsonl.py data/webxr_hand_YYYYMMDD_HHMMSS.jsonl --all-joints -o data/all_joints.png
```

The black line is the viewer/head trajectory. Green is viewer start, red is viewer end.
Plots default to an everyday coordinate display: `X = WebXR x`, `Y = WebXR z`, and `Z = WebXR y height`. Use `--display-coords webxr` to show raw WebXR axes.

Create a timestamp animation as a GIF:

```bash
python3 scripts/plot_webxr_jsonl.py data/webxr_hand_YYYYMMDD_HHMMSS.jsonl \
  --animate \
  --viewer-only \
  --fps 20 \
  --trail-frames 180 \
  -o data/viewer_motion.gif
```

Animate selected hand joints plus the viewer/head trajectory:

```bash
python3 scripts/plot_webxr_jsonl.py data/webxr_hand_YYYYMMDD_HHMMSS.jsonl \
  --animate \
  --joint wrist \
  --joint index-finger-tip \
  --joint thumb-tip \
  --animation-max-frames 400 \
  -o data/hand_and_viewer_motion.gif
```

The animation title shows the source `frame_index` and elapsed client timestamp. By default long logs are downsampled to about 400 rendered GIF frames; use `--stride` or `--animation-max-frames` to control that.

Animations show a coordinate panel on the right by default. In everyday mode it lists current `(X, Y, Z)` as `(WebXR x, WebXR z, WebXR y-height)`. Disable it with `--no-coordinate-panel`.

## Live skeleton viewer

Open a free-rotate 3D desktop viewer for the latest log while recording:

```bash
python3 scripts/view_webxr_skeleton.py --latest --live
```

Or follow a specific file:

```bash
python3 scripts/view_webxr_skeleton.py data/webxr_hand_YYYYMMDD_HHMMSS.jsonl --live
```

The viewer draws:

- viewer/head position as a black point
- viewer/head orientation as a small frustum/pyramid, with a red forward ray
- hand joints as colored points
- hand skeleton bones as colored lines
- a coordinate panel for current head and key hand joints

Use the mouse in the Matplotlib 3D window to rotate, pan, and zoom the view.
Press the spacebar to pause/resume live or playback updates.
The skeleton viewer also defaults to everyday coordinates: `X = WebXR x`, `Y = WebXR z`, `Z = WebXR y height`. Add `--display-coords webxr` to inspect raw WebXR axes.

Playback a saved file interactively:

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

## Next steps for MediaPipe comparison

MediaPipe and WebXR hands expose different landmark sets and coordinate frames. WebXR hand input commonly exposes 25 joints, while MediaPipe Hands commonly exposes 21 landmarks, so use a joint mapping table before comparing.

Compare shared stable joints first:

- wrist
- thumb-tip
- index-finger-tip
- middle-finger-tip
- ring-finger-tip
- pinky/little-finger-tip
- index/middle/ring/little MCP-like joints

Good first metrics:

- wrist-aligned normalized MPJPE
- pinch distance from thumb-tip to index-finger-tip
- fingertip distance curves over time

For a first pass, align each frame by wrist and normalize by palm scale or wrist-to-middle-MCP length. Raw WebXR XYZ and MediaPipe XYZ should not be compared directly.
