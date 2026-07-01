"use strict";

const els = {
  xrStatus: document.getElementById("xrStatus"),
  wsStatus: document.getElementById("wsStatus"),
  sessionStatus: document.getElementById("sessionStatus"),
  wsUrl: document.getElementById("wsUrl"),
  xrMode: document.getElementById("xrMode"),
  connectWsButton: document.getElementById("connectWsButton"),
  startXrButton: document.getElementById("startXrButton"),
  stopButton: document.getElementById("stopButton"),
  frameCount: document.getElementById("frameCount"),
  jointCount: document.getElementById("jointCount"),
  leftPresent: document.getElementById("leftPresent"),
  rightPresent: document.getElementById("rightPresent"),
  droppedFrames: document.getElementById("droppedFrames"),
  fpsEstimate: document.getElementById("fpsEstimate"),
  lastError: document.getElementById("lastError"),
};

let ws = null;
let xrSession = null;
let xrCanvas = null;
let gl = null;
let jointProgram = null;
let jointPositionBuffer = null;
let jointMatrixLocation = null;
let jointColorLocation = null;
let jointPointSizeLocation = null;
let referenceSpace = null;
let referenceSpaceName = "";
let sessionMode = "";
let frameIndex = 0;
let droppedFrames = 0;
let lastFpsTime = performance.now();
let framesSinceFps = 0;
let currentFpsEstimate = 0;

function defaultWsUrl() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const host = window.location.hostname || "localhost";
  return `${protocol}//${host}:8765`;
}

function setError(message) {
  els.lastError.textContent = message || "None";
  if (message) {
    console.error(message);
  }
}

function setWsStatus(message) {
  els.wsStatus.textContent = message;
}

function updateDebug({ joints = 0, left = false, right = false } = {}) {
  els.frameCount.textContent = String(frameIndex);
  els.jointCount.textContent = String(joints);
  els.leftPresent.textContent = String(left);
  els.rightPresent.textContent = String(right);
  els.droppedFrames.textContent = String(droppedFrames);
}

async function checkWebXRSupport() {
  if (!("xr" in navigator)) {
    els.xrStatus.textContent = "Unavailable";
    els.startXrButton.disabled = true;
    setError("navigator.xr is not available. WebXR requires HTTPS and browser/runtime support.");
    return;
  }

  const [vrSupported, arSupported] = await Promise.all([
    isSessionModeSupported("immersive-vr"),
    isSessionModeSupported("immersive-ar"),
  ]);

  const supportedModes = [];
  if (vrSupported) {
    supportedModes.push("immersive-vr");
  }
  if (arSupported) {
    supportedModes.push("immersive-ar");
  }

  els.xrStatus.textContent = supportedModes.length > 0 ? supportedModes.join(", ") : "Unavailable";
  els.startXrButton.disabled = supportedModes.length === 0;
  sendSessionEvent("support_checked", {
    immersive_vr: vrSupported,
    immersive_ar: arSupported,
  });
}

function connectWebSocket() {
  const url = els.wsUrl.value.trim();
  if (!url) {
    setError("WebSocket URL is empty.");
    return;
  }

  if (ws) {
    ws.close();
    ws = null;
  }

  try {
    ws = new WebSocket(url);
  } catch (error) {
    setWsStatus("Disconnected");
    setError(`Could not create WebSocket: ${error.message}`);
    return;
  }

  setWsStatus("Connecting...");

  ws.addEventListener("open", () => {
    setWsStatus("Connected");
    setError("");
    sendSessionMetadata();
  });

  ws.addEventListener("close", () => {
    setWsStatus("Disconnected");
  });

  ws.addEventListener("error", () => {
    setWsStatus("Error");
    setError("WebSocket error. Check server URL, certificate trust, and terminal logs.");
  });
}

function sendJson(payload) {
  if (!ws || ws.readyState !== WebSocket.OPEN) {
    droppedFrames += 1;
    els.droppedFrames.textContent = String(droppedFrames);
    return false;
  }

  ws.send(JSON.stringify(payload));
  return true;
}

