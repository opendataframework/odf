// ── Constants ────────────────────────────────────────────────────────────

const TW = 80, TH = 48;   // tile width / height (diamond)
const TW2 = TW / 2, TH2 = TH / 2;

// Populated from CSS custom properties by readTheme() — see Theme section.
const ACCENT = {
  config: '', component: '', repository: '',
  service: '', task: '', pipeline: '', alert: '',
};

// Colors for the six built-in @Layer names, also populated from CSS custom
// properties by readTheme(). Deliberately a separate channel from a node's
// own customizable accent (ACCENT / node.color) — see layerColor() below.
const LAYER_DEFAULT_COLORS = {
  api: '', storage: '', analytics: '', messaging: '', monitoring: '', security: '',
};

const TYPE_LABEL = {
  config:'Config', component:'@Component', repository:'@Repository',
  service:'@Service', task:'@Task', pipeline:'@Pipeline',
};

// The map-panel mode each DataView kind opens into (see setMapMode below) —
// single source of truth shared by showDataView's dispatch and
// selectFromSidebar's "follow the new selection into the same view" logic.
const VIEW_MODE = {
  table: 'data', location: 'geo',
  'streaming-video': 'stream', 'streaming-audio': 'stream',
  video: 'media', audio: 'media',
  image: 'image', document: 'document', timeseries: 'timeseries',
};

// Icon geometry/draw registry is declared after the draw functions exist —
// see "Icon registry" below, near the end of the building-styles section.

// ── Data ──────────────────────────────────────────────────────────────────
// Populated from GET /api/topology on load — see Init section at the bottom.

let nodes = [];
let edges = [];
let nodeMap = {};
let repoSchemas = {};
let layoutOverrides = {}; // node id -> {col, row}, persisted via /api/layout

// User-added empty cells extending the grid past the auto-fit bounds derived
// from node positions — one count per edge of the isometric diamond (see the
// NE/SE/SW/NW corner math above computeGridBounds). Persisted under the
// reserved '_grid' key in layoutOverrides (node ids are kebab-case class
// names and can never collide with it).
let gridExpand = { nw: 0, ne: 0, se: 0, sw: 0 };

// ── Canvas ────────────────────────────────────────────────────────────────

const canvas = document.getElementById('canvas');
// `let`, not `const` — the icon picker's swatch renderer temporarily repoints
// this at a small offscreen canvas so it can reuse the same draw functions
// for thumbnails (see renderIconSwatch).
let ctx      = canvas.getContext('2d');
let CW = 0, CH = 0;

function resize() {
  const r = document.getElementById('map').getBoundingClientRect();
  CW = r.width; CH = r.height;
  const dpr = window.devicePixelRatio || 1;
  canvas.width  = Math.round(CW * dpr);
  canvas.height = Math.round(CH * dpr);
  canvas.style.width  = CW + 'px';
  canvas.style.height = CH + 'px';
  updateOrigin();
  closeInspectorPopup();
  vignetteDirty = true;
  render();
  if (mapMode === 'geo' && geoMap) geoMap.invalidateSize();
}

// ── Theme ─────────────────────────────────────────────────────────────────
// Colors live once, as CSS custom properties (see :root / [data-theme]).
// DOM elements read them directly via var(...). Canvas can't do that, so
// readTheme() mirrors the same properties into plain JS values on init and
// on every toggle.

let BG_CANVAS, TILE_FILL, TILE_STROKE, WIRE, WIRE_GLOW;
let LABEL_BG_RGB, LABEL_BG_ALPHA, VIGNETTE_RGB, VIGNETTE_ALPHA;
let TEXT_MUTED, TITLE_ACCENT;

function readTheme() {
  const s = getComputedStyle(document.documentElement);
  const v = name => s.getPropertyValue(name).trim();

  for (const k of Object.keys(ACCENT)) ACCENT[k] = v(`--accent-${k}`);
  for (const k of Object.keys(LAYER_DEFAULT_COLORS)) LAYER_DEFAULT_COLORS[k] = v(`--layer-${k}`);

  BG_CANVAS      = v('--bg-canvas');
  TILE_FILL      = v('--tile-fill');
  TILE_STROKE    = v('--tile-stroke');
  WIRE           = v('--wire');
  WIRE_GLOW      = v('--wire-glow');
  LABEL_BG_RGB   = v('--label-bg-rgb');
  LABEL_BG_ALPHA = v('--label-bg-alpha');
  VIGNETTE_RGB   = v('--vignette-rgb');
  VIGNETTE_ALPHA = v('--vignette-alpha');
  TEXT_MUTED     = v('--text-muted');
  TITLE_ACCENT   = v('--title-accent');

  if (THEME_STYLE.onReadTheme) THEME_STYLE.onReadTheme(v);
}

// Canvas drawing knobs a theme can't express in CSS. The values here are the
// default look; a theme's optional theme.js overrides any of them through
// ODF.registerTheme(). `part` is 'tile', 'face' or 'top'.
const THEME_STYLE = {
  emptyTileLine: 0.6,
  tickSize: 1,
  tileLine: lit => lit ? 1.1 : 0.8,
  faceLine: 0.8,
  topLine: lit => lit ? 1.3 : 1,
  // Shadow applied to the stroke of a lit shape.
  litShadow(part, accent) {
    ctx.shadowColor = accent;
    ctx.shadowBlur = { tile: 7, face: 9, top: 12.6 }[part];
  },
  // Optional (buildPath, part, sMul) => void: extra strokes drawn under a lit
  // shape's own stroke.
  litFringe: null,
  // Optional (v) => void, called at the end of readTheme() with its CSS
  // custom-property reader, for themes that mirror extra variables.
  onReadTheme: null,
};

// Strokes the outline of a tile or box face with the caller's strokeStyle and
// lineWidth, adding the theme's lit fringe and shadow, and leaves the shadow
// state reset so it can't leak into later drawing calls.
function strokeShape(buildPath, part, accent, lit, sMul = 1) {
  if (lit && THEME_STYLE.litFringe) {
    THEME_STYLE.litFringe(buildPath, part, sMul);
    buildPath();
  }
  if (lit) THEME_STYLE.litShadow(part, accent);
  ctx.stroke();
  ctx.shadowBlur = 0;
  ctx.shadowOffsetX = 0;
  ctx.shadowOffsetY = 0;
}

function updateThemeButton(theme) {
  const btn = document.getElementById('theme-toggle');
  btn.innerHTML = theme === 'dark'
    ? '<span class="glyph">&#9789;</span> Dark'
    : '<span class="glyph">&#9728;</span> Light';
}

function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('odf-ui-theme', theme);
  readTheme();
  updateThemeButton(theme);
  vignetteDirty = true;
  render();
  if (mapMode === 'geo') refreshGeoMap();
}

function initTheme() {
  const stored = localStorage.getItem('odf-ui-theme');
  const prefersLight = window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches;
  const theme = stored || (prefersLight ? 'light' : 'dark');
  document.documentElement.setAttribute('data-theme', theme);
  readTheme();
  updateThemeButton(theme);
}

// ── Layer colors ─────────────────────────────────────────────────────────
// A layer's badge color is resolved user override (persisted alongside the
// rest of the layout under the reserved '_layers' key, node ids being
// kebab-case class names that can never collide with it) → curated default
// for one of the six built-in layers → a deterministic hash-based hue, so a
// custom user-defined @Layer still gets a stable color across reloads
// without needing a predefined entry.
function hashHue(name) {
  let h = 0;
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) >>> 0;
  return h % 360;
}

function layerColor(name) {
  if (!name) return null;
  const override = layoutOverrides._layers && layoutOverrides._layers[name];
  if (override) return override;
  if (LAYER_DEFAULT_COLORS[name]) return LAYER_DEFAULT_COLORS[name];
  const light = document.documentElement.getAttribute('data-theme') === 'light';
  return `hsl(${hashHue(name)}, ${light ? 55 : 45}%, ${light ? 38 : 58}%)`;
}

// Shared markup for a layer's colored badge — used in both the inspector
// popup (selectNode) and the sidebar's layer group headers/rows.
function layerLabel(name) {
  return name.charAt(0).toUpperCase() + name.slice(1);
}

function layerBadgeHtml(name) {
  if (!name) return '';
  const c = layerColor(name);
  return `<span class="layer-badge" style="background:color-mix(in srgb, ${c} 16%, transparent);color:${c};border:var(--tag-border-width,1px) solid color-mix(in srgb, ${c} 45%, transparent);box-shadow:var(--tag-shadow,none)">${layerLabel(name)}</span>`;
}

// Persists a layer color override to /api/layout, alongside node positions
// and _grid — see saveLayoutOverride() for the sibling per-node version.
function saveLayerColor(name, hex) {
  if (!layoutOverrides._layers) layoutOverrides._layers = {};
  if (hex) layoutOverrides._layers[name] = hex;
  else delete layoutOverrides._layers[name];
  fetch('/api/layout', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(layoutOverrides),
  }).catch(err => console.error('Failed to save layer color', err));
}

// ── Camera (pan / zoom) ──────────────────────────────────────────────────
// World-space coords are whatever iso() returns; the camera is a separate
// translate+scale applied at draw time, so all scene math stays untouched.

let panX = 0, panY = 0, zoom = 1;
const ZOOM_MIN = 0.5, ZOOM_MAX = 2.5;

// Zoom by `factor`, keeping the world point under screen point (sx, sy) fixed.
function zoomAt(sx, sy, factor) {
  const newZoom = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, zoom * factor));
  if (newZoom === zoom) return;
  const wx = (sx - panX) / zoom;
  const wy = (sy - panY) / zoom;
  panX = sx - wx * newZoom;
  panY = sy - wy * newZoom;
  zoom = newZoom;
  closeInspectorPopup();
  updateCoordReadout(null);
}

function resetView() { panX = 0; panY = 0; zoom = 1; closeInspectorPopup(); updateCoordReadout(null); }

function screenToWorld(sx, sy) {
  return { x: (sx - panX) / zoom, y: (sy - panY) / zoom };
}

// ── Grid bounds & origin ─────────────────────────────────────────────────
// Node (col, row) positions come from the server's dependency-depth layout —
// unlike a hand-authored map, the grid size and center aren't known ahead of
// time, so they're derived from the loaded nodes on load, then widened by
// any user-added cells (see gridExpand/expandGrid below).

let GRID_MIN_COL = 0, GRID_MAX_COL = 0, GRID_MIN_ROW = 0, GRID_MAX_ROW = 0;
let ORIGIN_X = 0, ORIGIN_Y = 0;

function computeGridBounds() {
  if (!nodes.length) {
    GRID_MIN_COL = GRID_MAX_COL = GRID_MIN_ROW = GRID_MAX_ROW = 0;
  } else {
    GRID_MIN_COL = Math.min(...nodes.map(n => n.col));
    GRID_MAX_COL = Math.max(...nodes.map(n => n.col));
    GRID_MIN_ROW = Math.min(...nodes.map(n => n.row));
    GRID_MAX_ROW = Math.max(...nodes.map(n => n.row));
  }
  // Each direction extends exactly one straight edge of the diamond: the
  // corners are (MIN_COL,MIN_ROW)=top, (MAX_COL,MIN_ROW)=right,
  // (MAX_COL,MAX_ROW)=bottom, (MIN_COL,MAX_ROW)=left (see iso()), so e.g.
  // decreasing MIN_ROW pushes the top and right corners apart — the NE edge.
  GRID_MIN_COL -= gridExpand.nw;
  GRID_MIN_ROW -= gridExpand.ne;
  GRID_MAX_COL += gridExpand.se;
  GRID_MAX_ROW += gridExpand.sw;
}

// Grows the grid by one ring of cells along `dir` ('nw'|'ne'|'se'|'sw') and
// persists it — see gridExpand's declaration for the edge/direction mapping.
function expandGrid(dir) {
  gridExpand[dir] += 1;
  computeGridBounds();
  updateGridTitle();
  saveGridExpand();
  addLog(`Grid expanded (${dir.toUpperCase()}) — now ${GRID_MAX_COL - GRID_MIN_COL + 3}×${GRID_MAX_ROW - GRID_MIN_ROW + 3}`, TITLE_ACCENT);
}

function updateGridTitle() {
  document.getElementById('map-title').textContent =
    `Topology · Grid ${GRID_MAX_COL - GRID_MIN_COL + 3}×${GRID_MAX_ROW - GRID_MIN_ROW + 3}`;
}

function saveGridExpand() {
  layoutOverrides._grid = { ...gridExpand };
  fetch('/api/layout', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(layoutOverrides),
  }).catch(err => console.error('Failed to save grid size', err));
}

function updateOrigin() {
  const midCol = (GRID_MIN_COL + GRID_MAX_COL) / 2;
  const midRow = (GRID_MIN_ROW + GRID_MAX_ROW) / 2;
  ORIGIN_X = CW / 2 - (midCol - midRow) * TW2;
  ORIGIN_Y = CH / 2 - (midCol + midRow) * TH2;
}

// Isometric projection — returns CSS-pixel screen coords
function iso(col, row) {
  return {
    x: (col - row) * TW2 + ORIGIN_X,
    y: (col + row) * TH2 + ORIGIN_Y,
  };
}

// Inverse of iso() — nearest grid cell under a world-space point
function isoInverse(x, y) {
  const X = (x - ORIGIN_X) / TW2;
  const Y = (y - ORIGIN_Y) / TH2;
  return { col: Math.round((X + Y) / 2), row: Math.round((Y - X) / 2) };
}

function clamp(v, lo, hi) { return Math.min(hi, Math.max(lo, v)); }

// The node currently occupying (col, row), if any — excludes `exclude` so a
// dragged node doesn't collide with itself while hovering its own cell.
function nodeAtCell(col, row, exclude) {
  return nodes.find(n => n !== exclude && n.col === col && n.row === row) || null;
}

// ── Coordinate readout (bottom-left of map) ─────────────────────────────

const crCell = document.getElementById('cr-cell');
const crZoom = document.getElementById('cr-zoom');

function updateCoordReadout(cell) {
  if (cell) {
    crCell.textContent = `${String(cell.col).padStart(2,'0')}:${String(cell.row).padStart(2,'0')}`;
  }
  crZoom.textContent = `${Math.round(zoom * 100)}%`;
}

// ── Helpers ───────────────────────────────────────────────────────────────

function rgba(hex, a) {
  const r = parseInt(hex.slice(1,3),16);
  const g = parseInt(hex.slice(3,5),16);
  const b = parseInt(hex.slice(5,7),16);
  return `rgba(${r},${g},${b},${a})`;
}

function lerp(a, b, t) { return [a[0]+(b[0]-a[0])*t, a[1]+(b[1]-a[1])*t]; }

function hashSeed(s) {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h*31 + s.charCodeAt(i)) >>> 0;
  return (h % 1000) / 1000;
}

function tilePath(sx, sy) {
  ctx.beginPath();
  ctx.moveTo(sx,       sy - TH2);
  ctx.lineTo(sx + TW2, sy);
  ctx.lineTo(sx,       sy + TH2);
  ctx.lineTo(sx - TW2, sy);
  ctx.closePath();
}

function drawEmptyTile(sx, sy) {
  tilePath(sx, sy);
  ctx.fillStyle   = TILE_FILL;
  ctx.fill();
  ctx.strokeStyle = TILE_STROKE;
  ctx.lineWidth   = THEME_STYLE.emptyTileLine;
  ctx.stroke();

  // blueprint tick at tile center
  const tick = THEME_STYLE.tickSize;
  ctx.fillStyle = TILE_STROKE;
  ctx.fillRect(sx - tick / 2, sy - tick / 2, tick, tick);
}

function drawOccupiedTile(sx, sy, accent, lit) {
  const path = () => tilePath(sx, sy);
  path();
  ctx.fillStyle = rgba(accent, lit ? 0.09 : 0.04);
  ctx.fill();
  ctx.strokeStyle = rgba(accent, lit ? 0.75 : 0.35);
  ctx.lineWidth = THEME_STYLE.tileLine(lit);
  strokeShape(path, 'tile', accent, lit);
}

// ── Base building primitive (a box, footprint scaled per type) ────────────

// Generalized isometric box: independent width/depth half-extents (rather
// than one shared `scale`) so it can be reused to build compound objects —
// a body with a smaller box stacked or docked onto it — instead of only
// ever drawing the single ground-footprint pad. `drawBox` below is the
// pad-shaped special case used throughout as the tile-occupancy footprint.
function isoBox(sx, sy, w2, h2, bh, accent, lit, opts = {}) {
  const fMul = opts.fillAlpha ?? 1;
  const sMul = opts.strokeAlpha ?? 1;

  // ── Right face ──
  const rightFace = () => {
    ctx.beginPath();
    ctx.moveTo(sx + w2, sy - bh);
    ctx.lineTo(sx + w2, sy);
    ctx.lineTo(sx,      sy + h2);
    ctx.lineTo(sx,      sy + h2 - bh);
    ctx.closePath();
  };
  rightFace();
  ctx.fillStyle   = rgba(accent, 0.05 * fMul);
  ctx.fill();
  ctx.strokeStyle = rgba(accent, (lit ? 0.55 : 0.35) * sMul);
  ctx.lineWidth   = THEME_STYLE.faceLine;
  strokeShape(rightFace, 'face', accent, lit, sMul);

  // ── Left face ──
  const leftFace = () => {
    ctx.beginPath();
    ctx.moveTo(sx - w2, sy - bh);
    ctx.lineTo(sx - w2, sy);
    ctx.lineTo(sx,      sy + h2);
    ctx.lineTo(sx,      sy + h2 - bh);
    ctx.closePath();
  };
  leftFace();
  ctx.fillStyle   = rgba(accent, 0.08 * fMul);
  ctx.fill();
  ctx.strokeStyle = rgba(accent, (lit ? 0.65 : 0.4) * sMul);
  ctx.lineWidth   = THEME_STYLE.faceLine;
  strokeShape(leftFace, 'face', accent, lit, sMul);

  // ── Top face ──
  const topFace = () => {
    ctx.beginPath();
    ctx.moveTo(sx,      sy - h2 - bh);
    ctx.lineTo(sx + w2, sy      - bh);
    ctx.lineTo(sx,      sy + h2 - bh);
    ctx.lineTo(sx - w2, sy      - bh);
    ctx.closePath();
  };
  topFace();
  ctx.fillStyle   = rgba(accent, (lit ? 0.16 : 0.1) * fMul);
  ctx.fill();
  ctx.strokeStyle = rgba(accent, (lit ? 1.0 : 0.6) * sMul);
  ctx.lineWidth   = THEME_STYLE.topLine(lit);
  strokeShape(topFace, 'top', accent, lit, sMul);

  return { w2, h2, topY: sy - bh };
}

