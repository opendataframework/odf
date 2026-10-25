// Liquid chrome: opaque icon faces filled with one vertical reflection across
// the whole icon (bright sky, a dark horizon band just above the middle, a
// lighter floor), tinted by the face's own accent shade, under thin bright
// edges and a soft glow when lit. The grid is faint tiles with a glossy dot
// at each center.
ODF.registerTheme({
  faces: {
    fill: 'shade',
    shade:    { top: 0.35, left: 0.05, right: -0.2 },
    shadeLit: { top: 0.5,  left: 0.2,  right: -0.05 },
    outline: 'accent',
    stroke:    { top: 0.85, left: 0.6, right: 0.5 },
    strokeLit: { top: 1,    left: 0.9, right: 0.8 },
    detail: -0.55,
  },
  faceFill(side, accent, lit, t, frame) {
    const base = shadeHex(accent, t);
    const g = ctx.createLinearGradient(frame.x, frame.top, frame.x, frame.bottom);
    g.addColorStop(0,    mixHex(base, '#ffffff', lit ? 0.7 : 0.55));
    g.addColorStop(0.4,  mixHex(base, '#ffffff', lit ? 0.35 : 0.22));
    g.addColorStop(0.48, mixHex(base, BG_CANVAS, 0.5));
    g.addColorStop(0.56, base);
    g.addColorStop(1,    mixHex(base, '#ffffff', 0.35));
    return g;
  },
  litShadow(part, accent) {
    ctx.shadowColor = rgba(accent, 0.7);
    ctx.shadowBlur = { tile: 8, face: 10, top: 14 }[part];
  },
  emptyTile(sx, sy) {
    tilePath(sx, sy);
    ctx.fillStyle = TILE_FILL;
    ctx.fill();
    ctx.strokeStyle = TILE_STROKE;
    ctx.lineWidth = 0.6;
    ctx.stroke();
    const dot = ctx.createRadialGradient(sx - 0.6, sy - 0.6, 0, sx, sy, 2.2);
    dot.addColorStop(0, '#ffffff');
    dot.addColorStop(1, rgba(TILE_STROKE, 0));
    ctx.fillStyle = dot;
    ctx.beginPath();
    ctx.arc(sx, sy, 2.2, 0, Math.PI * 2);
    ctx.fill();
  },
});
