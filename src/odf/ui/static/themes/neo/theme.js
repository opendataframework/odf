// Neobrutalist canvas: thick strokes, and a hard offset shadow in the
// tile-stroke ink color on lit shapes instead of a soft glow.
ODF.registerTheme({
  emptyTileLine: 2,
  tickSize: 2,
  tileLine: lit => lit ? 3 : 2,
  faceLine: 2,
  topLine: lit => lit ? 3.5 : 2.5,
  litShadow(part) {
    const offset = part === 'top' ? 4 : 3;
    ctx.shadowColor = TILE_STROKE;
    ctx.shadowBlur = 0;
    ctx.shadowOffsetX = offset;
    ctx.shadowOffsetY = offset;
  },
});
