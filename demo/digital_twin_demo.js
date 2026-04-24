const mapStage = document.getElementById("mapStage");
const mapOverlay = document.getElementById("mapOverlay");
const offlineMap = document.getElementById("offlineMap");
const deviceList = document.getElementById("deviceList");
const wsStatus = document.getElementById("wsStatus");
const mapModeStatus = document.getElementById("mapModeStatus");
const mapHint = document.getElementById("mapHint");
const fpsStatus = document.getElementById("fpsStatus");
const latencyStatus = document.getElementById("latencyStatus");
const pipTemplate = document.getElementById("pipTemplate");
const basemapModeBtn = document.getElementById("basemapModeBtn");
const calibrationInput = document.getElementById("calibrationInput");
const applyCalibrationBtn = document.getElementById("applyCalibrationBtn");
const resetCalibrationBtn = document.getElementById("resetCalibrationBtn");

let mapIns = null;
let mapMode = "online";
let offlineBasemapSource = "";
let calibrationHomography = null;
const CALIBRATION_STORAGE_KEY = "digitalTwinOfflineCalibration";

const OFFLINE_BASEMAP_CANDIDATES = [
  "./assets/park_basemap.png",
  "./assets/park_basemap.jpg",
  "./assets/park_basemap.jpeg",
  "./assets/park_basemap.webp",
];

const facilities = [
  { id: "F-01", name: "东门泵站", type: "pump", lat: 22.54718, lng: 113.94488, w: 90, h: 68, desc: "提升泵组 2x75kW" },
  { id: "F-02", name: "中央冷站", type: "cooling", lat: 22.54678, lng: 113.94578, w: 100, h: 76, desc: "冷却塔 + 冷机群控" },
  { id: "F-03", name: "配电房A", type: "power", lat: 22.54702, lng: 113.94662, w: 86, h: 64, desc: "10kV 配电柜" },
  { id: "F-04", name: "污水处理区", type: "water", lat: 22.54632, lng: 113.94726, w: 114, h: 88, desc: "污水池 + 格栅井" },
  { id: "F-05", name: "安防围栏", type: "security", lat: 22.54596, lng: 113.94526, w: 70, h: 54, desc: "周界防入侵" },
];

const devices = [
  { deviceId: "D-1001", name: "东门泵站", lat: 22.54726, lng: 113.94498, state: "online", alarmLevel: "none", cameraId: "CAM-01" },
  { deviceId: "D-1002", name: "中央冷站", lat: 22.54674, lng: 113.94562, state: "online", alarmLevel: "none", cameraId: "CAM-02" },
  { deviceId: "D-1003", name: "配电房A", lat: 22.54698, lng: 113.94668, state: "online", alarmLevel: "none", cameraId: "CAM-03" },
  { deviceId: "D-1004", name: "污水井组", lat: 22.54622, lng: 113.94712, state: "offline", alarmLevel: "none", cameraId: "CAM-04" },
  { deviceId: "D-1005", name: "南侧围栏", lat: 22.54586, lng: 113.94538, state: "online", alarmLevel: "low", cameraId: "CAM-05" },
];

const pipWindows = new Map();
let zSeed = 10;
let isConnected = true;
let fpsFrame = 0;
let fpsLastTs = performance.now();
let fakeLatency = 120;
const offlineBounds = buildOfflineBounds();
const defaultCalibrationPoints = buildDefaultCalibrationPoints();

function renderMapNodes() {
  mapOverlay.innerHTML = "";
  if (mapMode === "online" && !mapIns) return;
  renderFacilities();
  renderRoads();
  devices.forEach((d) => {
    const pt = projectPoint(d.lat, d.lng);
    const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
    const cls = getNodeClass(d);
    g.innerHTML = `
      <circle class="device-node ${cls}" cx="${pt.x}" cy="${pt.y}" r="8.5" data-id="${d.deviceId}"></circle>
      <text x="${pt.x}" y="${pt.y + 18}" text-anchor="middle" fill="#dff0ff" font-size="11">${d.deviceId}</text>
    `;
    g.addEventListener("click", () => openPiP(d));
    mapOverlay.appendChild(g);
  });
}

