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
    // Micro 5 is drawn on an 11px em: at 22 CSS pixels each of its pixels is
    // one canvas pixel, and `labelSnap` keeps it so at any zoom, on whole
    // canvas pixels. It has no bold, and an ink shadow lifts it off the grass.
    labelFont: "'Micro 5', Tahoma, sans-serif",
    labelSize: 22,
    labelSnap: true,
    labelBold: false,
    labelAlpha: 0.9,
    labelShadow: true,
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
