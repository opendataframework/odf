// Phosphor line art: icons drawn as bright outlines over the canvas color
// (hiding the grid behind them, with no tint), blooming when lit, on a
// dotted character-cell grid with a `+` at each cell's center.
ODF.registerTheme({
  faces: {
    fill: 'tint',
    tint:    { top: 0,    left: 0,    right: 0 },
    tintLit: { top: 0.06, left: 0.04, right: 0.02 },
    occlude: true,
    outline: 'accent',
    stroke:    { top: 0.9, left: 0.75, right: 0.6 },
    strokeLit: { top: 1,   left: 1,    right: 0.9 },
  },
  emptyTile(sx, sy) {
    tilePath(sx, sy);
    ctx.fillStyle = TILE_FILL;
    ctx.fill();
    ctx.strokeStyle = TILE_STROKE;
    ctx.lineWidth = 0.8;
    ctx.setLineDash([1, 3]);
    ctx.stroke();
    ctx.fillStyle = TILE_STROKE;
    ctx.fillRect(sx - 2, sy - 0.5, 4, 1);
    ctx.fillRect(sx - 0.5, sy - 2, 1, 4);
  },
  litShadow(part, accent) {
    ctx.shadowColor = accent;
    ctx.shadowBlur = { tile: 8, face: 10, top: 14 }[part];
  },
});
