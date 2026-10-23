// Soft glass: icon faces tinted well past the default wireframe and hiding
// what's behind them, thin outlines, and a lit shape lifted by a soft
// accent shadow under it instead of a glow around it.
ODF.registerTheme({
  faces: {
    tint:    { top: 0.26, left: 0.18, right: 0.1 },
    tintLit: { top: 0.36, left: 0.26, right: 0.16 },
    stroke:    { top: 0.55, left: 0.45, right: 0.4 },
    strokeLit: { top: 0.9,  left: 0.75, right: 0.7 },
  },
  litShadow(part, accent) {
    ctx.shadowColor = rgba(accent, 0.45);
    ctx.shadowBlur = part === 'tile' ? 6 : 8;
    ctx.shadowOffsetY = part === 'tile' ? 0 : 2;
  },
});
