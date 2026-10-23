// Sunny hillside: icons as glossy, saturated solids, with a bright sheen over
// their upper part that ends in a crisp highlight edge, like a candy button,
// thinly outlined in their own accent. Each stands on the soft shadow of a
// passing cloud, which spreads when the icon is lit. The grid is a freshly
// mown lawn: tiles in two greens, alternating in diagonal stripes, under the
// open sky of the canvas background.
(() => {
  let grassA = '#6ab845';
  let grassB = '#74c24e';
  let shadowRgb = '30,80,20';
  let shadowAlpha = 0.38;

  ODF.registerTheme({
    faces: {
      fill: 'shade',
      shade:    { top: 0.28, left: 0.02, right: -0.22 },
      shadeLit: { top: 0.4,  left: 0.14, right: -0.1 },
      outline: 'accent',
      stroke:    { top: 0.4, left: 0.3, right: 0.3 },
      strokeLit: { top: 0.8, left: 0.6, right: 0.6 },
      detail: -0.5,
    },
    faceFill(side, accent, lit, t, frame) {
      const base = shadeHex(accent, t);
      const g = ctx.createLinearGradient(frame.x, frame.top, frame.x, frame.bottom);
      g.addColorStop(0,    mixHex(base, '#ffffff', lit ? 0.6 : 0.5));
      g.addColorStop(0.42, mixHex(base, '#ffffff', lit ? 0.3 : 0.22));
      g.addColorStop(0.46, base);
      g.addColorStop(1,    shadeHex(accent, t - 0.12));
      return g;
    },
    groundShadow(x, y, e, accent, lit) {
      const rx = e.widthExtent * (lit ? 1.25 : 1.1);
      const a = shadowAlpha * (lit ? 0.7 : 1);
      ctx.translate(x, y + TH2 * e.scale * 0.15);
      ctx.scale(1, TH2 / TW2);
      const g = ctx.createRadialGradient(0, 0, 0, 0, 0, rx);
      g.addColorStop(0,   `rgba(${shadowRgb},${a})`);
      g.addColorStop(0.6, `rgba(${shadowRgb},${a * 0.4})`);
      g.addColorStop(1,   `rgba(${shadowRgb},0)`);
      ctx.fillStyle = g;
      ctx.beginPath();
      ctx.arc(0, 0, rx, 0, Math.PI * 2);
      ctx.fill();
    },
    onReadTheme(v) {
      grassA = v('--meadow-grass-a') || grassA;
      grassB = v('--meadow-grass-b') || grassB;
      shadowRgb = v('--meadow-shadow-rgb') || shadowRgb;
      shadowAlpha = parseFloat(v('--meadow-shadow-alpha')) || shadowAlpha;
    },
    litShadow(part, accent) {
      ctx.shadowColor = rgba(accent, 0.55);
      ctx.shadowBlur = { tile: 6, face: 8, top: 10 }[part];
    },
    emptyTile(sx, sy) {
      // The tile's column (see iso()), so stripes run along the rows.
      const col = Math.round(((sx - ORIGIN_X) / TW2 + (sy - ORIGIN_Y) / TH2) / 2);
      tilePath(sx, sy);
      ctx.fillStyle = col % 2 ? grassB : grassA;
      ctx.fill();
      ctx.strokeStyle = TILE_STROKE;
      ctx.lineWidth = 0.5;
      ctx.stroke();
    },
    runRingLine: 1.6,
    runRingShadow(state, color) {
      ctx.shadowColor = rgba(color, 0.6);
      ctx.shadowBlur = state === 'running' ? 8 : 4;
    },
    flowLine(accent) {
      ctx.shadowColor = rgba(accent, 0.5);
      ctx.shadowBlur = 5;
    },
  });
})();