function renderFacilities() {
  facilities.forEach((f) => {
    const pt = projectPoint(f.lat, f.lng);
    const scale = getFacilityScale();
    const w = f.w * scale;
    const h = f.h * scale;
    const x = pt.x - w / 2;
    const y = pt.y - h / 2;
    const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
    g.classList.add("facility");
    g.innerHTML = `
      <rect class="facility-rect ${f.type}" x="${x}" y="${y}" width="${w}" height="${h}" rx="6" ry="6"></rect>
      <rect class="facility-roof ${f.type}" x="${x + 8}" y="${y + 8}" width="${Math.max(16, w - 16)}" height="${Math.max(8, h * 0.16)}" rx="4" ry="4"></rect>
      <text class="facility-label" x="${pt.x}" y="${y + h + 16}" text-anchor="middle">${f.name}</text>
      <text class="facility-desc" x="${pt.x}" y="${y + h + 30}" text-anchor="middle">${f.desc}</text>
    `;
    mapOverlay.appendChild(g);
  });
}

function renderRoads() {
  const roads = [
    [
      [22.54752, 113.94440],
      [22.54744, 113.94755],
      [22.54578, 113.94745],
    ],
    [
      [22.54748, 113.94506],
      [22.54570, 113.94512],
    ],
    [
      [22.54706, 113.94600],
      [22.54618, 113.94720],
    ],
  ];
  roads.forEach((line) => {
    const d = line
      .map(([lat, lng], idx) => {
        if (mapMode === "offline") {
          const p = projectPoint(lat, lng);
          return `${idx === 0 ? "M" : "L"} ${p.x} ${p.y}`;
        }
        const pt = mapIns.latLngToContainerPoint([lat, lng]);
        return `${idx === 0 ? "M" : "L"} ${pt.x} ${pt.y}`;
      })
      .join(" ");
    const road = document.createElementNS("http://www.w3.org/2000/svg", "path");
    road.setAttribute("d", d);
    road.setAttribute("class", "road-line");
    mapOverlay.appendChild(road);
  });
}

function renderDeviceList() {
  deviceList.innerHTML = "";
  devices.forEach((d) => {
    const item = document.createElement("div");
    item.className = "device-item";
    item.innerHTML = `
      <span>${d.name}</span>
      <span class="state ${getNodeClass(d)}">${stateText(d)}</span>
    `;
    item.addEventListener("click", () => openPiP(d));
    deviceList.appendChild(item);
  });
}

function stateText(d) {
  if (d.alarmLevel === "high") return "高优告警";
  if (d.alarmLevel === "low") return "低优告警";
  return d.state === "online" ? "在线" : "离线";
}

function getNodeClass(d) {
  if (d.alarmLevel === "high") return "alarm-high";
  if (d.alarmLevel === "low") return "alarm-low";
  return d.state;
}

function openPiP(device) {
  if (pipWindows.has(device.deviceId)) {
    focusPiP(pipWindows.get(device.deviceId));
    return;
  }
  if (pipWindows.size >= 4) {
    const first = pipWindows.values().next().value;
    closePiP(first.dataset.id);
  }

  const node = pipTemplate.content.firstElementChild.cloneNode(true);
  node.dataset.id = device.deviceId;
  node.style.left = `${30 + pipWindows.size * 40}px`;
  node.style.top = `${30 + pipWindows.size * 30}px`;
  node.style.zIndex = ++zSeed;

  const title = node.querySelector(".pip-title");
  title.textContent = `${device.name} (${device.cameraId})`;
  const canvas = node.querySelector(".feed-canvas");
  startMockVideo(canvas, device.deviceId);

  bindDrag(node, node.querySelector(".pip-head"));
  bindResize(node, node.querySelector(".resize-handle"));
  bindPiPActions(node);

  mapStage.appendChild(node);
  pipWindows.set(device.deviceId, node);
}

function bindPiPActions(node) {
  const id = node.dataset.id;
  node.addEventListener("mousedown", () => focusPiP(node));
  node.querySelector(".close-btn").addEventListener("click", () => closePiP(id));
  node.querySelector(".top-btn").addEventListener("click", () => focusPiP(node));
  node.querySelector(".min-btn").addEventListener("click", () => {
    node.classList.toggle("minimized");
  });
}

function focusPiP(node) {
  node.style.zIndex = ++zSeed;
}

function closePiP(deviceId) {
  const node = pipWindows.get(deviceId);
  if (!node) return;
  node.remove();
  pipWindows.delete(deviceId);
}

