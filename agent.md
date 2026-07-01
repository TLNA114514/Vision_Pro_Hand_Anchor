# agent.md

## Project Goal

Build a minimal WebXR hand-joint streaming prototype for Apple Vision Pro.

The goal is not to build a polished UI or full XR app. The goal is to obtain rough Vision Pro hand joint positions through Safari WebXR and stream them to a desktop Python process for later comparison against MediaPipe or other hand-pose methods.

The prototype should:

1. Run as a local HTTPS web page.
2. Be opened in Safari on Apple Vision Pro.
3. Start an immersive WebXR session.
4. Request WebXR hand tracking.
5. Read left/right hand joint poses every XR frame.
6. Stream joint data to a Python WebSocket server.
7. Save received frames as JSONL.
8. Be simple, debuggable, and easy to modify.

## Important Context

This is for a rough data-collection prototype.

The user mainly wants to compare:

* Vision Pro WebXR hand joints
* MediaPipe hand landmarks
* Other hand tracking methods

Do not over-engineer the project. Prefer plain JavaScript, Python, and minimal dependencies.

## Target Architecture

```text
Apple Vision Pro Safari
  |
  | HTTPS page
  v
WebXR client
  |
  | WebSocket JSON messages
  v
Python WebSocket server on desktop/laptop
  |
  v
JSONL logs
```

## Repository Structure

Create the following structure:

```text
webxr-hand-stream/
  agent.md
  README.md
  certs/
    README.md
  web/
    index.html
    main.js
    style.css
  server/
    ws_logger.py
  scripts/
    make_self_signed_cert.sh
  data/
    .gitkeep
```

## Implementation Requirements

### 1. Web Client

Implement a plain browser client under `web/`.

The client should include:

* `index.html`
* `main.js`
* `style.css`

No React, no Three.js, no Babylon.js unless absolutely necessary.

The page should show:

* Project title
* WebXR support status
* WebSocket connection status
* A text input for WebSocket URL
* A button: `Connect WebSocket`
* A button: `Start WebXR Hand Tracking`
* A button: `Stop`
* A small live debug panel showing:

  * frame count
  * number of joints sent in last frame
  * left hand present / right hand present
  * last error message

### 2. WebXR Session

In `main.js`, implement:

```js
navigator.xr.isSessionSupported("immersive-vr")
```

Then start session with:

```js
navigator.xr.requestSession("immersive-vr", {
  requiredFeatures: ["local-floor"],
  optionalFeatures: ["hand-tracking"]
})
```

If `local-floor` fails, retry with:

```js
navigator.xr.requestSession("immersive-vr", {
  optionalFeatures: ["hand-tracking", "local"]
})
```

Use an XR reference space:

```js
session.requestReferenceSpace("local-floor")
```

Fallback to:

```js
session.requestReferenceSpace("local")
```

### 3. Reading Hand Joints

In each XR animation frame:

```js
session.requestAnimationFrame(onXRFrame)
```

Loop through:

```js
for (const inputSource of session.inputSources) {
  if (!inputSource.hand) continue;
}
```

For each hand:

```js
for (const [jointName, jointSpace] of inputSource.hand) {
  const pose = frame.getJointPose(jointSpace, referenceSpace);
}
```

For each valid pose, extract:

```js
pose.transform.position.x
pose.transform.position.y
pose.transform.position.z

pose.transform.orientation.x
pose.transform.orientation.y
pose.transform.orientation.z
pose.transform.orientation.w

pose.radius
```

The message format should be one JSON object per XR frame, not one message per joint.

Use this schema:

```json
{
  "type": "webxr_hand_frame",
  "source": "visionpro_safari_webxr",
  "client_time_ms": 12345.678,
  "xr_predicted_display_time_ms": 12345.678,
  "frame_index": 42,
  "reference_space": "local-floor",
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
```

If a joint pose is missing, either omit it or mark it as:

```json
{
  "name": "index-finger-tip",
  "valid": false
}
```

Prefer omitting invalid joints for the first prototype.

### 4. WebSocket Client

The web page should connect to a configurable WebSocket server.

Default value:

```text
wss://<current-host>:8765
```

But allow the user to edit it.

Also support insecure WebSocket for quick LAN testing if needed:

```text
ws://<desktop-ip>:8765
```

However, the page itself must be served over HTTPS for WebXR hand tracking.

Implement:

* reconnect only manually, not automatically
* send JSON string
* show connection status
* avoid crashing if WebSocket is disconnected
* count dropped frames when WebSocket is not open

### 5. Python WebSocket Logger

Implement `server/ws_logger.py`.

Use Python 3.10+.

Dependencies:

```text
websockets
```

The server should:

* Listen on `0.0.0.0:8765`
* Accept WebSocket connections
* Print client connection info
* Save incoming JSON messages to JSONL
* Create output path like:

```text
data/webxr_hand_YYYYMMDD_HHMMSS.jsonl
```

Each line should include:

```json
{
  "server_receive_time_ns": 1234567890123456789,
  "payload": { ... original web message ... }
}
```

Add basic validation:

* message must be valid JSON
* payload type should be `webxr_hand_frame`
* count received frames
* print one status line every 100 frames

### 6. HTTPS Local Server

The page must be served over HTTPS.

Add a simple command in README using Python:

```bash
python3 -m http.server 8443 --directory web
```

But Python’s built-in server is HTTP only, so also provide an HTTPS server option.

Implement either:

Option A: provide a tiny Python HTTPS static server script.

Preferred: create `server/https_static_server.py`.

It should:

* serve `web/`
* listen on `0.0.0.0:8443`
* use cert files from `certs/localhost.pem` and `certs/localhost-key.pem`

Option B: provide instructions using `npx http-server`.

