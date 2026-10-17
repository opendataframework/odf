// Research: a globe, a ledger, a chalkboard, lab glassware, notebooks and a
// study desk.
(() => {
  const { pt, poly, line, path, rect, dot, text, block, onFace, wave, strong } = ODF.iconKit;
  const add = (key, draw, meta) => ODF.registerIcon(key, draw, { group: 'Research', ...meta });

  // Globe → a globe on a stand, turning, with pins on two of the capitals.
  function drawGlobe(sx, sy, accent, lit) {
    const c = [sx, sy];
    block(c, 0.3, 0.3, 3, accent, lit);
    const [bx, by] = pt(c, 0, 0, 3);
    line(bx, by, bx, by - 6, accent, strong(lit), 1.6);
    const r = 12, cx = sx, cy = by - 6 - r;
    ctx.save();
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.fillStyle = rgba(accent, lit ? 0.16 : 0.1);
    ctx.fill();
    ctx.strokeStyle = rgba(accent, lit ? 1 : 0.7);
    ctx.lineWidth = lit ? 1.3 : 1;
    if (lit) { ctx.shadowColor = accent; ctx.shadowBlur = 8; }
    ctx.stroke();
    ctx.restore();
    // Parallels.
    for (const lat of [-0.5, 0, 0.5]) {
      const y = cy + lat * r, w = r * Math.sqrt(1 - lat * lat);
      ctx.save();
      ctx.beginPath();
      ctx.ellipse(cx, y, w, w * 0.22, 0, 0, Math.PI * 2);
      ctx.strokeStyle = rgba(accent, lit ? 0.45 : 0.3);
      ctx.lineWidth = 0.5;
      ctx.stroke();
      ctx.restore();
    }
    // Meridians, turning.
    const spin = animT * 0.6;
    for (let i = 0; i < 3; i++) {
      const lon = spin + (i * Math.PI) / 3;
      const w = Math.abs(Math.cos(lon)) * r;
      ctx.save();
      ctx.beginPath();
      ctx.ellipse(cx, cy, w, r, 0, 0, Math.PI * 2);
      ctx.strokeStyle = rgba(accent, lit ? 0.5 : 0.32);
      ctx.lineWidth = 0.5;
      ctx.stroke();
      ctx.restore();
    }
    // Pins, only while their side of the globe faces us.
    for (const [lon0, lat] of [[0.4, -0.45], [2.6, 0.3]]) {
      const lon = spin + lon0;
      if (Math.cos(lon) <= 0) continue;
      const px = cx + Math.sin(lon) * r * Math.sqrt(1 - lat * lat), py = cy + lat * r;
      const alpha = strong(lit) * Math.min(1, Math.cos(lon) * 3);
      line(px, py, px, py - 5, accent, alpha, 0.8);
      dot(px, py - 6, 1.8, accent, alpha);
    }
    // The stand's half-ring.
    ctx.save();
    ctx.beginPath();
    ctx.arc(cx, cy, r + 2.5, Math.PI * 0.6, Math.PI * 1.4);
    ctx.strokeStyle = rgba(accent, strong(lit));
    ctx.lineWidth = 1.2;
    ctx.stroke();
    ctx.restore();
  }

  // Ledger → an open ledger on a desk, its rows filling in one by one.
  function drawLedger(sx, sy, accent, lit) {
    const c = [sx, sy];
    const desk = block(c, 0.62, 0.42, 12, accent, lit);
    onFace(desk, 'v', len => rect(len * 0.3, -8, len * 0.4, 3, accent, 0.15, lit ? 0.7 : 0.45, 0.5));
    const top = [sx, sy - 12];
    const rows = 5, filled = Math.floor(animT * 1.5) % (rows * 2 + 3);
    for (const side of [-1, 1]) {
      const u0 = side < 0 ? -0.46 : 0.02, u1 = side < 0 ? -0.02 : 0.46;
      const spine = side < 0 ? u1 : u0, edge = side < 0 ? u0 : u1;
      // Pages lift slightly towards their outer edge.
      const P = (u, v) => pt(top, u, v, 1 + 2.5 * Math.abs(u - spine) / 0.44);
      poly([P(u0, -0.3), P(u1, -0.3), P(u1, 0.3), P(u0, 0.3)], accent, lit ? 0.22 : 0.14, strong(lit));
      for (let i = 0; i < rows; i++) {
        const v = -0.2 + i * 0.1;
        const n = side < 0 ? i : rows + i;
        const done = n < filled;
        const [x1, y1] = P(Math.min(spine, edge) + 0.05, v), [x2, y2] = P(Math.max(spine, edge) - 0.05, v);
        line(x1, y1, x2, y2, accent, done ? (lit ? 0.85 : 0.6) : 0.18, done ? 0.8 : 0.5);
      }
    }
  }

  // Chalkboard → a chalkboard on an easel: a scatter, a falling fitted
  // line and its slope, β.
  function drawSlopeBoard(sx, sy, accent, lit) {
    const c = [sx, sy];
    const head = pt(c, 0, 0, 34);
    for (const [u, v] of [[-0.36, 0.2], [0.36, 0.2], [0, -0.35]]) {
      const foot = pt(c, u, v);
      line(head[0], head[1], foot[0], foot[1], accent, lit ? 0.8 : 0.55, 1.1);
    }
    const board = block(pt(c, 0, 0.08), 0.46, 0.03, 24, accent, lit, { lift: 8, fillAlpha: 1.8 });
    onFace(board, 'v', len => {
      line(3, -3, len - 2, -3, accent, lit ? 0.6 : 0.4, 0.5);
      line(3, -3, 3, -21, accent, lit ? 0.6 : 0.4, 0.5);
      const points = [[0.1, 0.85], [0.22, 0.6], [0.3, 0.75], [0.42, 0.5], [0.5, 0.62],
        [0.6, 0.38], [0.7, 0.45], [0.8, 0.22], [0.9, 0.3]];
      points.forEach(([x, y], i) => {
        dot(4 + x * (len - 8), -4 - y * 16, 0.9 + 0.4 * wave(2.5, i), accent, lit ? 0.9 : 0.65);
      });
      // The line draws itself in, holds, and starts over.
      const t = Math.min(1, ((animT * 0.4) % 1.4));
      const x0 = 4, y0 = -4 - 0.85 * 16, x1 = len - 3, y1 = -4 - 0.2 * 16;
      line(x0, y0, x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, accent, lit ? 1 : 0.75, 1.1);
      text('β<0', len - 9, -15, accent, lit ? 1 : 0.8, lit);
    });
  }

  // Flask → a bench with a bubbling Erlenmeyer flask and a test tube.
  function drawFlask(sx, sy, accent, lit) {
    const c = [sx, sy];
    const bench = block(c, 0.62, 0.4, 10, accent, lit);
    onFace(bench, 'v', len => line(3, -6, len - 3, -6, accent, lit ? 0.5 : 0.3, 0.6));
    const tube = block(pt(c, 0.38, -0.15), 0.06, 0.06, 12, accent, lit, { lift: 10, fillAlpha: 1.5 });
    const [tx, ty] = pt(tube.g, 0, 0, 5);
    dot(tx, ty, 1.6, accent, 0.3 + 0.4 * wave(1.7));
    const [fx, fy] = pt(c, -0.1, 0.05, 10);
    const bodyH = 14, neckH = 8, half = 10, neck = 2.6;
    const outline = [[fx - half, fy], [fx + half, fy], [fx + neck, fy - bodyH], [fx + neck, fy - bodyH - neckH],
      [fx - neck, fy - bodyH - neckH], [fx - neck, fy - bodyH]];
    poly(outline, accent, lit ? 0.12 : 0.08, lit ? 1 : 0.7, { lw: lit ? 1.2 : 1, blur: lit ? 6 : 0 });
    // Liquid up to 55% of the body, with a gently sloshing surface.
    const level = bodyH * (0.55 + 0.05 * Math.sin(animT * 2));
    const w = neck + (half - neck) * (1 - level / bodyH);
    poly([[fx - half + 1, fy - 0.5], [fx + half - 1, fy - 0.5], [fx + w - 0.5, fy - level], [fx - w + 0.5, fy - level]],
      accent, lit ? 0.45 : 0.3, 0);
    for (let i = 0; i < 4; i++) {
      const t = (animT * 0.5 + i / 4) % 1;
      const y = fy - 2 - t * (bodyH + neckH + 10);
      const x = fx + Math.sin(animT * 3 + i * 2) * (t < 0.6 ? 3 : 1.5);
      dot(x, y, 0.8 + t * 1.2, accent, (1 - t) * (lit ? 0.9 : 0.6));
    }
  }

  // Logbook → a stack of lab notebooks with ribbons; the top one gets
  // a new ticked entry now and then.
  function drawLogbook(sx, sy, accent, lit) {
    const c = [sx, sy];
    const books = [[0, 0, 0], [0.04, -0.03, 5], [-0.03, 0.02, 10]];
    let top;
    books.forEach(([u, v, lift], i) => {
      top = block(pt(c, u, v), 0.44, 0.32, 4.5, accent, lit, { lift, fillAlpha: 1.3 });
      onFace(top, 'v', len => {
        line(len * (0.25 + i * 0.2), -1, len * (0.25 + i * 0.2), 4 + i, accent, lit ? 0.9 : 0.6, 1.2);
      });
    });
    const g = top.g;
    const rows = 4, shown = Math.floor(animT * 0.8) % (rows + 2);
    for (let i = 0; i < Math.min(shown, rows); i++) {
      const v = -0.2 + i * 0.12;
      const [ax, ay] = pt(g, -0.28, v, 4.5), [bx, by] = pt(g, 0.3, v, 4.5);
      const fresh = i === shown - 1;
      path([[ax - 3, ay - 0.5], [ax - 2, ay + 0.5], [ax - 0.2, ay - 1.8]], accent, lit ? 1 : 0.75, 0.7);
      line(ax + 1, ay, bx, by, accent, fresh ? 0.5 + 0.5 * wave(6) : (lit ? 0.7 : 0.5), 0.6);
    }
  }

  // Study desk → a desk with a monitor mid-conversation and a lamp.
  function drawStudyDesk(sx, sy, accent, lit) {
    const c = [sx, sy];
    const desk = block(c, 0.66, 0.38, 12, accent, lit);
    onFace(desk, 'v', len => {
      rect(len * 0.6, -10, len * 0.32, 4, accent, 0.15, lit ? 0.7 : 0.45, 0.5);
      dot(len * 0.76, -8, 0.8, accent, strong(lit));
    });
    const top = [sx, sy - 12];
    // Lamp at the back right, drawn first so the monitor sits in front.
    const [lx, ly] = pt(top, 0.45, -0.2);
    const [kx, ky] = [lx - 3, ly - 14];
    line(lx, ly, lx + 2, ly - 8, accent, strong(lit), 1.1);
    line(lx + 2, ly - 8, kx, ky, accent, strong(lit), 1.1);
    poly([[kx - 1, ky - 2], [kx + 2, ky + 1], [kx - 6, ky + 5], [kx - 7, ky + 1]], accent, lit ? 0.5 : 0.3, strong(lit));
    if (lit) {
      poly([[kx - 6, ky + 5], [kx - 1, ky + 2], [kx - 2, ky + 16], [kx - 16, ky + 16]], accent, 0.08 + 0.06 * wave(2), 0);
    }
    const stand = pt(top, -0.12, -0.08);
    line(stand[0], stand[1], stand[0], stand[1] - 4, accent, strong(lit), 1.4);
    const screen = block(pt(top, -0.12, -0.08), 0.36, 0.04, 17, accent, lit, { lift: 4, fillAlpha: 1.6 });
    onFace(screen, 'v', len => {
      rect(2, -15, len * 0.55, 3, accent, lit ? 0.5 : 0.35, 0, 0.4);
      rect(len * 0.4 - 2, -10.5, len * 0.6, 3, accent, lit ? 0.8 : 0.55, 0, 0.4);
      for (let i = 0; i < 3; i++) dot(4 + i * 3, -4.5, 0.9, accent, 0.3 + 0.7 * wave(6, -i * 0.9));
    });
  }

  add('globe', drawGlobe, { bh: 3, scale: 0.6, extraTop: 36, label: 'Globe' });
  add('ledger', drawLedger, { bh: 15, scale: 0.85, label: 'Ledger' });
  add('slope-board', drawSlopeBoard, { bh: 34, scale: 0.6, label: 'Chalkboard' });
  add('flask', drawFlask, { bh: 10, scale: 0.8, extraTop: 30, label: 'Flask' });
  add('logbook', drawLogbook, { bh: 15, scale: 0.75, label: 'Logbook' });
  add('study-desk', drawStudyDesk, { bh: 12, scale: 0.85, extraTop: 22, label: 'Study desk' });
})();
