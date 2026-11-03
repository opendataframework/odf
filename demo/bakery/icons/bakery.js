// The bakery's own topology icons, loaded through config.toml's
// `[ui] icon-scripts` and assigned to nodes in layout.json: an oven, a bread
// rack, a recipe card, an invoice, a messenger phone, a station clock, the
// weather, a folder of spreadsheets, flour sacks, an allergen-labelled jar and
// a café cup. Where one of odf's built-in icons already fits (the till, the
// delivery truck, the mailbox...), layout.json uses that instead.
//
// Each icon draws with the same ODF.iconKit helpers as the built-in ones, so
// it takes on the theme's look and lights up with its node.
(() => {
  const { pt, line, path, rect, dot, text, block, gable, cylinder, onFace, wave, strong } = ODF.iconKit;
  const add = (key, draw, meta) => ODF.registerIcon(key, draw, { group: 'Bakery', ...meta });

  // Wisps of steam rising from screen point (x, y), fading as they go.
  function steam(x, y, accent, lit, { count = 3, rise = 14, spread = 4 } = {}) {
    for (let i = 0; i < count; i++) {
      const t = (animT * 0.5 + i / count) % 1;
      const ox = x + (i - (count - 1) / 2) * spread;
      const pts = [];
      for (let k = 0; k <= 4; k++) {
        const h = (t + k * 0.08) * rise;
        pts.push([ox + 1.5 * Math.sin(animT * 2 + i * 2 + k), y - h]);
      }
      path(pts, accent, (lit ? 0.7 : 0.45) * (1 - t), 0.8);
    }
  }

  // Oven → a two-deck oven, both doors glowing, steam from the vent.
  function drawOven(sx, sy, accent, lit) {
    const c = [sx, sy];
    const vent = pt(c, -0.25, -0.2);
    block(vent, 0.07, 0.07, 6, accent, lit, { lift: 30 });
    const body = block(c, 0.5, 0.42, 30, accent, lit);
    onFace(body, 'v', len => {
      [-27, -13].forEach((y, i) => {
        rect(4, y, len - 8, 9, accent, 0.2 + 0.35 * wave(1.6, i * 2), strong(lit), 0.6);
        line(6, y - 1.6, len - 6, y - 1.6, accent, strong(lit), 1);
      });
    });
    onFace(body, 'u', len => {
      dot(len * 0.35, -23, 1.6, accent, strong(lit));
      dot(len * 0.65, -23, 1.6, accent, strong(lit));
      rect(len * 0.25, -14, len * 0.5, 2.5, accent, 0.15, strong(lit) * 0.7, 0.5);
      rect(len * 0.25, -14, len * 0.5 * (0.5 + 0.5 * wave(0.7)), 2.5, accent, 0.6, 0, 0.5);
    });
    const [vx, vy] = pt(vent, 0, 0, 36);
    steam(vx, vy, accent, lit, { count: 2, rise: 16 });
  }

  // Bread → a two-shelf rack of loaves, one still steaming.
  function drawBread(sx, sy, accent, lit) {
    const c = [sx, sy];
    const a = 0.5, b = 0.3;
    const post = (u, v) => {
      const [x1, y1] = pt(c, u, v, 0);
      const [x2, y2] = pt(c, u, v, 24);
      line(x1, y1, x2, y2, accent, strong(lit), 1.2);
    };
    post(-a, -b);
    post(a, -b);
    for (const z of [0, 14]) {
      block(c, a, b, 3, accent, lit, { lift: z });
      for (const u of [-0.3, 0, 0.3]) {
        const g = pt(c, u, 0, z + 3);
        gable(g, 0.11, 0.22, 3, 4, accent, lit, { axis: 'v', fillAlpha: 1.3 });
        for (const v of [-0.11, 0, 0.11]) {
          const [x1, y1] = pt(g, -0.05, v - 0.04, 6);
          const [x2, y2] = pt(g, 0.05, v + 0.04, 6);
          line(x1, y1, x2, y2, accent, strong(lit) * 0.8, 0.6);
        }
      }
    }
    post(-a, b);
    post(a, b);
    const [hx, hy] = pt(c, 0, 0, 24);
    steam(hx, hy, accent, lit, { count: 2, rise: 10, spread: 3 });
  }

  // Recipe → a recipe card on a stand, the current step highlighted.
  function drawRecipe(sx, sy, accent, lit) {
    const c = [sx, sy];
    block(c, 0.4, 0.3, 4, accent, lit);
    const card = block(pt(c, 0, -0.05), 0.36, 0.03, 24, accent, lit, { lift: 4, fillAlpha: 1.3 });
    const step = Math.floor(animT * 0.6) % 4;
    onFace(card, 'v', len => {
      text('RECIPE', len / 2, -18.5, accent, strong(lit), lit, 'bold 3.5px sans-serif');
      for (let i = 0; i < 4; i++) {
        const y = -14 + i * 3.5;
        const alpha = i === step ? 0.5 + 0.5 * wave(4) : strong(lit) * 0.7;
        dot(2.5, y, 0.7, accent, alpha);
        line(4.5, y, len - 2 - (i % 2) * 3, y, accent, alpha, 0.6);
      }
    });
    // A wooden spoon leaning on the card.
    const [x1, y1] = pt(c, 0.3, 0.2, 4);
    const [x2, y2] = pt(c, 0.38, -0.02, 24);
    line(x1, y1, x2, y2, accent, strong(lit), 1);
    ctx.save();
    ctx.beginPath();
    ctx.ellipse(x2, y2 - 1.5, 1.6, 2.6, 0.3, 0, Math.PI * 2);
    ctx.fillStyle = rgba(accent, lit ? 0.6 : 0.4);
    ctx.fill();
    ctx.restore();
  }

  // Invoice → an invoice on a stand: line items, a total, a DUE stamp
  // thumping on and fading.
  function drawInvoice(sx, sy, accent, lit) {
    const c = [sx, sy];
    block(c, 0.38, 0.26, 3, accent, lit);
    const sheet = block(pt(c, 0, -0.04), 0.34, 0.03, 30, accent, lit, { lift: 3, fillAlpha: 1.3 });
    onFace(sheet, 'v', len => {
      text('INVOICE', len / 2, -25, accent, strong(lit), lit, 'bold 3.2px sans-serif');
      for (let i = 0; i < 4; i++) {
        const y = -20 + i * 3.2;
        line(2, y, len * 0.55, y, accent, strong(lit) * 0.6, 0.5);
        line(len * 0.7, y, len - 2, y, accent, strong(lit) * 0.8, 0.5);
      }
      line(2, -6.5, len - 2, -6.5, accent, strong(lit), 0.6);
      line(len * 0.6, -4, len - 2, -4, accent, strong(lit), 1.2);
      const t = (animT * 0.4) % 1;
      if (t < 0.7) {
        ctx.save();
        ctx.translate(len * 0.35, -9);
        ctx.rotate(-0.35);
        ctx.scale(1 + Math.max(0, 0.1 - t) * 4, 1 + Math.max(0, 0.1 - t) * 4);
        const alpha = (lit ? 1 : 0.75) * (1 - t / 0.7);
        rect(-5, -3, 10, 4.5, ACCENT.alert, 0, alpha, 0.6);
        text('DUE', 0, 0.6, ACCENT.alert, alpha, lit, 'bold 3.5px sans-serif');
        ctx.restore();
      }
    });
  }

  // Messenger → a phone in its dock, messages coming in, and a speech
  // bubble over it typing.
  function drawMessenger(sx, sy, accent, lit) {
    const c = [sx, sy];
    block(c, 0.3, 0.22, 3, accent, lit);
    const phone = block(c, 0.2, 0.04, 28, accent, lit, { lift: 3, fillAlpha: 1.4 });
    const fresh = wave(1.2);
    onFace(phone, 'v', len => {
      rect(1.2, -26, len - 2.4, 22, accent, 0.12, strong(lit) * 0.6, 0.4);
      const rows = [[1.8, -23.5, 0.6], [len * 0.35, -19, 0.6], [1.8, -14.5, 0.5]];
      for (const [x, y, w] of rows) rect(x, y, (len - 3.6) * w, 3, accent, lit ? 0.5 : 0.35, 0, 0.4);
      rect(len * 0.35, -10, (len - 3.6) * 0.6 * fresh, 3, accent, lit ? 0.8 : 0.55, 0, 0.4);
      dot(len / 2, -2, 0.8, accent, strong(lit));
    });
    // Round speech bubble above the phone, bobbing.
    const bx = sx + 4, by = sy - 46 + 1.5 * Math.sin(animT * 1.8);
    ctx.save();
    ctx.beginPath();
    ctx.ellipse(bx, by, 10, 6, 0, 0, Math.PI * 2);
    ctx.moveTo(bx - 5, by + 4.5);
    ctx.lineTo(bx - 8, by + 9);
    ctx.lineTo(bx - 1, by + 5.8);
    ctx.fillStyle = rgba(accent, lit ? 0.25 : 0.15);
    ctx.fill();
    ctx.strokeStyle = rgba(accent, lit ? 0.95 : 0.65);
    ctx.lineWidth = 0.8;
    if (lit) { ctx.shadowColor = accent; ctx.shadowBlur = 5; }
    ctx.stroke();
    ctx.restore();
    for (let i = 0; i < 3; i++) dot(bx - 4 + i * 4, by, 1.1, accent, 0.3 + 0.7 * wave(6, -i * 0.9));
  }

  // Clock → a station clock on a post, its hands going round.
  function drawClock(sx, sy, accent, lit) {
    const c = [sx, sy];
    block(c, 0.2, 0.2, 3, accent, lit);
    const [px, py] = pt(c, 0, 0, 3);
    line(px, py, px, py - 13, accent, strong(lit), 1.6);
    const housing = block(c, 0.36, 0.05, 22, accent, lit, { lift: 16 });
    onFace(housing, 'v', len => {
      const cx = len / 2, cy = -11, r = 6.2;
      ctx.save();
      ctx.beginPath();
      ctx.arc(cx, cy, r, 0, Math.PI * 2);
      ctx.fillStyle = rgba(accent, lit ? 0.3 : 0.18);
      ctx.fill();
      ctx.strokeStyle = rgba(faceInk(accent), strong(lit));
      ctx.lineWidth = 0.7;
      ctx.stroke();
      ctx.restore();
      for (let i = 0; i < 12; i++) {
        const t = (i / 12) * Math.PI * 2;
        const k = i % 3 ? 0.85 : 0.75;
        line(cx + Math.sin(t) * r * k, cy - Math.cos(t) * r * k,
          cx + Math.sin(t) * r * 0.95, cy - Math.cos(t) * r * 0.95, accent, strong(lit) * 0.8, 0.4);
      }
      const minute = animT * 0.8, hour = minute / 12;
      line(cx, cy, cx + Math.sin(hour) * r * 0.5, cy - Math.cos(hour) * r * 0.5, accent, lit ? 1 : 0.8, 0.9);
      line(cx, cy, cx + Math.sin(minute) * r * 0.8, cy - Math.cos(minute) * r * 0.8, accent, lit ? 1 : 0.8, 0.6);
      dot(cx, cy, 0.7, accent, 1);
    });
  }

  // Weather → a sun turning its rays behind a drifting rain cloud.
  function drawWeather(sx, sy, accent, lit) {
    const c = [sx, sy];
    block(c, 0.4, 0.4, 3, accent, lit);
    const [gx, gy] = pt(c, 0, 0, 3);
    // Sun.
    const sunX = gx + 7, sunY = gy - 32;
    ctx.save();
    ctx.beginPath();
    ctx.arc(sunX, sunY, 5, 0, Math.PI * 2);
    ctx.fillStyle = rgba(accent, lit ? 0.7 : 0.45);
    if (lit) { ctx.shadowColor = accent; ctx.shadowBlur = 6; }
    ctx.fill();
    ctx.restore();
    for (let i = 0; i < 8; i++) {
      const t = animT * 0.4 + (i / 8) * Math.PI * 2;
      line(sunX + Math.cos(t) * 7, sunY + Math.sin(t) * 7,
        sunX + Math.cos(t) * 9.5, sunY + Math.sin(t) * 9.5, accent, strong(lit), 0.9);
    }
    // Cloud, drifting side to side in front of the sun.
    const cx = gx - 3 + 3 * Math.sin(animT * 0.6), cy = gy - 24;
    ctx.save();
    ctx.beginPath();
    ctx.arc(cx - 6, cy + 1, 4, Math.PI * 0.5, Math.PI * 1.5);
    ctx.arc(cx - 1, cy - 3, 5, Math.PI, Math.PI * 1.85);
    ctx.arc(cx + 5, cy, 4, Math.PI * 1.3, Math.PI * 0.5);
    ctx.closePath();
    ctx.fillStyle = rgba(accent, lit ? 0.35 : 0.22);
    ctx.fill();
    ctx.strokeStyle = rgba(accent, lit ? 0.95 : 0.7);
    ctx.lineWidth = 0.9;
    ctx.stroke();
    ctx.restore();
    // Rain falling from the cloud to the ground.
    for (let i = 0; i < 4; i++) {
      const t = (animT * 0.9 + i * 0.27) % 1;
      const x = cx - 6 + i * 4 - t * 1.5;
      const y = cy + 6 + t * 16;
      line(x, y, x - 0.8, y + 2.5, accent, (lit ? 0.85 : 0.6) * (1 - t * 0.6), 0.8);
    }
  }

  // Sheets → a folder of spreadsheets, the top sheet rising as it syncs.
  function drawSheets(sx, sy, accent, lit) {
    const c = [sx, sy];
    const back = pt(c, 0, -0.1);
    block(back, 0.45, 0.02, 20, accent, lit);
    block(pt(back, -0.24, 0), 0.15, 0.02, 3, accent, lit, { lift: 20 });
    const rise = 3 * wave(1.1);
    const sheet = block(pt(c, 0, -0.04), 0.38, 0.015, 18 + rise, accent, lit, { lift: 3, fillAlpha: 1.5 });
    const cell = Math.floor(animT * 1.5) % 4;
    onFace(sheet, 'v', len => {
      const top = -(18 + rise);
      const w = (len - 3) / 4;
      for (let i = 0; i < 4; i++) {
        rect(1.5 + i * w, top + 1.5, w, 2.6, accent, i === cell ? 0.4 + 0.5 * wave(5) : 0.08, strong(lit) * 0.6, 0.35);
        rect(1.5 + i * w, top + 4.1, w, 2.6, accent, 0.05, strong(lit) * 0.6, 0.35);
      }
    });
    const front = block(pt(c, 0, 0.04), 0.45, 0.02, 15, accent, lit, { fillAlpha: 1.2 });
    onFace(front, 'v', len => {
      text('SHEETS', len / 2, -6, accent, strong(lit), lit, 'bold 3.5px sans-serif');
    });
  }

  // Sacks → flour sacks on a pallet, a puff of flour now and then.
  function drawSacks(sx, sy, accent, lit) {
    const c = [sx, sy];
    block(c, 0.5, 0.4, 3, accent, lit);
    let front;
    for (const [u, v] of [[-0.22, -0.18], [0.22, -0.18], [0, 0.16]]) {
      const g = pt(c, u, v);
      const top = cylinder(g, 0.2, 14, accent, lit, { lift: 3 });
      const neck = cylinder(g, 0.07, 3, accent, lit, { lift: 17, fillAlpha: 1.3 });
      dot(neck.x, neck.y - 0.5, 1, accent, strong(lit));
      front = top;
    }
    text('FLOUR', front.x, front.y + 9, accent, strong(lit), lit, 'bold 3.2px sans-serif');
    const t = (animT * 0.35) % 1;
    if (t < 0.4) {
      for (let i = 0; i < 4; i++) {
        const k = t / 0.4;
        dot(front.x - 3 + i * 2 + Math.sin(i * 3) * k * 3, front.y - 4 - k * (6 + i * 2), 0.9,
          accent, (lit ? 0.8 : 0.55) * (1 - k));
      }
    }
  }

  // Label → a jar with an allergen warning on its label, blinking.
  function drawLabel(sx, sy, accent, lit) {
    const c = [sx, sy];
    const jar = cylinder(c, 0.25, 20, accent, lit);
    cylinder(c, 0.27, 3, accent, lit, { lift: 20, fillAlpha: 1.4 });
    const x = jar.x, y = jar.y + jar.ry + 11;
    rect(x - 6, y - 6, 12, 9, accent, 0.15, strong(lit), 0.6);
    const alpha = 0.4 + 0.6 * wave(4);
    ctx.save();
    ctx.beginPath();
    ctx.moveTo(x, y - 5);
    ctx.lineTo(x + 3.5, y + 1.5);
    ctx.lineTo(x - 3.5, y + 1.5);
    ctx.closePath();
    ctx.strokeStyle = rgba(ACCENT.alert, alpha);
    ctx.lineWidth = 0.8;
    if (lit) { ctx.shadowColor = ACCENT.alert; ctx.shadowBlur = 4; }
    ctx.stroke();
    ctx.restore();
    line(x, y - 2.8, x, y - 0.6, ACCENT.alert, alpha, 0.8);
    dot(x, y + 0.5, 0.45, ACCENT.alert, alpha);
  }

  // Cup → a café cup on its saucer, steaming.
  function drawCup(sx, sy, accent, lit) {
    const c = [sx, sy];
    isoDisc(sx, sy - 1, 13, accent, lit, { lineWidth: 0.9 });
    const cup = cylinder(c, 0.25, 11, accent, lit, { lift: 2 });
    ctx.save();
    ctx.beginPath();
    ctx.ellipse(cup.x, cup.y, cup.rx * 0.8, cup.ry * 0.8, 0, 0, Math.PI * 2);
    ctx.fillStyle = rgba(accent, lit ? 0.6 : 0.4);
    ctx.fill();
    ctx.beginPath();
    ctx.arc(cup.x + cup.rx + 0.5, cup.y + 5.5, 3, -Math.PI / 2, Math.PI / 2);
    ctx.strokeStyle = rgba(accent, strong(lit));
    ctx.lineWidth = 1.2;
    ctx.stroke();
    ctx.restore();
    steam(cup.x, cup.y - 2, accent, lit, { count: 3, rise: 14, spread: 3 });
  }

  add('bakery-oven', drawOven, { bh: 30, scale: 1, extraTop: 22, label: 'Oven' });
  add('bakery-bread', drawBread, { bh: 24, scale: 1, extraTop: 10, label: 'Bread rack' });
  add('bakery-recipe', drawRecipe, { bh: 28, scale: 0.6, label: 'Recipe card' });
  add('bakery-invoice', drawInvoice, { bh: 33, scale: 0.5, label: 'Invoice' });
  add('bakery-messenger', drawMessenger, { bh: 31, scale: 0.45, extraTop: 22, label: 'Messenger' });
  add('bakery-clock', drawClock, { bh: 38, scale: 0.45, label: 'Station clock' });
  add('bakery-weather', drawWeather, { bh: 3, scale: 0.8, extraTop: 40, label: 'Weather' });
  add('bakery-sheets', drawSheets, { bh: 24, scale: 0.6, label: 'Spreadsheets' });
  add('bakery-sacks', drawSacks, { bh: 21, scale: 1, extraTop: 6, label: 'Flour sacks' });
  add('bakery-label', drawLabel, { bh: 23, scale: 0.55, label: 'Allergen label' });
  add('bakery-cup', drawCup, { bh: 13, scale: 0.6, extraTop: 16, label: 'Café cup' });
})();
