// Tactical map: icons as translucent holograms, a faint tint behind bright
// outlines in their accent, glowing when lit. Each stands inside a segmented
// marker ring on the ground, which widens when the icon is lit. The grid is
// a city seen from above: blocks between thin streets, a wider avenue every
// few tiles, and the footprint of a building on some of the blocks.
(() => {
  const AVENUE_EVERY = 4;
  let block = '#11161c';
  let street = '#27303a';
  let avenue = '#3b4652';
  let building = '#161c23';
  let markerAlpha = 0.85;
  let glow = 1;

  // A stable pseudo-random value in [0, 1) for a tile, so the same blocks
  // keep their buildings from frame to frame.
  function hash(col, row) {
    const n = Math.sin(col * 127.1 + row * 311.7) * 43758.5453;
    return n - Math.floor(n);
  }

  ODF.registerTheme({
    faces: {
      fill: 'tint',
      tint:    { top: 0.14, left: 0.1,  right: 0.06 },
      tintLit: { top: 0.24, left: 0.16, right: 0.1 },
      occlude: true,
      outline: 'accent',
      stroke:    { top: 0.9, left: 0.7,  right: 0.55 },
      strokeLit: { top: 1,   left: 0.95, right: 0.85 },
    },
    litShadow(part, accent) {
      ctx.shadowColor = rgba(accent, 0.75);
      ctx.shadowBlur = { tile: 8, face: 10, top: 14 }[part] * glow;
    },
    emptyTile(sx, sy) {
      // The tile's column and row (see iso()).
      const X = (sx - ORIGIN_X) / TW2, Y = (sy - ORIGIN_Y) / TH2;
      const col = Math.round((X + Y) / 2), row = Math.round((Y - X) / 2);
      tilePath(sx, sy);
      ctx.fillStyle = block;
      ctx.fill();
      ctx.strokeStyle = street;
      ctx.lineWidth = 1.4;
      ctx.stroke();
      if (hash(col, row) < 0.45) {
        tilePath(sx, sy, 0.5 + hash(row, col) * 0.2);
        ctx.fillStyle = building;
        ctx.fill();
      }
      // Avenues run along the edge shared with the previous column (upper
      // left) and the previous row (upper right).
      ctx.strokeStyle = avenue;
      ctx.lineWidth = 2.4;
      ctx.beginPath();
      if (col % AVENUE_EVERY === 0) {
        ctx.moveTo(sx - TW2, sy);
        ctx.lineTo(sx, sy - TH2);
      }
      if (row % AVENUE_EVERY === 0) {
        ctx.moveTo(sx, sy - TH2);
        ctx.lineTo(sx + TW2, sy);
      }
      ctx.stroke();
    },
    groundShadow(x, y, e, accent, lit) {
      const r = e.widthExtent * (lit ? 1.12 : 0.96);
      const a = markerAlpha * (lit ? 1 : 0.7);
      ctx.translate(x, y);
      ctx.scale(1, TH2 / TW2);
      const g = ctx.createRadialGradient(0, 0, 0, 0, 0, r);
      g.addColorStop(0,   rgba(accent, lit ? 0.22 : 0.12));
      g.addColorStop(1,   rgba(accent, 0));
      ctx.fillStyle = g;
      ctx.beginPath();
      ctx.arc(0, 0, r, 0, Math.PI * 2);
      ctx.fill();
      // Four arcs with gaps on the diagonals.
      ctx.strokeStyle = rgba(accent, a);
      ctx.lineWidth = lit ? 1.8 : 1.3;
      if (lit) {
        ctx.shadowColor = rgba(accent, 0.7);
        ctx.shadowBlur = 8 * glow;
      }
      for (let i = 0; i < 4; i++) {
        const start = i * Math.PI / 2 + 0.22;
        ctx.beginPath();
        ctx.arc(0, 0, r, start, start + Math.PI / 2 - 0.44);
        ctx.stroke();
      }
    },
    onReadTheme(v) {
      block = v('--beacon-block') || block;
      street = v('--beacon-street') || street;
      avenue = v('--beacon-avenue') || avenue;
      building = v('--beacon-building') || building;
      markerAlpha = parseFloat(v('--beacon-marker-alpha')) || markerAlpha;
      glow = parseFloat(v('--beacon-glow')) || glow;
    },
    runRingLine: 1.6,
    runRingShadow(state, color) {
      ctx.shadowColor = rgba(color, 0.8);
      ctx.shadowBlur = (state === 'running' ? 12 : 6) * glow;
    },
    flowLine(accent) {
      ctx.shadowColor = rgba(accent, 0.7);
      ctx.shadowBlur = 8 * glow;
    },
  });
})();
