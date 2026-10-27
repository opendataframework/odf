// Machine learning: mail flowing through a model's life — a postbox, sorting
// drums, envelopes, a training bench, a podium, a run-log lectern, a model
// shelf, a checkpoint gate, an inbox tray, a standing desk and conveyors.
(() => {
  const { pt, poly, line, path, rect, dot, outline, block, wedge, cylinder, onFace, wave, strong } = ODF.iconKit;
  const add = (key, draw, meta) => ODF.registerIcon(key, draw, { group: 'ML', ...meta });

  // A flat envelope lying at height h above ground point c: half-extents a, b.
  function envelope(c, a, b, h, accent, lit, alpha = 1) {
    const P = (u, v) => pt(c, u, v, h);
    paintFace(outline([P(-a, -b), P(a, -b), P(a, b), P(-a, b)]), 'top', accent, lit, 2 * alpha, alpha, { lw: 0.7 });
    const m = P(0, 0.15 * b);
    path([P(-a, -b), m, P(a, -b)], faceInk(accent), strong(lit) * alpha, 0.7);
  }

  // Postbox → a round pillar box with a domed cap, letters dropping into
  // its slot.
  function drawPostbox(sx, sy, accent, lit) {
    const c = [sx, sy];
    cylinder(c, 0.46, 3, accent, lit);
    const body = cylinder(c, 0.32, 22, accent, lit, { lift: 3 });
    cylinder(c, 0.38, 2, accent, lit, { lift: 25, fillAlpha: 1.6 });
    const cap = cylinder(c, 0.24, 3, accent, lit, { lift: 27, fillAlpha: 1.6 });
    const ink = faceInk(accent), front = body.y + body.ry;
    rect(sx - body.rx * 0.45, front + 4, body.rx * 0.9, 2.5, ink, lit ? 0.7 : 0.45, strong(lit), 0.5);
    rect(sx - body.rx * 0.3, front + 9, body.rx * 0.6, 6, ink, 0.12, lit ? 0.7 : 0.45, 0.5);
    dot(sx, cap.y - 1.5, 1.4, accent, strong(lit));
    const t = (animT * 0.5) % 1;
    envelope([sx - 13 + 7 * t, sy + 6 - 10 * t], 0.2, 0.13, 22 - 6 * t, accent, lit, 1 - t * 0.8);
  }

  // Sorting bins → three drums of different sizes: train, test and stream.
  function drawSorter(sx, sy, accent, lit) {
    const c = [sx, sy];
    block(c, 0.82, 0.5, 3, accent, lit);
    const sizes = [[-0.48, 16, 0.3], [0.1, 9, 0.22], [0.54, 9, 0.22]];
    const active = Math.floor(animT * 0.8) % 3;
    sizes.forEach(([u, bh, r], i) => {
      cylinder(pt(c, u, 0), r, bh, accent, lit, { lift: 3, fillAlpha: i === active ? 2.4 : 1 });
      if (i === active) envelope(pt(c, u, 0), r * 0.5, 0.14, 3 + bh + 3 + 2 * wave(5), accent, lit);
    });
  }

  // Envelopes → a pile of envelopes.
  function drawEnvelopes(sx, sy, accent, lit) {
    const c = [sx, sy];
    block(c, 0.6, 0.45, 3, accent, lit);
    [[0.06, 0.04], [-0.05, -0.03], [0.03, -0.05], [-0.02, 0.03]].forEach(([u, v], i) => {
      block(pt(c, u, v), 0.44, 0.3, 2.6, accent, lit, { lift: 3 + i * 3.2, fillAlpha: 1.4 });
    });
    envelope(pt(c, -0.02, 0.03), 0.44, 0.3, 3 + 4 * 3.2 - 0.6 + 1.2 * wave(2), accent, lit);
  }

  // Training bench → a bench whose weight bars keep adjusting until they settle.
  function drawTrainer(sx, sy, accent, lit) {
    const c = [sx, sy];
    const bench = block(c, 0.7, 0.42, 9, accent, lit);
    onFace(bench, 'u', len => rect(len * 0.2, -6.5, len * 0.6, 3, accent, 0.15, lit ? 0.7 : 0.45, 0.5));
    const bars = 5, settle = Math.min(1, (animT * 0.25) % 1.6);
    for (let i = 0; i < bars; i++) {
      const target = [14, 6, 19, 9, 12][i];
      const noise = (1 - settle) * 7 * Math.sin(animT * 6 + i * 2.1);
      block(pt(c, -0.5 + i * 0.25, 0), 0.08, 0.2, Math.max(2, target + noise), accent, lit, { lift: 9, fillAlpha: 2 });
    }
  }

  // Podium → a round, tiered winner's dais with a flag on its top tier.
  function drawPodium(sx, sy, accent, lit) {
    const c = [sx, sy];
    cylinder(c, 0.72, 4, accent, lit);
    cylinder(c, 0.5, 4, accent, lit, { lift: 4 });
    const top = cylinder(c, 0.28, 7, accent, lit, { lift: 8, fillAlpha: 1.8 });
    const [fx, fy] = [sx, top.y];
    line(fx, fy, fx, fy - 16, accent, strong(lit), 1.1);
    const flutter = 1.5 * Math.sin(animT * 4);
    poly([[fx, fy - 16], [fx + 9, fy - 13 + flutter], [fx, fy - 10]], accent, lit ? 0.6 : 0.4, strong(lit));
  }

  // Run log → a lectern with the log open on its sloped top, a row ticked
  // off per run.
  function drawRunLog(sx, sy, accent, lit) {
    const c = [sx, sy];
    const lo = 9, hi = 17, b = 0.32;
    cylinder(c, 0.38, 2, accent, lit);
    block(c, 0.1, 0.1, lo, accent, lit, { lift: 2 });
    const desk = wedge(c, 0.46, b, hi, lo, accent, lit, { axis: 'v', lift: 2 + lo - 4 });
    // A point on the sloped top, which falls from hi at v = -b to lo at v = b.
    const P = (u, v) => pt(desk.g, u, v, hi + (lo - hi) * (v + b) / (2 * b));
    const rows = 4, shown = Math.floor(animT * 0.8) % (rows + 2);
    for (let i = 0; i < Math.min(shown, rows); i++) {
      const v = -0.22 + i * 0.14;
      const [ax, ay] = P(-0.32, v), [bx, by] = P(0.34, v);
      line(ax, ay, bx, by, faceInk(accent), i === shown - 1 ? 0.5 + 0.5 * wave(6) : (lit ? 0.7 : 0.5), 0.6);
    }
    const [sx0, sy0] = P(0, -b), [sx1, sy1] = P(0, b);
    line(sx0, sy0, sx1, sy1, faceInk(accent), lit ? 0.5 : 0.3, 0.6);
  }

  // Model shelf → a shelf of models; the one in production glows.
  function drawShelf(sx, sy, accent, lit) {
    const c = [sx, sy];
    const shelf = block(c, 0.6, 0.28, 30, accent, lit);
    onFace(shelf, 'v', len => {
      for (let row = 0; row < 3; row++) {
        const y = -2 - row * 9.5;
        line(1, y, len - 1, y, accent, lit ? 0.7 : 0.45, 0.6);
        for (let col = 0; col < 3; col++) {
          const production = row === 2 && col === 0;
          rect(3 + col * (len - 6) / 3, y - 7, (len - 6) / 3 - 2, 6, accent,
            production ? 0.45 + 0.4 * wave(3) : 0.14, production ? 1 : (lit ? 0.6 : 0.4), 0.5);
        }
      }
    });
  }

  // Checkpoint gate → a checkpoint: letters pass under a gate whose lamp blinks.
  function drawGate(sx, sy, accent, lit) {
    const c = [sx, sy];
    block(c, 0.8, 0.5, 3, accent, lit);
    block(pt(c, 0, -0.38), 0.12, 0.08, 22, accent, lit, { lift: 3 });
    const t = (animT * 0.35) % 1;
    envelope(pt(c, -0.6 + 1.2 * t, 0), 0.2, 0.14, 5, accent, lit, Math.sin(Math.PI * t));
    block(pt(c, 0, 0.38), 0.12, 0.08, 22, accent, lit, { lift: 3 });
    block(c, 0.14, 0.46, 4, accent, lit, { lift: 25, fillAlpha: 1.8 });
    const [lx, ly] = pt(c, 0, 0, 33);
    ctx.save();
    if (lit) { ctx.shadowColor = accent; ctx.shadowBlur = 6; }
    dot(lx, ly, 2.2, accent, 0.35 + 0.65 * wave(7));
    ctx.restore();
  }

  // Inbox tray → an inbox tray, each letter stamped as it lands.
  function drawTray(sx, sy, accent, lit) {
    const c = [sx, sy];
    const tray = block(c, 0.66, 0.46, 7, accent, lit);
    onFace(tray, 'v', len => rect(len * 0.3, -5, len * 0.4, 2, accent, lit ? 0.5 : 0.3, 0, 0.4));
    const step = Math.floor(animT * 0.7);
    [[-0.3, -0.12], [0.26, 0.1], [-0.02, 0.02]].forEach(([u, v], i) => {
      const g = pt(c, u, v);
      envelope(g, 0.26, 0.18, 8 + i * 1.6, accent, lit);
      if (i === 2) {
        const [mx, my] = pt(g, 0, 0.02, 8 + i * 1.6);
        const spam = step % 3 === 0;
        ctx.save();
        if (lit) { ctx.shadowColor = accent; ctx.shadowBlur = 4; }
        if (spam) {
          line(mx - 2.5, my + 1, mx + 2.5, my + 5, accent, 1, 1.1);
          line(mx + 2.5, my + 1, mx - 2.5, my + 5, accent, 1, 1.1);
        } else {
          path([[mx - 3, my + 3], [mx - 1, my + 5], [mx + 3, my + 0.5]], accent, 1, 1.1);
        }
        ctx.restore();
      }
    });
  }

  // Desk → a standing desk on two legs with two monitors, one of them
  // mid-conversation.
  function drawDesk(sx, sy, accent, lit) {
    const c = [sx, sy], h = 15;
    for (const u of [-0.56, 0.56]) block(pt(c, u, 0), 0.05, 0.28, h, accent, lit);
    block(c, 0.66, 0.36, 2, accent, lit, { lift: h });
    const top = [sx, sy - h - 2];
    const stand = (u, v) => {
      const [x, y] = pt(top, u, v);
      line(x, y, x, y - 4, accent, strong(lit), 1.4);
    };
    stand(-0.3, -0.1);
    const chat = block(pt(top, -0.3, -0.1), 0.26, 0.04, 14, accent, lit, { lift: 4, fillAlpha: 1.6 });
    onFace(chat, 'v', len => {
      rect(2, -12, len * 0.55, 2.5, accent, lit ? 0.5 : 0.35, 0, 0.4);
      rect(len * 0.4 - 2, -8, len * 0.6, 2.5, accent, lit ? 0.8 : 0.55, 0, 0.4);
      for (let i = 0; i < 3; i++) dot(4 + i * 3, -3.5, 0.9, accent, 0.3 + 0.7 * wave(6, -i * 0.9));
    });
    stand(0.3, -0.1);
    const plot = block(pt(top, 0.3, -0.1), 0.26, 0.04, 14, accent, lit, { lift: 4, fillAlpha: 1.6 });
    onFace(plot, 'v', len => {
      path([[2, -3], [len * 0.3, -7], [len * 0.55, -5], [len - 2, -11]], accent, strong(lit), 0.8);
    });
    envelope(pt(top, 0.1, 0.24), 0.14, 0.09, 0.5, accent, lit);
  }

  // Conveyor → an inclined belt carrying boxes up from the back left. With
  // `loop`, an arrow circling above it marks the belt as feeding back into
  // itself.
  function drawConveyor(sx, sy, accent, lit, loop) {
    const c = [sx, sy], a = 0.86, low = 4, high = 16;
    const belt = wedge(c, a, 0.3, low, high, accent, lit);
    onFace(belt, 'v', len => {
      for (let i = 0; i < 4; i++) {
        const x = 4 + i * (len - 8) / 3;
        dot(x, -2.5, 1.3, accent, lit ? 0.7 : 0.45);
      }
    });
    for (let i = 0; i < 3; i++) {
      const t = (animT * 0.3 + i / 3) % 1, u = -0.7 + 1.4 * t;
      block(pt(c, u, 0), 0.13, 0.16, 6, accent, lit,
        { lift: low + (high - low) * (u + a) / (2 * a), fillAlpha: 2, strokeAlpha: Math.min(1, 4 * Math.sin(Math.PI * t)) });
    }
    if (loop) {
      const [cx, cy] = pt(c, 0, 0, 32);
      const turn = animT * 1.5;
      ctx.save();
      if (lit) { ctx.shadowColor = accent; ctx.shadowBlur = 5; }
      ctx.strokeStyle = rgba(accent, lit ? 1 : 0.7);
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      ctx.arc(cx, cy, 6, turn, turn + Math.PI * 1.5);
      ctx.stroke();
      const end = turn + Math.PI * 1.5;
      const [ex, ey] = [cx + 6 * Math.cos(end), cy + 6 * Math.sin(end)];
      poly([[ex + 3 * Math.cos(end), ey + 3 * Math.sin(end)],
        [ex + 3 * Math.cos(end + 2.2), ey + 3 * Math.sin(end + 2.2)],
        [ex + 3 * Math.cos(end - 2.2), ey + 3 * Math.sin(end - 2.2)]], accent, 1, 0);
      ctx.restore();
    }
  }

  add('postbox', drawPostbox, { bh: 30, scale: 0.8, label: 'Postbox' });
  add('sorter', drawSorter, { bh: 19, scale: 0.85, extraTop: 10, label: 'Sorting bins' });
  add('envelopes', drawEnvelopes, { bh: 16, scale: 0.85, label: 'Envelopes' });
  add('trainer', drawTrainer, { bh: 9, scale: 0.85, extraTop: 22, label: 'Training bench' });
  add('podium', drawPodium, { bh: 15, scale: 0.85, extraTop: 18, label: 'Podium' });
  add('run-log', drawRunLog, { bh: 24, scale: 0.75, label: 'Run log' });
  add('model-shelf', drawShelf, { bh: 30, scale: 0.8, label: 'Model shelf' });
  add('gate', drawGate, { bh: 29, scale: 0.8, extraTop: 6, label: 'Checkpoint gate' });
  add('tray', drawTray, { bh: 7, scale: 0.85, extraTop: 8, label: 'Inbox tray' });
  add('ml-desk', drawDesk, { bh: 17, scale: 0.85, extraTop: 20, label: 'Desk' });
  add('conveyor', (sx, sy, accent, lit) => drawConveyor(sx, sy, accent, lit, false),
    { bh: 22, scale: 0.8, label: 'Conveyor' });
  add('conveyor-loop', (sx, sy, accent, lit) => drawConveyor(sx, sy, accent, lit, true),
    { bh: 22, scale: 0.8, extraTop: 20, label: 'Conveyor (loop)' });
})();