function bindDrag(node, handle) {
  let dragging = false;
  let startX = 0;
  let startY = 0;
  let baseLeft = 0;
  let baseTop = 0;
  handle.addEventListener("mousedown", (e) => {
    dragging = true;
    startX = e.clientX;
    startY = e.clientY;
    baseLeft = node.offsetLeft;
    baseTop = node.offsetTop;
    focusPiP(node);
  });
  window.addEventListener("mousemove", (e) => {
    if (!dragging) return;
    const nextLeft = Math.max(0, Math.min(mapStage.clientWidth - node.offsetWidth, baseLeft + e.clientX - startX));
    const nextTop = Math.max(0, Math.min(mapStage.clientHeight - node.offsetHeight, baseTop + e.clientY - startY));
    node.style.left = `${nextLeft}px`;
    node.style.top = `${nextTop}px`;
  });
  window.addEventListener("mouseup", () => { dragging = false; });
}

function bindResize(node, handle) {
  let resizing = false;
  let startX = 0;
  let startY = 0;
  let baseW = 0;
  let baseH = 0;
  handle.addEventListener("mousedown", (e) => {
    e.stopPropagation();
    resizing = true;
    startX = e.clientX;
    startY = e.clientY;
    baseW = node.offsetWidth;
    baseH = node.offsetHeight;
    focusPiP(node);
  });
  window.addEventListener("mousemove", (e) => {
    if (!resizing) return;
    const width = Math.max(260, Math.min(700, baseW + e.clientX - startX));
    const height = Math.max(160, Math.min(500, baseH + e.clientY - startY));
    node.style.width = `${width}px`;
    node.style.height = `${height}px`;
  });
  window.addEventListener("mouseup", () => { resizing = false; });
}

function startMockVideo(canvas, seedText) {
  const ctx = canvas.getContext("2d");
  let tick = 0;
  function draw() {
    if (!canvas.isConnected) return;
    tick += 1;
    const t = tick / 15;
    ctx.fillStyle = "#071221";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    const x = (Math.sin(t) * 0.4 + 0.5) * canvas.width;
    const y = (Math.cos(t * 0.6) * 0.4 + 0.5) * canvas.height;
    const g = ctx.createRadialGradient(x, y, 10, x, y, 140);
    g.addColorStop(0, "rgba(0,255,200,0.9)");
    g.addColorStop(1, "rgba(0,80,120,0)");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "#d7efff";
    ctx.font = "16px sans-serif";
    ctx.fillText(`实时画面 ${seedText}`, 16, 24);
    ctx.fillText(new Date().toLocaleTimeString(), 16, 48);
    requestAnimationFrame(draw);
  }
  requestAnimationFrame(draw);
}

function setConnection(state) {
  isConnected = state;
  wsStatus.className = `badge ${state ? "ok" : "err"}`;
  wsStatus.textContent = state ? "数据通道：已连接" : "数据通道：断开";
}

function injectAlarm() {
  const target = devices[Math.floor(Math.random() * devices.length)];
  target.alarmLevel = "high";
  target.state = "online";
  renderMapNodes();
  renderDeviceList();
  openPiP(target);
  focusPiP(pipWindows.get(target.deviceId));
  setTimeout(() => {
    target.alarmLevel = "none";
    renderMapNodes();
    renderDeviceList();
  }, 7000);
}

function disconnectForTenSeconds() {
  if (!isConnected) return;
  setConnection(false);
  let sec = 10;
  wsStatus.className = "badge warn";
  wsStatus.textContent = `数据通道：重连中 ${sec}s`;
  const timer = setInterval(() => {
    sec -= 1;
    wsStatus.textContent = sec > 0 ? `数据通道：重连中 ${sec}s` : "数据通道：已连接";
    if (sec <= 0) {
      clearInterval(timer);
      setConnection(true);
    }
  }, 1000);
}

function bindActions() {
  basemapModeBtn.addEventListener("click", toggleBasemapMode);
  applyCalibrationBtn.addEventListener("click", applyCalibrationFromInput);
  resetCalibrationBtn.addEventListener("click", resetCalibrationToDefault);
  document.getElementById("alarmBtn").addEventListener("click", injectAlarm);
  document.getElementById("disconnectBtn").addEventListener("click", disconnectForTenSeconds);
  document.getElementById("closeAllBtn").addEventListener("click", () => {
    [...pipWindows.keys()].forEach((id) => closePiP(id));
  });
}

function startPerfPanel() {
  function loop(ts) {
    fpsFrame += 1;
    if (ts - fpsLastTs >= 1000) {
      const fps = Math.round((fpsFrame * 1000) / (ts - fpsLastTs));
      fpsStatus.textContent = `FPS: ${fps}`;
      fpsFrame = 0;
      fpsLastTs = ts;
      fakeLatency = isConnected ? Math.max(60, Math.min(220, fakeLatency + (Math.random() * 16 - 8))) : 999;
      latencyStatus.textContent = `延迟: ${Math.round(fakeLatency)} ms`;
    }
    requestAnimationFrame(loop);
  }
  requestAnimationFrame(loop);
}