function drawBox(sx, sy, bh, accent, lit, scale = 1) {
  return isoBox(sx, sy, TW2 * scale, TH2 * scale, bh, accent, lit);
}

// Flattened ellipse for round parts that sit on a horizontal, ground-parallel
// plane — wheels, rotor discs, a lens, a dish — axis-scaled by `squash` so it
// reads as "round" under the same diamond projection as the tile grid.
function isoDisc(cx, cy, rx, accent, lit, opts = {}) {
  const ry = rx * (opts.squash ?? (TH2 / TW2));
  ctx.save();
  ctx.beginPath();
  ctx.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2);
  ctx.fillStyle = rgba(accent, opts.fillAlpha ?? (lit ? 0.3 : 0.2));
  if (lit) { ctx.shadowColor = accent; ctx.shadowBlur = opts.glow ?? 4; }
  ctx.fill();
  ctx.strokeStyle = rgba(accent, opts.strokeAlpha ?? (lit ? 0.95 : 0.8));
  ctx.lineWidth = opts.lineWidth ?? 1.3;
  ctx.stroke();
  ctx.restore();
}

// ── Per-type building styles ────────────────────────────────────────────

// Config → flat glowing platform (base layer)
function drawConfigPlatform(sx, sy, accent, lit) {
  const bh = 8;
  drawBox(sx, sy, bh, accent, lit, 1);
  const pulse = (Math.sin(animT * 2) + 1) / 2;
  ctx.save();
  ctx.beginPath();
  ctx.ellipse(sx, sy - bh - 2, TW2 * 0.55, TH2 * 0.4 * (0.85 + 0.15 * pulse), 0, 0, Math.PI * 2);
  ctx.strokeStyle = rgba(accent, 0.2 + 0.3 * pulse);
  ctx.lineWidth = 1;
  ctx.shadowColor = accent;
  ctx.shadowBlur = 5 + 4 * pulse;
  ctx.stroke();
  ctx.restore();
}

// @Component → wide low warehouse (gabled roof ridge)
function drawWarehouse(sx, sy, accent, lit) {
  const bh = 34;
  const { h2 } = drawBox(sx, sy, bh, accent, lit, 1.15);
  ctx.save();
  ctx.beginPath();
  ctx.moveTo(sx, sy - h2 - bh);
  ctx.lineTo(sx, sy + h2 - bh);
  ctx.strokeStyle = rgba(accent, lit ? 0.9 : 0.5);
  ctx.lineWidth = lit ? 1.3 : 1;
  if (lit) { ctx.shadowColor = accent; ctx.shadowBlur = 5; }
  ctx.stroke();
  ctx.restore();
}

// @Repository → tall server rack (rack-unit lines + blinking status light)
function drawServerRack(sx, sy, accent, lit) {
  const bh = 74;
  const scale = 0.55;
  const { w2 } = drawBox(sx, sy, bh, accent, lit, scale);
  const rTop = [[sx + w2, sy - bh], [sx, sy + TH2 * scale - bh]];
  const rBot = [[sx + w2, sy],      [sx, sy + TH2 * scale]];
  const n = 5;
  ctx.save();
  ctx.strokeStyle = rgba(accent, lit ? 0.5 : 0.25);
  ctx.lineWidth = 0.7;
  for (let i = 1; i < n; i++) {
    const t = i / n;
    const p1 = lerp(rTop[0], rBot[0], t);
    const p2 = lerp(rTop[1], rBot[1], t);
    ctx.beginPath();
    ctx.moveTo(p1[0], p1[1]);
    ctx.lineTo(p2[0], p2[1]);
    ctx.stroke();
  }
  ctx.restore();

  const blink = (Math.sin(animT * 6 + sx) + 1) / 2 > 0.5;
  ctx.save();
  ctx.beginPath();
  ctx.arc(sx + w2 * 0.55, sy - bh * 0.85, 1.6, 0, Math.PI * 2);
  ctx.fillStyle = blink ? ACCENT.task : rgba(ACCENT.task, 0.15);
  if (blink) { ctx.shadowColor = ACCENT.task; ctx.shadowBlur = 4; }
  ctx.fill();
  ctx.restore();
}

// @Service → antenna tower (tapered mast + blinking tip light + guy wires)
function drawAntennaTower(sx, sy, accent, lit) {
  const bh = 56;
  const { h2 } = drawBox(sx, sy, bh, accent, lit, 0.5);
  const mastTop = sy - h2 - bh;
  const tipY = mastTop - 30;

  ctx.save();
  ctx.strokeStyle = rgba(accent, lit ? 0.9 : 0.5);
  ctx.lineWidth = 1;
  if (lit) { ctx.shadowColor = accent; ctx.shadowBlur = 5; }
  ctx.beginPath();
  ctx.moveTo(sx, mastTop);
  ctx.lineTo(sx, tipY);
  ctx.stroke();

  ctx.lineWidth = 0.6;
  ctx.strokeStyle = rgba(accent, 0.25);
  ctx.beginPath(); ctx.moveTo(sx, tipY + 10); ctx.lineTo(sx - 14, sy - bh * 0.3); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(sx, tipY + 10); ctx.lineTo(sx + 14, sy - bh * 0.3); ctx.stroke();
  ctx.restore();

  const pulse = (Math.sin(animT * 4) + 1) / 2;
  ctx.save();
  ctx.beginPath();
  ctx.arc(sx, tipY, 2, 0, Math.PI * 2);
  ctx.fillStyle = ACCENT.alert;
  ctx.shadowColor = ACCENT.alert;
  ctx.shadowBlur = 4 + 4 * pulse;
  ctx.fill();
  ctx.restore();
}

// @Task → small factory cube (chimney + rising smoke)
function drawFactoryCube(sx, sy, accent, lit) {
  const bh = 30;
  const { w2, h2 } = drawBox(sx, sy, bh, accent, lit, 0.8);
  const cx = sx - w2 * 0.35, cBase = sy - h2 * 0.2 - bh, cH = 16, cw = 5;

  ctx.save();
  ctx.fillStyle = rgba(accent, 0.12);
  ctx.strokeStyle = rgba(accent, lit ? 0.7 : 0.4);
  ctx.lineWidth = 0.8;
  ctx.beginPath();
  ctx.rect(cx - cw / 2, cBase - cH, cw, cH);
  ctx.fill();
  ctx.stroke();
  ctx.restore();

  for (let i = 0; i < 3; i++) {
    const phase = (animT * 0.5 + i / 3) % 1;
    const py = cBase - cH - phase * 18;
    const alpha = (1 - phase) * 0.3;
    ctx.save();
    ctx.beginPath();
    ctx.arc(cx + Math.sin(phase * 6 + i) * 2, py, 2 + phase * 2, 0, Math.PI * 2);
    ctx.fillStyle = rgba(accent, alpha);
    ctx.fill();
    ctx.restore();
  }
}

// @Pipeline → conveyor belt pad (moving diagonal tread)
function drawConveyorPad(sx, sy, accent, lit) {
  const bh = 10;
  const { w2, h2 } = drawBox(sx, sy, bh, accent, lit, 1);
  ctx.save();
  ctx.beginPath();
  ctx.moveTo(sx,      sy - h2 - bh);
  ctx.lineTo(sx + w2, sy      - bh);
  ctx.lineTo(sx,      sy + h2 - bh);
  ctx.lineTo(sx - w2, sy      - bh);
  ctx.closePath();
  ctx.clip();
  ctx.strokeStyle = rgba(accent, lit ? 0.5 : 0.28);
  ctx.lineWidth = 2.2;
  const shift = (animT * 10) % 16;
  for (let i = -4; i <= 4; i++) {
    const off = i * 8 + shift;
    ctx.beginPath();
    ctx.moveTo(sx - w2 + off,          sy - bh - h2);
    ctx.lineTo(sx - w2 + off + h2*1.6, sy - bh + h2);
    ctx.stroke();
  }
  ctx.restore();
}

// ── Icon registry ──────────────────────────────────────────────────────────
// One entry per selectable icon shape. The six below are the exec-type
// defaults (drawn when a node has no `icon` override — see iconKey() below).
// Every other built-in icon is purely user-selectable, assignable to any node
// regardless of exec type, and lives in its group's file under icons/,
// registering itself through ODF.registerIcon once this script has run.
//
// bh/scale    — base box height / footprint scale, matching each draw fn
// extraTop    — anything drawn above the box (antenna, dish, wings…), added
//               to derive topExtent for label placement & hit testing
// draw        — renders the icon at (sx, sy) with the given accent/lit state
// label       — swatch tooltip / accessible name in the icon picker
// group       — the icon picker tab the swatch is listed under
const ICONS = {
  config:     { draw: drawConfigPlatform, bh: 8,  scale: 1,    extraTop: 0,  label: 'Config platform',         group: 'Defaults' },
  component:  { draw: drawWarehouse,      bh: 34, scale: 1.15, extraTop: 6,  label: '@Component warehouse',    group: 'Defaults' },
  repository: { draw: drawServerRack,     bh: 74, scale: 0.55, extraTop: 0,  label: '@Repository server rack', group: 'Defaults' },
  service:    { draw: drawAntennaTower,   bh: 56, scale: 0.5,  extraTop: 34, label: '@Service antenna',        group: 'Defaults' },
  task:       { draw: drawFactoryCube,    bh: 30, scale: 0.8,  extraTop: 20, label: '@Task factory cube',      group: 'Defaults' },
  pipeline:   { draw: drawConveyorPad,    bh: 10, scale: 1,    extraTop: 0,  label: '@Pipeline conveyor',      group: 'Defaults' },
};
// Derives the label placement/hit-testing extents for one ICONS entry —
// shared by the built-in postprocessing pass below and by ODF.registerIcon
// (see "Icon/color extension hook") so a custom icon gets the same treatment
// as a built-in one.
function finalizeIconEntry(key) {
  const e = ICONS[key];
  e.topExtent   = e.bh + TH2 * e.scale + e.extraTop;
  e.widthExtent = TW2 * e.scale;
}
for (const key in ICONS) finalizeIconEntry(key);

// Resolves which registry entry to draw for a node: its icon override, or
// its exec-type default. Falls back to the type default if the stored icon
// key is unrecognized (e.g. stale after a future rename), so render() and
// friends never index the registry with an unknown key.
function iconKey(node) {
  const key = node.icon || node.type;
  return ICONS[key] ? key : node.type;
}

// Curated swatch palette for the color picker — distinct from the 6 exec-type
// accent hues so a custom color reads as deliberately "custom," and chosen to
// stay legible against both the dark and light tile/wire backgrounds. Each
// entry is {hex, label} — built-ins have no meaningful name so their label
// is just the hex itself (matching the picker's existing hex tooltip);
// entries registered via loadUiExtensions() get a real label.
const COLOR_SWATCHES = [
  '#e05d5d', '#e0975d', '#e0c85d', '#a3d15c',
  '#5ccf8f', '#4fc4c4', '#5aa8e0', '#7a8ce0',
  '#a35de0', '#e05dbf', '#c9c9c9', '#8a97a6',
].map(hex => ({ hex, label: hex }));

// ── Icon/color extension hook ───────────────────────────────────────────
// Called by the built-in icon group files under icons/ (plain <script> tags
// after this one) and by custom .js files that loadUiExtensions() (see Init
// section) loads — those registered server-side via
// odf.ui.extensions.register_icon_script, either by a framework-extension
// package (Python, import time) or by [ui] icon-scripts in config.toml. Each
// file calls ODF.registerIcon(key, draw, meta) at its top level, same
// signature/shared primitives (drawBox, isoBox, isoDisc, rgba, ctx, animT,
// plus ODF.iconKit from icons/shared.js) as every draw function above, so a
// custom icon renders at the same fidelity as a built-in one. `meta.group`
// names the icon picker tab it's listed under — 'Custom' unless given.
window.ODF = {
  registerIcon(key, draw, meta = {}) {
    ICONS[key] = { draw, bh: 0, scale: 1, extraTop: 0, label: key, group: 'Custom', ...meta };
    finalizeIconEntry(key);
  },
  // Called by a theme's optional theme.js to override THEME_STYLE entries.
  registerTheme(overrides) {
    Object.assign(THEME_STYLE, overrides);
    readTheme();
    vignetteDirty = true;
  },
};

// Resolves a node's effective accent color for canvas drawing: its color
// override, or its exec-type default. ACCENT is already a literal hex string
// (refreshed by readTheme() on every theme toggle), so this stays correct
// across themes without any extra bookkeeping.
function nodeAccent(node) {
  return node.color || ACCENT[node.type];
}

// Resolves a node's effective accent color for DOM `style="color:...` use.
// Uncustomized nodes keep the live CSS var reference so they keep repainting
// for free on theme toggle (matching today's behavior); only a node with an
// explicit override gets pinned to a literal value.
function nodeAccentCss(node) {
  return node.color || `var(--accent-${node.type})`;
}

// ── Edges — grid-aligned wires with a traveling glow pulse ────────────────

function edgePath(fromNode, toNode) {
  const f = iso(fromNode.col, fromNode.row);
  const bend = iso(toNode.col, fromNode.row);
  const t = iso(toNode.col, toNode.row);
  return [[f.x, f.y], [bend.x, bend.y], [t.x, t.y]];
}

function drawEdge(fromNode, toNode, dashed) {
  const pts = edgePath(fromNode, toNode);
  const c = dashed ? ACCENT.alert : WIRE;
  const g = dashed ? ACCENT.alert : WIRE_GLOW;

  ctx.save();
  ctx.shadowColor = g;
  ctx.shadowBlur  = dashed ? 5 : 3;
  ctx.beginPath();
  ctx.moveTo(pts[0][0], pts[0][1]);
  for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i][0], pts[i][1]);
  ctx.strokeStyle = c;
  ctx.lineWidth   = dashed ? 1.1 : 1.3;
  ctx.setLineDash(dashed ? [5,3] : []);
  ctx.stroke();
  ctx.restore();
  ctx.setLineDash([]);

  // bend joint
  const bx = pts[1][0], by = pts[1][1];
  if ((bx !== pts[0][0] || by !== pts[0][1]) && (bx !== pts[2][0] || by !== pts[2][1])) {
    ctx.save();
    ctx.beginPath();
    ctx.arc(bx, by, 1.4, 0, Math.PI * 2);
    ctx.fillStyle = rgba(dashed ? ACCENT.alert : ACCENT.service, 0.5);
    ctx.fill();
    ctx.restore();
  }

  // traveling pulse, colored by destination node
  const accent = nodeAccent(toNode);
  const segLens = [];
  let total = 0;
  for (let i = 1; i < pts.length; i++) {
    const l = Math.hypot(pts[i][0] - pts[i-1][0], pts[i][1] - pts[i-1][1]);
    segLens.push(l);
    total += l;
  }
  if (total > 0.5) {
    const speed = 55;
    const seed = hashSeed(fromNode.id + toNode.id) * total;
    let d = (animT * speed + seed) % total;
    let px = pts[0][0], py = pts[0][1];
    for (let i = 0; i < segLens.length; i++) {
      if (d <= segLens[i]) {
        const t = segLens[i] === 0 ? 0 : d / segLens[i];
        px = pts[i][0] + (pts[i+1][0] - pts[i][0]) * t;
        py = pts[i][1] + (pts[i+1][1] - pts[i][1]) * t;
        break;
      }
      d -= segLens[i];
    }
    ctx.save();
    ctx.beginPath();
    ctx.arc(px, py, 1.6, 0, Math.PI * 2);
    ctx.fillStyle = accent;
    ctx.shadowColor = accent;
    ctx.shadowBlur = 5;
    ctx.fill();
    ctx.restore();
  }
}

function drawLabel(node, sx, sy, lit) {
  const accent = nodeAccent(node);
  const ly = sy - ICONS[iconKey(node)].topExtent - 8;
  const text = node.label.toUpperCase();

  ctx.save();
  ctx.textAlign    = 'center';
  ctx.textBaseline = 'bottom';
  ctx.font         = `${lit ? 'bold ' : ''}9.5px 'SF Mono', 'Courier New', monospace`;

  let tw = 0;
  if (lit) {
    tw = ctx.measureText(text).width + 12;
    ctx.fillStyle   = `rgba(${LABEL_BG_RGB},${LABEL_BG_ALPHA})`;
    ctx.strokeStyle = rgba(accent, 0.55);
    ctx.lineWidth   = 0.8;
    ctx.beginPath();
    ctx.rect(sx - tw/2, ly - 13, tw, 15);
    ctx.fill();
    ctx.stroke();
    ctx.shadowColor = accent;
    ctx.shadowBlur  = 6;
  }

  ctx.fillStyle = lit ? accent : rgba(accent, 0.45);
  ctx.fillText(text, sx, ly);

  // Layer badge — a small dot pinned to the label chip's corner, shown only
  // while hovered/selected/dragged (not permanently on the tile) so the
  // grid stays uncluttered; separate color channel from the node's own
  // accent, see layerColor().
  if (lit && node.layer) {
    ctx.shadowBlur = 0;
    ctx.beginPath();
    ctx.arc(sx + tw/2, ly - 13, 3.5, 0, Math.PI * 2);
    ctx.fillStyle = layerColor(node.layer);
    ctx.fill();
    ctx.lineWidth = 1;
    ctx.strokeStyle = BG_CANVAS;
    ctx.stroke();
  }

  ctx.restore();
}

