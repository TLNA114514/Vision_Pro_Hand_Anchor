# Vision Pro WebXR Hand Anchor

**Language / 语言**: [中文](#中文说明) | [English](#english)

---

## 中文说明

[English](#english)

### 这是什么

这是一个用于 Apple Vision Pro Safari 的最小 WebXR 手部关节点采集原型。它通过本地 HTTPS 页面启动 WebXR immersive session，读取 Vision Pro 暴露的手部关节点与头显/viewer pose，通过 WebSocket 发送到电脑端 Python logger，并保存成 JSONL。

项目重点是数据采集、调试和后续对比，不是完整 XR 应用。

### 数据流

```text
Apple Vision Pro Safari
  -> HTTPS WebXR 页面
  -> 每帧读取 hand joints + viewer/head pose
  -> WebSocket JSON
  -> Python logger
  -> data/webxr_hand_*.jsonl
  -> 离线/实时 3D 可视化
```

### 采集内容

- WebXR 手部关节点位置、朝向和 radius
- 左手/右手 handedness
- 头显/viewer 的 position、orientation 和 transform matrix
- 每帧时间戳、frame index、reference space、FPS 估计
- WebXR session 诊断事件

### 不做什么

- 不把 WebXR joints 当作绝对真值
- 不假设 WebXR 原始 XYZ 可以直接和 MediaPipe 比
- 不依赖 React、Three.js、Xcode 或 macOS
- 不提交本地证书、采集 JSONL 和生成图片

### 环境要求

- Python 3.10+
- OpenSSL
- Apple Vision Pro + Safari
- Vision Pro 和电脑在同一 Wi-Fi
- Python 包：`websockets`
- 可视化可选包：`matplotlib`

### 安装

如果使用当前项目里已经创建过的 conda 环境：

```bash
source /home/luojiangrui/miniconda3/etc/profile.d/conda.sh
conda activate vphand
```

或者自己创建环境：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install websockets matplotlib
```

生成本地证书，传入电脑的局域网 IP：

```bash
bash scripts/make_self_signed_cert.sh 192.168.1.23
```

### 启动服务

启动 WebSocket logger：

```bash
python3 server/ws_logger.py
```

默认监听：

```text
wss://0.0.0.0:8765
```

启动 HTTPS 静态页面：

```bash
python3 server/https_static_server.py
```

默认页面地址：

```text
https://<电脑局域网IP>:8443
```

### 在 Vision Pro 上运行

1. 确认 Vision Pro 和电脑在同一 Wi-Fi。
2. 在电脑端启动 `server/ws_logger.py`。
3. 在电脑端启动 `server/https_static_server.py`。
4. 在 Vision Pro Safari 打开：

   ```text
   https://<电脑局域网IP>:8443
   ```

5. 接受本地证书警告。
6. WebSocket URL 填：

   ```text
   wss://<电脑局域网IP>:8765
   ```

7. 点击 `Connect WebSocket`。
8. 选择 XR mode。当前 Vision Pro Safari 可能只支持 `immersive-vr`，不一定支持 `immersive-ar`。
9. 点击 `Start WebXR Hand Tracking`。
10. 移动双手和头显，检查终端 FPS 与 `data/` 下的 JSONL。

### 坐标系

WebXR 原始坐标通常是 **Y-up**：

```text
WebXR x = 左右
WebXR y = 高度/向上
WebXR z = 前后/深度
```

为了更符合常见地面坐标理解，绘图脚本默认显示为：

```text
显示 X = WebXR x
显示 Y = WebXR z
显示 Z = WebXR y，高度
```

如果想看原始 WebXR 坐标，加：

```bash
--display-coords webxr
```

### 数据格式

每行 JSONL 是一个 server record：

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

### 轨迹绘图

静态 3D 轨迹图：

```bash
python3 scripts/plot_webxr_jsonl.py data/webxr_hand_YYYYMMDD_HHMMSS.jsonl -o data/trajectory.png
```

只画 viewer/head：

```bash
python3 scripts/plot_webxr_jsonl.py data/webxr_hand_YYYYMMDD_HHMMSS.jsonl \
  --viewer-only \
  -o data/viewer_trajectory.png
```

生成按时间移动的 GIF：

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

右侧坐标面板默认开启；关闭：

```bash
--no-coordinate-panel
```

### 实时/回放骨架 Viewer

实时查看最新日志：

```bash
python3 scripts/view_webxr_skeleton.py --latest --live
```

实时查看指定文件：

```bash
python3 scripts/view_webxr_skeleton.py data/webxr_hand_YYYYMMDD_HHMMSS.jsonl --live
```

离线回放：

```bash
python3 scripts/view_webxr_skeleton.py data/webxr_hand_YYYYMMDD_HHMMSS.jsonl --stride 3
```

保存回放为 GIF：

```bash
python3 scripts/view_webxr_skeleton.py data/webxr_hand_YYYYMMDD_HHMMSS.jsonl \
  --stride 5 \
  --max-frames 300 \
  --save-gif data/skeleton_playback.gif
```

Viewer 显示：

- 头显/viewer 位置
- 头显朝向小金字塔/视锥
- 红色 forward ray
- 左右手关节点
- 手部骨架连线
- 右侧实时坐标面板

操作：

- 鼠标旋转、缩放、平移 3D 视角
- 空格键暂停/继续 live 或 playback

常用参数：

```bash
--fixed-range 2.0
--fixed-height-center 1.2
--viewer-size 0.18
--joint-size 24
--interval-ms 50
--display-coords webxr
```

### 常见问题

如果页面显示 WebXR 不可用：

- 确认页面是 HTTPS
- 检查 Safari WebXR feature flags
- 更新 visionOS
- 重启 Safari
- 先尝试 `immersive-vr`

如果 `immersive-ar` 不可用：

- 这通常是当前 visionOS/Safari WebXR 暴露能力限制
- Vision Pro 硬件支持 passthrough/AR，但 Safari WebXR 不一定暴露 `immersive-ar`
- 真实手上叠加关节点需要浏览器支持 `immersive-ar`；否则只能在 `immersive-vr` 或桌面 viewer 中调试

### MediaPipe 对比建议

WebXR hand input 常见 25 个 joints，MediaPipe Hands 常见 21 个 landmarks。不要直接比较原始 XYZ。

建议先比较：

- wrist
- thumb-tip
- index-finger-tip
- middle-finger-tip
- ring-finger-tip
- pinky/little-finger-tip
- MCP-like joints

建议指标：

- wrist-aligned normalized MPJPE
- thumb-tip 到 index-finger-tip 的 pinch distance
- fingertip distance curves over time

[Back to top / 返回顶部](#vision-pro-webxr-hand-anchor) | [English](#english)

---

## English

[中文](#中文说明)

### What This Is

This is a minimal WebXR hand-anchor and trajectory capture prototype for Apple Vision Pro Safari. It serves a local HTTPS page, starts an immersive WebXR session, reads Vision Pro hand joints and viewer/head pose, streams each frame to a Python WebSocket logger, and saves the data as JSONL.

The goal is data collection, debugging, and later comparison, not a full XR application.

### Data Flow

```text
Apple Vision Pro Safari
  -> HTTPS WebXR page
  -> per-frame hand joints + viewer/head pose
  -> WebSocket JSON
  -> Python logger
  -> data/webxr_hand_*.jsonl
  -> offline/live 3D visualization
```

### Captured Data

- WebXR hand joint position, orientation, and radius
- left/right handedness
- viewer/head position, orientation, and transform matrix
- frame timing, frame index, reference space, and FPS estimate
- WebXR session diagnostic events

### Not Included

- No full visualization engine
- No assumption that WebXR joints are ground truth
- No assumption that raw WebXR XYZ directly matches MediaPipe
- No React, Three.js, Xcode, or macOS requirement
- No committed local certificates, JSONL logs, or generated images

### Requirements

- Python 3.10+
- OpenSSL
- Apple Vision Pro with Safari
- Vision Pro and desktop/laptop on the same Wi-Fi
- Python package: `websockets`
- Optional visualization package: `matplotlib`

### Setup

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

### Start Services

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

### Run on Apple Vision Pro

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

### Coordinate System

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

### Data Format

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

### Plot Trajectories

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

### Live Skeleton Viewer

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

### Troubleshooting

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

### MediaPipe Comparison Notes

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

[Back to top](#vision-pro-webxr-hand-anchor) | [中文](#中文说明)