function init() {
  initOfflineBasemap();
  initCalibrationPanel();
  initMap();
  window.addEventListener("resize", renderMapNodes);
  renderMapNodes();
  renderDeviceList();
  bindActions();
  startPerfPanel();
}

function initMap() {
  if (!window.L) {
    setMapMode("offline", true);
    return;
  }
  mapIns = L.map("realMap", {
    zoomControl: false,
    attributionControl: true,
  }).setView([22.54682, 113.94608], 17);

  L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
    maxZoom: 20,
    subdomains: "abcd",
  }).addTo(mapIns);

  mapIns.on("move zoom resize", renderMapNodes);
  setMapMode("online");
}

function initOfflineBasemap() {
  const params = new URLSearchParams(window.location.search);
  const customBasemap = params.get("offlineBasemap");
  const candidates = customBasemap
    ? [customBasemap, ...OFFLINE_BASEMAP_CANDIDATES]
    : OFFLINE_BASEMAP_CANDIDATES.slice();
  loadFirstAvailableImage(candidates);
}

function loadFirstAvailableImage(candidates) {
  if (!candidates.length) return;
  const [url, ...rest] = candidates;
  const image = new Image();
  image.onload = () => {
    offlineBasemapSource = url;
    offlineMap.style.setProperty("--offline-basemap-image", `url("${url}")`);
    offlineMap.classList.add("custom-basemap");
    if (mapMode === "offline") {
      updateMapHintAndStatus();
    }
  };
  image.onerror = () => {
    loadFirstAvailableImage(rest);
  };
  image.src = url;
}

function buildOfflineBounds() {
  const all = [...devices, ...facilities];
  const lats = all.map((i) => i.lat);
  const lngs = all.map((i) => i.lng);
  const padLat = 0.00028;
  const padLng = 0.00032;
  return {
    minLat: Math.min(...lats) - padLat,
    maxLat: Math.max(...lats) + padLat,
    minLng: Math.min(...lngs) - padLng,
    maxLng: Math.max(...lngs) + padLng,
  };
}

function buildDefaultCalibrationPoints() {
  return [
    { lat: offlineBounds.maxLat, lng: offlineBounds.minLng, x: 0.02, y: 0.02 },
    { lat: offlineBounds.maxLat, lng: offlineBounds.maxLng, x: 0.98, y: 0.02 },
    { lat: offlineBounds.minLat, lng: offlineBounds.maxLng, x: 0.98, y: 0.98 },
    { lat: offlineBounds.minLat, lng: offlineBounds.minLng, x: 0.02, y: 0.98 },
  ];
}

function initCalibrationPanel() {
  const saved = localStorage.getItem(CALIBRATION_STORAGE_KEY);
  let points = defaultCalibrationPoints;
  if (saved) {
    try {
      const parsed = JSON.parse(saved);
      if (Array.isArray(parsed) && parsed.length >= 4) {
        points = parsed;
      }
    } catch (_err) {
      points = defaultCalibrationPoints;
    }
  }
  calibrationInput.value = JSON.stringify(points, null, 2);
  updateCalibrationHomography(points);
}

function applyCalibrationFromInput() {
  try {
    const points = JSON.parse(calibrationInput.value);
    if (!Array.isArray(points) || points.length < 4) {
      throw new Error("至少提供4个标定点");
    }
    updateCalibrationHomography(points);
    localStorage.setItem(CALIBRATION_STORAGE_KEY, JSON.stringify(points));
    renderMapNodes();
    mapHint.textContent = "离线标定已应用：可继续微调 x/y 并再次点击应用标定";
  } catch (err) {
    mapHint.textContent = `离线标定失败：${err.message}`;
  }
}

function resetCalibrationToDefault() {
  calibrationInput.value = JSON.stringify(defaultCalibrationPoints, null, 2);
  localStorage.removeItem(CALIBRATION_STORAGE_KEY);
  updateCalibrationHomography(defaultCalibrationPoints);
  renderMapNodes();
  mapHint.textContent = "离线标定已恢复默认";
}