// ── Render ────────────────────────────────────────────────────────────────

let hoverId = null, selectId = null;
let animT = 0;

// Sort order for painter's algorithm (back → front) and a col,row → node
// lookup. Both only need rebuilding when a node's grid position actually
// changes (init/layout-load, drag), so `layoutDirty` gates that work instead
// of redoing a sort + hashmap allocation on every animation frame.
let byDepth = [];
let layoutDirty = true;
let nodeAtTileCache = {};

// Vignette is fixed to the viewport and only depends on canvas size / theme
// colors, so it's rebuilt on resize/theme-change (`vignetteDirty`) rather
// than reallocated every frame.
let vignetteGradient = null;
let vignetteDirty = true;

function render() {
  const dpr = window.devicePixelRatio || 1;

  if (layoutDirty) {
    byDepth.sort((a, b) => (a.col + a.row) - (b.col + b.row));
    nodeAtTileCache = Object.fromEntries(nodes.map(n => [`${n.col},${n.row}`, n]));
    layoutDirty = false;
  }
  const nodeAtTile = nodeAtTileCache;

  // Reset to device pixels and clear/fill the full viewport
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, CW, CH);
  ctx.fillStyle = BG_CANVAS;
  ctx.fillRect(0, 0, CW, CH);

  // Apply camera (pan/zoom) for all world-space scene content
  ctx.setTransform(dpr * zoom, 0, 0, dpr * zoom, dpr * panX, dpr * panY);

  // World-space visible bounds (viewport rect run back through the camera),
  // padded enough to cover tall buildings/labels near the edge.
  const margin = 260;
  const viewL = -panX / zoom - margin,      viewR = (CW - panX) / zoom + margin;
  const viewT = -panY / zoom - margin,      viewB = (CH - panY) / zoom + margin;

  // 1 — Grid tiles (drawn with a one-tile empty border around the loaded nodes)
  for (let c = GRID_MIN_COL - 1; c <= GRID_MAX_COL + 1; c++) {
    for (let r = GRID_MIN_ROW - 1; r <= GRID_MAX_ROW + 1; r++) {
      const {x, y} = iso(c, r);
      if (x < viewL || x > viewR || y < viewT || y > viewB) continue;
      const key  = `${c},${r}`;
      const node = nodeAtTile[key];
      if (node) {
        const lit = node.id === hoverId || node.id === selectId || node === dragNode;
        drawOccupiedTile(x, y, nodeAccent(node), lit);
      } else {
        drawEmptyTile(x, y);
      }
    }
  }

  // 1.5 — Drop-target ring for the node currently being dragged
  if (dragNode) {
    const {x, y} = iso(dragNode.col, dragNode.row);
    const ok = !nodeAtCell(dragNode.col, dragNode.row, dragNode);
    const ringColor = ok ? ACCENT.task : ACCENT.alert;
    tilePath(x, y);
    ctx.save();
    ctx.strokeStyle = ringColor;
    ctx.lineWidth = 1.6;
    ctx.shadowColor = ringColor;
    ctx.shadowBlur = 7;
    ctx.stroke();
    ctx.restore();
  }

  // 2 — Edges (grid-aligned wires, drawn at ground level, behind buildings)
  for (const e of edges) {
    drawEdge(nodeMap[e.from], nodeMap[e.to], e.dashed || false);
  }

  // 3 — Buildings (back to front, per-type silhouette)
  for (const node of byDepth) {
    const {x, y} = iso(node.col, node.row);
    if (x < viewL || x > viewR || y < viewT || y > viewB) continue;
    const lit = node.id === hoverId || node.id === selectId || node === dragNode;
    ICONS[iconKey(node)].draw(x, y, nodeAccent(node), lit);
  }

  // 4 — Labels (always on top)
  for (const node of byDepth) {
    const {x, y} = iso(node.col, node.row);
    if (x < viewL || x > viewR || y < viewT || y > viewB) continue;
    const lit = node.id === hoverId || node.id === selectId || node === dragNode;
    drawLabel(node, x, y, lit);
  }

  // 5 — Vignette (fixed to the viewport, unaffected by pan/zoom)
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  if (vignetteDirty || !vignetteGradient) {
    const vg = ctx.createRadialGradient(CW/2, CH/2, CH*0.25, CW/2, CH/2, CH*0.8);
    vg.addColorStop(0, 'transparent');
    vg.addColorStop(1, `rgba(${VIGNETTE_RGB},${VIGNETTE_ALPHA})`);
    vignetteGradient = vg;
    vignetteDirty = false;
  }
  ctx.fillStyle = vignetteGradient;
  ctx.fillRect(0, 0, CW, CH);
}

// ── Hit detection ─────────────────────────────────────────────────────────

function hitTest(mx, my) {
  // front-to-back order
  for (let i = byDepth.length - 1; i >= 0; i--) {
    const node = byDepth[i];
    const {x, y} = iso(node.col, node.row);
    const ic = ICONS[iconKey(node)], te = ic.topExtent, we = ic.widthExtent;
    if (mx >= x - we - 2 && mx <= x + we + 2 &&
        my >= y - te - 2 && my <= y + TH2 + 2) {
      return node.id;
    }
  }
  return null;
}

// ── Interaction ────────────────────────────────────────────────────────────
// Mousedown on empty grid: drag to pan. Mousedown on a building: drag it to
// a different cell (snapping live to the grid; drop on an occupied cell and
// it reverts). Either way, a click with no real movement just selects.
// Scroll/pinch zooms toward the cursor.

let isDragging = false, dragMoved = false;
let dragStart = { x: 0, y: 0 }, panStart = { x: 0, y: 0 };
let dragNode = null, dragOrigin = null;

function canvasPoint(e) {
  const r = canvas.getBoundingClientRect();
  return { x: e.clientX - r.left, y: e.clientY - r.top };
}

canvas.addEventListener('mousedown', e => {
  e.preventDefault();
  const p = canvasPoint(e);
  const w = screenToWorld(p.x, p.y);
  const hit = hitTest(w.x, w.y);

  dragStart  = p;
  isDragging = true;
  dragMoved  = false;

  if (hit) {
    dragNode   = nodeMap[hit];
    dragOrigin = { col: dragNode.col, row: dragNode.row };
  } else {
    dragNode  = null;
    panStart  = { x: panX, y: panY };
    closeInspectorPopup();
  }
  canvas.style.cursor = 'grabbing';
});

canvas.addEventListener('mousemove', e => {
  const p = canvasPoint(e);
  const w = screenToWorld(p.x, p.y);
  updateCoordReadout(isoInverse(w.x, w.y));
  if (isDragging) return; // dragging/panning is driven by the window listener below
  const hit = hitTest(w.x, w.y);
  if (hit !== hoverId) {
    hoverId = hit;
    canvas.style.cursor = hit ? 'pointer' : 'grab';
  }
});

window.addEventListener('mousemove', e => {
  if (!isDragging) return;
  const p = canvasPoint(e);
  const dx = p.x - dragStart.x, dy = p.y - dragStart.y;
  if (Math.abs(dx) > 3 || Math.abs(dy) > 3) dragMoved = true;

  if (dragNode) {
    if (!dragMoved) return; // require a small nudge before lifting the building
    const w = screenToWorld(p.x, p.y);
    const cell = isoInverse(w.x, w.y);
    dragNode.col = clamp(cell.col, GRID_MIN_COL - 1, GRID_MAX_COL + 1);
    dragNode.row = clamp(cell.row, GRID_MIN_ROW - 1, GRID_MAX_ROW + 1);
    updateCoordReadout({ col: dragNode.col, row: dragNode.row });
    layoutDirty = true;
  } else {
    panX = panStart.x + dx;
    panY = panStart.y + dy;
  }
});

window.addEventListener('mouseup', e => {
  if (!isDragging) return;
  isDragging = false;

  const node = dragNode;
  dragNode = null;

  if (node) {
    if (dragMoved) {
      if (nodeAtCell(node.col, node.row, node)) {
        node.col = dragOrigin.col;
        node.row = dragOrigin.row;
        layoutDirty = true;
        addLog(`${node.label} — cell occupied, move reverted`, ACCENT.alert);
      } else {
        addLog(`${node.label} moved to (${node.col}, ${node.row})`, nodeAccent(node));
        saveLayoutOverride(node);
      }
    }
    selectNode(node.id);
  }

  const p = canvasPoint(e);
  const w = screenToWorld(p.x, p.y);
  const hit = hitTest(w.x, w.y);
  if (!node && !dragMoved) selectNode(hit);
  hoverId = hit;
  canvas.style.cursor = hit ? 'pointer' : 'grab';
});

// Persists a committed drag-move to /api/layout so it survives a page
// refresh — see the layoutOverrides fetch/apply in init(). Best-effort: a
// failed PUT just leaves the previous save in place server-side, so the
// move still holds for the rest of this session even if it isn't persisted.
function saveLayoutOverride(node) {
  const entry = { col: node.col, row: node.row };
  if (node.icon) entry.icon = node.icon; // omitted entirely once reset, so it doesn't linger as a stale key
  if (node.color) entry.color = node.color; // ditto for a reset color override
  layoutOverrides[node.id] = entry;
  fetch('/api/layout', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(layoutOverrides),
  }).catch(err => console.error('Failed to save layout', err));
}

canvas.addEventListener('wheel', e => {
  e.preventDefault();
  const p = canvasPoint(e);
  const factor = Math.pow(1.0015, -e.deltaY);
  zoomAt(p.x, p.y, factor);
}, { passive: false });

document.getElementById('zoom-in').addEventListener('click', () => zoomAt(CW/2, CH/2, 1.25));
document.getElementById('zoom-out').addEventListener('click', () => zoomAt(CW/2, CH/2, 1/1.25));
document.getElementById('zoom-reset').addEventListener('click', resetView);

document.getElementById('grid-nw').addEventListener('click', () => expandGrid('nw'));
document.getElementById('grid-ne').addEventListener('click', () => expandGrid('ne'));
document.getElementById('grid-sw').addEventListener('click', () => expandGrid('sw'));
document.getElementById('grid-se').addEventListener('click', () => expandGrid('se'));

document.getElementById('theme-toggle').addEventListener('click', () => {
  const cur = document.documentElement.getAttribute('data-theme') || 'dark';
  applyTheme(cur === 'dark' ? 'light' : 'dark');
});

function selectNode(id) {
  if (!id) { deselectNode(); return; }
  closeStylePicker(); // never leave it open/orphaned when selection moves to another node
  closeLayerColorPicker();
  selectId = id;

  const node  = nodeMap[id];
  const cVar  = nodeAccentCss(node);
  const repo  = repoSchemas[id];

  document.getElementById('inspector-popup-body').innerHTML =
    `<div class="detail-title" style="color:${cVar}">${node.label}</div>` +
    (node.layer || node.decorator || node.file
      ? `<div class="detail-meta">${layerBadgeHtml(node.layer)}${node.decorator ? `<span class="deco">${node.decorator}</span>` : ''}${node.file ? `<span class="file">${node.file}</span>` : ''}</div>`
      : '') +
    `<div class="detail-desc">${node.desc}</div>` +
    '<div class="detail-actions">' +
      (repo && repo.view
        ? '<button class="data-btn primary" id="view-btn">View &rarr;</button>'
        : '') +
      (repo && repo.streamable
        ? `<button class="data-btn ${node.streaming ? 'danger' : 'primary'}" id="stream-toggle-btn">${node.streaming ? 'Stop' : 'Start'} Streaming &rarr;</button>`
        : '') +
      (node.type === 'service'
        ? `<button class="data-btn ${node.running ? 'danger' : 'primary'}" id="lifecycle-btn">${node.running ? 'Stop' : 'Start'} &rarr;</button>`
        : '') +
      (node.type === 'task' || node.type === 'pipeline'
        ? '<button class="data-btn primary" id="execute-btn">Execute &rarr;</button>'
        : '') +
      (node.details ? '<button class="data-btn" id="show-details-btn">Details &rarr;</button>' : '') +
      (node.chart ? '<button class="data-btn primary" id="show-chart-btn">View Chart &rarr;</button>' : '') +
      '<button class="data-btn" id="show-logs-btn">Show Logs &rarr;</button>' +
      '<button class="data-btn" id="customize-btn">Customize &rarr;</button>' +
    '</div>';

  document.querySelectorAll('.node-item').forEach(el => el.classList.remove('selected'));
  const si = document.querySelector(`.node-item[data-id="${id}"]`);
  if (si) si.classList.add('selected');

  if (repo && repo.view) {
    document.getElementById('view-btn').addEventListener('click', () => showDataView(id));
  }
  if (repo && repo.streamable) {
    document.getElementById('stream-toggle-btn').addEventListener('click', () => toggleStream(id));
  }
  if (node.type === 'service') {
    document.getElementById('lifecycle-btn').addEventListener('click', () => toggleService(id));
  }
  if (node.type === 'task' || node.type === 'pipeline') {
    document.getElementById('execute-btn').addEventListener('click', () => executeNode(id));
  }
  if (node.details) {
    document.getElementById('show-details-btn').addEventListener('click', () => showDetailsView(id));
  }
  if (node.chart) {
    document.getElementById('show-chart-btn').addEventListener('click', () => showChartView(id));
  }
  document.getElementById('show-logs-btn').addEventListener('click', () => showLogsView(id));
  document.getElementById('customize-btn').addEventListener('click', e => openStylePicker(node, e.currentTarget));

  showInspectorPopup(node);
  addLog(node.label, nodeAccent(node));
}

// Inspector popup is positioned once, at selection time, from the node's
// current screen position — not live-tracked while panning/zooming (see
// closeInspectorPopup(), called from those interactions instead). Clamped
// so it never renders outside the map panel.
function showInspectorPopup(node) {
  const popup = document.getElementById('inspector-popup');
  popup.classList.add('open');

  const w = iso(node.col, node.row);
  const sx = w.x * zoom + panX;
  const sy = w.y * zoom + panY;
  const extent = ICONS[iconKey(node)].topExtent * zoom;

  const pw = popup.offsetWidth, ph = popup.offsetHeight;
  let left = sx - pw / 2;
  let top  = sy - extent - ph - 14;
  if (top < 8) top = sy + 14; // not enough room above — drop it below the tile instead

  popup.style.left = `${clamp(left, 8, CW - pw - 8)}px`;
  popup.style.top  = `${clamp(top, 8, CH - ph - 8)}px`;
}

function closeInspectorPopup() {
  document.getElementById('inspector-popup').classList.remove('open');
  closeStylePicker(); // never leave the style picker orphaned once its anchor popup closes
  closeLayerColorPicker();
}

// ── Style picker ─────────────────────────────────────────────────────────
// Single popover, opened from the inspector's one "Customize" button, that
// bundles both customization axes for a node — its grid shape (icon) and its
// accent color — as two labeled sections, instead of a separate action
// button per axis (which made the inspector's action row noisy as soon as a
// second override type existed).

// Renders one icon into a small offscreen canvas by temporarily repointing
// the shared `ctx` binding at it (all draw functions close over `ctx`).
function renderIconSwatch(canvasEl, key, accent) {
  const saved = ctx;
  ctx = canvasEl.getContext('2d');
  ctx.clearRect(0, 0, canvasEl.width, canvasEl.height);
  ICONS[key].draw(canvasEl.width / 2, canvasEl.height * 0.8, accent, false);
  ctx = saved;
}

// The icon picker's tabs: every group an icon is registered under, in
// first-registered order, with 'Custom' kept last.
function iconGroups() {
  const groups = [...new Set(Object.values(ICONS).map(e => e.group))];
  return groups.sort((a, b) => (a === 'Custom') - (b === 'Custom'));
}

// Builds the group tabs and the swatches of `group` — the group of the
// node's current icon unless a tab click passes another.
function buildIconPicker(node, group = ICONS[iconKey(node)].group) {
  const tabs = document.getElementById('icon-picker-tabs');
  tabs.innerHTML = '';
  for (const name of iconGroups()) {
    const tab = document.createElement('button');
    tab.className = 'icon-picker-tab' + (name === group ? ' active' : '');
    tab.textContent = name;
    tab.addEventListener('click', () => {
      buildIconPicker(node, name);
      clampStylePicker();
    });
    tabs.appendChild(tab);
  }

  const grid = document.getElementById('icon-picker-grid');
  grid.innerHTML = '';
  const accent = nodeAccent(node);
  const current = iconKey(node);

  for (const key of Object.keys(ICONS)) {
    if (ICONS[key].group !== group) continue;
    const btn = document.createElement('button');
    btn.className = 'icon-swatch' + (current === key && node.icon ? ' selected' : '');
    btn.title = ICONS[key].label;
    const mini = document.createElement('canvas');
    mini.width = 40; mini.height = 40;
    renderIconSwatch(mini, key, accent);
    btn.appendChild(mini);
    btn.addEventListener('click', () => {
      node.icon = key;
      saveLayoutOverride(node);
      closeStylePicker();
    });
    grid.appendChild(btn);
  }

  const resetBtn = document.createElement('button');
  resetBtn.className = 'icon-swatch reset';
  resetBtn.textContent = 'Reset to default';
  resetBtn.addEventListener('click', () => {
    delete node.icon;
    saveLayoutOverride(node);
    closeStylePicker();
  });
  grid.appendChild(resetBtn);
}

