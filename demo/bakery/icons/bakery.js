// The bakery's own topology icons, loaded through config.toml's
// `[ui] icon-scripts` and assigned to every node in layout.json, so the canvas
// reads as the bakery rather than as odf: its staff at their desks (one desk
// per agent, each with that role's tools), the papers on them, the shop front,
// the bakehouse, and the hatches its tools' items come in through.
//
// One family look throughout: tidy solids from the same ODF.iconKit helpers
// as odf's built-in icons, so they take on the theme's look and light up with
// their node; details drawn onto their faces, so they read on the ink theme's
// outline-less tonal solids; and at most one slow, small motion each.
(() => {
  const { pt, poly, line, path, rect, dot, text, block, gable, wedge, cylinder, onFace, wave, strong, ink } = ODF.iconKit;
  const add = (key, draw, group, meta) => ODF.registerIcon(key, draw, { group: `Bakery · ${group}`, ...meta });

  const FONT = 'bold 3.2px sans-serif';
  const soft = lit => (lit ? 0.65 : 0.4);
  const seg = (p, q, color, alpha, lw) => line(p[0], p[1], q[0], q[1], color, alpha, lw);
  // A flat plane at v = +b (its 'v' side) or u = +a ('u'), for onFace() to
  // draw on without a solid behind it: wheels, legs, glints.
  const plane = (c, a, b, lift = 0) => ({ g: [c[0], c[1] - lift], a, b });

  function ellipse(x, y, rx, ry, color, fillA, strokeA, lw = 0.8) {
    ctx.save();
    ctx.beginPath();
    ctx.ellipse(x, y, rx, ry, 0, 0, Math.PI * 2);
    if (fillA) { ctx.fillStyle = rgba(color, fillA); ctx.fill(); }
    if (strokeA) { ctx.strokeStyle = rgba(color, strokeA); ctx.lineWidth = lw; ctx.stroke(); }
    ctx.restore();
  }

  // A warning triangle of size s centred on (x, y), in the alert color.
  function warning(x, y, s, alpha) {
    const col = ACCENT.alert;
    poly([[x, y - s], [x + s * 0.95, y + s * 0.65], [x - s * 0.95, y + s * 0.65]], col, alpha * 0.2, alpha, { lw: 0.6 });
    line(x, y - s * 0.45, x, y + s * 0.05, col, alpha, 0.6);
    dot(x, y + s * 0.35, 0.35, col, alpha);
  }

  // Lines of writing on a face, `n` rows from y0 down, every other one short.
  function rows(len, y0, n, accent, lit, { gap = 3.2, x0 = 2, x1 = 2, ragged = 3 } = {}) {
    for (let i = 0; i < n; i++) {
      const y = y0 + i * gap;
      line(x0, y, len - x1 - (i % 2) * ragged, y, accent, strong(lit) * 0.6, 0.5);
    }
  }

  // ── Staff: a desk, a clerk at it, and the role's own tools ─────────────

  const DESK_H = 11;

  // A person seated on ground point p, facing the viewer's left: the chair's
  // back, the torso, the head. Returns the head's top.
  function clerk(p, accent, lit) {
    block(pt(p, 0, -0.11), 0.13, 0.025, 15, accent, lit);
    block(p, 0.1, 0.07, 9, accent, lit, { lift: 7, fillAlpha: 1.3 });
    return cylinder(p, 0.07, 4.5, accent, lit, { lift: 16.5, fillAlpha: 1.8 });
  }

  // A desk with a drawer, and a clerk behind it reaching for its top.
  // `on(u, v, h)` is a point on the desk's top, h above it.
  function station(sx, sy, accent, lit, { seated = true } = {}) {
    const c = [sx, sy];
    const seat = pt(c, 0, -0.34);
    const dc = pt(c, 0, 0.12);
    const head = seated ? clerk(seat, accent, lit) : null;
    const desk = block(dc, 0.44, 0.2, DESK_H, accent, lit);
    onFace(desk, 'v', len => {
      rect(len * 0.56, -9.5, len * 0.36, 6.5, accent, 0, strong(lit) * 0.5, 0.4);
      line(len * 0.67, -6.3, len * 0.81, -6.3, accent, strong(lit), 0.8);
    });
    if (seated) {
      for (const s of [-1, 1]) {
        seg(pt(seat, s * 0.1, 0.05, 15), pt(dc, s * 0.13, -0.08, DESK_H), ink(accent), strong(lit), 1.4);
      }
    }
    return { c, dc, head, on: (u, v, h = 0) => pt(dc, u, v, DESK_H + h) };
  }

  // Order desk → a clerk in a headset, the orders on a spike and the phone,
  // its light pulsing as a restaurant writes in.
  function drawOrderDesk(sx, sy, accent, lit) {
    const st = station(sx, sy, accent, lit);
    const { head } = st;
    ctx.save();
    ctx.beginPath();
    ctx.arc(head.x, head.y + 2.2, 3.1, Math.PI * 1.05, Math.PI * 1.95);
    ctx.strokeStyle = rgba(ink(accent), strong(lit));
    ctx.lineWidth = 0.8;
    ctx.stroke();
    ctx.restore();
    line(head.x - 3, head.y + 2.6, head.x - 1.2, head.y + 4.6, ink(accent), strong(lit), 0.6);

    const spike = st.on(-0.25, 0.03);
    [[0, 0], [1.1, 0.025], [2.2, -0.02]].forEach(([z, du]) => {
      block(pt(spike, du, 0), 0.1, 0.08, 0.7, accent, lit, { lift: z, fillAlpha: 1.9 });
    });
    line(spike[0], spike[1] - 2.9, spike[0], spike[1] - 8, ink(accent), strong(lit), 0.7);

    const phone = st.on(0.22, 0.03);
    block(phone, 0.11, 0.08, 2.2, accent, lit, { fillAlpha: 1.3 });
    block(pt(phone, 0, -0.035), 0.1, 0.03, 1.2, accent, lit, { lift: 2.2, fillAlpha: 1.6 });
    const [lx, ly] = pt(phone, 0.04, 0.05, 2.2);
    dot(lx, ly, 0.9, accent, 0.3 + 0.7 * wave(2.5));
  }

  // Specials → a clerk beside the café's chalk board, tomorrow's last
  // special being written up.
  function drawSpecials(sx, sy, accent, lit) {
    const st = station(sx, sy, accent, lit);
    block(st.on(-0.2, 0.04), 0.07, 0.05, 1.5, accent, lit, { fillAlpha: 1.5 });
    const b0 = pt(st.c, 0.64, 0.02);
    seg(pt(b0, 0.12, 0, 0), pt(b0, 0, 0, 23), ink(accent), strong(lit), 0.9);
    const board = block(b0, 0.03, 0.27, 18, accent, lit, { lift: 5 });
    onFace(board, 'u', len => {
      rect(0.8, -17.2, len - 1.6, 16.4, accent, 0.55, 0, 0.4);
      for (let i = 0; i < 3; i++) {
        const y = -13.5 + i * 4;
        dot(2.2, y, 0.45, accent, strong(lit));
        const full = len - 5 - (i % 2) * 2;
        const w = i < 2 ? full : full * (0.15 + 0.85 * ((animT * 0.2) % 1));
        line(3.4, y, 3.4 + w, y, accent, strong(lit), 0.55);
      }
    });
    for (const v of [-0.24, 0.24]) {
      seg(pt(b0, -0.02, v, 5), pt(b0, -0.02, v * 1.2, 0), ink(accent), strong(lit), 0.9);
    }
  }

  // Allergen officer → a clerk going over a product's label with a magnifier,
  // a warning on the label.
  function drawAllergenOfficer(sx, sy, accent, lit) {
    const st = station(sx, sy, accent, lit);
    const label = block(st.on(0.02, 0.02), 0.17, 0.015, 8, accent, lit, { fillAlpha: 1.8 });
    onFace(label, 'v', len => {
      warning(len * 0.24, -4.3, 1.9, strong(lit));
      rows(len, -6, 2, accent, lit, { x0: len * 0.46, gap: 2.6, ragged: 1.5 });
    });
    const [x, y] = st.on(0.02, 0.02, 6);
    const mx = x + 2.5 * Math.sin(animT * 0.7), my = y - 1;
    line(mx + 2.2, my + 2.2, mx + 5, my + 5, ink(accent), strong(lit), 1.3);
    ellipse(mx, my, 3, 3, ink(accent), lit ? 0.2 : 0.12, strong(lit), 0.9);
  }

  // Account manager → a clerk at a contract, pen beside it, and the price a
  // restaurant pays rising on a small chart.
  function drawAccountManager(sx, sy, accent, lit) {
    const st = station(sx, sy, accent, lit);
    const paper = st.on(-0.14, 0.03);
    block(paper, 0.15, 0.11, 0.5, accent, lit, { fillAlpha: 1.9 });
    for (let i = 0; i < 3; i++) {
      seg(pt(paper, -0.11, -0.07 + i * 0.04, 0.5), pt(paper, 0.09 - (i % 2) * 0.05, -0.07 + i * 0.04, 0.5),
        ink(accent), strong(lit) * 0.6, 0.45);
    }
    const sig = [];
    for (let k = 0; k <= 6; k++) {
      const [px, py] = pt(paper, -0.1 + k * 0.025, 0.065, 0.5);
      sig.push([px, py - 0.6 * Math.sin(k * 1.9)]);
    }
    path(sig, ink(accent), strong(lit), 0.5);
    seg(pt(paper, 0.08, 0.08, 0.8), pt(paper, 0.2, -0.02, 1.2), ink(accent), strong(lit), 0.9);
    [3, 4.5, 6.5].forEach((h, i) => {
      const grow = i === 2 ? 0.55 + 0.45 * wave(0.6) : 1;
      block(st.on(0.14 + i * 0.09, 0.02), 0.03, 0.03, h * grow, accent, lit, { fillAlpha: 1.5 });
    });
  }

  // Invoice clerk → a clerk at an open ledger, a rubber stamp rising off its
  // pad and settling again.
  function drawInvoiceClerk(sx, sy, accent, lit) {
    const st = station(sx, sy, accent, lit);
    for (const u of [-0.25, -0.02]) {
      const page = st.on(u, 0.03);
      block(page, 0.11, 0.12, 0.8, accent, lit, { fillAlpha: 1.9 });
      for (let i = 0; i < 4; i++) {
        const v = -0.08 + i * 0.05;
        seg(pt(page, -0.08, v, 0.8), pt(page, 0.08, v, 0.8), ink(accent), strong(lit) * 0.55, 0.4);
      }
    }
    seg(st.on(-0.135, -0.09, 0.8), st.on(-0.135, 0.15, 0.8), ink(accent), strong(lit), 0.6);
    const pad = st.on(0.27, 0.03);
    block(pad, 0.08, 0.07, 0.6, accent, lit, { fillAlpha: 0.8 });
    const z = 0.6 + 3 * wave(0.9);
    block(pad, 0.06, 0.05, 1.5, accent, lit, { lift: z, fillAlpha: 1.4 });
    cylinder(pad, 0.025, 3, accent, lit, { lift: z + 1.5 });
    cylinder(pad, 0.05, 1.4, accent, lit, { lift: z + 4.5, fillAlpha: 1.5 });
  }

  // Back office → a filing cabinet and a desk with its tray of papers: the
  // bakery's rules at work behind the scenes.
  function drawBackOffice(sx, sy, accent, lit) {
    const c = [sx, sy];
    const cab = block(pt(c, -0.28, -0.22), 0.16, 0.18, 24, accent, lit);
    onFace(cab, 'v', len => {
      for (let i = 0; i < 3; i++) {
        const y = -22.8 + i * 7.6;
        rect(1.2, y, len - 2.4, 6.6, accent, 0, strong(lit) * 0.55, 0.4);
        line(len / 2 - 1.5, y + 2.2, len / 2 + 1.5, y + 2.2, accent, strong(lit), 0.8);
      }
    });
    const desk = block(pt(c, 0.14, 0.18), 0.3, 0.18, DESK_H, accent, lit);
    onFace(desk, 'v', len => {
      rect(len * 0.56, -9.5, len * 0.36, 6.5, accent, 0, strong(lit) * 0.5, 0.4);
      line(len * 0.67, -6.3, len * 0.81, -6.3, accent, strong(lit), 0.8);
    });
    const tray = pt(c, 0.14, 0.18, DESK_H);
    block(tray, 0.14, 0.1, 1.6, accent, lit, { fillAlpha: 0.9 });
    for (let i = 0; i < 2; i++) block(pt(tray, 0, 0), 0.12, 0.08, 0.7, accent, lit, { lift: 1.6 + i * 0.8, fillAlpha: 1.9 });
  }

  // Assistant → a desk with a terminal on it, the cursor blinking: the
  // language model the agents write with.
  function drawAssistant(sx, sy, accent, lit) {
    const st = station(sx, sy, accent, lit, { seated: false });
    block(st.on(0, -0.1), 0.04, 0.03, 2.5, accent, lit);
    const screen = block(st.on(0, -0.1), 0.26, 0.025, 12, accent, lit, { lift: 2.5, fillAlpha: 1.2 });
    onFace(screen, 'v', len => {
      rect(1, -11.2, len - 2, 10.2, accent, 0.5, 0, 0.4);
      rows(len, -8.5, 2, accent, lit, { x0: 2.5, x1: 3, gap: 2.6, ragged: 4 });
      if (wave(3.5) > 0.4) rect(2.5, -4.2, 1.4, 1.8, accent, strong(lit), 0, 0.3);
    });
    block(st.on(0, 0.09), 0.2, 0.06, 0.8, accent, lit, { fillAlpha: 1.4 });
  }

  // ── Office: papers on a stand ──────────────────────────────────────────

  function stand(c, accent, lit, a = 0.36) {
    block(c, a, 0.2, 3, accent, lit);
  }

  // A sheet standing upright on c, `h` tall, with draw(len, top) drawing its
  // contents on its face.
  function sheet(c, h, accent, lit, draw, { a = 0.32, lift = 3 } = {}) {
    const s = block(pt(c, 0, -0.04), a, 0.025, h, accent, lit, { lift, fillAlpha: 1.5 });
    onFace(s, 'v', len => draw(len, -h));
    return s;
  }

  // A draft on its stand, with a mark: approved, amended or rejected.
  function draft(sx, sy, accent, lit, mark) {
    const c = [sx, sy];
    stand(c, accent, lit);
    sheet(c, 28, accent, lit, (len, top) => {
      text('DRAFT', len / 2, top + 5, accent, strong(lit), lit, FONT);
      rows(len, top + 9, 4, accent, lit);
      mark(len, top);
    });
  }

  // Approve → the draft with a round check-mark stamp.
  function drawApprove(sx, sy, accent, lit) {
    draft(sx, sy, accent, lit, len => {
      const x = len * 0.68, y = -6.5;
      const alpha = lit ? 0.6 + 0.4 * wave(1.2) : strong(lit);
      ellipse(x, y, 3.4, 3.4, ink(accent), 0.12, alpha, 0.6);
      path([[x - 1.7, y], [x - 0.5, y + 1.3], [x + 1.8, y - 1.5]], accent, alpha, 0.9);
    });
  }

  // Amend → the draft with a line struck through and rewritten, pencil in hand.
  function drawAmend(sx, sy, accent, lit) {
    draft(sx, sy, accent, lit, (len, top) => {
      const y = top + 9 + 3.2;
      line(1.5, y, len - 1.5, y, accent, strong(lit), 0.7);
      const p = (animT * 0.3) % 1;
      const x = 2 + (len - 4) * p;
      line(2, -5, x, -5, accent, strong(lit), 0.7);
      line(x, -5, x + 3, -11, accent, strong(lit), 1.3);
    });
  }

  // Reject → the draft crossed through.
  function drawReject(sx, sy, accent, lit) {
    draft(sx, sy, accent, lit, (len, top) => {
      const alpha = lit ? 0.95 : 0.75;
      line(len * 0.18, top + 7, len * 0.82, -3, ACCENT.alert, alpha, 1.1);
      line(len * 0.82, top + 7, len * 0.18, -3, ACCENT.alert, alpha, 1.1);
    });
  }

  // Contract → a signed contract in its folder, a seal by the signature.
  function drawContract(sx, sy, accent, lit) {
    const c = [sx, sy];
    stand(c, accent, lit);
    block(pt(c, 0, -0.1), 0.35, 0.02, 22, accent, lit, { lift: 3 });
    sheet(c, 26, accent, lit, (len, top) => {
      line(2, top + 3.5, len * 0.6, top + 3.5, accent, strong(lit), 0.9);
      rows(len, top + 7, 5, accent, lit, { gap: 2.6 });
      const sig = [];
      const p = Math.min(1, (animT * 0.25) % 1.4);
      for (let k = 0; k <= 10 * p; k++) sig.push([2 + k * 0.6, -5 - 1.2 * Math.sin(k * 1.4)]);
      path(sig, accent, strong(lit), 0.55);
      ellipse(len * 0.78, -5, 2.2, 2.2, accent, lit ? 0.6 : 0.45, strong(lit), 0.5);
    });
  }

  // Invoice → a supplier's invoice, its total underlined twice.
  function drawInvoice(sx, sy, accent, lit) {
    const c = [sx, sy];
    stand(c, accent, lit);
    sheet(c, 30, accent, lit, (len, top) => {
      text('INVOICE', len / 2, top + 5, accent, strong(lit), lit, FONT);
      for (let i = 0; i < 4; i++) {
        const y = top + 9.5 + i * 3.2;
        line(2, y, len * 0.55, y, accent, strong(lit) * 0.55, 0.5);
        line(len * 0.7, y, len - 2, y, accent, strong(lit) * 0.8, 0.5);
      }
      line(2, -7.5, len - 2, -7.5, accent, strong(lit) * 0.6, 0.4);
      text('£', len * 0.5, -3.6, accent, strong(lit), lit, FONT);
      line(len * 0.62, -4.5, len - 2, -4.5, accent, strong(lit), 1);
      line(len * 0.62, -3.2, len - 2, -3.2, accent, strong(lit), 0.5);
    });
  }

  // Order book → a restaurant's week of standing orders, today's column
  // moving on.
  function drawOrderBook(sx, sy, accent, lit) {
    const c = [sx, sy];
    stand(c, accent, lit);
    sheet(c, 26, accent, lit, (len, top) => {
      text('WEEK', len / 2, top + 5, accent, strong(lit), lit, FONT);
      const w = (len - 3) / 7, h = 4.2;
      const today = Math.floor(animT * 0.25) % 7;
      for (let col = 0; col < 7; col++) {
        for (let r = 0; r < 4; r++) {
          const fill = col === today ? (lit ? 0.55 : 0.4) : 0.06;
          rect(1.5 + col * w, top + 7.5 + r * h, w, h, accent, fill, strong(lit) * 0.45, 0.3);
        }
      }
    });
  }

  // Order slips → amended order slips on a spike, the newest marked.
  function drawOrderSlips(sx, sy, accent, lit) {
    const c = [sx, sy];
    cylinder(c, 0.2, 2, accent, lit);
    const slips = [[0.03, -0.02], [-0.03, 0.02], [0.02, 0.03], [-0.01, -0.02]];
    slips.forEach(([du, dv], i) => block(pt(c, du, dv), 0.26, 0.18, 0.8, accent, lit, { lift: 2 + i * 1.5, fillAlpha: 1.9 }));
    const top = 2 + (slips.length - 1) * 1.5 + 0.8;
    for (let i = 0; i < 3; i++) {
      const v = -0.1 + i * 0.07;
      seg(pt(c, -0.2, v, top), pt(c, 0.12 - (i % 2) * 0.08, v, top), ink(accent), strong(lit) * 0.55, 0.5);
    }
    const [nx, ny] = pt(c, 0.15, 0.1, top);
    dot(nx, ny, 1.2, accent, 0.35 + 0.65 * wave(2));
    const [x, y] = pt(c, 0, 0, top);
    line(x, y, x, y - 9, ink(accent), strong(lit), 0.8);
  }

  // In-tray → a two-tier tray of drafts waiting, a fresh one sliding in.
  function drawInTray(sx, sy, accent, lit) {
    const c = [sx, sy];
    const a = 0.38, b = 0.28;
    const post = (u, v) => seg(pt(c, u, v, 0), pt(c, u, v, 14), ink(accent), strong(lit), 1);
    post(-a, -b); post(a, -b);
    for (const z of [0, 11]) {
      block(c, a, b, 2, accent, lit, { lift: z });
      block(pt(c, 0, -b + 0.02), a, 0.02, 4, accent, lit, { lift: z + 2 });
      for (let i = 0; i < 3; i++) block(pt(c, (i % 2) * 0.02, 0.01), 0.32, 0.22, 0.9, accent, lit, { lift: z + 2 + i * 1, fillAlpha: 1.9 });
    }
    const k = (animT * 0.25) % 1;
    const fade = Math.min(1, k * 5, (1 - k) * 5);
    block(pt(c, 0.28 * (1 - Math.min(1, k * 1.6)), 0.01), 0.32, 0.22, 0.9, accent, lit, { lift: 16, fillAlpha: 1.9, strokeAlpha: fade });
    post(-a, b); post(a, b);
  }

  // Recipes → the bakery's recipe binder, an ear of wheat on its cover.
  function drawRecipe(sx, sy, accent, lit) {
    const c = [sx, sy];
    block(c, 0.34, 0.16, 2, accent, lit);
    const binder = block(pt(c, 0, -0.02), 0.28, 0.09, 26, accent, lit, { lift: 2 });
    onFace(binder, 'v', len => {
      text('RECIPES', len / 2, -20, accent, strong(lit), lit, FONT);
      const x = len / 2;
      line(x, -4, x, -15, accent, strong(lit), 0.6);
      for (let i = 0; i < 4; i++) {
        const y = -14 + i * 2.3;
        ellipse(x - 1.2, y, 0.9, 1.4, accent, strong(lit) * 0.8, 0);
        ellipse(x + 1.2, y, 0.9, 1.4, accent, strong(lit) * 0.8, 0);
      }
      rect(len * 0.8, -26, 1.3, 7, accent, strong(lit), 0, 0.3);
    });
    onFace(binder, 'u', len => {
      rect(len * 0.2, -20, len * 0.6, 5, accent, 0.15, strong(lit) * 0.6, 0.4);
    });
  }

  // Allergen chart → the allergen matrix on a stand: products down, allergens
  // across, one product's row looked over at a time.
  function drawAllergenChart(sx, sy, accent, lit) {
    const c = [sx, sy];
    stand(c, accent, lit);
    sheet(c, 30, accent, lit, (len, top) => {
      warning(len / 2, top + 3.5, 1.9, strong(lit));
      const cols = 5, rowsN = 5, w = (len - 3) / cols, h = 3.6;
      const look = Math.floor(animT * 0.4) % rowsN;
      for (let r = 0; r < rowsN; r++) {
        for (let col = 0; col < cols; col++) {
          const has = (r * 3 + col * 2) % 5 === 0;
          const color = has ? ACCENT.alert : accent;
          const fill = has ? (r === look ? 0.85 : 0.5) : (r === look ? 0.25 : 0.05);
          rect(1.5 + col * w, top + 7.5 + r * h, w, h, color, fill, strong(lit) * 0.4, 0.3);
        }
      }
    });
  }

  // Forecast → the coming days' demand on an easel: the past as a line, the
  // forecast dashed, its last point pulsing.
  function drawForecast(sx, sy, accent, lit) {
    const c = [sx, sy];
    seg(pt(c, 0, -0.3, 0), pt(c, 0, -0.06, 30), ink(accent), strong(lit), 0.9);
    const board = block(pt(c, 0, -0.04), 0.34, 0.025, 23, accent, lit, { lift: 7, fillAlpha: 1.5 });
    onFace(board, 'v', len => {
      line(2, -3, len - 1.5, -3, accent, strong(lit) * 0.7, 0.5);
      line(2, -3, 2, -21, accent, strong(lit) * 0.7, 0.5);
      const ys = [-8, -11, -9, -14, -12, -16, -15, -18];
      const pts = ys.map((y, i) => [3 + i * (len - 5) / (ys.length - 1), y]);
      path(pts.slice(0, 5), accent, strong(lit), 0.8);
      ctx.save();
      ctx.setLineDash([1.2, 1]);
      path(pts.slice(4), accent, strong(lit), 0.8);
      ctx.restore();
      const [ex, ey] = pts[pts.length - 1];
      dot(ex, ey, 1.1, accent, 0.4 + 0.6 * wave(2));
    });
    for (const u of [-0.3, 0.3]) seg(pt(c, u, -0.02, 7), pt(c, u * 1.15, 0.12, 0), ink(accent), strong(lit), 0.9);
  }

  // Margins → what each contract costs to make beside what it pays; the
  // last one is paid below cost.
  function drawMargins(sx, sy, accent, lit) {
    const c = [sx, sy];
    block(c, 0.5, 0.28, 2, accent, lit);
    const pairs = [[7, 13], [10, 15], [13, 10]];
    pairs.forEach(([cost, price], i) => {
      const u = -0.3 + i * 0.3;
      block(pt(c, u - 0.05, 0.04), 0.045, 0.045, cost, accent, lit, { lift: 2, fillAlpha: 0.9 });
      const loss = price < cost;
      const color = loss ? ACCENT.alert : accent;
      const h = loss ? price * (0.85 + 0.15 * wave(1.2)) : price;
      block(pt(c, u + 0.05, 0.04), 0.045, 0.045, h, color, lit, { lift: 2, fillAlpha: 1.6 });
    });
  }

  // What-if → a balance weighing an ingredient's new price against the
  // bakery's margins, tipping gently.
  function drawWhatIf(sx, sy, accent, lit) {
    const c = [sx, sy];
    cylinder(c, 0.2, 2.5, accent, lit);
    block(c, 0.03, 0.03, 19, accent, lit, { lift: 2.5 });
    const [px, py] = pt(c, 0, 0, 22);
    const tip = 0.16 * Math.sin(animT * 0.6);
    const half = 13, dx = half * Math.cos(tip), dy = half * Math.sin(tip);
    const L = [px - dx, py - dy], R = [px + dx, py + dy];
    seg(L, R, ink(accent), strong(lit), 1.2);
    dot(px, py, 1.3, ink(accent), strong(lit));
    for (const [x, y] of [L, R]) {
      line(x - 3, y + 8, x, y, ink(accent), soft(lit), 0.5);
      line(x + 3, y + 8, x, y, ink(accent), soft(lit), 0.5);
      ellipse(x, y + 8.5, 5, 1.8, accent, lit ? 0.6 : 0.45, strong(lit), 0.6);
    }
    // A price tag on the left pan, coins on the right.
    const [tx, ty] = [L[0], L[1] + 5.5];
    poly([[tx - 3, ty - 1.8], [tx + 2, ty - 1.8], [tx + 3.6, ty], [tx + 2, ty + 1.8], [tx - 3, ty + 1.8]], accent, lit ? 0.7 : 0.5, strong(lit), { lw: 0.5 });
    text('£', tx - 0.3, ty + 1.1, ink(accent), strong(lit), lit, 'bold 3px sans-serif');
    for (let i = 0; i < 3; i++) ellipse(R[0], R[1] + 7.5 - i * 1.3, 2.4, 0.9, accent, lit ? 0.8 : 0.6, strong(lit), 0.4);
  }

  // Archive → a box of files: the bakery's history, imported.
  function drawArchive(sx, sy, accent, lit) {
    const c = [sx, sy];
    const box = block(c, 0.38, 0.28, 12, accent, lit);
    onFace(box, 'v', len => {
      rect(len * 0.3, -9, len * 0.4, 4, accent, 0.15, strong(lit) * 0.6, 0.4);
      text('ARCHIVE', len / 2, -10.5, accent, strong(lit), lit, FONT);
    });
    for (let i = 0; i < 5; i++) {
      const h = 2.5 + ((i * 7) % 3);
      block(pt(c, -0.26 + i * 0.13, -0.02), 0.015, 0.22, h, accent, lit, { lift: 12, fillAlpha: 1.7 });
    }
  }

  // Spreadsheets → a folder of spreadsheets on the shared drive, one cell
  // after another updating.
  function drawSheets(sx, sy, accent, lit) {
    const c = [sx, sy];
    const back = pt(c, 0, -0.1);
    block(back, 0.45, 0.02, 20, accent, lit);
    block(pt(back, -0.24, 0), 0.15, 0.02, 3, accent, lit, { lift: 20 });
    const sheetBlk = block(pt(c, 0, -0.04), 0.38, 0.015, 19, accent, lit, { lift: 3, fillAlpha: 1.5 });
    const cell = Math.floor(animT * 0.8) % 8;
    onFace(sheetBlk, 'v', len => {
      const w = (len - 3) / 4;
      for (let i = 0; i < 8; i++) {
        const col = i % 4, r = Math.floor(i / 4);
        rect(1.5 + col * w, -17.5 + r * 2.6, w, 2.6, accent, i === cell ? (lit ? 0.6 : 0.45) : 0.06, strong(lit) * 0.5, 0.35);
      }
    });
    const front = block(pt(c, 0, 0.04), 0.45, 0.02, 15, accent, lit, { fillAlpha: 1.2 });
    onFace(front, 'v', len => text('SHEETS', len / 2, -6, accent, strong(lit), lit, FONT));
  }

  // ── Front of house ─────────────────────────────────────────────────────

  // Bistro → a restaurant the bakery supplies: a shop front under a striped
  // awning, its window lit.
  function drawBistro(sx, sy, accent, lit) {
    const c = [sx, sy];
    const shop = block(c, 0.42, 0.36, 24, accent, lit);
    onFace(shop, 'v', len => {
      rect(len * 0.1, -12, len * 0.46, 8.5, accent, 0.2 + 0.25 * wave(0.6), strong(lit) * 0.7, 0.4);
      rect(len * 0.66, -13, len * 0.22, 13, accent, 0.15, strong(lit), 0.5);
      text('BISTRO', len / 2, -19.5, accent, strong(lit), lit, FONT);
    });
    onFace(shop, 'u', len => rect(len * 0.25, -14, len * 0.5, 8, accent, 0.15, strong(lit) * 0.6, 0.4));
    wedge(pt(c, 0, 0.43), 0.42, 0.07, 4, 1.2, accent, lit, { lift: 13, axis: 'v', fillAlpha: 1.6 });
    for (let u = -0.32; u <= 0.33; u += 0.16) {
      seg(pt(c, u, 0.37, 17), pt(c, u, 0.5, 14.2), ink(accent), soft(lit), 1.6);
    }
  }

  // Till → the café's till on its counter, a receipt printing.
  function drawTill(sx, sy, accent, lit) {
    const c = [sx, sy];
    const counter = block(c, 0.5, 0.4, 13, accent, lit);
    onFace(counter, 'v', len => line(3, -9, len - 3, -9, accent, soft(lit), 0.5));
    const top = pt(c, 0, 0, 13);
    const body = wedge(pt(top, 0.04, 0.06), 0.3, 0.24, 6, 3.5, accent, lit, { axis: 'v', fillAlpha: 1.3 });
    for (const u of [-0.15, 0, 0.15]) {
      for (const v of [0, 0.12]) {
        const [x, y] = pt(top, 0.04 + u, 0.06 + v, 5 - v * 8);
        dot(x, y, 0.6, ink(accent), strong(lit));
      }
    }
    onFace(body, 'v', len => {
      const L = 2 + 6 * ((animT * 0.25) % 1);
      rect(len * 0.6, -3.5 - L, len * 0.22, L, accent, 0.4, strong(lit) * 0.6, 0.4);
    });
    const display = block(pt(top, 0.04, -0.2), 0.26, 0.035, 7, accent, lit, { lift: 6, fillAlpha: 1.6 });
    onFace(display, 'v', len => text(`£${(4.2 + (Math.floor(animT * 0.5) % 9) * 1.1).toFixed(2)}`, len / 2, -2.2, accent, strong(lit), lit, 'bold 3.6px monospace'));
  }

  // Display case → the café's glass counter: loaves at the back, buns at the
  // front, a glint running over the glass.
  function drawDisplayCase(sx, sy, accent, lit) {
    const c = [sx, sy];
    const base = block(c, 0.5, 0.32, 10, accent, lit);
    onFace(base, 'v', len => line(3, -5, len - 3, -5, accent, soft(lit), 0.5));
    const top = pt(c, 0, 0, 10);
    for (const u of [-0.28, 0, 0.28]) gable(pt(top, u, -0.12), 0.1, 0.07, 2.5, 2.5, accent, lit, { fillAlpha: 1.7 });
    for (const u of [-0.3, -0.1, 0.1, 0.3]) cylinder(pt(top, u, 0.13), 0.07, 2.2, accent, lit, { fillAlpha: 1.9 });
    const glass = block(c, 0.5, 0.32, 11, accent, lit, { lift: 10, fillAlpha: 0.3, strokeAlpha: 0.6 });
    onFace(glass, 'v', len => {
      const t = (animT * 0.12) % 1;
      const x = -4 + t * (len + 8);
      line(x, -1, x + 4, -10, '#ffffff', 0.35 * Math.sin(t * Math.PI), 1.2);
    });
  }

  // Day-old → a basket of yesterday's loaves, a half-price tag swaying.
  function drawDayOld(sx, sy, accent, lit) {
    const c = [sx, sy];
    gable(pt(c, -0.12, -0.06), 0.24, 0.09, 2.5, 3, accent, lit, { lift: 6, fillAlpha: 1.5 });
    gable(pt(c, 0.12, 0.02), 0.09, 0.2, 2.5, 3, accent, lit, { lift: 6, axis: 'v', fillAlpha: 1.6 });
    const basket = block(c, 0.4, 0.3, 8, accent, lit);
    const weave = len => {
      for (let x = 2; x < len - 1; x += 2.5) line(x, -7.5, x, -0.5, accent, soft(lit), 0.4);
      line(1, -4, len - 1, -4, accent, soft(lit), 0.4);
    };
    onFace(basket, 'v', weave);
    onFace(basket, 'u', weave);
    const [ax, ay] = pt(c, 0.4, 0.3, 7);
    const sway = 0.25 * Math.sin(animT * 0.9);
    ctx.save();
    ctx.translate(ax, ay);
    ctx.rotate(sway);
    line(0, 0, 0, 3.5, ink(accent), strong(lit), 0.5);
    rect(-3.2, 3.5, 6.4, 5, accent, lit ? 0.75 : 0.55, strong(lit), 0.4);
    text('½', 0, 7.6, ink(accent), strong(lit), lit, 'bold 3.6px sans-serif');
    ctx.restore();
  }

  // Shutter → closing the café: its shutter half down over the lit front.
  function drawShutter(sx, sy, accent, lit) {
    const c = [sx, sy];
    const front = block(c, 0.42, 0.34, 24, accent, lit);
    const k = 0.45 + 0.25 * wave(0.5);
    onFace(front, 'v', len => {
      const top = -19, h = 17;
      rect(len * 0.06, top - 2.5, len * 0.88, 2.5, accent, 0.5, strong(lit), 0.4);
      rect(len * 0.1, top, len * 0.8, h, accent, 0.25 + 0.15 * wave(0.7), strong(lit) * 0.6, 0.4);
      rect(len * 0.1, top, len * 0.8, h * k, accent, 0.6, strong(lit), 0.5);
      for (let y = top + 1.6; y < top + h * k - 0.5; y += 1.6) line(len * 0.1, y, len * 0.9, y, accent, soft(lit), 0.35);
      line(len * 0.45, top + h * k - 0.8, len * 0.55, top + h * k - 0.8, accent, strong(lit), 0.8);
    });
    onFace(front, 'u', len => {
      rect(len * 0.12, -16.5, len * 0.76, 5, accent, 0.2, strong(lit), 0.4);
      text('CLOSED', len / 2, -13, accent, strong(lit), lit, FONT);
    });
  }

  // Van → the bakery's delivery van, loaded for the morning's round.
  function drawVan(sx, sy, accent, lit) {
    const c = [sx, sy];
    const cargo = block(pt(c, -0.15, 0), 0.45, 0.3, 19, accent, lit, { lift: 4 });
    onFace(cargo, 'v', len => {
      text('BAKERY', len / 2, -11, accent, strong(lit), lit, FONT);
      line(3, -7.5, len - 3, -7.5, accent, soft(lit), 0.5);
    });
    const cab = wedge(pt(c, 0.5, 0), 0.2, 0.3, 15, 10, accent, lit, { lift: 4, axis: 'u' });
    onFace(cab, 'u', len => rect(len * 0.15, -9, len * 0.7, 4, accent, lit ? 0.45 : 0.3, strong(lit), 0.4));
    onFace(cab, 'v', len => rect(len * 0.2, -9.5, len * 0.5, 4, accent, lit ? 0.35 : 0.22, strong(lit), 0.4));
    onFace(plane(c, 0.7, 0.3), 'v', () => {
      for (const u of [-0.45, 0, 0.5]) {
        const x = (u + 0.7) * TW2 / 2;
        ellipse(x, -3.2, 3.2, 3.2, accent, lit ? 0.6 : 0.45, strong(lit), 0.8);
        dot(x, -3.2, 0.9, accent, strong(lit));
      }
    });
  }

  // Messenger → a phone in its dock, a restaurant's message coming in.
  function drawMessenger(sx, sy, accent, lit) {
    const c = [sx, sy];
    block(c, 0.3, 0.22, 3, accent, lit);
    const phone = block(c, 0.2, 0.04, 28, accent, lit, { lift: 3, fillAlpha: 1.4 });
    const fresh = Math.min(1, ((animT * 0.3) % 1) * 2);
    onFace(phone, 'v', len => {
      rect(1.2, -26, len - 2.4, 22, accent, 0.12, strong(lit) * 0.6, 0.4);
      const msgs = [[1.8, -23.5, 0.6], [len * 0.35, -19, 0.6], [1.8, -14.5, 0.5]];
      for (const [x, y, w] of msgs) rect(x, y, (len - 3.6) * w, 3, accent, lit ? 0.5 : 0.35, 0, 0.4);
      rect(1.8, -10, (len - 3.6) * 0.6 * fresh, 3, accent, lit ? 0.8 : 0.55, 0, 0.4);
      dot(len / 2, -2, 0.8, accent, strong(lit));
    });
  }

  // ── Bakehouse ──────────────────────────────────────────────────────────

  // Oven → the two-deck oven of the night's bake, its doors glowing in turn.
  function drawOven(sx, sy, accent, lit) {
    const c = [sx, sy];
    const body = block(c, 0.5, 0.42, 30, accent, lit);
    onFace(body, 'v', len => {
      [-27, -13].forEach((y, i) => {
        rect(4, y, len - 8, 9, accent, 0.2 + 0.35 * wave(0.8, i * Math.PI), strong(lit), 0.6);
        line(6, y - 1.6, len - 6, y - 1.6, accent, strong(lit), 1);
      });
    });
    onFace(body, 'u', len => {
      dot(len * 0.35, -23, 1.6, accent, strong(lit));
      dot(len * 0.65, -23, 1.6, accent, strong(lit));
      rect(len * 0.25, -14, len * 0.5, 2.5, accent, 0.15, strong(lit) * 0.7, 0.5);
      text('220°', len / 2, -7, accent, strong(lit), lit, FONT);
    });
    block(pt(c, -0.25, -0.2), 0.07, 0.07, 5, accent, lit, { lift: 30 });
  }

  // Proof rack → a rolling rack of trays for the bake, the bake sheet
  // clipped to its side, one line ticked off after another.
  function drawProofRack(sx, sy, accent, lit) {
    const c = [sx, sy];
    const a = 0.36, b = 0.26;
    const post = (u, v) => seg(pt(c, u, v, 1), pt(c, u, v, 30), ink(accent), strong(lit), 1);
    post(-a, -b); post(a, -b); post(-a, b);
    [3, 11, 19, 27].forEach((z, i) => {
      block(c, a, b, 1.2, accent, lit, { lift: z });
      if (i % 2 === 0) {
        for (const u of [-0.2, 0.05, 0.28]) gable(pt(c, u, 0.02), 0.09, 0.18, 2, 2.2, accent, lit, { lift: z + 1.2, axis: 'v', fillAlpha: 1.6 });
      } else {
        for (const u of [-0.22, 0, 0.22]) for (const v of [-0.1, 0.1]) cylinder(pt(c, u, v), 0.06, 1.8, accent, lit, { lift: z + 1.2, fillAlpha: 1.8 });
      }
    });
    post(a, b);
    for (const [u, v] of [[-a, b], [a, b], [a, -b]]) {
      const [x, y] = pt(c, u, v);
      dot(x, y, 1.2, ink(accent), strong(lit));
    }
    const clip = block(pt(c, a + 0.02, 0.04), 0.012, 0.17, 13, accent, lit, { lift: 12, fillAlpha: 1.8 });
    const tick = Math.floor(animT * 0.5) % 4;
    onFace(clip, 'u', len => {
      for (let i = 0; i < 4; i++) {
        const y = -10.5 + i * 2.6;
        line(1.5, y, len - 1.5, y, accent, i <= tick ? strong(lit) : strong(lit) * 0.35, 0.5);
      }
    });
  }

  // Flour sacks → sacks of flour on a pallet.
  function drawSacks(sx, sy, accent, lit) {
    const c = [sx, sy];
    block(c, 0.5, 0.4, 3, accent, lit);
    let front;
    for (const [u, v] of [[-0.22, -0.18], [0.22, -0.18], [0, 0.16]]) {
      const g = pt(c, u, v);
      front = cylinder(g, 0.2, 14, accent, lit, { lift: 3 });
      const neck = cylinder(g, 0.07, 3, accent, lit, { lift: 17, fillAlpha: 1.3 });
      dot(neck.x, neck.y - 0.5, 1, ink(accent), strong(lit));
    }
    text('FLOUR', front.x, front.y + 9, ink(accent), strong(lit), lit, FONT);
  }

  // Price sacks → a sack with what the supplier charges for it on a tag.
  function drawPriceSacks(sx, sy, accent, lit) {
    const c = [sx, sy];
    block(c, 0.36, 0.3, 3, accent, lit);
    const sack = cylinder(c, 0.24, 16, accent, lit, { lift: 3 });
    const neck = cylinder(c, 0.08, 3.5, accent, lit, { lift: 19, fillAlpha: 1.3 });
    text('FLOUR', sack.x, sack.y + 10, ink(accent), strong(lit), lit, FONT);
    const [ax, ay] = [neck.x + 1.5, neck.y + 2];
    ctx.save();
    ctx.translate(ax, ay);
    ctx.rotate(-0.5 + 0.2 * Math.sin(animT * 0.8));
    line(0, 0, 5, 0, ink(accent), strong(lit), 0.5);
    poly([[5, -2.2], [11, -2.2], [11, 2.2], [5, 2.2], [3.6, 0]], accent, lit ? 0.75 : 0.55, strong(lit), { lw: 0.5 });
    text('£', 8.2, 1.2, ink(accent), strong(lit), lit, 'bold 3.4px sans-serif');
    ctx.restore();
  }

  // Trace → an ingredient followed from its sack into a loaf and out to a
  // restaurant's crate, along a trail of dots.
  function drawTrace(sx, sy, accent, lit) {
    const c = [sx, sy];
    const stops = [[-0.42, -0.32], [0, 0], [0.42, 0.3]].map(([u, v]) => pt(c, u, v, 0.5));
    const n = 12;
    for (let i = 0; i < n; i++) {
      const t = (i / n + animT * 0.12) % 1;
      const leg = t < 0.5 ? 0 : 1, k = (t % 0.5) * 2;
      const [p, q] = [stops[leg], stops[leg + 1]];
      dot(p[0] + (q[0] - p[0]) * k, p[1] + (q[1] - p[1]) * k, 0.8, accent, soft(lit) + 0.3 * Math.sin(t * Math.PI));
    }
    cylinder(pt(c, -0.42, -0.32), 0.15, 11, accent, lit);
    cylinder(pt(c, -0.42, -0.32), 0.05, 2.5, accent, lit, { lift: 11, fillAlpha: 1.3 });
    gable(c, 0.2, 0.11, 4, 3.5, accent, lit, { fillAlpha: 1.6 });
    const crate = block(pt(c, 0.42, 0.3), 0.16, 0.14, 8, accent, lit);
    onFace(crate, 'v', len => {
      line(1, -4, len - 1, -4, accent, strong(lit) * 0.6, 0.5);
      line(len * 0.5, -7.5, len * 0.5, -0.5, accent, strong(lit) * 0.6, 0.5);
    });
  }

  // Label printer → the printer feeding out a product's label, its allergen
  // warning on it.
  function drawLabelPrinter(sx, sy, accent, lit) {
    const c = [sx, sy];
    const body = block(pt(c, 0, -0.08), 0.3, 0.24, 12, accent, lit);
    onFace(body, 'v', len => line(3, -6.5, len - 3, -6.5, accent, strong(lit), 0.8));
    onFace(body, 'u', len => {
      dot(len * 0.3, -8, 1, accent, strong(lit));
      dot(len * 0.55, -8, 1, accent, soft(lit));
    });
    cylinder(pt(c, -0.04, -0.12), 0.14, 1.4, accent, lit, { lift: 12, fillAlpha: 1.6 });
    const L = 0.06 + 0.28 * ((animT * 0.2) % 1);
    const mid = pt(c, 0, 0.16 + L / 2);
    block(mid, 0.2, L / 2, 0.4, accent, lit, { lift: 5.4, fillAlpha: 2 });
    if (L > 0.18) {
      const [x, y] = pt(mid, -0.06, 0.02, 5.8);
      warning(x, y, 1.5, strong(lit));
      seg(pt(mid, 0.02, -0.03, 5.8), pt(mid, 0.15, -0.03, 5.8), ink(accent), strong(lit) * 0.6, 0.4);
    }
  }

  // ── Wiring: how the bakery's tools reach it ─────────────────────────────

  // Hatch → a delivery hatch in a wall: an item from a tool comes through
  // onto its shelf.
  function drawHatch(sx, sy, accent, lit) {
    const c = [sx, sy];
    const wall = block(pt(c, 0, -0.2), 0.42, 0.1, 26, accent, lit);
    onFace(wall, 'v', len => {
      rect(len * 0.2, -19, len * 0.6, 10, accent, 0.5, strong(lit) * 0.7, 0.5);
      rect(len * 0.3, -24, len * 0.4, 3, accent, 0.25, strong(lit), 0.4);
    });
    block(c, 0.32, 0.1, 1.5, accent, lit, { lift: 7.5, fillAlpha: 1.4 });
    const k = (animT * 0.3) % 1;
    const fade = Math.min(1, k * 6, (1 - k) * 4);
    block(pt(c, 0, -0.12 + 0.14 * Math.min(1, k * 2)), 0.1, 0.07, 4, accent, lit, { lift: 9, fillAlpha: 1.6, strokeAlpha: fade });
    for (const u of [-0.25, 0.25]) seg(pt(c, u, -0.1, 3), pt(c, u, 0.08, 7.5), ink(accent), strong(lit), 0.8);
  }

  // Post → a rack of envelopes, an unread one marked.
  function drawPost(sx, sy, accent, lit) {
    const c = [sx, sy];
    block(c, 0.36, 0.26, 4, accent, lit);
    for (const [v, h] of [[-0.14, 18], [-0.03, 16]]) block(pt(c, 0, v), 0.32, 0.015, h, accent, lit, { lift: 4, fillAlpha: 1.2 });
    const env = block(pt(c, 0, 0.1), 0.32, 0.015, 14, accent, lit, { lift: 4, fillAlpha: 1.7 });
    onFace(env, 'v', len => {
      path([[1, -13.4], [len / 2, -7], [len - 1, -13.4]], accent, strong(lit), 0.6);
      line(1, -0.8, len * 0.4, -5.5, accent, strong(lit) * 0.5, 0.4);
      line(len - 1, -0.8, len * 0.6, -5.5, accent, strong(lit) * 0.5, 0.4);
    });
    const [bx, by] = pt(c, 0.3, 0.1, 20);
    dot(bx, by, 1.8, accent, 0.4 + 0.6 * wave(2));
  }

  // Clock → a station clock on a post, keeping the bakery's time.
  function drawClock(sx, sy, accent, lit) {
    const c = [sx, sy];
    block(c, 0.2, 0.2, 3, accent, lit);
    const [px, py] = pt(c, 0, 0, 3);
    line(px, py, px, py - 13, ink(accent), strong(lit), 1.6);
    const housing = block(c, 0.36, 0.05, 22, accent, lit, { lift: 16 });
    onFace(housing, 'v', len => {
      const cx = len / 2, cy = -11, r = 6.2;
      ellipse(cx, cy, r, r, accent, lit ? 0.3 : 0.18, strong(lit), 0.7);
      for (let i = 0; i < 12; i++) {
        const t = (i / 12) * Math.PI * 2;
        const k = i % 3 ? 0.85 : 0.75;
        line(cx + Math.sin(t) * r * k, cy - Math.cos(t) * r * k,
          cx + Math.sin(t) * r * 0.95, cy - Math.cos(t) * r * 0.95, accent, strong(lit) * 0.8, 0.4);
      }
      const minute = animT * 0.5, hour = minute / 12;
      line(cx, cy, cx + Math.sin(hour) * r * 0.5, cy - Math.cos(hour) * r * 0.5, accent, lit ? 1 : 0.8, 0.9);
      line(cx, cy, cx + Math.sin(minute) * r * 0.8, cy - Math.cos(minute) * r * 0.8, accent, lit ? 1 : 0.8, 0.6);
      dot(cx, cy, 0.7, accent, 1);
    });
  }

  // Weather → the forecast the bake plans by: a sun behind a drifting cloud.
  function drawWeather(sx, sy, accent, lit) {
    const c = [sx, sy];
    block(c, 0.4, 0.4, 3, accent, lit);
    const [gx, gy] = pt(c, 0, 0, 3);
    const sunX = gx + 7, sunY = gy - 30;
    ellipse(sunX, sunY, 5, 5, accent, lit ? 0.7 : 0.45, 0);
    for (let i = 0; i < 8; i++) {
      const t = animT * 0.15 + (i / 8) * Math.PI * 2;
      line(sunX + Math.cos(t) * 7, sunY + Math.sin(t) * 7,
        sunX + Math.cos(t) * 9.5, sunY + Math.sin(t) * 9.5, accent, strong(lit), 0.9);
    }
    const cx = gx - 3 + 2.5 * Math.sin(animT * 0.4), cy = gy - 22;
    ctx.save();
    ctx.beginPath();
    ctx.arc(cx - 6, cy + 1, 4, Math.PI * 0.5, Math.PI * 1.5);
    ctx.arc(cx - 1, cy - 3, 5, Math.PI, Math.PI * 1.85);
    ctx.arc(cx + 5, cy, 4, Math.PI * 1.3, Math.PI * 0.5);
    ctx.closePath();
    ctx.fillStyle = rgba(accent, lit ? 0.45 : 0.3);
    ctx.fill();
    ctx.strokeStyle = rgba(accent, lit ? 0.95 : 0.7);
    ctx.lineWidth = 0.9;
    ctx.stroke();
    ctx.restore();
    line(gx, gy, gx, cy + 5, ink(accent), soft(lit), 0.6);
  }

  add('bakery-order-desk', drawOrderDesk, 'Staff', { bh: 14, scale: 0.6, label: 'Order desk' });
  add('bakery-specials', drawSpecials, 'Staff', { bh: 14, scale: 0.65, extraTop: 2, label: 'Specials board' });
  add('bakery-allergen-officer', drawAllergenOfficer, 'Staff', { bh: 14, scale: 0.6, label: 'Allergen officer' });
  add('bakery-account-manager', drawAccountManager, 'Staff', { bh: 14, scale: 0.6, label: 'Account manager' });
  add('bakery-invoice-clerk', drawInvoiceClerk, 'Staff', { bh: 14, scale: 0.6, label: 'Invoice clerk' });
  add('bakery-back-office', drawBackOffice, 'Staff', { bh: 22, scale: 0.6, label: 'Back office' });
  add('bakery-assistant', drawAssistant, 'Staff', { bh: 18, scale: 0.6, label: 'Assistant terminal' });

  add('bakery-approve', drawApprove, 'Office', { bh: 31, scale: 0.4, label: 'Approve draft' });
  add('bakery-amend', drawAmend, 'Office', { bh: 31, scale: 0.4, label: 'Amend draft' });
  add('bakery-reject', drawReject, 'Office', { bh: 31, scale: 0.4, label: 'Reject draft' });
  add('bakery-contract', drawContract, 'Office', { bh: 29, scale: 0.4, label: 'Contract' });
  add('bakery-invoice', drawInvoice, 'Office', { bh: 33, scale: 0.4, label: 'Invoice' });
  add('bakery-order-book', drawOrderBook, 'Office', { bh: 29, scale: 0.4, label: 'Order book' });
  add('bakery-order-slips', drawOrderSlips, 'Office', { bh: 16, scale: 0.4, label: 'Order slips' });
  add('bakery-in-tray', drawInTray, 'Office', { bh: 18, scale: 0.5, label: 'In-tray' });
  add('bakery-recipe', drawRecipe, 'Office', { bh: 28, scale: 0.45, label: 'Recipe binder' });
  add('bakery-allergen-chart', drawAllergenChart, 'Office', { bh: 33, scale: 0.4, label: 'Allergen chart' });
  add('bakery-forecast', drawForecast, 'Office', { bh: 30, scale: 0.4, label: 'Forecast easel' });
  add('bakery-margins', drawMargins, 'Office', { bh: 17, scale: 0.55, label: 'Margins' });
  add('bakery-what-if', drawWhatIf, 'Office', { bh: 24, scale: 0.4, label: 'Balance' });
  add('bakery-archive', drawArchive, 'Office', { bh: 16, scale: 0.5, label: 'Archive box' });
  add('bakery-sheets', drawSheets, 'Office', { bh: 24, scale: 0.6, label: 'Spreadsheets' });

  add('bakery-bistro', drawBistro, 'Front', { bh: 24, scale: 0.8, label: 'Bistro' });
  add('bakery-till', drawTill, 'Front', { bh: 26, scale: 0.6, label: 'Till' });
  add('bakery-display-case', drawDisplayCase, 'Front', { bh: 21, scale: 0.65, label: 'Display case' });
  add('bakery-day-old', drawDayOld, 'Front', { bh: 11, scale: 0.6, label: 'Day-old basket' });
  add('bakery-shutter', drawShutter, 'Front', { bh: 24, scale: 0.8, label: 'Café shutter' });
  add('bakery-van', drawVan, 'Front', { bh: 23, scale: 0.75, label: 'Delivery van' });
  add('bakery-messenger', drawMessenger, 'Front', { bh: 31, scale: 0.45, label: 'Messenger' });

  add('bakery-oven', drawOven, 'Bakehouse', { bh: 35, scale: 1, label: 'Deck oven' });
  add('bakery-proof-rack', drawProofRack, 'Bakehouse', { bh: 30, scale: 0.65, label: 'Rack and bake sheet' });
  add('bakery-sacks', drawSacks, 'Bakehouse', { bh: 21, scale: 1, label: 'Flour sacks' });
  add('bakery-price-sacks', drawPriceSacks, 'Bakehouse', { bh: 23, scale: 0.6, label: 'Priced sack' });
  add('bakery-trace', drawTrace, 'Bakehouse', { bh: 11, scale: 0.9, label: 'Ingredient trail' });
  add('bakery-label-printer', drawLabelPrinter, 'Bakehouse', { bh: 14, scale: 0.55, label: 'Label printer' });

  add('bakery-hatch', drawHatch, 'Wiring', { bh: 26, scale: 0.55, label: 'Delivery hatch' });
  add('bakery-post', drawPost, 'Wiring', { bh: 22, scale: 0.45, label: 'Post rack' });
  add('bakery-clock', drawClock, 'Wiring', { bh: 38, scale: 0.45, label: 'Station clock' });
  add('bakery-weather', drawWeather, 'Wiring', { bh: 3, scale: 0.8, extraTop: 38, label: 'Weather' });
})();
