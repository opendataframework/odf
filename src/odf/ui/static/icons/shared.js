// Drawing kit shared by the icon group files in this directory, exposed as
// ODF.iconKit so its short names (line, rect, dot...) stay off the global
// scope. Custom icon scripts loaded through `[ui] icon-scripts` can use it too.
//
// Built on `block()`, an iso box whose footprint is stretched along the
// grid's own axes (U runs screen right-down, V left-down) — app.js's isoBox
// only does square-footprint diamonds. `onFace()` shears the canvas onto one
// of a block's two visible walls so windows, doors and charts can be drawn
// as plain rects and lines.
(() => {
  const U = [TW2 / 2, TH2 / 2];
  const V = [-TW2 / 2, TH2 / 2];
  const SLOPE = TH2 / TW2;

  // Screen point at (u, v) grid offset from ground point c, raised by h.
  function pt(c, u, v, h = 0) {
    return [c[0] + u * U[0] + v * V[0], c[1] + u * U[1] + v * V[1] - h];
  }

  function poly(pts, accent, fillA, strokeA, { lw = 0.8, blur = 0 } = {}) {
    ctx.save();
    ctx.beginPath();
    ctx.moveTo(pts[0][0], pts[0][1]);
    for (const p of pts.slice(1)) ctx.lineTo(p[0], p[1]);
    ctx.closePath();
    if (fillA) { ctx.fillStyle = rgba(accent, fillA); ctx.fill(); }
    if (strokeA) {
      if (blur) { ctx.shadowColor = accent; ctx.shadowBlur = blur; }
      ctx.strokeStyle = rgba(accent, strokeA);
      ctx.lineWidth = lw;
      ctx.stroke();
    }
    ctx.restore();
  }

  function line(x1, y1, x2, y2, accent, alpha, lw = 0.8) {
    ctx.save();
    ctx.strokeStyle = rgba(accent, alpha);
    ctx.lineWidth = lw;
    ctx.lineCap = 'round';
    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x2, y2);
    ctx.stroke();
    ctx.restore();
  }

  function path(points, accent, alpha, lw = 0.8) {
    if (points.length < 2) return;
    ctx.save();
    ctx.strokeStyle = rgba(accent, alpha);
    ctx.lineWidth = lw;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.beginPath();
    ctx.moveTo(points[0][0], points[0][1]);
    for (const p of points.slice(1)) ctx.lineTo(p[0], p[1]);
    ctx.stroke();
    ctx.restore();
  }

  function rect(x, y, w, h, accent, fillA, strokeA, lw = 0.7) {
    poly([[x, y], [x + w, y], [x + w, y + h], [x, y + h]], accent, fillA, strokeA, { lw });
  }

  function dot(x, y, r, accent, alpha) {
    ctx.beginPath();
    ctx.arc(x, y, r, 0, Math.PI * 2);
    ctx.fillStyle = rgba(accent, alpha);
    ctx.fill();
  }

  function text(label, x, y, accent, alpha, lit, font = 'bold 6px serif') {
    ctx.save();
    ctx.font = font;
    ctx.textAlign = 'center';
    ctx.fillStyle = rgba(accent, alpha);
    if (lit) { ctx.shadowColor = accent; ctx.shadowBlur = 3; }
    ctx.fillText(label, x, y);
    ctx.restore();
  }

  // Box centered on ground point c: half-extents a along U and b along V
  // (1 = a full tile), height bh, floating `lift` px above the ground.
  // Same face styling as the built-in isoBox.
  function block(c, a, b, bh, accent, lit, { lift = 0, fillAlpha = 1, strokeAlpha = 1 } = {}) {
    const g = [c[0], c[1] - lift];
    const P = (u, v, h) => pt(g, u, v, h);
    const blur = lit ? 9 : 0;
    poly([P(a, -b, 0), P(a, b, 0), P(a, b, bh), P(a, -b, bh)], accent,
      0.05 * fillAlpha, (lit ? 0.55 : 0.35) * strokeAlpha, { blur });
    poly([P(-a, b, 0), P(a, b, 0), P(a, b, bh), P(-a, b, bh)], accent,
      0.08 * fillAlpha, (lit ? 0.65 : 0.4) * strokeAlpha, { blur });
    poly([P(-a, -b, bh), P(a, -b, bh), P(a, b, bh), P(-a, b, bh)], accent,
      (lit ? 0.16 : 0.1) * fillAlpha, (lit ? 1 : 0.6) * strokeAlpha,
      { lw: lit ? 1.3 : 1, blur: blur * 1.4 });
    return { g, a, b, bh };
  }

  // Runs draw(len) in a wall's own flat coordinates: x from 0 to len along
  // the wall's bottom edge, y negative going up. 'v' is the left-front
  // wall, 'u' the right-front one.
  function onFace(blk, side, draw) {
    const { g, a, b } = blk;
    ctx.save();
    if (side === 'v') {
      const o = pt(g, -a, b);
      ctx.transform(1, SLOPE, 0, 1, o[0], o[1]);
      draw(a * TW2);
    } else {
      const o = pt(g, a, b);
      ctx.transform(1, -SLOPE, 0, 1, o[0], o[1]);
      draw(b * TW2);
    }
    ctx.restore();
  }

  const wave = (speed, offset = 0) => (Math.sin(animT * speed + offset) + 1) / 2;
  const strong = lit => (lit ? 0.9 : 0.6);

  ODF.iconKit = { SLOPE, pt, poly, line, path, rect, dot, text, block, onFace, wave, strong };
})();
