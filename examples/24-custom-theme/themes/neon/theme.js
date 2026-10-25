// Neon coast: icons as neon tubing, a faint tint behind bright outlines in
// their accent, glowing when lit, each over a soft pool of its own light on
// the floor. Empty tiles are a checkered floor in two tones from
// `--tile-a`/`--tile-b`, edged in `--tile-grid`, so night gets a dark floor
// with a pink neon grid and day a pastel terrazzo. `--glow` scales every
// glow, so day mode keeps only a hint of it. Unlike ../pixel and
// ../park, this sets no `pixelSize`: the canvas stays at the screen's
// resolution, where the glows stay smooth.
(() => {
  let tileA = '#1a0d36';
  let tileB = '#160b2e';
  let tileGrid = 'rgba(255,47,168,.28)';
  let glow = 1;

  ODF.registerTheme({
    labelFont: "'Rajdhani', 'Arial Narrow', sans-serif",
    labelSize: 12,
    faces: {
      fill: 'tint',
      tint:    { top: 0.16, left: 0.12, right: 0.08 },
      tintLit: { top: 0.28, left: 0.2,  right: 0.14 },
      occlude: true,
      outline: 'accent',
      lineScale: 1.2,
      stroke:    { top: 1, left: 0.85, right: 0.75 },
      strokeLit: { top: 1, left: 1,    right: 1 },
    },
    onReadTheme(v) {
      tileA = v('--tile-a') || tileA;
      tileB = v('--tile-b') || tileB;
      tileGrid = v('--tile-grid') || tileGrid;
      glow = parseFloat(v('--glow')) || 0;
    },
    emptyTile(sx, sy) {
      const { col, row } = isoInverse(sx, sy);
      tilePath(sx, sy);
      ctx.fillStyle = (col + row) % 2 === 0 ? tileA : tileB;
      ctx.fill();
      ctx.strokeStyle = tileGrid;
      ctx.lineWidth = 1;
      ctx.stroke();
    },
    groundShadow(x, y, e, accent, lit) {
      const r = e.widthExtent * (lit ? 1.25 : 1.05);
      ctx.translate(x, y);
      ctx.scale(1, TH2 / TW2);
      const g = ctx.createRadialGradient(0, 0, 0, 0, 0, r);
      g.addColorStop(0, rgba(accent, (lit ? 0.35 : 0.2) * Math.max(glow, 0.4)));
      g.addColorStop(1, rgba(accent, 0));
      ctx.fillStyle = g;
      ctx.beginPath();
      ctx.arc(0, 0, r, 0, Math.PI * 2);
      ctx.fill();
    },
    litShadow(part, accent) {
      ctx.shadowColor = accent;
      ctx.shadowBlur = { tile: 12, face: 14, top: 18 }[part] * glow;
    },
    runRingLine: 1.8,
    runRingShadow(state, color) {
      ctx.shadowColor = color;
      ctx.shadowBlur = (state === 'running' ? 16 : 10) * glow;
    },
    flowLine(accent) {
      ctx.shadowColor = accent;
      ctx.shadowBlur = 12 * glow;
    },
  });
})();