function buildColorPicker(node) {
  const grid = document.getElementById('color-picker-grid');
  grid.innerHTML = '';

  for (const { hex, label } of COLOR_SWATCHES) {
    const btn = document.createElement('button');
    btn.className = 'color-swatch' + (node.color === hex ? ' selected' : '');
    btn.title = label;
    btn.style.background = hex;
    btn.addEventListener('click', () => {
      node.color = hex;
      saveLayoutOverride(node);
      closeStylePicker();
      selectNode(node.id);
      buildSidebar();
    });
    grid.appendChild(btn);
  }

  const resetBtn = document.createElement('button');
  resetBtn.className = 'color-swatch reset';
  resetBtn.textContent = 'Reset to default';
  resetBtn.addEventListener('click', () => {
    delete node.color;
    saveLayoutOverride(node);
    closeStylePicker();
    selectNode(node.id);
    buildSidebar();
  });
  grid.appendChild(resetBtn);
}

function openStylePicker(node, anchorBtn) {
  buildIconPicker(node);
  buildColorPicker(node);
  const pop = document.getElementById('style-picker-popover');
  pop.classList.add('open');

  const r = anchorBtn.getBoundingClientRect();
  const mapR = document.getElementById('map').getBoundingClientRect();
  clampStylePicker(r.left - mapR.left, r.bottom - mapR.top + 6);
}

// Places the style picker at (left, top) within #map — where it already is
// by default — pulled back inside the map's edges. Re-run after a group tab
// changes the popover's size.
function clampStylePicker(left, top) {
  const pop = document.getElementById('style-picker-popover');
  const mapEl = document.getElementById('map');
  left ??= pop.offsetLeft;
  top ??= pop.offsetTop;
  pop.style.left = `${clamp(left, 8, mapEl.clientWidth - pop.offsetWidth - 8)}px`;
  pop.style.top  = `${clamp(top, 8, mapEl.clientHeight - pop.offsetHeight - 8)}px`;
}

function closeStylePicker() {
  document.getElementById('style-picker-popover').classList.remove('open');
}

// ── Layer color picker ──────────────────────────────────────────────────
// A separate, standalone popover (not the per-node style-picker-popover
// above) — it's anchored from a sidebar swatch button, outside #map's
// coordinate space, and only ever needs the color section (a layer has no
// shape to customize). Reuses the same COLOR_SWATCHES palette as node colors
// purely for a consistent picker UI; the two color channels never collide
// since a layer badge and a node's own accent are rendered separately.

function buildLayerColorPicker(layerName) {
  const grid = document.getElementById('layer-color-picker-grid');
  grid.innerHTML = '';
  const current = layoutOverrides._layers && layoutOverrides._layers[layerName];

  const apply = hex => {
    saveLayerColor(layerName, hex);
    closeLayerColorPicker();
    buildSidebar();
    if (selectId && nodeMap[selectId] && nodeMap[selectId].layer === layerName) selectNode(selectId);
    render();
  };

  for (const { hex, label } of COLOR_SWATCHES) {
    const btn = document.createElement('button');
    btn.className = 'color-swatch' + (current === hex ? ' selected' : '');
    btn.title = label;
    btn.style.background = hex;
    btn.addEventListener('click', () => apply(hex));
    grid.appendChild(btn);
  }

  const resetBtn = document.createElement('button');
  resetBtn.className = 'color-swatch reset';
  resetBtn.textContent = 'Reset to default';
  resetBtn.addEventListener('click', () => apply(null));
  grid.appendChild(resetBtn);
}

function onLayerColorPopoverOutsideClick(e) {
  const pop = document.getElementById('layer-color-popover');
  if (!pop.contains(e.target)) closeLayerColorPicker();
}

function openLayerColorPicker(layerName, anchorBtn) {
  closeLayerColorPicker(); // avoid stacking outside-click listeners if one was already open
  buildLayerColorPicker(layerName);
  const pop = document.getElementById('layer-color-popover');
  pop.classList.add('open');

  const r = anchorBtn.getBoundingClientRect();
  pop.style.left = `${clamp(r.left, 8, window.innerWidth - pop.offsetWidth - 8)}px`;
  pop.style.top  = `${clamp(r.bottom + 6, 8, window.innerHeight - pop.offsetHeight - 8)}px`;

  document.addEventListener('mousedown', onLayerColorPopoverOutsideClick);
}

function closeLayerColorPicker() {
  document.getElementById('layer-color-popover').classList.remove('open');
  document.removeEventListener('mousedown', onLayerColorPopoverOutsideClick);
}

function deselectNode() {
  selectId = null;
  document.querySelectorAll('.node-item').forEach(el => el.classList.remove('selected'));
  closeInspectorPopup();
}

document.getElementById('inspector-popup-close').addEventListener('click', deselectNode);

// The Activity and Chat drawers share the map's right edge, so at most one is
// open. `name` is 'activity', 'chat' or null (close both); the header button
// of the open drawer is marked active.
function setDrawer(name) {
  for (const key of ['activity', 'chat']) {
    const open = key === name;
    const btn = document.getElementById(`${key}-toggle`);
    document.getElementById(`${key}-drawer`).classList.toggle('open', open);
    btn.classList.toggle('active', open);
    btn.setAttribute('aria-pressed', String(open));
  }
}

for (const key of ['activity', 'chat']) {
  document.getElementById(`${key}-toggle`).addEventListener('click', () => {
    const open = document.getElementById(`${key}-drawer`).classList.contains('open');
    setDrawer(open ? null : key);
  });
  document.getElementById(`${key}-drawer-close`).addEventListener('click', () => setDrawer(null));
}

// Sidebar clicks always update the Object Inspector (selectNode above). If a
// data/stream/map/logs view is currently swapped into the map panel, follow
// the new selection into that same view when it supports it, so switching
// objects doesn't force a trip back through the topology first. Falls back
// to topology when the newly selected node has no equivalent view.
function selectFromSidebar(id) {
  selectNode(id);
  if (mapMode === 'topology') return;
  const schema = repoSchemas[id];
  const kind = schema && schema.view && schema.view.kind;
  if (kind && VIEW_MODE[kind] === mapMode) {
    showDataView(id);
  } else if (mapMode === 'details' && nodeMap[id].details) {
    showDetailsView(id);
  } else if (mapMode === 'chart' && nodeMap[id].chart) {
    showChartView(id);
  } else if (mapMode === 'logs') {
    showLogsView(id);
  } else {
    backToTopology();
  }
}

// ── Lifecycle actions ────────────────────────────────────────────────────
// Backs the "Start"/"Stop" action on @Service nodes and the "Execute" action
// on @Task/@Pipeline nodes. POST /api/components/{id}/{start,stop,execute}
// drives odf.context.Context.start()/stop()/execute() directly — the same
// calls Project.start()/stop() make, just scoped to one resolved instance.

async function toggleService(id) {
  const node = nodeMap[id];
  const action = node.running ? 'stop' : 'start';
  const btn = document.getElementById('lifecycle-btn');
  if (btn) btn.disabled = true;
  try {
    const res = await fetch(`/api/components/${id}/${action}`, { method: 'POST' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    node.running = !node.running;
    addLog(`${node.label} ${node.running ? 'started' : 'stopped'}`, ACCENT.service);
  } catch (err) {
    addLog(`Failed to ${action} ${node.label}`, ACCENT.alert);
  }
  selectNode(id);
}

async function executeNode(id) {
  const node = nodeMap[id];
  const btn = document.getElementById('execute-btn');
  if (btn) btn.disabled = true;
  try {
    const res = await fetch(`/api/components/${id}/execute`, { method: 'POST' });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `HTTP ${res.status}`);
    }
    addLog(`${node.label} executed`, nodeAccent(node));
  } catch (err) {
    addLog(`${node.label} execute failed — ${err.message}`, ACCENT.alert);
  }
  if (btn) btn.disabled = false;
}

// ── Sidebar tabs ───────────────────────────────────────────────────────────
// The sidebar is an icon rail plus the active tab's panel. Adding a tab is one
// SIDEBAR_TABS entry here plus one matching .sb-panel[data-panel] in the
// markup. Collapsing hides the panel but leaves the rail, so it can reopen.
// Like the layer-group collapse state, this is a per-browser view preference,
// so it lives in localStorage rather than /api/layout.

const SIDEBAR_TABS = [
  { id: 'objects', label: 'Objects',
    icon: '<svg viewBox="0 0 16 16"><path d="M6 4h7M6 8h7M6 12h7"/><path d="M3 4h.01M3 8h.01M3 12h.01"/></svg>' },
];
const SIDEBAR_KEY = 'odf-ui-sidebar';
let sidebarState = { collapsed: false, tab: SIDEBAR_TABS[0].id };

function loadSidebarState() {
  try {
    const s = JSON.parse(localStorage.getItem(SIDEBAR_KEY) || '{}');
    if (typeof s.collapsed === 'boolean') sidebarState.collapsed = s.collapsed;
    if (SIDEBAR_TABS.some(t => t.id === s.tab)) sidebarState.tab = s.tab;
  } catch {}
}

function saveSidebarState() {
  try { localStorage.setItem(SIDEBAR_KEY, JSON.stringify(sidebarState)); } catch {}
}

function applySidebarState() {
  const { collapsed, tab } = sidebarState;
  document.getElementById('sidebar').classList.toggle('collapsed', collapsed);
  for (const btn of document.querySelectorAll('.sb-tab')) {
    const on = btn.dataset.tab === tab;
    btn.classList.toggle('active', on && !collapsed);
    btn.setAttribute('aria-selected', String(on));
    btn.setAttribute('aria-expanded', String(on && !collapsed));
  }
  for (const p of document.querySelectorAll('.sb-panel')) {
    p.classList.toggle('active', p.dataset.panel === tab);
  }
  const c = document.getElementById('sb-collapse');
  const label = collapsed ? 'Expand sidebar' : 'Collapse sidebar';
  c.title = label;
  c.setAttribute('aria-label', label);
  c.setAttribute('aria-expanded', String(!collapsed));
}

function setSidebarState(patch) {
  Object.assign(sidebarState, patch);
  saveSidebarState();
  applySidebarState();
}

function initSidebarTabs() {
  loadSidebarState();
  const rail = document.getElementById('sb-rail');
  const collapseBtn = document.getElementById('sb-collapse');
  for (const t of SIDEBAR_TABS) {
    const btn = document.createElement('button');
    btn.className   = 'sb-tab';
    btn.dataset.tab = t.id;
    btn.title       = t.label;
    btn.setAttribute('role', 'tab');
    btn.setAttribute('aria-label', t.label);
    btn.setAttribute('aria-controls', `sb-panel-${t.id}`);
    btn.innerHTML   = t.icon;
    // The active tab's button toggles collapse; any other tab opens (and
    // expands) its own panel.
    btn.addEventListener('click', () => {
      if (sidebarState.tab === t.id) setSidebarState({ collapsed: !sidebarState.collapsed });
      else setSidebarState({ tab: t.id, collapsed: false });
    });
    rail.insertBefore(btn, collapseBtn);
  }
  collapseBtn.addEventListener('click', () => setSidebarState({ collapsed: !sidebarState.collapsed }));
  applySidebarState();
}

// Collapsing changes #map's width without a window resize, so the canvas is
// re-measured when #map itself changes size. Skips no-op sizes so it doesn't
// double up with the window 'resize' listener.
function observeMapSize() {
  const map = document.getElementById('map');
  new ResizeObserver(() => {
    const r = map.getBoundingClientRect();
    if (r.width !== CW || r.height !== CH) resize();
  }).observe(map);
}

// ── Sidebar ────────────────────────────────────────────────────────────────
// Grouped into a collapsible tree keyed by @Layer, since a flat list gives no
// sense of which layer a component belongs to (the same gap the canvas/
// inspector layer badges close). Nodes with no layer (Config, a bare
// @Component never wrapped in a @Layer) land in a trailing "No Layer" group
// with no color swatch, since there's nothing layer-specific to customize.

function loadCollapsedLayers() {
  try {
    return new Set(JSON.parse(localStorage.getItem('odf-ui-collapsed-layers') || '[]'));
  } catch {
    return new Set();
  }
}

// Collapse state is a pure view preference (not shared layout), so it lives
// in localStorage rather than round-tripping through /api/layout.
function toggleLayerGroup(name) {
  const collapsed = loadCollapsedLayers();
  if (collapsed.has(name)) collapsed.delete(name); else collapsed.add(name);
  localStorage.setItem('odf-ui-collapsed-layers', JSON.stringify([...collapsed]));
  const group = document.querySelector(`.layer-group[data-layer="${CSS.escape(name)}"]`);
  if (group) group.classList.toggle('collapsed');
}

function buildNodeItem(node) {
  const cVar = nodeAccentCss(node);
  const lbl  = TYPE_LABEL[node.type] || node.type;
  const item = document.createElement('div');
  item.className  = 'node-item';
  item.dataset.id = node.id;
  item.style.setProperty('--row-accent', cVar);
  item.innerHTML  =
    `<span class="node-tag" style="background:color-mix(in srgb, ${cVar} 14%, transparent);color:${cVar};border:var(--tag-border-width,1px) solid color-mix(in srgb, ${cVar} 40%, transparent);box-shadow:var(--tag-shadow,none)">${lbl.replace('@','')}</span>` +
    `<span class="node-lbl">${node.label}</span>`;
  item.addEventListener('click', () => selectFromSidebar(node.id));
  return item;
}

function buildSidebar() {
  const list = document.getElementById('node-list');
  list.innerHTML = '';

  const groups = new Map(); // layer name, or null for "no layer" -> nodes[]
  for (const node of nodes) {
    const key = node.layer || null;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(node);
  }
  const orderedKeys = [...groups.keys()].filter(k => k !== null);
  if (groups.has(null)) orderedKeys.push(null); // "no layer" group always last

  const collapsed = loadCollapsedLayers();

  for (const key of orderedKeys) {
    const groupNodes = groups.get(key);
    const groupName  = key || 'no-layer';
    const label = key ? layerLabel(key) : 'No Layer';
    const color = key ? layerColor(key) : 'var(--text-dim)';

    const group = document.createElement('div');
    group.className = 'layer-group' + (collapsed.has(groupName) ? ' collapsed' : '');
    group.dataset.layer = groupName;

    const header = document.createElement('div');
    header.className = 'layer-group-header';
    header.innerHTML =
      '<span class="layer-caret">&#9662;</span>' +
      (key
        ? `<button class="layer-swatch-btn" style="background:${color}" title="Change ${label} color" aria-label="Change ${label} color"></button>`
        : `<span class="layer-swatch-btn" style="background:${color};cursor:default"></span>`) +
      `<span class="layer-group-name">${label}</span>` +
      `<span class="layer-group-count">${groupNodes.length}</span>`;
    header.addEventListener('click', e => {
      if (e.target.closest('.layer-swatch-btn')) return;
      toggleLayerGroup(groupName);
    });
    group.appendChild(header);

    if (key) {
      const swatchBtn = header.querySelector('.layer-swatch-btn');
      swatchBtn.addEventListener('click', e => {
        e.stopPropagation();
        openLayerColorPicker(key, swatchBtn);
      });
    }

    const body = document.createElement('div');
    body.className = 'layer-group-body';
    for (const node of groupNodes) body.appendChild(buildNodeItem(node));
    group.appendChild(body);

    list.appendChild(group);
  }
}

function addLog(msg, color) {
  const lines = document.getElementById('log-lines');
  const div   = document.createElement('div');
  div.className = 'log-line';
  const ts = new Date().toTimeString().slice(0, 8);
  div.innerHTML = `<span class="dot" style="background:${color || TEXT_MUTED}"></span><span class="ts">${ts}</span><span>${msg}</span>`;
  lines.prepend(div);
  while (lines.children.length > 40) lines.removeChild(lines.lastChild);
}

// ── Chat ─────────────────────────────────────────────────────────────────
// Backs the Chat drawer — hidden unless GET /api/chat/config reports
// enabled (i.e. Project.start(chat=True) was passed). History lives only in
// this tab (chatHistory), resent in full with each turn — no server-side
// session storage.

let chatHistory = [];
let chatBusy = false;

async function initChat() {
  try {
    const res = await fetch('/api/chat/config');
    if (!res.ok) return;
    const cfg = await res.json();
    if (cfg.enabled) document.getElementById('chat-toggle').classList.add('visible');
  } catch (err) {
    console.error('Failed to load chat config', err);
  }
}

function appendChatMessage(role, text) {
  const list = document.getElementById('chat-messages');
  const div = document.createElement('div');
  div.className = 'chat-msg ' + role;
  div.textContent = text;
  list.appendChild(div);
  list.scrollTop = list.scrollHeight;
  return div;
}