function sendSessionMetadata() {
  sendJson({
    type: "webxr_hand_metadata",
    source: "visionpro_safari_webxr",
    client_time_ms: performance.now(),
    page_url: window.location.href,
    user_agent: navigator.userAgent,
    selected_xr_mode: els.xrMode.value,
  });
}

function sendSessionEvent(event, details = {}) {
  if (!ws || ws.readyState !== WebSocket.OPEN) {
    return false;
  }

  ws.send(JSON.stringify({
    type: "webxr_session_event",
    source: "visionpro_safari_webxr",
    client_time_ms: performance.now(),
    event,
    ...details,
  }));
  return true;
}

async function isSessionModeSupported(mode) {
  try {
    return await navigator.xr.isSessionSupported(mode);
  } catch (error) {
    sendSessionEvent("support_check_failed", { mode, error: error.message });
    return false;
  }
}

async function requestHandTrackingSession() {
  const selectedMode = els.xrMode.value;
  const vrCandidates = [
    {
      mode: "immersive-vr",
      init: {
        requiredFeatures: ["hand-tracking", "local-floor"],
        optionalFeatures: ["local"],
      },
    },
    {
      mode: "immersive-vr",
      init: {
        requiredFeatures: ["hand-tracking"],
        optionalFeatures: ["local-floor", "local"],
      },
    },
  ];
  const arCandidates = [
    {
      mode: "immersive-ar",
      init: {
        requiredFeatures: ["hand-tracking", "local-floor"],
        optionalFeatures: ["local"],
      },
    },
    {
      mode: "immersive-ar",
      init: {
        requiredFeatures: ["hand-tracking"],
        optionalFeatures: ["local-floor", "local"],
      },
    },
  ];
  const candidates = selectedMode === "immersive-ar"
    ? arCandidates
    : selectedMode === "immersive-vr"
      ? vrCandidates
      : [...arCandidates, ...vrCandidates];

  const errors = [];
  for (const candidate of candidates) {
    const supported = await isSessionModeSupported(candidate.mode);
    if (!supported) {
      errors.push(`${candidate.mode}: not supported`);
      continue;
    }

    try {
      sendSessionEvent("request_session_attempt", {
        selected_mode: selectedMode,
        ...candidate,
      });
      const session = await navigator.xr.requestSession(candidate.mode, candidate.init);
      sessionMode = candidate.mode;
      return session;
    } catch (error) {
      errors.push(`${candidate.mode} ${JSON.stringify(candidate.init)}: ${error.name || "Error"} ${error.message}`);
      sendSessionEvent("request_session_failed", {
        selected_mode: selectedMode,
        mode: candidate.mode,
        init: candidate.init,
        error_name: error.name,
        error: error.message,
      });
    }
  }

  throw new Error(`All hand-tracking session attempts failed. ${errors.join(" | ")}`);
}

async function requestReferenceSpace(session) {
  try {
    referenceSpaceName = "local-floor";
    return await session.requestReferenceSpace("local-floor");
  } catch (firstError) {
    referenceSpaceName = "local";
    setError(`local-floor reference space failed, using local: ${firstError.message}`);
    return session.requestReferenceSpace("local");
  }
}

async function setupXRRenderLayer(session) {
  xrCanvas = document.createElement("canvas");
  xrCanvas.width = 1;
  xrCanvas.height = 1;
  xrCanvas.style.position = "fixed";
  xrCanvas.style.left = "0";
  xrCanvas.style.top = "0";
  xrCanvas.style.width = "1px";
  xrCanvas.style.height = "1px";
  xrCanvas.style.opacity = "0";
  xrCanvas.style.pointerEvents = "none";
  document.body.appendChild(xrCanvas);

  gl = xrCanvas.getContext("webgl2", { xrCompatible: true, alpha: true })
    || xrCanvas.getContext("webgl", { xrCompatible: true, alpha: true });
  if (!gl) {
    throw new Error("Could not create WebGL context required by immersive WebXR.");
  }

  if (typeof gl.makeXRCompatible === "function") {
    await gl.makeXRCompatible();
  }

  if (!("XRWebGLLayer" in window)) {
    throw new Error("XRWebGLLayer is not available in this browser.");
  }

  session.updateRenderState({
    baseLayer: new XRWebGLLayer(session, gl, {
      alpha: true,
      antialias: true,
    }),
  });

  setupJointRenderer();
}

