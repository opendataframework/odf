// Neobrutalist canvas: thick strokes, and a hard offset shadow in the
// tile-stroke ink color on lit shapes instead of a soft glow. Icons are flat
// solid accent faces in three tones, outlined in the same ink.
ODF.registerTheme({
  emptyTileLine: 2,
  tickSize: 2,
  tileLine: lit => lit ? 3 : 2,
  faceLine: 2,
  topLine: lit => lit ? 3.5 : 2.5,
  faces: {
    fill: 'shade',
    shade:    { top: 0.12, left: 0,    right: -0.3 },
    shadeLit: { top: 0.28, left: 0.14, right: -0.16 },
    outline: 'ink',
    detail: -0.75,
    lineScale: 0.6,
  },
  litShadow(part) {
    const offset = part === 'top' ? 4 : 3;
    ctx.shadowColor = TILE_STROKE;
    ctx.shadowBlur = 0;
    ctx.shadowOffsetX = offset;
    ctx.shadowOffsetY = offset;
  },
});
