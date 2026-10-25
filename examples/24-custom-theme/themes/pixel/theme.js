// Pixel art: the topology canvas is drawn at half resolution (`pixelSize`)
// and theme.css scales it back up without smoothing, so every line, face and
// label lands on a 2×2 CSS pixel grid. Icons are flat sprites in three tones
// of their accent, outlined in ink. Nothing glows: a lit icon is a tone
// lighter on a thicker tile line. Each empty tile is a solid diamond with a
// dithered checker at its center.
ODF.registerTheme({
  pixelSize: 2,
  // Silkscreen is drawn on an 8px grid: at 16 CSS pixels it lands on exactly
  // 8 canvas pixels, and `labelSnap` keeps it there at any zoom, on whole
  // canvas pixels, so labels stay crisp at half resolution. An ink shadow
  // keeps them readable over the tiles.
  labelFont: "'Silkscreen', 'Courier New', monospace",
  labelSize: 16,
  labelSnap: true,
  labelAlpha: 0.85,
  labelShadow: true,
  faces: {
    fill: 'shade',
    shade:    { top: 0.2,  left: -0.1, right: -0.35 },
    shadeLit: { top: 0.4,  left: 0.1,  right: -0.15 },
    shadeBase: 'canvas',
    outline: 'ink',
    detail: -0.55,
  },
  emptyTileLine: 1,
  tileLine: lit => lit ? 2 : 1,
  faceLine: 1,
  topLine: lit => lit ? 2 : 1,
  litShadow() {},
  emptyTile(sx, sy) {
    tilePath(sx, sy);
    ctx.fillStyle = TILE_FILL;
    ctx.fill();
    ctx.strokeStyle = TILE_STROKE;
    ctx.lineWidth = 1;
    ctx.stroke();
    ctx.fillStyle = TILE_STROKE;
    for (const [dx, dy] of [[-2, -1], [0, -1], [-1, 0], [1, 0], [-2, 1], [0, 1]]) {
      ctx.fillRect(Math.round(sx) + dx, Math.round(sy) + dy, 1, 1);
    }
  },
  runRingLine: 2,
  runRingShadow() {},
  flowLine() {},
});
