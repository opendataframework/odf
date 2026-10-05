// Buildings: office blocks, a bank, a storefront, a stockroom and a factory.
(() => {
  const { pt, poly, line, rect, dot, block, onFace, wave, strong } = ODF.iconKit;
  const add = (key, draw, meta) => ODF.registerIcon(key, draw, { group: 'Buildings', ...meta });

  // Building A / Building B → plain iso blocks with a few floor bands (each
  // interpolated between its wall's own corners so it follows the wall's iso
  // shear) and a rooftop antenna broadcasting "((•))" signal arcs that loop
  // with animT. `seed` offsets the wave phase so neighboring buildings don't
  // pulse in lockstep.
  function drawBuilding(sx, sy, accent, lit, { bh, scale, floors, seed }) {
    const { w2, h2, topY } = drawBox(sx, sy, bh, accent, lit, scale);

    // Floor bands on both visible walls.
    const walls = [
      [[sx - w2, sy - bh], [sx - w2, sy], [sx, sy + h2 - bh], [sx, sy + h2]],
      [[sx + w2, sy - bh], [sx + w2, sy], [sx, sy + h2 - bh], [sx, sy + h2]],
    ];
    ctx.save();
    ctx.strokeStyle = rgba(accent, lit ? 0.45 : 0.25);
    ctx.lineWidth = 0.6;
    for (const [outerTop, outerBot, innerTop, innerBot] of walls) {
      for (let f = 1; f <= floors; f++) {
        const t = f / (floors + 1);
        const a = lerp(outerTop, outerBot, t), b = lerp(innerTop, innerBot, t);
        ctx.beginPath();
        ctx.moveTo(a[0], a[1]);
        ctx.lineTo(b[0], b[1]);
        ctx.stroke();
      }
    }
    ctx.restore();

    // Antenna mast from the roof-diamond center.
    const tipY = topY - 14;
    ctx.save();
    ctx.strokeStyle = rgba(accent, lit ? 0.9 : 0.55);
    ctx.lineWidth = 1;
    ctx.lineCap = 'round';
    ctx.beginPath();
    ctx.moveTo(sx, topY);
    ctx.lineTo(sx, tipY);
    ctx.stroke();
    ctx.restore();

    // Signal arcs — left and right of the tip, expanding and fading out.
    const spread = 0.8;
    ctx.save();
    ctx.lineWidth = 1.1;
    ctx.lineCap = 'round';
    if (lit) { ctx.shadowColor = accent; ctx.shadowBlur = 4; }
    for (let i = 0; i < 3; i++) {
      const phase = (animT * 0.8 + i / 3 + seed) % 1;
      const r = 4 + phase * 10;
      ctx.strokeStyle = rgba(accent, (1 - phase) * (lit ? 0.9 : 0.45));
      ctx.beginPath();
      ctx.arc(sx, tipY, r, -spread, spread);
      ctx.stroke();
      ctx.beginPath();
      ctx.arc(sx, tipY, r, Math.PI - spread, Math.PI + spread);
      ctx.stroke();
    }
    ctx.restore();

    // Pulsing tip.
    const pulse = (Math.sin(animT * 4 + seed * Math.PI * 2) + 1) / 2;
    ctx.save();
    ctx.beginPath();
    ctx.arc(sx, tipY, 1.8, 0, Math.PI * 2);
    ctx.fillStyle = rgba(accent, 0.95);
    ctx.shadowColor = accent;
    ctx.shadowBlur = 3 + 4 * pulse;
    ctx.fill();
    ctx.restore();
  }

  function drawBuildingA(sx, sy, accent, lit) {
    drawBuilding(sx, sy, accent, lit, { bh: 48, scale: 0.55, floors: 4, seed: 0 });
  }

  function drawBuildingB(sx, sy, accent, lit) {
    drawBuilding(sx, sy, accent, lit, { bh: 24, scale: 0.9, floors: 2, seed: 0.5 });
  }

  // Bank → a classical bank on its steps, with data
  // packets streaming out of the door.
  function drawBank(sx, sy, accent, lit) {
    const c = [sx, sy];
    block(c, 0.8, 0.62, 3, accent, lit);
    const a = 0.66, b = 0.48, bh = 17, rise = 8;
    const body = block(c, a, b, bh, accent, lit, { lift: 3 });
    const top = [sx, sy - 3];
    onFace(body, 'v', len => {
      const columns = 5;
      for (let i = 0; i < columns; i++) {
        const x = 2 + i * (len - 6) / (columns - 1);
        rect(x, -bh + 3, 2, bh - 4, accent, lit ? 0.3 : 0.2, strong(lit), 0.5);
      }
      rect(len / 2 - 3, -9, 6, 9, accent, 0.25 + 0.3 * wave(2.5), strong(lit));
    });
    onFace(body, 'u', len => {
      for (let i = 0; i < 2; i++) rect(len * (0.2 + i * 0.4), -12, len * 0.2, 6, accent, 0.15, lit ? 0.7 : 0.45, 0.5);
    });
    // Gable roof: ridge runs front to back, the pediment faces the V wall.
    poly([pt(top, -a, -b, bh), pt(top, 0, -b, bh + rise), pt(top, 0, b, bh + rise), pt(top, -a, b, bh)],
      accent, 0.08, lit ? 0.6 : 0.4);
    poly([pt(top, 0, -b, bh + rise), pt(top, a, -b, bh), pt(top, a, b, bh), pt(top, 0, b, bh + rise)],
      accent, lit ? 0.16 : 0.1, lit ? 1 : 0.6, { lw: lit ? 1.2 : 1, blur: lit ? 8 : 0 });
    poly([pt(top, -a, b, bh), pt(top, a, b, bh), pt(top, 0, b, bh + rise)],
      accent, lit ? 0.22 : 0.14, strong(lit));
    const [ox, oy] = pt(top, 0, b, bh + rise * 0.4);
    dot(ox, oy, 1.4, accent, strong(lit));
    // Packets leave the door and head off towards the front-left.
    for (let i = 0; i < 3; i++) {
      const t = (animT * 0.5 + i / 3) % 1;
      const fade = Math.min(1, t * 6, (1 - t) * 3);
      block(pt(c, 0, b + 0.15 + t * 0.9), 0.07, 0.07, 4, accent, lit, {
        lift: 3 + 4 * Math.sin(t * Math.PI), fillAlpha: 3 * fade, strokeAlpha: fade,
      });
    }
  }

  // Storefront → storefront: shop window, door and a striped awning.
  function drawStorefront(sx, sy, accent, lit) {
    const c = [sx, sy];
    const body = block(c, 0.8, 0.8, 24, accent, lit);
    const glow = 0.2 + 0.2 * wave(2);
    onFace(body, 'v', () => {
      rect(3, -13, 17, 9, accent, glow + (lit ? 0.1 : 0), lit ? 0.9 : 0.6);
      line(11.5, -13, 11.5, -4, accent, lit ? 0.7 : 0.45);
      rect(23, -13, 6, 13, accent, 0.12, lit ? 0.9 : 0.6);
      ctx.beginPath();
      ctx.arc(27.5, -6.5, 0.8, 0, Math.PI * 2);
      ctx.fillStyle = rgba(accent, 0.9);
      ctx.fill();
    });
    onFace(body, 'u', len => {
      rect(len * 0.3, -14, len * 0.4, 7, accent, glow * 0.7, lit ? 0.7 : 0.45);
    });
    const { a, b } = body, stripes = 6;
    for (let i = 0; i < stripes; i++) {
      const u0 = -a + (2 * a * i) / stripes, u1 = -a + (2 * a * (i + 1)) / stripes;
      poly([pt(c, u0, b, 19), pt(c, u1, b, 19), pt(c, u1, b + 0.2, 14), pt(c, u0, b + 0.2, 14)],
        accent, i % 2 ? 0.12 : (lit ? 0.6 : 0.45), lit ? 0.9 : 0.6);
    }
  }

  // Stockroom → stockroom: roll-up door that slowly opens onto crates, plus a
  // stack of crates outside.
  function drawStockroom(sx, sy, accent, lit) {
    const c = [sx, sy];
    const body = block(c, 0.7, 0.7, 26, accent, lit);
    onFace(body, 'v', len => {
      const x = 5, w = len - 10, h = 17;
      const open = 0.55 * wave(0.8);
      rect(x, -h, w, h, accent, 0.3, lit ? 0.9 : 0.6);
      for (let i = 0; i < 3; i++) {
        rect(x + 2 + i * 5.5, -4.5, 4.5, 4.5, accent, 0.25, lit ? 0.8 : 0.5, 0.5);
      }
      const doorH = h * (1 - open);
      rect(x, -h, w, doorH, accent, lit ? 0.22 : 0.15, lit ? 0.9 : 0.6);
      for (let y = -h + 2.5; y < -h + doorH; y += 2.5) {
        line(x + 0.5, y, x + w - 0.5, y, accent, lit ? 0.5 : 0.3, 0.5);
      }
    });
    onFace(body, 'u', len => rect(len * 0.3, -21, len * 0.4, 5, accent, 0.25, lit ? 0.7 : 0.45));
    const crate = (u, v, lift) => {
      const blk = block(pt(c, u, v), 0.12, 0.12, 8, accent, lit, { lift, fillAlpha: 1.8 });
      onFace(blk, 'v', len => line(0, -4, len, -4, accent, lit ? 0.7 : 0.45, 0.6));
    };
    crate(0.86, -0.1, 0);
    crate(0.86, 0.25, 0);
    crate(0.86, 0.25, 8);
  }

  // Factory → a factory with a sawtooth roof and a smoking chimney.
  function drawFactory(sx, sy, accent, lit) {
    const c = [sx, sy];
    const a = 0.75, b = 0.5, bh = 16, teeth = 3, rise = 8;
    // Chimney first, so the hall sits in front of its base.
    const chimney = block(pt(c, -0.45, -0.3), 0.08, 0.08, bh + rise + 12, accent, lit, { fillAlpha: 1.5 });
    const top = pt(chimney.g, 0, 0, chimney.bh);
    for (let i = 0; i < 3; i++) {
      const phase = (animT * 0.35 + i / 3) % 1;
      dot(top[0] + 3 * phase + 1.5 * Math.sin(animT * 2 + i), top[1] - 3 - phase * 14,
        1.6 + phase * 3, accent, (1 - phase) * (lit ? 0.45 : 0.3));
    }
    const hall = block(c, a, b, bh, accent, lit);
    onFace(hall, 'v', len => {
      for (let i = 0; i < 4; i++) rect(3 + i * (len - 4) / 4, -11, (len - 4) / 4 - 3, 6, accent, 0.2, lit ? 0.8 : 0.5, 0.5);
    });
    onFace(hall, 'u', len => rect(len / 2 - 5, -10, 10, 10, accent, 0.15, lit ? 0.9 : 0.6));
    // Each tooth slopes up along U and ends in a glazed wall facing +U.
    for (let i = 0; i < teeth; i++) {
      const u0 = -a + (2 * a * i) / teeth, u1 = -a + (2 * a * (i + 1)) / teeth;
      poly([pt(c, u0, -b, bh), pt(c, u1, -b, bh + rise), pt(c, u1, b, bh + rise), pt(c, u0, b, bh)],
        accent, lit ? 0.16 : 0.1, lit ? 0.9 : 0.55, { lw: lit ? 1.1 : 0.9 });
      poly([pt(c, u1, -b, bh), pt(c, u1, -b, bh + rise), pt(c, u1, b, bh + rise), pt(c, u1, b, bh)],
        accent, 0.2 + 0.2 * wave(1.5, i), lit ? 0.8 : 0.5);
      poly([pt(c, u0, b, bh), pt(c, u1, b, bh), pt(c, u1, b, bh + rise)],
        accent, 0.08, lit ? 0.65 : 0.4);
    }
  }

  add('building-a', drawBuildingA, { bh: 48, scale: 0.55, extraTop: 22, label: 'Building A' });
  add('building-b', drawBuildingB, { bh: 24, scale: 0.9, extraTop: 22, label: 'Building B' });
  add('bank', drawBank, { bh: 28, scale: 1, label: 'Bank' });
  add('storefront', drawStorefront, { bh: 24, scale: 0.8, label: 'Storefront' });
  add('stockroom', drawStockroom, { bh: 26, scale: 1, label: 'Stockroom' });
  add('factory', drawFactory, { bh: 24, scale: 1, extraTop: 14, label: 'Factory' });
})();
