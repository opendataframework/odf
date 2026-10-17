// Chromatic-split fringe on lit shapes, giving the canvas the same
// RGB-misregistration look as the CSS chrome.
(() => {
  let splitA, splitB;

  const FRINGE = {
    tile: { alpha: 0.45, width: 1 },
    face: { alpha: 0.35, width: 0.8 },
    top:  { alpha: 0.4,  width: 1.3 },
  };

  // Rebuilds `buildPath`'s path offset by dx (via a transform, since an
  // already-recorded path can't be re-offset after the fact) and strokes it
  // in one channel color.
  function fringeStroke(buildPath, dx, color, alpha, width) {
    ctx.save();
    ctx.translate(dx, 0);
    buildPath();
    ctx.strokeStyle = rgba(color, alpha);
    ctx.lineWidth = width;
    ctx.stroke();
    ctx.restore();
  }

  ODF.registerTheme({
    onReadTheme(v) {
      splitA = v('--split-a');
      splitB = v('--split-b');
    },
    litFringe(buildPath, part, sMul) {
      const { alpha, width } = FRINGE[part];
      // The tile outline ignores the box stroke multiplier.
      const a = part === 'tile' ? alpha : alpha * sMul;
      fringeStroke(buildPath, 1, splitA, a, width);
      fringeStroke(buildPath, -1, splitB, a, width);
    },
  });
})();