function setupJointRenderer() {
  const vertexSource = `
    attribute vec3 a_position;
    uniform mat4 u_matrix;
    uniform float u_pointSize;

    void main() {
      gl_Position = u_matrix * vec4(a_position, 1.0);
      gl_PointSize = u_pointSize;
    }
  `;
  const fragmentSource = `
    precision mediump float;
    uniform vec4 u_color;

    void main() {
      vec2 centered = gl_PointCoord - vec2(0.5);
      if (dot(centered, centered) > 0.25) {
        discard;
      }
      gl_FragColor = u_color;
    }
  `;

  const vertexShader = compileShader(gl.VERTEX_SHADER, vertexSource);
  const fragmentShader = compileShader(gl.FRAGMENT_SHADER, fragmentSource);
  jointProgram = gl.createProgram();
  gl.attachShader(jointProgram, vertexShader);
  gl.attachShader(jointProgram, fragmentShader);
  gl.bindAttribLocation(jointProgram, 0, "a_position");
  gl.linkProgram(jointProgram);

  if (!gl.getProgramParameter(jointProgram, gl.LINK_STATUS)) {
    const info = gl.getProgramInfoLog(jointProgram);
    throw new Error(`Could not link joint renderer: ${info}`);
  }

  gl.deleteShader(vertexShader);
  gl.deleteShader(fragmentShader);
  jointPositionBuffer = gl.createBuffer();
  jointMatrixLocation = gl.getUniformLocation(jointProgram, "u_matrix");
  jointColorLocation = gl.getUniformLocation(jointProgram, "u_color");
  jointPointSizeLocation = gl.getUniformLocation(jointProgram, "u_pointSize");
}

function compileShader(type, source) {
  const shader = gl.createShader(type);
  gl.shaderSource(shader, source);
  gl.compileShader(shader);

  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    const info = gl.getShaderInfoLog(shader);
    gl.deleteShader(shader);
    throw new Error(`Could not compile shader: ${info}`);
  }

  return shader;
}

async function startWebXR() {
  if (!navigator.xr) {
    setError("navigator.xr is not available.");
    return;
  }

  if (xrSession) {
    setError("A WebXR session is already running.");
    return;
  }

  try {
    xrSession = await requestHandTrackingSession();
    await setupXRRenderLayer(xrSession);
    referenceSpace = await requestReferenceSpace(xrSession);

    frameIndex = 0;
    framesSinceFps = 0;
    currentFpsEstimate = 0;
    lastFpsTime = performance.now();
    els.sessionStatus.textContent = "Running";
    setError("");

    xrSession.addEventListener("end", handleSessionEnded);
    xrSession.addEventListener("inputsourceschange", (event) => {
      sendSessionEvent("inputsourceschange", {
        added: Array.from(event.added).map(describeInputSource),
        removed: Array.from(event.removed).map(describeInputSource),
      });
    });
    sendSessionEvent("session_started", {
      mode: sessionMode,
      selected_mode: els.xrMode.value,
      reference_space: referenceSpaceName,
      enabled_features: xrSession.enabledFeatures ? Array.from(xrSession.enabledFeatures) : null,
      has_base_layer: Boolean(xrSession.renderState && xrSession.renderState.baseLayer),
    });
    xrSession.requestAnimationFrame(onXRFrame);
  } catch (error) {
    xrSession = null;
    referenceSpace = null;
    els.sessionStatus.textContent = "Stopped";
    sendSessionEvent("session_start_failed", {
      error_name: error.name,
      error: error.message,
    });
    setError(`Could not start WebXR session: ${error.message}`);
  }
}

async function stopAll() {
  if (xrSession) {
    try {
      await xrSession.end();
    } catch (error) {
      setError(`Error stopping WebXR session: ${error.message}`);
    }
  }

  if (ws) {
    ws.close();
    ws = null;
  }

  setWsStatus("Disconnected");
}