function updateCalibrationHomography(points) {
  const p = points.slice(0, 4).map((item) => ({
    lat: Number(item.lat),
    lng: Number(item.lng),
    x: Number(item.x),
    y: Number(item.y),
  }));
  if (p.some((i) => [i.lat, i.lng, i.x, i.y].some((v) => Number.isNaN(v)))) {
    throw new Error("标定点包含非数字值");
  }
  calibrationHomography = buildHomography(p);
}

function projectPoint(lat, lng) {
  if (mapMode === "online" && mapIns) {
    return mapIns.latLngToContainerPoint([lat, lng]);
  }
  const w = mapStage.clientWidth || 1;
  const h = mapStage.clientHeight || 1;
  if (calibrationHomography) {
    const p = applyHomography(calibrationHomography, lng, lat);
    return { x: p.x * w, y: p.y * h };
  }
  const px = ((lng - offlineBounds.minLng) / (offlineBounds.maxLng - offlineBounds.minLng)) * w;
  const py = ((offlineBounds.maxLat - lat) / (offlineBounds.maxLat - offlineBounds.minLat)) * h;
  return { x: px, y: py };
}

function getFacilityScale() {
  if (mapMode === "online" && mapIns) {
    return Math.max(0.55, Math.min(1.8, Math.pow(2, mapIns.getZoom() - 16)));
  }
  return 1;
}

function setMapMode(mode, autoFallback = false) {
  mapMode = mode;
  const isOffline = mode === "offline";
  mapStage.classList.toggle("offline", isOffline);
  updateMapHintAndStatus();
  basemapModeBtn.textContent = isOffline ? "切换到在线底图" : "切换到离线底图";
  if (autoFallback) {
    basemapModeBtn.disabled = true;
    basemapModeBtn.textContent = "离线底图（自动）";
  } else {
    basemapModeBtn.disabled = false;
  }
  renderMapNodes();
}

function updateMapHintAndStatus() {
  if (mapMode === "offline") {
    const hasCustom = !!offlineBasemapSource;
    mapModeStatus.textContent = hasCustom ? "底图：离线(本地图片)" : "底图：离线";
    mapHint.textContent = hasCustom
      ? `离线底图模式：已加载 ${offlineBasemapSource}`
      : "离线底图模式：断网可用，支持设备联动与 PiP 演示（可放置 ./assets/park_basemap.png）";
    return;
  }
  mapModeStatus.textContent = "底图：在线";
  mapHint.textContent = "真实底图模式：可缩放/拖拽地图，点击设备点位打开画中画";
}

function toggleBasemapMode() {
  if (mapMode === "online") {
    setMapMode("offline");
  } else if (window.L && mapIns) {
    setMapMode("online");
  }
}

function buildHomography(points) {
  const A = [];
  const b = [];
  points.forEach((p) => {
    const X = p.lng;
    const Y = p.lat;
    const x = p.x;
    const y = p.y;
    A.push([X, Y, 1, 0, 0, 0, -x * X, -x * Y]);
    b.push(x);
    A.push([0, 0, 0, X, Y, 1, -y * X, -y * Y]);
    b.push(y);
  });
  const h = solveLinearSystem(A, b);
  return { h11: h[0], h12: h[1], h13: h[2], h21: h[3], h22: h[4], h23: h[5], h31: h[6], h32: h[7] };
}

function applyHomography(H, X, Y) {
  const den = H.h31 * X + H.h32 * Y + 1;
  if (Math.abs(den) < 1e-12) return { x: 0.5, y: 0.5 };
  return {
    x: (H.h11 * X + H.h12 * Y + H.h13) / den,
    y: (H.h21 * X + H.h22 * Y + H.h23) / den,
  };
}

function solveLinearSystem(A, b) {
  const n = b.length;
  const M = A.map((row, i) => [...row, b[i]]);
  for (let col = 0; col < n; col += 1) {
    let pivot = col;
    for (let row = col + 1; row < n; row += 1) {
      if (Math.abs(M[row][col]) > Math.abs(M[pivot][col])) pivot = row;
    }
    if (Math.abs(M[pivot][col]) < 1e-12) throw new Error("标定点退化，请更换四点");
    [M[col], M[pivot]] = [M[pivot], M[col]];
    const div = M[col][col];
    for (let j = col; j <= n; j += 1) M[col][j] /= div;
    for (let row = 0; row < n; row += 1) {
      if (row === col) continue;
      const factor = M[row][col];
      for (let j = col; j <= n; j += 1) M[row][j] -= factor * M[col][j];
    }
  }
  return M.map((row) => row[n]);
}

init();
