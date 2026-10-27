// Tonal solids: icon faces are opaque shades of their muted accent with no
// outlines, told apart by tone like the theme's grey surfaces, and a lit
// icon is raised a step in tone over a soft black shadow instead of a glow
// in its color.
ODF.registerTheme({
  faces: {
    fill: 'shade',
    shade:    { top: 0.22, left: -0.08, right: -0.3 },
    shadeLit: { top: 0.38, left: 0.06,  right: -0.16 },
    outline: 'none',
    detail: -0.6,
  },
  litShadow(part) {
    ctx.shadowColor = 'rgba(0,0,0,0.35)';
    ctx.shadowBlur = part === 'tile' ? 4 : 8;
    ctx.shadowOffsetY = part === 'tile' ? 0 : 2;
  },
});