async function sendChatMessage() {
  if (chatBusy) return;
  const input = document.getElementById('chat-input');
  const text = input.value.trim();
  if (!text) return;
  input.value = '';
  chatHistory.push({ role: 'user', content: text });
  appendChatMessage('user', text);

  chatBusy = true;
  const assistantDiv = appendChatMessage('assistant', '');
  let assistantContent = '';
  const list = document.getElementById('chat-messages');

  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages: chatHistory }),
    });
    if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop();
      for (const line of lines) {
        if (!line) continue;
        const event = JSON.parse(line);
        if (event.type === 'token') {
          assistantContent += event.content;
          assistantDiv.textContent = assistantContent;
          list.scrollTop = list.scrollHeight;
        } else if (event.type === 'tool_call') {
          appendChatMessage('tool', `→ ${event.name}(${JSON.stringify(event.arguments)})`);
        } else if (event.type === 'tool_result') {
          appendChatMessage('tool', `← ${event.name}: ${event.result}`);
        } else if (event.type === 'error') {
          appendChatMessage('error', `Chat error: ${event.message} — is \`ollama serve\` running?`);
        }
      }
    }
  } catch (err) {
    appendChatMessage('error', `Chat error: ${err.message}`);
  } finally {
    if (assistantContent) {
      chatHistory.push({ role: 'assistant', content: assistantContent });
    } else {
      assistantDiv.remove();
    }
    chatBusy = false;
  }
}

// ── Chat @mention autocomplete ──────────────────────────────────────────
// Suggests component ids from the topology (`nodes`/`nodeMap`, already
// fetched for the graph view) while typing an `@handle` in chat-input.

let mentionMatches = [];
let mentionActive = -1;
let mentionStart = -1;

function currentMentionQuery(input) {
  const upToCaret = input.value.slice(0, input.selectionStart);
  const match = upToCaret.match(/(?:^|\s)@([A-Za-z0-9-]*)$/);
  if (!match) return null;
  return { query: match[1].toLowerCase(), start: input.selectionStart - match[1].length - 1 };
}

function updateMentionActive() {
  const menu = document.getElementById('chat-mention-menu');
  [...menu.children].forEach((el, i) => el.classList.toggle('active', i === mentionActive));
}

function renderMentionMenu(query) {
  const menu = document.getElementById('chat-mention-menu');
  mentionMatches = nodes
    .filter(n => n.id.startsWith(query) || n.label.toLowerCase().startsWith(query))
    .slice(0, 8);
  if (!mentionMatches.length) {
    menu.hidden = true;
    mentionActive = -1;
    return;
  }
  mentionActive = 0;
  menu.innerHTML = mentionMatches
    .map(n => `<div class="mention-item" data-id="${n.id}"><span>@${n.id}</span><span class="mention-label">${n.label}</span></div>`)
    .join('');
  menu.hidden = false;
  updateMentionActive();
}

function hideMentionMenu() {
  document.getElementById('chat-mention-menu').hidden = true;
  mentionMatches = [];
  mentionActive = -1;
  mentionStart = -1;
}

function applyMention(input, id) {
  const value = input.value;
  const caret = input.selectionStart;
  const before = value.slice(0, mentionStart);
  const after = value.slice(caret);
  const replacement = `@${id} `;
  input.value = before + replacement + after;
  const cursor = before.length + replacement.length;
  input.setSelectionRange(cursor, cursor);
  hideMentionMenu();
  input.focus();
}

document.getElementById('chat-mention-menu').addEventListener('mousedown', e => {
  const item = e.target.closest('.mention-item');
  if (!item) return;
  e.preventDefault();
  applyMention(document.getElementById('chat-input'), item.dataset.id);
});

document.getElementById('chat-input').addEventListener('input', e => {
  const mention = currentMentionQuery(e.target);
  if (!mention) { hideMentionMenu(); return; }
  mentionStart = mention.start;
  renderMentionMenu(mention.query);
});

document.getElementById('chat-input').addEventListener('blur', () => {
  // Delay so a mousedown selection on the menu registers before it's hidden.
  setTimeout(hideMentionMenu, 150);
});

document.getElementById('chat-send').addEventListener('click', sendChatMessage);
document.getElementById('chat-input').addEventListener('keydown', e => {
  const menuOpen = !document.getElementById('chat-mention-menu').hidden && mentionMatches.length;
  if (menuOpen) {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      mentionActive = (mentionActive + 1) % mentionMatches.length;
      updateMentionActive();
      return;
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      mentionActive = (mentionActive - 1 + mentionMatches.length) % mentionMatches.length;
      updateMentionActive();
      return;
    }
    if (e.key === 'Enter' || e.key === 'Tab') {
      e.preventDefault();
      applyMention(e.target, mentionMatches[mentionActive].id);
      return;
    }
    if (e.key === 'Escape') {
      e.preventDefault();
      hideMentionMenu();
      return;
    }
  }
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendChatMessage();
  }
});

// ── Header clock ─────────────────────────────────────────────────────────

function tickClock() {
  document.getElementById('hdr-clock').textContent = new Date().toTimeString().slice(0, 8);
}

// ── Stats ─────────────────────────────────────────────────────────────────

function renderStats(data) {
  const types = data.stats.types || {};
  document.getElementById('stat-project').textContent   = data.project;
  document.getElementById('stat-objects').textContent   = String(data.stats.objects);
  document.getElementById('stat-links').textContent     = String(data.stats.links);
  document.getElementById('stat-services').textContent  = String(types.service || 0);
  document.getElementById('stat-tasks').textContent     = String(types.task || 0);
  document.getElementById('stat-pipelines').textContent = String(types.pipeline || 0);
  document.getElementById('hdr-subtitle').textContent   = `Topology · ${data.project}`;
  document.getElementById('node-count').textContent     = String(data.stats.objects).padStart(2, '0');
  document.title = `${BRAND} — ${data.project}`;
}

// ── Map panel view ───────────────────────────────────────────────────────
// Backs "Edit Data" / "View Stream" / "Show Logs" — instead of a floating
// modal, these swap the topology canvas out for an inline panel inside the
// same #map surface, with a "← Topology" button to switch back. Sidebar
// selection follows the active mode (see selectFromSidebar above), so this
// is the single place that knows how to enter/leave each mode.

let mapMode = 'topology'; // 'topology' | 'data' | 'stream' | 'media' | 'image' | 'document' | 'timeseries' | 'logs' | 'geo' | 'details' | 'chart'
let audioStreamActive = false; // guards the streaming-audio poll-and-chain loop, see playAudioStream()

function setMapMode(mode) {
  if (mapMode === 'logs' && mode !== 'logs') {
    clearInterval(logsPollTimer);
    logsPollTimer = null;
    activeLogComponentId = null;
  }
  if (mapMode === 'stream' && mode !== 'stream') {
    audioStreamActive = false;
    const img = document.getElementById('stream-img');
    if (img) img.src = '';
    const audio = document.getElementById('stream-audio');
    if (audio) {
      audio.pause();
      if (audio.src) URL.revokeObjectURL(audio.src);
      audio.src = '';
    }
  }
  if (mapMode === 'geo' && mode !== 'geo') destroyGeoMap();
  if (mapMode === 'image' && mode !== 'image') closeImageLightbox();
  if (mapMode === 'chart' && mode !== 'chart') {
    const frame = document.getElementById('chart-frame');
    if (frame) frame.src = 'about:blank';
  }
  if (replayMode && mode !== mapMode) teardownReplay();
  if (mode === 'topology') activeRepoId = null;
  if (mode !== 'topology') closeStylePicker(); // its anchor (the inspector popup) is hidden outside topology
  mapMode = mode;
  document.getElementById('map').className = 'panel mode-' + mode;
  document.getElementById('map-panel-hdr-extra').innerHTML = '';
}

function backToTopology() { setMapMode('topology'); }

document.getElementById('map-back-btn').addEventListener('click', backToTopology);

// ── Data view ────────────────────────────────────────────────────────────
// Backs the single "View" action on repository nodes — dispatches on the
// DataView kind the server resolved (see odf.view.DataViewProtocol /
// odf.ui.data._view_dict) to exactly one of the renderers below. A
// repository gets one view, never a mix.

let activeRepoId = null;
const TABLE_PAGE_SIZE_OPTIONS = [10, 25, 50, 100];
let tableOffset = 0;
let tablePageSize = TABLE_PAGE_SIZE_OPTIONS[1];
let tableTotal = 0;
let tsHiddenFields = new Set(); // numeric fields the user unchecked from the timeseries chart
let tsHiddenFieldsRepoId = null; // repo the above selection belongs to — reset on repo change, kept across page/mode switches

// ── Replay (timeline scrubber) state ────────────────────────────────────
// Shared by Map/Timeseries/Media replay modes (see renderTimelineBar/
// wireTimelineBar below, and odf.view.ReplayProtocol server-side). Map and
// Timeseries have no native playback element, so Play drives a synthetic
// requestAnimationFrame clock that plays the whole [replayMin, replayMax]
// span out over REPLAY_BASE_SECONDS real seconds (scaled by replaySpeed).
// Media instead mirrors the bound <video>/<audio> element's own clock — see
// wireMediaReplay — so replayRaf/replaySpeed are unused in that mode.
const REPLAY_BASE_SECONDS = 20;
let replayMode = false;
let replayRepoId = null;
let replayField = null;      // the time field name for the active repo (schema.replay_field)
let replayRecords = [];      // full record set for the active repo, sorted by replayField ascending, fetched once on entering replay
let replayMin = 0, replayMax = 0;
let replayPos = 0;
let replayPlaying = false;
let replaySpeed = 1;
let replayRaf = null;
let replayLastTick = null;
let replayMediaCleanup = null; // teardown fn for the bound media element's listeners, in media replay only

// Per-column filters (field name -> substring needle), sent to the backend
// as query params on every /records fetch — table, timeline and map modes
// all hit the same endpoint, so a filter set in the table carries over to
// whichever mode is active. Reset only when a genuinely different repo is
// opened (see enterRepoView), not on page/mode switches.
let tableFilters = {};
let filterDebounceTimer = null;
let lastFocusedFilterField = null;
let lastFocusedFilterCaret = null;

// Marks activeRepoId as the given repo, resetting per-repo view state
// (pagination offset, filters, remembered filter focus) only when it's an
// actual repo change — a mode switch on the same repo keeps all of it.
function enterRepoView(repoId) {
  if (activeRepoId !== repoId) {
    tableOffset = 0;
    tableFilters = {};
    lastFocusedFilterField = null;
    teardownReplay();
  }
  activeRepoId = repoId;
}

function recordsQuery() {
  const params = new URLSearchParams({ limit: String(tablePageSize), offset: String(tableOffset) });
  for (const [field, value] of Object.entries(tableFilters)) {
    if (value) params.set(field, value);
  }
  return params.toString();
}

// Renders the table/alt-view switcher into the panel header — only shown for
// repositories whose DataView offers more than one way to look at the same
// data (currently TimeseriesView and LocationView).
const ALT_VIEW_MODES = {
  timeseries: { label: 'Timeline', show: showTimeseriesView },
  location: { label: 'Map', show: showMapView },
};

function renderModeSwitcher(schema, mode) {
  const extra = document.getElementById('map-panel-hdr-extra');
  const alt = ALT_VIEW_MODES[schema.view.kind];
  if (!alt) { extra.innerHTML = ''; return; }
  extra.innerHTML =
    '<select id="view-mode-select" class="view-mode-select" title="Switch view">' +
    `<option value="${schema.view.kind}"${mode !== 'table' ? ' selected' : ''}>${alt.label}</option>` +
    `<option value="table"${mode === 'table' ? ' selected' : ''}>Table</option>` +
    '</select>';
  document.getElementById('view-mode-select').addEventListener('change', e => {
    if (e.target.value === 'table') showTableView(schema.id);
    else alt.show(schema.id);
  });
}

// ── Replay toggle ──────────────────────────────────────────────────────
// A repository is replay-eligible when the server resolved a timestamp
// field for it (schema.replay_field — always set for TimeseriesView, or
// opt-in via odf.view.ReplayProtocol for Location/Video/Audio views). The
// toggle button lives in the same fixed header slot renderModeSwitcher uses,
// independent of the table/alt-view <select> — a repo can offer both, one,
// or neither.
function timeFieldOf(schema) { return schema.replay_field; }
function replayEligible(schema) { return schema.replay_field != null; }