function handleSessionEnded() {
  sendSessionEvent("session_ended", {
    mode: sessionMode,
    frame_index: frameIndex,
  });
  xrSession = null;
  gl = null;
  jointProgram = null;
  jointPositionBuffer = null;
  jointMatrixLocation = null;
  jointColorLocation = null;
  jointPointSizeLocation = null;
  if (xrCanvas) {
    xrCanvas.remove();
    xrCanvas = null;
  }
  referenceSpace = null;
  referenceSpaceName = "";
  sessionMode = "";
  els.sessionStatus.textContent = "Stopped";
}

function describeInputSource(inputSource) {
  return {
    handedness: inputSource.handedness || "none",
    target_ray_mode: inputSource.targetRayMode || null,
    profiles: inputSource.profiles ? Array.from(inputSource.profiles) : [],
    has_hand: Boolean(inputSource.hand),
    hand_joint_count: inputSource.hand ? Array.from(inputSource.hand).length : 0,
    has_grip_space: Boolean(inputSource.gripSpace),
    has_target_ray_space: Boolean(inputSource.targetRaySpace),
  };
}

function extractJoint(jointName, jointSpace, frame) {
  const pose = frame.getJointPose(jointSpace, referenceSpace);
  if (!pose) {
    return null;
  }

  const { position, orientation } = pose.transform;
  return {
    name: jointName,
    valid: true,
    jointSpace,
    position: [position.x, position.y, position.z],
    orientation: [orientation.x, orientation.y, orientation.z, orientation.w],
    radius: pose.radius ?? null,
  };
}

function serializeHands(hands) {
  return hands.map((hand) => ({
    handedness: hand.handedness,
    joints: hand.joints.map((joint) => ({
      name: joint.name,
      valid: joint.valid,
      position: joint.position,
      orientation: joint.orientation,
      radius: joint.radius,
    })),
  }));
}

function serializeViewerPose(viewerPose) {
  if (!viewerPose) {
    return { valid: false };
  }

  const { position, orientation, matrix } = viewerPose.transform;
  return {
    valid: true,
    position: [position.x, position.y, position.z],
    orientation: [orientation.x, orientation.y, orientation.z, orientation.w],
    matrix: Array.from(matrix),
  };
}

function extractHands(frame) {
  const hands = [];
  let jointCount = 0;
  let leftPresent = false;
  let rightPresent = false;
  let handInputSourceCount = 0;

  for (const inputSource of xrSession.inputSources) {
    if (!inputSource.hand) {
      continue;
    }

    handInputSourceCount += 1;
    const joints = [];
    for (const [jointName, jointSpace] of inputSource.hand) {
      const joint = extractJoint(jointName, jointSpace, frame);
      if (joint) {
        joints.push(joint);
      }
    }

    if (joints.length === 0) {
      continue;
    }

    if (inputSource.handedness === "left") {
      leftPresent = true;
    }
    if (inputSource.handedness === "right") {
      rightPresent = true;
    }

    jointCount += joints.length;
    hands.push({
      handedness: inputSource.handedness || "none",
      joints,
    });
  }

  return { hands, handInputSourceCount, jointCount, leftPresent, rightPresent };
}

function updateFps() {
  framesSinceFps += 1;
  const now = performance.now();
  const elapsedMs = now - lastFpsTime;
  if (elapsedMs >= 1000) {
    const fps = (framesSinceFps * 1000) / elapsedMs;
    currentFpsEstimate = fps;
    els.fpsEstimate.textContent = fps.toFixed(1);
    console.log(`WebXR FPS: ${fps.toFixed(1)}`);
    framesSinceFps = 0;
    lastFpsTime = now;
  }
}

function multiplyMat4(a, b) {
  const out = new Float32Array(16);
  for (let row = 0; row < 4; row += 1) {
    for (let col = 0; col < 4; col += 1) {
      out[(col * 4) + row] =
        a[(0 * 4) + row] * b[(col * 4) + 0] +
        a[(1 * 4) + row] * b[(col * 4) + 1] +
        a[(2 * 4) + row] * b[(col * 4) + 2] +
        a[(3 * 4) + row] * b[(col * 4) + 3];
    }
  }
  return out;
}

