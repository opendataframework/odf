// Studio clay: icons as matte painted solids under one soft key light from
// the top-left, so the top face is brightest and the right face darkest,
// with no outlines. Each face darkens toward the floor (ambient occlusion)
// and the icon stands on a soft contact shadow cast down-right. A lit icon
// lifts: its faces brighten and its shadow spreads out and fades. Nothing
// glows. The grid is a matte floor with barely visible seams.
(() => {
  let shadowRgb = '0,0,0';
  let shadowAlpha = 0.55;

  ODF.registerTheme({
    faces: {
      fill: 'shade',
      shade:    { top: 0.3,  left: 0,    right: -0.28 },
      shadeLit: { top: 0.42, left: 0.12, right: -0.16 },
      outline: 'none',
      detail: -0.5,
    },
    faceFill(side, accent, lit, t, frame) {
      const g = ctx.createLinearGradient(frame.x, frame.top, frame.x, frame.bottom);
      g.addColorStop(0,   shadeHex(accent, t + 0.08));
      g.addColorStop(0.6, shadeHex(accent, t));
      g.addColorStop(1,   shadeHex(accent, t - 0.22));
      return g;
    },
    groundShadow(x, y, e, accent, lit) {
      const rx = e.widthExtent * (lit ? 1.2 : 1.05);
      const a = shadowAlpha * (lit ? 0.65 : 1);
      ctx.translate(x + rx * 0.1, y + TH2 * e.scale * 0.2);
      ctx.scale(1, TH2 / TW2);
      const g = ctx.createRadialGradient(0, 0, 0, 0, 0, rx);
      g.addColorStop(0,   `rgba(${shadowRgb},${a})`);
      g.addColorStop(0.5, `rgba(${shadowRgb},${a * 0.45})`);
      g.addColorStop(1,   `rgba(${shadowRgb},0)`);
      ctx.fillStyle = g;
      ctx.beginPath();
      ctx.arc(0, 0, rx, 0, Math.PI * 2);
      ctx.fill();
    },
    onReadTheme(v) {
      shadowRgb = v('--clay-shadow-rgb') || shadowRgb;
      shadowAlpha = parseFloat(v('--clay-shadow-alpha')) || shadowAlpha;
    },
    tileLine: lit => lit ? 1 : 0.7,
    litShadow(part) {
      ctx.shadowColor = `rgba(${shadowRgb},${shadowAlpha * 0.5})`;
      ctx.shadowBlur = part === 'tile' ? 4 : 8;
      ctx.shadowOffsetX = part === 'tile' ? 0 : 1;
      ctx.shadowOffsetY = part === 'tile' ? 0 : 3;
    },
    emptyTile(sx, sy) {
      tilePath(sx, sy);
      ctx.fillStyle = TILE_FILL;
      ctx.fill();
      ctx.strokeStyle = TILE_STROKE;
      ctx.lineWidth = 0.5;
      ctx.stroke();
    },
    runRingLine: 1.6,
    runRingShadow(state, color) {
      ctx.shadowColor = rgba(color, 0.5);
      ctx.shadowBlur = state === 'running' ? 6 : 3;
    },
    flowLine(accent) {
      ctx.shadowColor = rgba(accent, 0.4);
      ctx.shadowBlur = 4;
    },
  });
})();