If using Node:

```bash
npx http-server web -S -C certs/localhost.pem -K certs/localhost-key.pem -p 8443
```

Prefer Python-only if possible.

### 7. Certificate Script

Create:

```text
scripts/make_self_signed_cert.sh
```

It should generate:

```text
certs/localhost.pem
certs/localhost-key.pem
```

using OpenSSL.

Include SAN entries for:

* localhost
* 127.0.0.1
* the machine LAN IP if passed as an argument

Example:

```bash
bash scripts/make_self_signed_cert.sh 192.168.1.23
```

The script should print a reminder:

```text
On Vision Pro, Safari may warn that this certificate is not trusted.
For quick testing, open the page and proceed if Safari allows it.
For cleaner testing, use a trusted local certificate or tunnel.
```

### 8. README

Write a practical README with the following sections:

1. What this is
2. What it captures
3. What it does not capture
4. Requirements
5. Setup
6. Start WebSocket logger
7. Start HTTPS web server
8. Run on Apple Vision Pro
9. Troubleshooting
10. Data format
11. Next steps for MediaPipe comparison

### 9. Vision Pro Running Instructions

In README, include the following user-facing instructions:

```text
1. Put the desktop/laptop and Vision Pro on the same Wi-Fi.
2. Find the desktop/laptop LAN IP, for example 192.168.1.23.
3. Start the Python WebSocket logger:
   python3 server/ws_logger.py
4. Start the HTTPS static server:
   python3 server/https_static_server.py
5. On Vision Pro, open Safari.
6. Visit:
   https://192.168.1.23:8443
7. Accept the local certificate warning if Safari allows it.
8. Click Connect WebSocket.
9. Click Start WebXR Hand Tracking.
10. Grant permissions if prompted.
11. Move both hands in view.
12. Check the desktop terminal and data/ folder for JSONL output.
```

Also include:

```text
If the page says WebXR is unavailable:
- update visionOS if possible
- check Safari WebXR feature flags
- restart Safari
- make sure the page is loaded over HTTPS
- try immersive-vr before immersive-ar
```

### 10. Troubleshooting Notes

Add these points:

* WebXR APIs require HTTPS secure context.
* Vision Pro Safari behavior differs by visionOS version.
* WebXR hand tracking may be unavailable until an immersive session starts.
* `inputSource.hand` may be undefined if hand tracking permission is missing or not granted.
* `getJointPose()` can return null for occluded or unavailable joints.
* `handedness` may be `"left"`, `"right"`, or `"none"` depending on implementation.
* The coordinate frame is WebXR reference-space dependent.
* Do not compare raw XYZ directly with MediaPipe.
* For MediaPipe comparison, first align by wrist and normalize by palm scale or wrist-to-middle-MCP length.

### 11. MediaPipe Comparison Preparation

Add a `docs` or README section explaining that MediaPipe and WebXR joints are different.

Mention:

* WebXR hand input commonly exposes 25 joints.
* MediaPipe Hands commonly exposes 21 landmarks.
* Need a joint mapping table.
* Compare only shared stable joints first:

  * wrist
  * thumb-tip
  * index-finger-tip
  * middle-finger-tip
  * ring-finger-tip
  * pinky/little-finger-tip
  * index/middle/ring/little MCP-like joints
* Use wrist-aligned normalized MPJPE first.
* Also compare pinch distance:

  * thumb-tip to index-finger-tip
* Also compare fingertip distance curves over time.

### 12. Coding Style

Keep code simple and readable.

Use:

* plain JavaScript
* Python standard library where possible
* `websockets` for WebSocket server
* no frontend build step
* no bundler
* no framework

All code should run with:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install websockets
```

### 13. Deliverables

After implementation, the repository should allow the user to run:

```bash
bash scripts/make_self_signed_cert.sh <LAN_IP>
python3 server/ws_logger.py
python3 server/https_static_server.py
```

Then open on Vision Pro:

```text
https://<LAN_IP>:8443
```

And produce:

```text
data/webxr_hand_*.jsonl
```

### 14. Do Not Do

Do not implement a full visualization engine.

Do not add Three.js unless needed.

Do not add React.

Do not require a Mac.

Do not require Xcode.

Do not assume WebXR hand joints are ground truth.

Do not assume raw WebXR XYZ can be directly compared with MediaPipe XYZ.

Do not hide errors. Show errors clearly in the page and terminal.

### 15. Nice-to-Have

If time remains, add:

* CSV export script from JSONL
* basic live table of joints
* frame-rate estimate
* dropped-frame counter
* recording start/stop button
* session metadata message at the beginning of recording
* browser user-agent logging
* reference-space name logging
* optional compression by sending only positions instead of orientations

## Expected Minimal Files

### `web/index.html`

Should load `style.css` and `main.js`.

### `web/main.js`

Should implement:

* feature detection
* WebSocket connection
* WebXR session start/stop
* hand joint extraction
* per-frame JSON sending
* UI status updates

### `server/ws_logger.py`

Should implement:

* WebSocket server
* JSONL writer
* receive timestamp
* frame counter
* basic validation

### `server/https_static_server.py`

Should implement:

* HTTPS static file server
* serve `web/`
* bind to `0.0.0.0:8443`

### `scripts/make_self_signed_cert.sh`

Should generate cert/key files for HTTPS testing.

## Final Check

Before considering the task done, verify:

1. The web page loads locally.
2. The WebSocket server accepts a connection.
3. The browser can send a test JSON message.
4. The JSONL file is created.
5. The code does not require a Mac.
6. The README clearly explains how to open the page on Vision Pro.
7. The README clearly warns that WebXR vs MediaPipe requires coordinate alignment and joint mapping.
