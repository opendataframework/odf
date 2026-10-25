// Theme park: the topology canvas is drawn at half resolution (`pixelSize`)
// and theme.css scales it back up without smoothing. Icons are sprite-like
// solids lit from above, a bright top over a mid left and a dark right face,
// outlined in a dark tone. Nothing glows. Empty tiles are a mown lawn: grass
// in two tones that alternate tile by tile, from `--grass-a`/`--grass-b`, so
// the day and night parks each have their own. Links are footpaths in the
// theme's sandy `--wire`.
(() => {
  let grassA = '#5f8f30';
  let grassB = '#578628';

  ODF.registerTheme({
    pixelSize: 2,
    // Large enough to stay legible on the half-resolution canvas.
    labelFont: "'Pixelify Sans', Tahoma, sans-serif",
    labelSize: 16,
    faces: {
      fill: 'shade',
      shade:    { top: 0.25, left: -0.05, right: -0.3 },
      shadeLit: { top: 0.45, left: 0.12,  right: -0.12 },
      outline: 'ink',
      detail: -0.55,
    },
    onReadTheme(v) {
      grassA = v('--grass-a') || grassA;
      grassB = v('--grass-b') || grassB;
    },
    emptyTile(sx, sy) {
      const { col, row } = isoInverse(sx, sy);
      tilePath(sx, sy);
      ctx.fillStyle = (col + row) % 2 === 0 ? grassA : grassB;
      ctx.fill();
      ctx.strokeStyle = TILE_STROKE;
      ctx.lineWidth = 1;
      ctx.stroke();
    },
    emptyTileLine: 1,
    tileLine: lit => lit ? 2 : 1,
    faceLine: 1,
    topLine: lit => lit ? 2 : 1,
    litShadow() {},
    runRingLine: 2,
    runRingShadow() {},
    flowLine() {},
  });
})();
