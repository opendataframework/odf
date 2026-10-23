// Flat silhouettes: opaque icon faces in nearly one tone of their accent,
// outlined in ink, so an icon reads as a flat shape rather than a lit box.
// Nothing glows: a lit icon is a step lighter on a thicker tile line, run
// rings are thicker instead of blurred, and wires carry calls without a halo.
// The grid is a hairline graph-paper lattice with no center ticks.
ODF.registerTheme({
  faces: {
    fill: 'shade',
    shade:    { top: 0.02, left: -0.06, right: -0.12 },
    shadeLit: { top: 0.16, left: 0.08,  right: 0.02 },
    shadeBase: 'canvas',
    outline: 'ink',
    detail: -0.5,
  },
  tileLine: lit => lit ? 1.2 : 0.8,
  litShadow() {},
  emptyTile(sx, sy) {
    tilePath(sx, sy);
    ctx.strokeStyle = TILE_STROKE;
    ctx.lineWidth = 0.5;
    ctx.stroke();
  },
  runRingLine: 2,
  runRingShadow() {},
  flowLine() {},
});