function renderReplayToggle(schema) {
  if (!replayEligible(schema)) return;
  const extra = document.getElementById('map-panel-hdr-extra');
  const btn = document.createElement('button');
  btn.id = 'replay-toggle-btn';
  btn.className = 'data-btn' + (replayMode ? ' primary' : '');
  btn.textContent = replayMode ? 'Exit Replay' : 'Replay';
  btn.addEventListener('click', () => (replayMode ? exitReplayMode : enterReplayMode)(schema));
  extra.appendChild(btn);
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

function showDataView(repoId) {
  const schema = repoSchemas[repoId];
  if (!schema || !schema.view) return;
  switch (schema.view.kind) {
    case 'table': return showTableView(repoId);
    case 'location': return showMapView(repoId);
    case 'streaming-video':
    case 'streaming-audio': return showStreamView(repoId);
    case 'video':
    case 'audio': return showMediaView(repoId);
    case 'image': return showImageView(repoId);
    case 'document': return showDocumentView(repoId);
    case 'timeseries': return showTimeseriesView(repoId);
  }
}

async function showTableView(repoId) {
  enterRepoView(repoId);
  const schema = repoSchemas[repoId];
  setMapMode('data');
  document.getElementById('map-panel-title').textContent = `${schema.label} · ${schema.entity}`;
  renderModeSwitcher(schema, 'table');
  await refreshDataTable();
}

async function refreshDataTable() {
  const schema = repoSchemas[activeRepoId];
  const body = document.getElementById('map-panel-body');
  let records;
  try {
    const res = await fetch(`/api/repositories/${activeRepoId}/records?${recordsQuery()}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    records = await res.json();
    tableTotal = Number(res.headers.get('X-Total-Count') ?? records.length);
  } catch (err) {
    body.innerHTML = '<span class="detail-empty">// failed to load records</span>';
    return;
  }
  if (!records.length && tableOffset > 0) {
    tableOffset = Math.max(0, tableOffset - tablePageSize);
    return refreshDataTable();
  }
  renderDataTable(schema, records);
}

function renderDataTable(schema, records) {
  const body = document.getElementById('map-panel-body');
  // schema.view.fields only means a column subset for TableView — for
  // LocationView it's the (lat, lon) pair and for TimeseriesView there's no
  // `fields` at all, neither of which should narrow the table's columns.
  const fieldNames = (schema.view.kind === 'table' && schema.view.fields) || schema.fields.map(f => f.name);
  const cols = fieldNames.map(name => schema.fields.find(f => f.name === name)).filter(Boolean);

  let html = '<table class="data-table"><thead><tr>';
  for (const f of cols) html += `<th>${f.name}</th>`;
  html += schema.writable ? '<th></th>' : '';
  html += '</tr><tr class="filter-row">';
  for (const f of cols) {
    const value = escapeHtml(tableFilters[f.name] || '');
    html += `<th><input class="col-filter" data-field="${f.name}" placeholder="Filter…" value="${value}"></th>`;
  }
  html += schema.writable ? '<th></th>' : '';
  html += '</tr></thead><tbody>';

  if (!records.length) {
    html += `<tr class="empty-row"><td colspan="${cols.length + 1}">// no records</td></tr>`;
  }
  for (const record of records) {
    html += `<tr data-key="${escapeHtml(record[schema.key])}">`;
    for (const f of cols) html += `<td data-field="${f.name}">${escapeHtml(record[f.name] ?? '')}</td>`;
    if (schema.writable) {
      html += '<td class="actions">' +
        '<button class="data-btn edit-row">Edit</button>' +
        '<button class="data-btn danger delete-row">Delete</button></td>';
    }
    html += '</tr>';
  }
  html += '</tbody></table>';
  html += renderPaginationBar();
  if (schema.writable) html += '<button class="data-btn primary block" id="add-row-btn">+ Add</button>';
  body.innerHTML = html;
  wirePaginationBar(refreshDataTable);
  wireColumnFilters(body);

  if (!schema.writable) return;

  body.querySelectorAll('.edit-row').forEach(btn => {
    btn.addEventListener('click', () => startEditRow(btn.closest('tr'), schema));
  });
  body.querySelectorAll('.delete-row').forEach(btn => {
    btn.addEventListener('click', () => deleteRow(btn.closest('tr'), schema));
  });
  document.getElementById('add-row-btn').addEventListener('click', () => startAddRow(schema));
}

// Wires each column's filter input to a debounced, server-side refetch
// (filters are query params — see recordsQuery/parse_filters), then
// restores focus + caret to whichever input the user was just typing in,
// since refreshDataTable() re-renders the whole table on every keystroke.
function wireColumnFilters(body) {
  body.querySelectorAll('.col-filter').forEach(input => {
    input.addEventListener('input', e => {
      const field = e.target.dataset.field;
      if (e.target.value) tableFilters[field] = e.target.value;
      else delete tableFilters[field];
      tableOffset = 0;
      lastFocusedFilterField = field;
      lastFocusedFilterCaret = e.target.selectionStart;
      clearTimeout(filterDebounceTimer);
      filterDebounceTimer = setTimeout(refreshDataTable, 300);
    });
  });
  if (!lastFocusedFilterField) return;
  const input = body.querySelector(`.col-filter[data-field="${lastFocusedFilterField}"]`);
  if (!input) return;
  input.focus();
  const pos = lastFocusedFilterCaret ?? input.value.length;
  input.setSelectionRange(pos, pos);
}

function renderPaginationBar() {
  const start = tableTotal === 0 ? 0 : tableOffset + 1;
  const end = Math.min(tableOffset + tablePageSize, tableTotal);
  const sizeOptions = TABLE_PAGE_SIZE_OPTIONS
    .map(n => `<option value="${n}"${n === tablePageSize ? ' selected' : ''}>${n} / page</option>`)
    .join('');
  return '<div class="pagination">' +
    `<span class="pagination-range">${start}–${end} of ${tableTotal}</span>` +
    `<button class="data-btn" id="page-prev-btn"${tableOffset === 0 ? ' disabled' : ''}>&larr; Prev</button>` +
    `<button class="data-btn" id="page-next-btn"${end >= tableTotal ? ' disabled' : ''}>Next &rarr;</button>` +
    `<select id="page-size-select">${sizeOptions}</select>` +
    '</div>';
}

function wirePaginationBar(refresh) {
  document.getElementById('page-prev-btn').addEventListener('click', () => {
    tableOffset = Math.max(0, tableOffset - tablePageSize);
    refresh();
  });
  document.getElementById('page-next-btn').addEventListener('click', () => {
    tableOffset += tablePageSize;
    refresh();
  });
  document.getElementById('page-size-select').addEventListener('change', e => {
    tablePageSize = Number(e.target.value);
    tableOffset = 0;
    refresh();
  });
}

// ── Timeline scrubber (replay mode) ─────────────────────────────────────
// Shared floating-overlay bar (same `.floating-pagination` container the
// pagination bar uses — see setReplayMode call sites in Map/Timeseries/Media
// below) offering a play/pause button, a scrubber, and elapsed/total labels.
// Purely presentational: it exposes drag/play/pause as callbacks and leaves
// "what advancing time means" to whichever view is driving it (a synthetic
// requestAnimationFrame clock for Map/Timeseries, or a bound media element's
// own clock for Video/Audio — see startSyntheticClock / wireMediaReplay).

function formatClock(seconds) {
  seconds = Math.max(0, Math.round(seconds));
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  return h > 0
    ? `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
    : `${m}:${String(s).padStart(2, '0')}`;
}

// Map/Timeseries have no native playback element, so they get a speed
// selector for the synthetic clock; Media's clock is the element's own, at
// true 1x, so no speed control is shown there.
function replaySpeedApplicable() { return mapMode === 'geo' || mapMode === 'timeseries'; }

function renderTimelineBar() {
  const span = replayMax - replayMin;
  const pct = span <= 0 ? 0 : Math.round(((replayPos - replayMin) / span) * 1000);
  const speedOptions = [0.5, 1, 2, 4]
    .map(s => `<option value="${s}"${s === replaySpeed ? ' selected' : ''}>${s}&times;</option>`)
    .join('');
  return '<div class="timeline-bar">' +
    `<button class="data-btn primary" id="replay-playpause-btn" title="${replayPlaying ? 'Pause' : 'Play'}">${replayPlaying ? '&#10073;&#10073;' : '&#9654;'}</button>` +
    `<span class="timeline-elapsed">${formatClock(replayPos - replayMin)}</span>` +
    `<input type="range" id="replay-scrubber" min="0" max="1000" step="1" value="${pct}">` +
    `<span class="timeline-total">${formatClock(span)}</span>` +
    (replaySpeedApplicable()
      ? `<select id="replay-speed-select" title="Playback speed">${speedOptions}</select>`
      : '') +
    '</div>';
}

function wireTimelineBar({ onScrubInput, onPlay, onPause }) {
  document.getElementById('replay-playpause-btn').addEventListener('click', () => {
    if (replayPlaying) onPause(); else onPlay();
  });
  document.getElementById('replay-scrubber').addEventListener('input', e => {
    if (replayPlaying) onPause();
    const span = replayMax - replayMin;
    const pos = replayMin + (Number(e.target.value) / 1000) * span;
    setReplayPos(pos);
    onScrubInput(pos);
  });
  const speedSel = document.getElementById('replay-speed-select');
  if (speedSel) speedSel.addEventListener('change', e => { replaySpeed = Number(e.target.value); });
}

// Pushes a new scrub position into the bar's own UI (range value + elapsed
// label) without re-invoking onScrubInput — called by whichever clock is
// driving playback (the synthetic RAF tick, or a media element's native
// `timeupdate`) so the two don't fight each other.
function setReplayPos(pos) {
  replayPos = Math.min(replayMax, Math.max(replayMin, pos));
  const range = document.getElementById('replay-scrubber');
  if (!range) return; // bar was swapped away
  const span = replayMax - replayMin;
  range.value = span <= 0 ? 0 : Math.round(((replayPos - replayMin) / span) * 1000);
  const elapsed = document.querySelector('.timeline-elapsed');
  if (elapsed) elapsed.textContent = formatClock(replayPos - replayMin);
}

function setReplayPlaying(playing) {
  replayPlaying = playing;
  const btn = document.getElementById('replay-playpause-btn');
  if (!btn) return;
  btn.innerHTML = playing ? '&#10073;&#10073;' : '&#9654;';
  btn.title = playing ? 'Pause' : 'Play';
}

// Drives replayPos forward at wall-clock speed for Map/Timeseries — plays
// the whole [replayMin, replayMax] span out over REPLAY_BASE_SECONDS real
// seconds (scaled by replaySpeed) rather than the repo's actual time span,
// since that span can be anywhere from minutes to weeks. `onTick(pos)`
// re-renders the view for the new position; playback stops automatically at
// replayMax.
function startSyntheticClock(onTick) {
  replayLastTick = performance.now();
  const step = now => {
    if (!replayPlaying) return;
    const dt = (now - replayLastTick) / 1000;
    replayLastTick = now;
    const span = replayMax - replayMin;
    const perRealSecond = span > 0 ? (span / REPLAY_BASE_SECONDS) * replaySpeed : 0;
    const pos = Math.min(replayMax, replayPos + dt * perRealSecond);
    setReplayPos(pos);
    onTick(pos);
    if (pos >= replayMax) { setReplayPlaying(false); replayRaf = null; return; }
    replayRaf = requestAnimationFrame(step);
  };
  replayRaf = requestAnimationFrame(step);
}

function stopReplayClock() {
  if (replayRaf) { cancelAnimationFrame(replayRaf); replayRaf = null; }
  replayLastTick = null;
}

// Fetches a repository's full record set once, sorted by its replay field,
// and flips replayMode on — see renderReplayToggle above for how a repo
// opts in (schema.replay_field). Re-renders the same view afterwards, which
// then branches on replayMode to show the timeline bar instead of pagination.
async function enterReplayMode(schema) {
  const field = timeFieldOf(schema);
  if (!field) return;
  let all;
  try {
    const res = await fetch(`/api/repositories/${schema.id}/records`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    all = await res.json();
  } catch (err) {
    return;
  }
  const sorted = all.filter(r => r[field] != null).sort((a, b) => a[field] - b[field]);
  if (!sorted.length) return;
  replayField = field;
  replayRepoId = schema.id;
  replayRecords = sorted;
  replayMin = Number(sorted[0][field]);
  replayMax = Number(sorted[sorted.length - 1][field]);
  replayPos = replayMin;
  replaySpeed = 1;
  replayPlaying = false;
  replayMode = true;
  showDataView(schema.id);
}

function exitReplayMode(schema) {
  teardownReplay();
  showDataView(schema.id);
}

// Cancels any running clock/media binding and clears replay state — called
// both by the Exit Replay button and whenever the active repo/mode changes
// out from under an in-progress replay (see enterRepoView/setMapMode).
function teardownReplay() {
  stopReplayClock();
  if (replayMediaCleanup) { replayMediaCleanup(); replayMediaCleanup = null; }
  replayMode = false;
  replayPlaying = false;
  replayRepoId = null;
  replayRecords = [];
  replayField = null;
}

function startEditRow(tr, schema) {
  const key = tr.dataset.key;
  for (const f of schema.fields) {
    if (f.name === schema.key) continue;
    const td = tr.querySelector(`td[data-field="${f.name}"]`);
    td.innerHTML = `<input value="${escapeHtml(td.textContent)}">`;
  }
  const actions = tr.querySelector('td.actions');
  actions.innerHTML =
    '<button class="data-btn primary save-row">Save</button>' +
    '<button class="data-btn cancel-row">Cancel</button>';
  actions.querySelector('.save-row').addEventListener('click', () => saveEditRow(tr, schema, key));
  actions.querySelector('.cancel-row').addEventListener('click', refreshDataTable);
}

async function saveEditRow(tr, schema, key) {
  const body = {};
  for (const f of schema.fields) {
    if (f.name === schema.key) continue;
    body[f.name] = tr.querySelector(`td[data-field="${f.name}"] input`).value;
  }
  try {
    const res = await fetch(`/api/repositories/${activeRepoId}/records/${encodeURIComponent(key)}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    addLog(`Saved ${schema.entity} ${key}`, ACCENT.repository);
  } catch (err) {
    addLog(`Failed to save ${schema.entity} ${key}`, ACCENT.alert);
  }
  refreshDataTable();
}

function startAddRow(schema) {
  document.getElementById('add-row-btn').disabled = true;
  const table = document.querySelector('.data-table tbody');
  const tr = document.createElement('tr');
  let html = '';
  for (const f of schema.fields) {
    html += f.name === schema.key
      ? '<td class="detail-empty">auto</td>'
      : `<td><input placeholder="${f.name}"></td>`;
  }
  html += '<td class="actions">' +
    '<button class="data-btn primary save-new">Save</button>' +
    '<button class="data-btn cancel-new">Cancel</button></td>';
  tr.innerHTML = html;
  table.appendChild(tr);

  tr.querySelector('.save-new').addEventListener('click', async () => {
    const body = {};
    const inputs = tr.querySelectorAll('input');
    let i = 0;
    for (const f of schema.fields) {
      if (f.name === schema.key) continue;
      body[f.name] = inputs[i++].value;
    }
    try {
      const res = await fetch(`/api/repositories/${activeRepoId}/records`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      addLog(`Created ${schema.entity}`, ACCENT.repository);
    } catch (err) {
      addLog(`Failed to create ${schema.entity}`, ACCENT.alert);
    }
    refreshDataTable();
  });
  tr.querySelector('.cancel-new').addEventListener('click', refreshDataTable);
}

async function deleteRow(tr, schema) {
  const key = tr.dataset.key;
  if (!confirm(`Delete ${schema.entity} ${key}?`)) return;
  try {
    const res = await fetch(`/api/repositories/${activeRepoId}/records/${encodeURIComponent(key)}`, { method: 'DELETE' });
    if (!res.ok && res.status !== 204) throw new Error(`HTTP ${res.status}`);
    addLog(`Deleted ${schema.entity} ${key}`, ACCENT.repository);
  } catch (err) {
    addLog(`Failed to delete ${schema.entity} ${key}`, ACCENT.alert);
  }
  refreshDataTable();
}

window.addEventListener('keydown', e => {
  if (imageIndex >= 0) {
    // An open image takes the keys first, so Esc returns to the grid rather
    // than all the way to the topology.
    if (e.key === 'Escape') closeImageLightbox();
    else if (e.target.closest('input, textarea, select')) return;
    else if (e.key === 'ArrowLeft') stepImageLightbox(-1);
    else if (e.key === 'ArrowRight') stepImageLightbox(1);
    return;
  }
  if (e.key !== 'Escape') return;
  if (mapMode !== 'topology') backToTopology();
  else if (selectId) deselectNode();
});

// ── Streaming toggle ─────────────────────────────────────────────────────
// Backs the "Start Streaming"/"Stop Streaming" action on streamable
// repository nodes — the repository analogue of a @Service's Start/Stop
// action. POST /api/repositories/{id}/{start,stop}-stream drives
// odf.context.Context.start_stream()/stop_stream() directly: a background
// thread on the server iterates the repository's stream() and keeps
// running independent of any viewer. `node.streaming` mirrors that
// server-side state (seeded from GET /api/repositories on load) rather than
// being tracked purely client-side. The separate "View Stream" view below
// just attaches a viewer to whatever is already running — it neither starts
// nor stops the stream.

async function toggleStream(id) {
  if (nodeMap[id].streaming) {
    await stopStreaming(id);
  } else {
    await startStreaming(id);
  }
}

async function startStreaming(id) {
  const node = nodeMap[id];
  if (node.streaming) return;
  const btn = document.getElementById('stream-toggle-btn');
  if (btn) btn.disabled = true;
  try {
    const res = await fetch(`/api/repositories/${id}/start-stream`, { method: 'POST' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    node.streaming = true;
    addLog(`${repoSchemas[id].label} streaming started`, ACCENT.repository);
  } catch (err) {
    addLog(`Failed to start streaming ${repoSchemas[id].label}`, ACCENT.alert);
  }
  if (selectId === id) selectNode(id);
}

async function stopStreaming(id) {
  const node = nodeMap[id];
  if (!node.streaming) return;
  const btn = document.getElementById('stream-toggle-btn');
  if (btn) btn.disabled = true;
  try {
    const res = await fetch(`/api/repositories/${id}/stop-stream`, { method: 'POST' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    node.streaming = false;
    addLog(`${repoSchemas[id].label} streaming stopped`, ACCENT.repository);
  } catch (err) {
    addLog(`Failed to stop streaming ${repoSchemas[id].label}`, ACCENT.alert);
  }
  if (selectId === id) selectNode(id);
}

// ── Stream view ───────────────────────────────────────────────────────────
// Backs the "View Stream" action on streamable repository nodes — attaches a
// dedicated viewer to the stream started by the Start/Stop toggle above,
// independent of that toggle's own hidden connection, so entering/leaving
// this view doesn't itself start or stop the stream. GET /stream 409s if
// nothing has called start_stream() yet, surfaced below as a placeholder.
// The endpoint otherwise returns a multipart/x-mixed-replace MJPEG
// response, which a plain <img> renders natively — no video element or JS
// decoding needed. The image's src is only set while this view is active,
// and cleared on leaving it (see setMapMode), so the browser drops this
// viewer's own HTTP connection instead of streaming into a hidden view
// forever.

function showStreamView(repoId) {
  const schema = repoSchemas[repoId];
  setMapMode('stream');
  document.getElementById('map-panel-title').textContent = `${schema.label} · live`;
  const isAudio = schema.view.kind === 'streaming-audio';
  // No native `controls` on the audio element: it's fed a new, fully-formed
  // WAV file every chunk, so a native seek bar would show that one chunk's
  // duration/position — implying a bounded track you can scrub, when this
  // is actually an unbounded live feed. Chrome-less <audio> plus our own
  // LIVE indicator avoids that false affordance; the play/pause button only
  // controls local listening, not the underlying stream (see Start/Stop).
  document.getElementById('map-panel-body').innerHTML = isAudio
    ? `<div class="stream-audio-bar">
         <span id="stream-live-dot" class="stream-live-dot buffering"></span>
         <span id="stream-live-label" class="stream-live-label">BUFFERING…</span>
         <audio id="stream-audio"></audio>
         <button id="stream-audio-toggle" class="data-btn" type="button">Pause</button>
       </div>`
    : `<img id="stream-img" src="/api/repositories/${repoId}/stream" alt="${schema.label} stream">`;
  if (isAudio) {
    playAudioStream(repoId);
    document.getElementById('stream-audio-toggle').addEventListener('click', (e) => {
      const audio = document.getElementById('stream-audio');
      if (audio.paused) {
        audio.play().catch(() => {});
        e.target.textContent = 'Pause';
      } else {
        audio.pause();
        e.target.textContent = 'Resume';
      }
    });
  } else {
    document.getElementById('stream-img').addEventListener('error', () => {
      document.getElementById('map-panel-body').innerHTML =
        '<div class="stream-placeholder">// stream unavailable — click Start Streaming first</div>';
    });
  }
  addLog(`Opened stream · ${schema.label}`, ACCENT.repository);
}

// Streaming-audio chunks come one complete WAV clip per request (see
// odf.ui.server.stream_records) rather than over one multiplexed connection
// like the MJPEG video stream above — multipart/x-mixed-replace has no
// browser support for <audio>. This chains playback client-side: play one
// chunk, and on 'ended' switch to the next — until audioStreamActive is
// cleared by leaving the view (see setMapMode). The chunk after the one
// about to play is fetched in the background (nextChunk) as soon as
// playback starts, rather than waiting for 'ended' to begin fetching — that
// hides the request round-trip so there's no gap between chunks on top of
// the repository's own chunk-to-chunk phase continuity (see
// app.audio.synth_melody_wav in the streaming-audio-view example).
//
// The very first fetch can take up to one whole chunk period: subscribing
// to a stream that's already running attaches to a queue that only holds
// the single newest not-yet-delivered chunk (see DispatchRadio's own
// comments on _INTERVAL_SECONDS), and a brand new subscriber starts with
// nothing queued — it waits for the producer's next tick. The BUFFERING
// indicator (see showStreamView) exists so that wait reads as expected
// startup, not as a broken player.
async function playAudioStream(repoId) {
  audioStreamActive = true;
  const audio = document.getElementById('stream-audio');
  const fetchChunk = () => fetch(`/api/repositories/${repoId}/stream`).then((res) => {
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.blob();
  });
  let nextChunk = null;
  const playNext = async (prefetched) => {
    if (!audioStreamActive) return;
    let blob;
    try {
      blob = await (prefetched || fetchChunk());
    } catch (err) {
      if (audioStreamActive) {
        document.getElementById('map-panel-body').innerHTML =
          '<div class="stream-placeholder">// stream unavailable — click Start Streaming first</div>';
      }
      return;
    }
    if (!audioStreamActive) return;
    if (audio.src) URL.revokeObjectURL(audio.src);
    audio.src = URL.createObjectURL(blob);
    audio.play().catch(() => {});
    document.getElementById('stream-live-dot')?.classList.remove('buffering');
    const label = document.getElementById('stream-live-label');
    if (label) label.textContent = 'LIVE';
    nextChunk = fetchChunk();
  };
  audio.addEventListener('ended', () => playNext(nextChunk));
  await playNext();
}

// ── Map view ──────────────────────────────────────────────────────────────
// Backs the "View Map" action on repository nodes whose DataView is a
// LocationView (see odf.view.LocationView / odf.ui.data.resolve_view).
// Reuses the same GET /api/repositories/{id}/records endpoint the table
// view reads — no separate geo endpoint. This is the whole view for the
// repo, not a second mode alongside a table — records show up only as
// marker popups. Plots real OpenStreetMap tiles via Leaflet (loaded from a
// CDN, see <head>/the script tag near the top of <body>) with one marker per
// geo-tagged record; clicking a marker pops up that record's actual field
// values. Dark theme is approximated by CSS-inverting the raster tiles
// (there's no vendored dark tile set) — markers/popups stay themed normally
// via CSS custom properties.

let geoMap = null;
let geoMarkers = null;

function destroyGeoMap() {
  if (geoMap) { geoMap.remove(); geoMap = null; geoMarkers = null; }
}

async function showMapView(repoId) {
  destroyGeoMap(); // switching repos while already in geo mode would otherwise orphan the old map
  enterRepoView(repoId);
  const schema = repoSchemas[repoId];
  setMapMode('geo');
  document.getElementById('map-panel-title').textContent = `${schema.label} · map`;
  renderModeSwitcher(schema, 'location');
  renderReplayToggle(schema);
  document.getElementById('map-panel-body').innerHTML =
    '<div id="geo-map"></div><div id="geo-pagination" class="floating-pagination"></div>';
  await refreshGeoMap();
}

// Fetches one page of records at a time (same tableOffset/tablePageSize as
// the table view) and plots only that page's markers — plotting the whole
// repository at once wouldn't scale for a large dataset. In replay mode,
// skips the network entirely and plots a cumulative trail from the record
// set already cached by enterReplayMode (see renderGeoTimelineBar).
async function refreshGeoMap() {
  const schema = repoSchemas[activeRepoId];
  if (replayMode && replayRepoId === activeRepoId) {
    renderGeoMap(schema, replayRecords.filter(r => r[replayField] <= replayPos), { trail: true });
    renderGeoTimelineBar(schema);
    return;
  }
  let records;
  try {
    const res = await fetch(`/api/repositories/${activeRepoId}/records?${recordsQuery()}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    records = await res.json();
    tableTotal = Number(res.headers.get('X-Total-Count') ?? records.length);
  } catch (err) {
    const body = document.getElementById('map-panel-body');
    if (mapMode === 'geo') { destroyGeoMap(); body.innerHTML = '<span class="detail-empty">// failed to load records</span>'; }
    return;
  }
  if (!records.length && tableOffset > 0) {
    tableOffset = Math.max(0, tableOffset - tablePageSize);
    return refreshGeoMap();
  }
  renderGeoMap(schema, records);
  renderGeoPagination();
}

function renderGeoPagination() {
  const el = document.getElementById('geo-pagination');
  if (!el) return; // view was swapped away while the fetch was in flight
  el.innerHTML = renderPaginationBar();
  wirePaginationBar(refreshGeoMap);
}

// Cumulative trail replay: dragging/playing re-filters the cached
// replayRecords to `time <= pos` and redraws every visible marker (see
// renderGeoMap's `trail` option for the newest-marker styling).
function renderGeoTimelineBar(schema) {
  const el = document.getElementById('geo-pagination');
  if (!el) return; // view was swapped away while the fetch was in flight
  el.innerHTML = renderTimelineBar();
  const showAt = pos => renderGeoMap(schema, replayRecords.filter(r => r[replayField] <= pos), { trail: true });
  wireTimelineBar({
    onScrubInput: showAt,
    onPlay: () => { setReplayPlaying(true); startSyntheticClock(showAt); },
    onPause: () => { setReplayPlaying(false); stopReplayClock(); },
  });
}

function geoPopupHtml(schema, record) {
  const rows = schema.fields.map(f =>
    `<tr><th>${escapeHtml(f.name)}</th><td>${escapeHtml(record[f.name] ?? '')}</td></tr>`
  ).join('');
  return `<div class="geo-popup">` +
    `<div class="detail-title" style="color:${ACCENT.repository}">${escapeHtml(schema.label)}</div>` +
    `<table class="data-table">${rows}</table>` +
    `</div>`;
}

// `opts.trail` (replay mode): every record with time <= the scrub position
// stays visible as a dimmed trail marker, with the single newest one drawn
// larger/opaque as the "current" position — see renderGeoTimelineBar.
function renderGeoMap(schema, records, opts = {}) {
  const el = document.getElementById('geo-map');
  if (!el) return; // view was swapped away while the fetch was in flight

  const [latField, lonField] = schema.view.fields;
  const points = records
    .map(r => ({ lat: Number(r[latField]), lon: Number(r[lonField]), record: r }))
    .filter(p => Number.isFinite(p.lat) && Number.isFinite(p.lon));

  const isNewMap = !geoMap;
  if (isNewMap) {
    geoMap = L.map(el, { attributionControl: true, zoomControl: true }).setView([20, 0], 2);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors',
    }).addTo(geoMap);
    geoMarkers = L.layerGroup().addTo(geoMap);
  } else {
    geoMarkers.clearLayers();
  }

  const accent = ACCENT.repository;
  points.forEach((p, i) => {
    const isCurrent = opts.trail && i === points.length - 1;
    L.circleMarker([p.lat, p.lon], {
      radius: opts.trail ? (isCurrent ? 8 : 4) : 6,
      color: accent,
      weight: 1.5,
      fillColor: accent,
      fillOpacity: opts.trail ? (isCurrent ? 1 : 0.35) : 0.85,
    })
      .bindPopup(geoPopupHtml(schema, p.record))
      .addTo(geoMarkers);
  });

  if (isNewMap) {
    // In replay mode, fit to the whole route up front (replayRecords) rather
    // than just the currently-visible trail, so the view doesn't need to
    // zoom out repeatedly as the trail grows.
    const boundsSource = opts.trail
      ? replayRecords
          .map(r => ({ lat: Number(r[latField]), lon: Number(r[lonField]) }))
          .filter(p => Number.isFinite(p.lat) && Number.isFinite(p.lon))
      : points;
    if (boundsSource.length === 1) {
      geoMap.setView([boundsSource[0].lat, boundsSource[0].lon], 12);
    } else if (boundsSource.length > 1) {
      geoMap.fitBounds(L.latLngBounds(boundsSource.map(p => [p.lat, p.lon])), { padding: [30, 30], maxZoom: 13 });
    }
  }

  geoMap.invalidateSize();
}

// ── Image view ────────────────────────────────────────────────────────────
// Backs the "View Images" action on repository nodes whose DataView is an
// ImageView — a grid of thumbnails, one per record, each sourced from
// GET /api/repositories/{id}/records/{key}/media (see UiServer.record_media).
// Selecting a thumbnail opens that image in #image-lightbox, which covers
// the panel body (not the panel header) until closed.

let imageRecords = []; // the grid's records, in display order
let imageIndex = -1;   // index into imageRecords of the image open in the lightbox, -1 when closed

function mediaUrl(repoId, key) {
  return `/api/repositories/${repoId}/records/${encodeURIComponent(key)}/media`;
}

// The type the server detected for a record's media, to name a format this
// browser can't decode (HEIC outside Safari, say). Only the response headers
// are needed, so the body is dropped unread.
async function mediaContentType(url) {
  try {
    const res = await fetch(url);
    if (res.body) res.body.cancel();
    return res.ok ? (res.headers.get('Content-Type') || '') : `HTTP ${res.status}`;
  } catch (err) {
    return '';
  }
}

function mediaFallbackHtml(detail) {
  return "<span>Can't display this image</span>" +
    (detail ? `<span class="media-fallback-detail">${escapeHtml(detail)}</span>` : '');
}

async function showImageView(repoId) {
  activeRepoId = repoId;
  const schema = repoSchemas[repoId];
  setMapMode('image');
  closeImageLightbox();
  document.getElementById('map-panel-title').textContent = `${schema.label} · images`;
  await refreshImageView();
}

async function refreshImageView() {
  const schema = repoSchemas[activeRepoId];
  const body = document.getElementById('map-panel-body');
  imageRecords = [];
  let records;
  try {
    const res = await fetch(`/api/repositories/${activeRepoId}/records`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    records = await res.json();
  } catch (err) {
    body.innerHTML = '<span class="detail-empty">// failed to load records</span>';
    return;
  }
  if (!records.length) {
    body.innerHTML = '<span class="detail-empty">// no records</span>';
    return;
  }
  imageRecords = records;
  body.innerHTML = '<div class="media-grid">' + records.map((r, i) => {
    const key = escapeHtml(r[schema.key]);
    return `<button class="media-tile" data-index="${i}" title="Open ${key}">` +
      `<img loading="lazy" src="${escapeHtml(mediaUrl(activeRepoId, r[schema.key]))}" alt="${key}">` +
      `<div class="media-caption">${key}</div></button>`;
  }).join('') + '</div>';
  const grid = body.querySelector('.media-grid');
  grid.addEventListener('click', e => {
    const tile = e.target.closest('.media-tile');
    if (tile) openImageLightbox(Number(tile.dataset.index));
  });
  // `error` doesn't bubble, hence the capturing listener. The tile stays a
  // button, so an image that won't render can still be opened.
  grid.addEventListener('error', async e => {
    if (e.target.tagName !== 'IMG') return;
    const url = e.target.src;
    const fallback = document.createElement('div');
    fallback.className = 'media-fallback';
    fallback.innerHTML = mediaFallbackHtml('');
    e.target.replaceWith(fallback);
    fallback.innerHTML = mediaFallbackHtml(await mediaContentType(url));
  }, true);
}

function openImageLightbox(index) {
  const record = imageRecords[index];
  if (!record) return;
  const schema = repoSchemas[activeRepoId];
  const url = mediaUrl(activeRepoId, record[schema.key]);
  imageIndex = index;

  const img = document.getElementById('image-lightbox-img');
  document.getElementById('image-lightbox-error').hidden = true;
  img.hidden = false;
  img.alt = String(record[schema.key]);
  img.src = url;
  document.getElementById('image-lightbox-open').href = url;
  document.getElementById('image-lightbox-caption').innerHTML =
    `<span>${index + 1} / ${imageRecords.length}</span>` +
    Object.entries(record)
      .filter(([k]) => k !== schema.view.field)
      .map(([k, v]) => `<span><b>${escapeHtml(k)}</b>: ${escapeHtml(v ?? '')}</span>`)
      .join('');
  document.getElementById('image-lightbox-prev').disabled = index === 0;
  document.getElementById('image-lightbox-next').disabled = index === imageRecords.length - 1;

  const lightbox = document.getElementById('image-lightbox');
  lightbox.style.top = document.getElementById('map-panel-body').offsetTop + 'px';
  lightbox.hidden = false;
}

function closeImageLightbox() {
  if (imageIndex < 0) return;
  const tile = document.querySelector(`.media-tile[data-index="${imageIndex}"]`);
  imageIndex = -1;
  document.getElementById('image-lightbox').hidden = true;
  document.getElementById('image-lightbox-img').removeAttribute('src');
  if (tile) tile.focus();
}

function stepImageLightbox(delta) {
  openImageLightbox(imageIndex + delta);
}

document.getElementById('image-lightbox-prev').addEventListener('click', () => stepImageLightbox(-1));
document.getElementById('image-lightbox-next').addEventListener('click', () => stepImageLightbox(1));
document.getElementById('image-lightbox-close').addEventListener('click', closeImageLightbox);
document.getElementById('image-lightbox-stage').addEventListener('click', e => {
  if (e.target === e.currentTarget) closeImageLightbox();
});
document.getElementById('image-lightbox-img').addEventListener('error', async e => {
  const index = imageIndex;
  if (index < 0) return;
  const error = document.getElementById('image-lightbox-error');
  e.target.hidden = true;
  error.innerHTML = mediaFallbackHtml('');
  error.hidden = false;
  const detail = await mediaContentType(e.target.src);
  if (imageIndex === index) error.innerHTML = mediaFallbackHtml(detail); // still on the same image
});

// ── Media view (bounded Video/Audio) ────────────────────────────────────
// Backs the "View Video"/"View Audio" action on repository nodes whose
// DataView is a VideoView/AudioView — a list of seekable clips, one per
// record. Distinct from the live "Stream view" above: this repo is
// ReadableProtocol, not StreamableProtocol, so there's no Start/Stop toggle
// and no shared background feed, just ordinary bounded records.

async function showMediaView(repoId) {
  enterRepoView(repoId);
  const schema = repoSchemas[repoId];
  setMapMode('media');
  document.getElementById('map-panel-title').textContent = `${schema.label} · ${schema.view.kind}`;
  renderReplayToggle(schema);
  await refreshMediaView();
}

async function refreshMediaView() {
  const schema = repoSchemas[activeRepoId];
  const body = document.getElementById('map-panel-body');
  if (replayMode && replayRepoId === activeRepoId) {
    renderMediaReplay(schema);
    return;
  }
  let records;
  try {
    const res = await fetch(`/api/repositories/${activeRepoId}/records`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    records = await res.json();
  } catch (err) {
    body.innerHTML = '<span class="detail-empty">// failed to load records</span>';
    return;
  }
  if (!records.length) {
    body.innerHTML = '<span class="detail-empty">// no records</span>';
    return;
  }
  const tag = schema.view.kind === 'video' ? 'video' : 'audio';
  body.innerHTML = '<div class="media-list">' + records.map(r => {
    const key = escapeHtml(r[schema.key]);
    return `<div class="media-item"><div class="media-caption">${key}</div>` +
      `<${tag} controls src="${escapeHtml(mediaUrl(activeRepoId, r[schema.key]))}"></${tag}></div>`;
  }).join('') + '</div>';
}

// Replay mode renders a single active clip (the common case is one clip per
// repository) instead of a list of every clip, bound bidirectionally to the
// shared timeline — see wireMediaReplay. There is deliberately no cross-clip
// auto-chaining: if several timestamped clips exist, scrubbing past one's
// range just swaps to whichever record's time range contains the new
// position, on the next scrub/tick.
function renderMediaReplay(schema) {
  const body = document.getElementById('map-panel-body');
  const tag = schema.view.kind === 'video' ? 'video' : 'audio';
  const clip = activeClipFor(replayPos);
  const key = escapeHtml(String(clip[schema.key]));
  body.innerHTML =
    '<div class="media-list"><div class="media-item">' +
    `<div class="media-caption">${key}</div>` +
    `<${tag} controls id="replay-media-el" src="${escapeHtml(mediaUrl(activeRepoId, clip[schema.key]))}"></${tag}>` +
    '</div></div>' +
    `<div class="floating-pagination">${renderTimelineBar()}</div>`;
  wireMediaReplay(schema);
}

// The last record in replayRecords (sorted ascending by replayField) with
// time <= pos, or the first record if pos precedes every clip's start.
function activeClipFor(pos) {
  let clip = replayRecords[0];
  for (const r of replayRecords) {
    if (r[replayField] <= pos) clip = r;
    else break;
  }
  return clip;
}

function wireMediaReplay(schema) {
  const el = document.getElementById('replay-media-el');
  if (!el) return;
  let currentClip = activeClipFor(replayPos);

  const onLoadedMetadata = () => {
    el.currentTime = Math.min(Math.max(0, replayPos - currentClip[replayField]), el.duration || 0);
  };
  const onTimeUpdate = () => setReplayPos(Number(currentClip[replayField]) + el.currentTime);
  const onPlaying = () => setReplayPlaying(true);
  const onPaused = () => setReplayPlaying(false);

  el.addEventListener('loadedmetadata', onLoadedMetadata);
  el.addEventListener('timeupdate', onTimeUpdate);
  el.addEventListener('play', onPlaying);
  el.addEventListener('pause', onPaused);
  el.addEventListener('ended', onPaused);
  if (el.readyState >= 1) onLoadedMetadata(); // metadata already available (e.g. cached clip)

  replayMediaCleanup = () => {
    el.removeEventListener('loadedmetadata', onLoadedMetadata);
    el.removeEventListener('timeupdate', onTimeUpdate);
    el.removeEventListener('play', onPlaying);
    el.removeEventListener('pause', onPaused);
    el.removeEventListener('ended', onPaused);
  };

  // Dragging the shared scrubber swaps the active clip (if the new position
  // falls outside the currently loaded one) or just seeks within it.
  wireTimelineBar({
    onScrubInput: pos => {
      const clip = activeClipFor(pos);
      if (String(clip[schema.key]) !== String(currentClip[schema.key])) {
        currentClip = clip;
        el.src = mediaUrl(activeRepoId, clip[schema.key]);
        // el.currentTime is set once `loadedmetadata` fires for the new src.
      } else {
        el.currentTime = Math.min(Math.max(0, pos - clip[replayField]), el.duration || 0);
      }
    },
    onPlay: () => el.play(),
    onPause: () => el.pause(),
  });
}

// ── Document view ─────────────────────────────────────────────────────────
// Backs the "View Document" action on repository nodes whose DataView is a
// DocumentView — one record per block, the declared JSON-shaped field
// rendered as a collapsible tree (Postman-style) instead of a stringified
// table cell; the record's other fields show as a small header above it.

async function showDocumentView(repoId) {
  activeRepoId = repoId;
  const schema = repoSchemas[repoId];
  setMapMode('document');
  document.getElementById('map-panel-title').textContent = `${schema.label} · documents`;
  await refreshDocumentView();
}

async function refreshDocumentView() {
  const schema = repoSchemas[activeRepoId];
  const body = document.getElementById('map-panel-body');
  let records;
  try {
    const res = await fetch(`/api/repositories/${activeRepoId}/records`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    records = await res.json();
  } catch (err) {
    body.innerHTML = '<span class="detail-empty">// failed to load records</span>';
    return;
  }
  if (!records.length) {
    body.innerHTML = '<span class="detail-empty">// no records</span>';
    return;
  }
  const field = schema.view.field;
  body.innerHTML = '<div class="doc-list">' + records.map(r => {
    const header = Object.entries(r)
      .filter(([k]) => k !== field)
      .map(([k, v]) => `<span><b>${escapeHtml(k)}</b>: ${escapeHtml(v ?? '')}</span>`)
      .join('');
    return `<div class="doc-record"><div class="doc-header">${header}</div>` +
      `<div class="doc-tree">${renderJsonTree(r[field])}</div></div>`;
  }).join('') + '</div>';
}

function renderJsonTree(value) {
  if (value === null || value === undefined) return '<span class="doc-null">null</span>';
  if (Array.isArray(value)) {
    if (!value.length) return '<span class="doc-punct">[]</span>';
    return '<div class="doc-node"><span class="doc-punct">[</span><div class="doc-children">' +
      value.map(v => `<div>${renderJsonTree(v)}</div>`).join('') +
      '</div><span class="doc-punct">]</span></div>';
  }
  if (typeof value === 'object') {
    const entries = Object.entries(value);
    if (!entries.length) return '<span class="doc-punct">{}</span>';
    return '<div class="doc-node"><span class="doc-punct">{</span><div class="doc-children">' +
      entries.map(([k, v]) => `<div><span class="doc-key">${escapeHtml(k)}</span>: ${renderJsonTree(v)}</div>`).join('') +
      '</div><span class="doc-punct">}</span></div>';
  }
  if (typeof value === 'string') return `<span class="doc-string">"${escapeHtml(value)}"</span>`;
  return `<span class="doc-scalar">${escapeHtml(String(value))}</span>`;
}

// ── Timeseries view ───────────────────────────────────────────────────────
// Backs the "View Timeline" action on repository nodes whose DataView is a
// TimeseriesView — a line chart plotting every other numeric entity field
// against the declared timestamp field. Plain inline SVG, no charting
// dependency (see ChartProtocol/showChartView above for anything fancier —
// that's a component-authored, server-rendered alternative).

async function showTimeseriesView(repoId) {
  enterRepoView(repoId);
  const schema = repoSchemas[repoId];
  setMapMode('timeseries');
  document.getElementById('map-panel-title').textContent = `${schema.label} · timeline`;
  renderModeSwitcher(schema, 'timeseries');
  renderReplayToggle(schema);
  await refreshTimeseriesView();
}

async function refreshTimeseriesView() {
  const schema = repoSchemas[activeRepoId];
  const body = document.getElementById('map-panel-body');
  if (replayMode && replayRepoId === activeRepoId) {
    renderTimeseriesChart(schema, replayRecords.filter(r => r[replayField] <= replayPos));
    return;
  }
  let records;
  try {
    const res = await fetch(`/api/repositories/${activeRepoId}/records?${recordsQuery()}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    records = await res.json();
    tableTotal = Number(res.headers.get('X-Total-Count') ?? records.length);
  } catch (err) {
    body.innerHTML = '<span class="detail-empty">// failed to load records</span>';
    return;
  }
  if (!records.length && tableOffset > 0) {
    tableOffset = Math.max(0, tableOffset - tablePageSize);
    return refreshTimeseriesView();
  }
  renderTimeseriesChart(schema, records);
}

// Renders whichever bottom bar is active — the replay timeline vs ordinary
// pagination — sharing the same `.floating-pagination` container both
// branches of renderTimeseriesChart use (empty-state and normal).
function renderTsBottomBar(schema) {
  if (replayMode && replayRepoId === activeRepoId) {
    const showAt = pos => renderTimeseriesChart(schema, replayRecords.filter(r => r[replayField] <= pos));
    return {
      html: renderTimelineBar(),
      wire: () => wireTimelineBar({
        onScrubInput: showAt,
        onPlay: () => { setReplayPlaying(true); startSyntheticClock(showAt); },
        onPause: () => { setReplayPlaying(false); stopReplayClock(); },
      }),
    };
  }
  return { html: renderPaginationBar(), wire: () => wirePaginationBar(refreshTimeseriesView) };
}

// Renders one page of records as a line chart — pagination is shared with
// the table view (same tableOffset/tablePageSize), since plotting the whole
// repository at once wouldn't scale for a large dataset. The per-field
// visibility selection (tsHiddenFields) is driven by clicking legend items,
// and persists across page/mode switches for the same repository.
function renderTimeseriesChart(schema, records) {
  const body = document.getElementById('map-panel-body');
  if (tsHiddenFieldsRepoId !== activeRepoId) {
    tsHiddenFields = new Set();
    tsHiddenFieldsRepoId = activeRepoId;
  }
  const bottomBar = renderTsBottomBar(schema);
  const isReplay = replayMode && replayRepoId === activeRepoId;
  if (!records.length) {
    body.innerHTML = '<span class="detail-empty">// no records</span>' +
      `<div class="floating-pagination">${bottomBar.html}</div>`;
    bottomBar.wire();
    return;
  }
  const tsField = schema.view.field;
  const numericFields = schema.fields
    .map(f => f.name)
    .filter(name => name !== tsField && typeof records[0][name] === 'number');
  const visibleFields = numericFields.filter(name => !tsHiddenFields.has(name));
  const sorted = [...records].sort((a, b) => a[tsField] - b[tsField]);
  const w = 640, h = 280, pad = 32;
  const xs = sorted.map(r => Number(r[tsField]));
  const xMin = Math.min(...xs), xMax = Math.max(...xs);
  const xScale = x => xMax === xMin ? pad : pad + ((x - xMin) / (xMax - xMin)) * (w - 2 * pad);
  const colors = [ACCENT.repository, ACCENT.component, ACCENT.service, ACCENT.task, ACCENT.pipeline];
  const series = visibleFields.map(name => {
    const i = numericFields.indexOf(name);
    const ys = sorted.map(r => Number(r[name]));
    const yMin = Math.min(...ys), yMax = Math.max(...ys);
    const yScale = y => yMax === yMin ? h / 2 : h - pad - ((y - yMin) / (yMax - yMin)) * (h - 2 * pad);
    const points = sorted.map((r, idx) => `${xScale(xs[idx])},${yScale(Number(r[name]))}`).join(' ');
    const color = colors[i % colors.length];
    // Replay mode: a small circle at each visible series' last point marks
    // the playhead — the leading edge of the progressively-revealed chart.
    const lastIdx = sorted.length - 1;
    const playhead = isReplay
      ? `<circle cx="${xScale(xs[lastIdx])}" cy="${yScale(Number(sorted[lastIdx][name]))}" r="3.5" fill="${color}"/>`
      : '';
    return `<polyline points="${points}" fill="none" stroke="${color}" stroke-width="1.5"/>${playhead}`;
  }).join('');
  const legend = numericFields.map((name, i) => {
    const hidden = tsHiddenFields.has(name);
    return `<label class="ts-legend-item${hidden ? ' hidden' : ''}" data-field="${escapeHtml(name)}" title="Click to ${hidden ? 'show' : 'hide'}">` +
      `<span class="ts-swatch" style="background:${colors[i % colors.length]}"></span>${escapeHtml(name)}</label>`;
  }).join('');
  const chart = visibleFields.length
    ? `<svg class="timeseries-chart" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">${series}</svg>`
    : '<span class="detail-empty">// select a column to plot</span>';
  body.innerHTML = `<div class="ts-legend">${legend}</div>` + chart +
    `<div class="floating-pagination">${bottomBar.html}</div>`;

  body.querySelectorAll('.ts-legend-item').forEach(el => {
    el.addEventListener('click', () => {
      const name = el.dataset.field;
      if (tsHiddenFields.has(name)) tsHiddenFields.delete(name);
      else tsHiddenFields.add(name);
      renderTimeseriesChart(schema, records);
    });
  });
  bottomBar.wire();
}

// ── Logs view ─────────────────────────────────────────────────────────────
// Backs the "Show Logs" action, present on every node. Reads
// GET /api/components/{id}/logs, which tails that component's own log file
// (see odf.logger.LogManager — every component gets one automatically).
// Polls while active so a running Service's logs update live.

const LOG_LEVEL_COLOR = {
  DEBUG: 'var(--text-dim)', INFO: 'var(--text-muted)',
  WARNING: 'var(--accent-task)', ERROR: 'var(--accent-alert)',
};

let activeLogComponentId = null;
let logsPollTimer = null;

async function showLogsView(id) {
  activeLogComponentId = id;
  const node = nodeMap[id];
  setMapMode('logs');
  document.getElementById('map-panel-title').textContent = `${node.label} · logs`;
  await refreshLogs();
  clearInterval(logsPollTimer);
  logsPollTimer = setInterval(refreshLogs, 2000);
}

async function refreshLogs() {
  const body = document.getElementById('map-panel-body');
  let entries;
  try {
    const res = await fetch(`/api/components/${activeLogComponentId}/logs`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    entries = await res.json();
  } catch (err) {
    body.innerHTML = '<span class="detail-empty">// failed to load logs</span>';
    return;
  }
  renderLogs(entries);
}

function renderLogs(entries) {
  const body = document.getElementById('map-panel-body');
  if (!entries.length) {
    body.innerHTML = '<span class="detail-empty">// no logs yet</span>';
    return;
  }
  const wasAtBottom = body.scrollTop + body.clientHeight >= body.scrollHeight - 4;
  let html = '<div class="map-logs-lines">';
  for (const e of entries) {
    const color = LOG_LEVEL_COLOR[e.level] || 'var(--text-muted)';
    html += '<div class="log-line">' +
      `<span class="dot" style="background:${color}"></span>` +
      (e.ts ? `<span class="ts">${escapeHtml(e.ts)}</span>` : '') +
      `<span>${escapeHtml(e.message)}</span></div>`;
  }
  html += '</div>';
  body.innerHTML = html;
  if (wasAtBottom) body.scrollTop = body.scrollHeight;
}

// ── Details view ─────────────────────────────────────────────────────────
// Backs the "Details" action, present on nodes whose node.details flag came
// back true from GET /api/topology (i.e. isinstance(instance,
// DetailsProtocol) server-side). Reads GET /api/components/{id}/details —
// a plain key/value dict the component itself returns from details(). A
// value that looks like a URL is rendered as a clickable link; the
// framework itself makes no such distinction, this is UI-only sugar.

let activeDetailsComponentId = null;

async function showDetailsView(id) {
  activeDetailsComponentId = id;
  const node = nodeMap[id];
  setMapMode('details');
  document.getElementById('map-panel-title').textContent = `${node.label} · details`;
  await refreshDetails();
}

async function refreshDetails() {
  const body = document.getElementById('map-panel-body');
  let entries;
  try {
    const res = await fetch(`/api/components/${activeDetailsComponentId}/details`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    entries = await res.json();
  } catch (err) {
    body.innerHTML = '<span class="detail-empty">// failed to load details</span>';
    return;
  }
  renderDetails(entries);
}

function renderDetails(entries) {
  const body = document.getElementById('map-panel-body');
  const keys = Object.keys(entries);
  if (!keys.length) {
    body.innerHTML = '<span class="detail-empty">// no details</span>';
    return;
  }
  let html = '<table class="data-table"><thead><tr><th>Key</th><th>Value</th></tr></thead><tbody>';
  for (const key of keys) {
    const value = String(entries[key]);
    const cell = /^https?:\/\//.test(value)
      ? `<a href="${escapeHtml(value)}" target="_blank" rel="noopener">${escapeHtml(value)}</a>`
      : escapeHtml(value);
    html += `<tr><td>${escapeHtml(key)}</td><td>${cell}</td></tr>`;
  }
  html += '</tbody></table>';
  body.innerHTML = html;
}

// ── Chart view ───────────────────────────────────────────────────────────
// Backs the "View Chart" action, present on nodes whose node.chart flag came
// back true from GET /api/topology (i.e. isinstance(instance, ChartProtocol)
// server-side). Points an iframe straight at GET
// /api/components/{id}/chart — the component builds its own self-contained
// HTML there (inline image/JS, no external refs) using whatever Python
// charting library it likes, so the framework itself never needs a JS
// charting dependency.

function showChartView(id) {
  const node = nodeMap[id];
  setMapMode('chart');
  document.getElementById('map-panel-title').textContent = `${node.label} · chart`;
  document.getElementById('map-panel-body').innerHTML =
    `<iframe id="chart-frame" src="/api/components/${id}/chart"></iframe>`;
}

// ── Init ──────────────────────────────────────────────────────────────────
// Unlike a hand-authored map, the graph isn't known until the project has
// resolved its Context server-side — so everything below waits on a single
// fetch of /api/topology before the canvas has anything to draw.

// Reassigned by loadUiExtensions() if [ui] brand is set in config — read by
// renderStats() below for the browser tab title, alongside hdr-brand (set
// directly, since that one has no other reason to be re-rendered per poll).
let BRAND = 'ODF';

// Loads custom icons/colors registered server-side (see odf.ui.extensions)
// before the first topology render, so a node already carrying a custom
// icon/color override doesn't flash through the type-default fallback on
// first paint. Icon scripts load sequentially via ODF.registerIcon (see
// "Icon/color extension hook" above); a script that fails to load is logged
// and skipped rather than blocking the rest of the UI.
async function loadUiExtensions() {
  let ext = { iconScripts: [], colors: {}, logo: null, brand: null };
  try {
    const res = await fetch('/api/ui/extensions');
    if (res.ok) ext = await res.json();
  } catch (err) {
    console.error('Failed to load UI extensions', err);
  }

  if (ext.logo) {
    const mark = document.getElementById('brand-mark');
    mark.classList.add('has-logo');
    mark.innerHTML = `<img src="${ext.logo}" alt="logo">`;
  }

  if (ext.brand) {
    BRAND = ext.brand;
    document.getElementById('hdr-brand').textContent = BRAND;
  }

  for (const src of ext.iconScripts) {
    await new Promise(resolve => {
      const script = document.createElement('script');
      script.src = src;
      script.onload = resolve;
      script.onerror = () => { console.error(`Failed to load icon script ${src}`); resolve(); };
      document.head.appendChild(script);
    });
  }

  for (const [name, hex] of Object.entries(ext.colors)) {
    COLOR_SWATCHES.push({ hex, label: name });
  }
}

async function init() {
  await loadUiExtensions();

  let data = { project: 'ODF Project', nodes: [], edges: [], stats: { objects: 0, links: 0, types: {} } };
  try {
    const res = await fetch('/api/topology');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    data = await res.json();
  } catch (err) {
    console.error('Failed to load topology', err);
    document.getElementById('map-title').textContent =
      'Topology · failed to load — is the project still running?';
  }

  try {
    const rr = await fetch('/api/repositories');
    if (rr.ok) {
      repoSchemas = Object.fromEntries((await rr.json()).map(r => [r.id, r]));
    }
  } catch (err) {
    console.error('Failed to load repositories', err);
  }

  try {
    const lr = await fetch('/api/layout');
    if (lr.ok) layoutOverrides = await lr.json();
  } catch (err) {
    console.error('Failed to load saved layout', err);
  }

  if (layoutOverrides._grid) gridExpand = { ...gridExpand, ...layoutOverrides._grid };

  nodes = data.nodes;
  edges = data.edges;
  nodeMap = Object.fromEntries(nodes.map(n => [n.id, n]));
  for (const [id, schema] of Object.entries(repoSchemas)) {
    if (nodeMap[id]) nodeMap[id].streaming = schema.streaming;
  }
  for (const [id, pos] of Object.entries(layoutOverrides)) {
    if (!nodeMap[id]) continue;
    if (pos.icon) nodeMap[id].icon = pos.icon;
    if (pos.color) nodeMap[id].color = pos.color;
  }
  byDepth = [...nodes];
  computeGridBounds();
  renderStats(data);

  buildSidebar();
  initTheme();
  initSidebarTabs();
  window.addEventListener('resize', resize);
  resize();
  observeMapSize();
  updateCoordReadout({ col: 0, row: 0 });

  updateGridTitle();

  tickClock();
  setInterval(tickClock, 1000);

  addLog(`${data.stats.objects} objects · ${data.stats.links} links resolved`);
  addLog(`Topology loaded · ${data.project}`, TITLE_ACCENT);
  initChat();

  // Animation loop — powers blinking lights, pulsing beacons and wire pulses.
  // Capped at ~30fps (plenty for these subtle effects) and paused while the
  // tab is hidden, since an uncapped 60fps full-canvas redraw running
  // forever in the background is what was driving up CPU/GPU usage.
  const FRAME_INTERVAL = 1000 / 30;
  const reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  let lastFrameTime = 0;

  function loop(ts) {
    requestAnimationFrame(loop);
    if (document.hidden) return;
    if (ts - lastFrameTime < FRAME_INTERVAL) return;
    lastFrameTime = ts;
    animT = ts / 1000;
    render();
  }

  if (reduceMotion) {
    render(); // static frame only — no continuous rAF loop for reduced-motion users
  } else {
    requestAnimationFrame(loop);
  }
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) render(); // repaint immediately on return instead of waiting for the next tick
  });
}

// Deferred until the scripts after this one — the icon group files and
// theme.js — have run, so the first paint already has every built-in icon.
document.addEventListener('DOMContentLoaded', init);