function renderJointDots(frame, viewerPose, hands) {
  if (!gl || !jointProgram || !jointPositionBuffer || hands.length === 0) {
    return;
  }

  const baseLayer = xrSession.renderState && xrSession.renderState.baseLayer;
  if (!baseLayer) {
    return;
  }

  gl.bindFramebuffer(gl.FRAMEBUFFER, baseLayer.framebuffer);
  gl.enable(gl.DEPTH_TEST);
  gl.depthFunc(gl.LEQUAL);
  gl.enable(gl.BLEND);
  gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
  gl.useProgram(jointProgram);
  gl.bindBuffer(gl.ARRAY_BUFFER, jointPositionBuffer);
  gl.enableVertexAttribArray(0);
  gl.vertexAttribPointer(0, 3, gl.FLOAT, false, 0, 0);
  gl.uniform4f(jointColorLocation, 1, 1, 1, 1);
  gl.uniform1f(jointPointSizeLocation, 11);

  for (const view of viewerPose.views) {
    const viewport = baseLayer.getViewport(view);
    gl.viewport(viewport.x, viewport.y, viewport.width, viewport.height);
    const viewProjectionMatrix = multiplyMat4(view.projectionMatrix, view.transform.inverse.matrix);

    for (const hand of hands) {
      const positions = [];
      for (const joint of hand.joints) {
        if (!joint.jointSpace) {
          continue;
        }

        const pose = frame.getJointPose(joint.jointSpace, referenceSpace);
        if (!pose) {
          continue;
        }

        const { position } = pose.transform;
        positions.push(position.x, position.y, position.z);
      }

      if (positions.length === 0) {
        continue;
      }

      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(positions), gl.DYNAMIC_DRAW);
      gl.uniformMatrix4fv(jointMatrixLocation, false, viewProjectionMatrix);
      gl.drawArrays(gl.POINTS, 0, positions.length / 3);
    }
  }
}

function onXRFrame(time, frame) {
  if (!xrSession || !referenceSpace) {
    return;
  }

  xrSession.requestAnimationFrame(onXRFrame);

  const viewerPose = frame.getViewerPose(referenceSpace);

  if (gl && xrSession.renderState && xrSession.renderState.baseLayer) {
    gl.bindFramebuffer(gl.FRAMEBUFFER, xrSession.renderState.baseLayer.framebuffer);
    gl.clearColor(0, 0, 0, 0);
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
  }

  frameIndex += 1;
  updateFps();

  let handData;
  try {
    handData = extractHands(frame);
  } catch (error) {
    sendSessionEvent("frame_extract_failed", {
      frame_index: frameIndex,
      error_name: error.name,
      error: error.message,
    });
    setError(`Frame extraction failed: ${error.message}`);
    return;
  }

  const { hands, handInputSourceCount, jointCount, leftPresent, rightPresent } = handData;
  updateDebug({ joints: jointCount, left: leftPresent, right: rightPresent });
  if (viewerPose) {
    renderJointDots(frame, viewerPose, hands);
  }

  sendJson({
    type: "webxr_hand_frame",
    source: "visionpro_safari_webxr",
    client_time_ms: performance.now(),
    xr_predicted_display_time_ms: time,
    frame_index: frameIndex,
    client_fps_estimate: currentFpsEstimate,
    session_mode: sessionMode,
    reference_space: referenceSpaceName,
    input_source_count: xrSession.inputSources.length,
    hand_input_source_count: handInputSourceCount,
    viewer_pose: serializeViewerPose(viewerPose),
    hands: serializeHands(hands),
  });
}

function init() {
  els.wsUrl.value = defaultWsUrl();
  els.connectWsButton.addEventListener("click", connectWebSocket);
  els.startXrButton.addEventListener("click", startWebXR);
  els.stopButton.addEventListener("click", stopAll);
  updateDebug();
  checkWebXRSupport();
}

init();
