// Drawing kit shared by the icon group files in this directory, exposed as
// ODF.iconKit so its short names (line, rect, dot...) stay off the global
// scope. Custom icon scripts loaded through `[ui] icon-scripts` can use it too.
//
// Built on `block()`, an iso box whose footprint is stretched along the
// grid's own axes (U runs screen right-down, V left-down) — app.js's isoBox
// only does square-footprint diamonds — and the other solids beside it
// (`stepped`, `gable`, `wedge`, `cylinder`). Every solid paints its faces
// through app.js's paintFace(), so it takes on the theme's icon look. `onFace()` shears the canvas onto one
// of a block's two visible walls so windows, doors and charts can be drawn
// as plain rects and lines.
(() => {
  const U = [TW2 / 2, TH2 / 2];
  const V = [-TW2 / 2, TH2 / 2];
  const SLOPE = TH2 / TW2;

  // Inside onFace() details are drawn onto a wall, so they take the theme's
  // face ink (see faceInk) instead of the bare accent.
  let onWall = 0;
  const ink = accent => (onWall ? faceInk(accent) : accent);

  // Screen point at (u, v) grid offset from ground point c, raised by h.
  function pt(c, u, v, h = 0) {
    return [c[0] + u * U[0] + v * V[0], c[1] + u * U[1] + v * V[1] - h];
  }

  function poly(pts, accent, fillA, strokeA, { lw = 0.8, blur = 0 } = {}) {
    accent = ink(accent);
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
    accent = ink(accent);
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
    accent = ink(accent);
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
    accent = ink(accent);
    ctx.beginPath();
    ctx.arc(x, y, r, 0, Math.PI * 2);
    ctx.fillStyle = rgba(accent, alpha);
    ctx.fill();
  }

  function text(label, x, y, accent, alpha, lit, font = 'bold 6px serif') {
    accent = ink(accent);
    ctx.save();
    ctx.font = font;
    ctx.textAlign = 'center';
    ctx.fillStyle = rgba(accent, alpha);
    if (lit) { ctx.shadowColor = accent; ctx.shadowBlur = 3; }
    ctx.fillText(label, x, y);
    ctx.restore();
  }

  // Closed path through screen points, for paintFace().
  function outline(pts) {
    return () => {
      ctx.beginPath();
      ctx.moveTo(pts[0][0], pts[0][1]);
      for (const p of pts.slice(1)) ctx.lineTo(p[0], p[1]);
      ctx.closePath();
    };
  }

  // Box centered on ground point c: half-extents a along U and b along V
  // (1 = a full tile), height bh, floating `lift` px above the ground.
  // Faces are painted like the built-in isoBox's, in the theme's look.
  function block(c, a, b, bh, accent, lit, { lift = 0, fillAlpha = 1, strokeAlpha = 1 } = {}) {
    const g = [c[0], c[1] - lift];
    const P = (u, v, h) => pt(g, u, v, h);
    const face = (pts, side) => paintFace(outline(pts), side, accent, lit, fillAlpha, strokeAlpha);
    face([P(a, -b, 0), P(a, b, 0), P(a, b, bh), P(a, -b, bh)], 'right');
    face([P(-a, b, 0), P(a, b, 0), P(a, b, bh), P(-a, b, bh)], 'left');
    face([P(-a, -b, bh), P(a, -b, bh), P(a, b, bh), P(-a, b, bh)], 'top');
    return { g, a, b, bh };
  }

  // Blocks stacked on ground point c, each tier {a, b, h} sitting on the one
  // below it (and optionally shifted by {u, v}): setback towers, steps.
  // Returns the top tier's block.
  function stepped(c, tiers, accent, lit, { lift = 0, fillAlpha = 1, strokeAlpha = 1 } = {}) {
    let blk, z = lift;
    for (const { a, b, h, u = 0, v = 0 } of tiers) {
      blk = block(pt(c, u, v), a, b, h, accent, lit, { lift: z, fillAlpha, strokeAlpha });
      z += h;
    }
    return blk;
  }

  // Walls of height h under a pitched roof whose ridge rises `ridge` px above
  // them, running along the U axis (`axis: 'u'`, gable end on the right
  // wall) or the V axis (gable end on the left wall). The far slope is
  // painted first, so the near walls and slope cover what they should.
  function gable(c, a, b, h, ridge, accent, lit, { lift = 0, axis = 'u', fillAlpha = 1, strokeAlpha = 1 } = {}) {
    const g = [c[0], c[1] - lift];
    // Q(s, t, z): s along the ridge, t across it.
    const Q = axis === 'u' ? (s, t, z) => pt(g, s, t, z) : (s, t, z) => pt(g, t, s, z);
    const [S, T] = axis === 'u' ? [a, b] : [b, a];
    const end = axis === 'u' ? 'right' : 'left', eave = axis === 'u' ? 'left' : 'right';
    const face = (pts, side) => paintFace(outline(pts), side, accent, lit, fillAlpha, strokeAlpha);
    const top = h + ridge;
    face([Q(-S, 0, top), Q(S, 0, top), Q(S, -T, h), Q(-S, -T, h)], 'top');
    face([Q(S, -T, 0), Q(S, T, 0), Q(S, T, h), Q(S, 0, top), Q(S, -T, h)], end);
    face([Q(-S, T, 0), Q(S, T, 0), Q(S, T, h), Q(-S, T, h)], eave);
    face([Q(-S, T, h), Q(S, T, h), Q(S, 0, top), Q(-S, 0, top)], 'top');
    return { g, a, b, bh: h, ridge };
  }

  // Box whose roof slopes from height h1 at the back to h2 at the front,
  // along U (`axis: 'u'`) or V: lean-to roofs, ramps, desks, consoles.
  function wedge(c, a, b, h1, h2, accent, lit, { lift = 0, axis = 'u', fillAlpha = 1, strokeAlpha = 1 } = {}) {
    const g = [c[0], c[1] - lift];
    const H = axis === 'u' ? (u, v) => (u < 0 ? h1 : h2) : (u, v) => (v < 0 ? h1 : h2);
    const P = (u, v, top) => pt(g, u, v, top ? H(u, v) : 0);
    const face = (pts, side) => paintFace(outline(pts), side, accent, lit, fillAlpha, strokeAlpha);
    face([P(a, -b), P(a, b), P(a, b, 1), P(a, -b, 1)], 'right');
    face([P(-a, b), P(a, b), P(a, b, 1), P(-a, b, 1)], 'left');
    face([P(-a, -b, 1), P(a, -b, 1), P(a, b, 1), P(-a, b, 1)], 'top');
    return { g, a, b, bh: Math.max(h1, h2) };
  }

  // Upright cylinder of radius r (in the same units as block's half-extents)
  // and height h on ground point c: tanks, silos, drums, pods. Its side is
  // shaded in two halves, like a box's two walls, under one outline.
  // Returns the top cap's center and radii.
  function cylinder(c, r, h, accent, lit, { lift = 0, fillAlpha = 1, strokeAlpha = 1 } = {}) {
    const rx = r * TW2 * Math.SQRT1_2, ry = r * TH2 * Math.SQRT1_2;
    const [x, y] = [c[0], c[1] - lift];
    const half = sign => () => {
      ctx.beginPath();
      ctx.moveTo(x + sign * rx, y - h);
      ctx.ellipse(x, y, rx, ry, 0, sign < 0 ? Math.PI : 0, Math.PI / 2, sign < 0);
      ctx.ellipse(x, y - h, rx, ry, 0, Math.PI / 2, sign < 0 ? Math.PI : 0, sign > 0);
      ctx.closePath();
    };
    const side = () => {
      ctx.beginPath();
      ctx.moveTo(x - rx, y - h);
      ctx.ellipse(x, y, rx, ry, 0, Math.PI, 0, true);
      ctx.lineTo(x + rx, y - h);
      ctx.ellipse(x, y - h, rx, ry, 0, 0, Math.PI, false);
      ctx.closePath();
    };
    const cap = () => {
      ctx.beginPath();
      ctx.ellipse(x, y - h, rx, ry, 0, 0, Math.PI * 2);
    };
    paintFace(half(-1), 'left', accent, lit, fillAlpha, strokeAlpha, { stroke: false });
    paintFace(half(1), 'right', accent, lit, fillAlpha, strokeAlpha, { stroke: false });
    paintFace(side, 'left', accent, lit, fillAlpha, strokeAlpha, { fill: false });
    paintFace(cap, 'top', accent, lit, fillAlpha, strokeAlpha);
    return { x, y: y - h, rx, ry, h };
  }

  // Runs draw(len) in a wall's own flat coordinates: x from 0 to len along
  // the wall's bottom edge, y negative going up. 'v' is the left-front
  // wall, 'u' the right-front one.
  function onFace(blk, side, draw) {
    const { g, a, b } = blk;
    ctx.save();
    onWall++;
    try {
      if (side === 'v') {
        const o = pt(g, -a, b);
        ctx.transform(1, SLOPE, 0, 1, o[0], o[1]);
        draw(a * TW2);
      } else {
        const o = pt(g, a, b);
        ctx.transform(1, -SLOPE, 0, 1, o[0], o[1]);
        draw(b * TW2);
      }
    } finally {
      onWall--;
      ctx.restore();
    }
  }

  const wave = (speed, offset = 0) => (Math.sin(animT * speed + offset) + 1) / 2;
  const strong = lit => (lit ? 0.9 : 0.6);

  ODF.iconKit = {
    SLOPE, pt, poly, line, path, rect, dot, text, outline, block, stepped, gable, wedge, cylinder,
    onFace, wave, strong, solid: solidFaces, ink: faceInk,
  };
})();
