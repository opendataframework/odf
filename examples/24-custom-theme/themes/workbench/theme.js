// Flat editor solids: opaque icon faces in a few close tones of their
// accent, outlined in ink, like file icons in a side bar. Nothing glows: a
// lit icon is a step lighter on a thicker tile line, run rings are thicker
// instead of blurred, and wires carry calls without a halo. The grid is a
// hairline lattice, like an editor's indent guides.
ODF.registerTheme({
  faces: {
    fill: 'shade',
    shade:    { top: 0.06, left: -0.1, right: -0.22 },
    shadeLit: { top: 0.22, left: 0.06, right: -0.06 },
    shadeBase: 'canvas',
    outline: 'ink',
    detail: -0.55,
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
