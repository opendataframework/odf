// Buildings: a tower, a pitched-roof block, a bank, a storefront, a stockroom
// and a factory.
(() => {
  const { pt, outline, line, rect, dot, block, gable, wedge, cylinder, onFace, wave, strong } = ODF.iconKit;
  const add = (key, draw, meta) => ODF.registerIcon(key, draw, { group: 'Buildings', ...meta });

  // Windows in rows and columns across a wall of length `len` (see onFace),
  // from `y0` up to `y1` px above its bottom edge. `lights(i)` gives window
  // i's fill alpha.
  function windows(len, rows, cols, y0, y1, accent, lit, lights) {
    const gx = len / cols, gy = (y1 - y0) / rows;
    for (let r = 0, i = 0; r < rows; r++) {
      for (let k = 0; k < cols; k++, i++) {
        rect(k * gx + gx * 0.25, -y0 - (r + 1) * gy + gy * 0.3, gx * 0.5, gy * 0.45,
          accent, lights(i), lit ? 0.6 : 0.35, 0.5);
      }
    }
  }

  // Building A → a setback tower, each tier narrower than the one under it,
  // with a rooftop antenna broadcasting "((•))" signal arcs that loop with
  // animT.
  function drawBuildingA(sx, sy, accent, lit) {
    const c = [sx, sy];
    const tiers = [{ a: 0.55, b: 0.55, h: 26 }, { a: 0.42, b: 0.42, h: 16 }, { a: 0.28, b: 0.28, h: 12 }];
    let z = 0;
    for (const { a, b, h } of tiers) {
      const blk = block(c, a, b, h, accent, lit, { lift: z });
      const rows = Math.round(h / 7);
      for (const side of ['u', 'v']) {
        onFace(blk, side, len => windows(len, rows, Math.max(2, Math.round(len / 8)), 2, h - 1,
          accent, lit, () => (lit ? 0.3 : 0.18)));
      }
      z += h;
    }

    // Antenna mast from the roof center.
    const topY = sy - z, tipY = topY - 14;
    line(sx, topY, sx, tipY, accent, lit ? 0.9 : 0.55, 1);

    // Signal arcs — left and right of the tip, expanding and fading out.
    const spread = 0.8;
    ctx.save();
    ctx.lineWidth = 1.1;
    ctx.lineCap = 'round';
    if (lit) { ctx.shadowColor = accent; ctx.shadowBlur = 4; }
    for (let i = 0; i < 3; i++) {
      const phase = (animT * 0.8 + i / 3) % 1;
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
    const pulse = (Math.sin(animT * 4) + 1) / 2;
    ctx.save();
    ctx.beginPath();
    ctx.arc(sx, tipY, 1.8, 0, Math.PI * 2);
    ctx.fillStyle = rgba(accent, 0.95);
    ctx.shadowColor = accent;
    ctx.shadowBlur = 3 + 4 * pulse;
    ctx.fill();
    ctx.restore();
  }

  // Building B → a long two-storey block under a pitched roof, its windows
  // lighting up one after another as if people were coming in, with a
  // chimney at the back.
  function drawBuildingB(sx, sy, accent, lit) {
    const c = [sx, sy];
    const a = 0.82, b = 0.5, h = 18, ridge = 11;
    block(pt(c, -0.45, -0.2), 0.07, 0.07, h + ridge + 5, accent, lit, { fillAlpha: 1.5 });
    const house = gable(c, a, b, h, ridge, accent, lit);
    const on = Math.floor(animT * 1.2) % 12;
    onFace(house, 'v', len => windows(len, 2, 6, 1, h - 1, accent, lit,
      i => (i <= on ? 0.55 : 0.12) + (lit ? 0.1 : 0)));
    onFace(house, 'u', len => {
      rect(len / 2 - 3, -11, 6, 11, accent, 0.2, strong(lit), 0.6);
    });
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
    gable(top, a, b, 0, rise, accent, lit, { axis: 'v', lift: bh });
    const [ox, oy] = pt(top, 0, b, bh + rise * 0.4);
    dot(ox, oy, 1.4, faceInk(accent), strong(lit));
    // Packets leave the door and head off towards the front-left.
    for (let i = 0; i < 3; i++) {
      const t = (animT * 0.5 + i / 3) % 1;
      const fade = Math.min(1, t * 6, (1 - t) * 3);
      block(pt(c, 0, b + 0.15 + t * 0.9), 0.07, 0.07, 4, accent, lit, {
        lift: 3 + 4 * Math.sin(t * Math.PI), fillAlpha: 3 * fade, strokeAlpha: fade,
      });
    }
  }

  // Storefront → a low shop behind a taller false front: shop window, door
  // and a striped awning.
  function drawStorefront(sx, sy, accent, lit) {
    const c = [sx, sy];
    const shop = block(pt(c, 0, -0.12), 0.8, 0.6, 18, accent, lit);
    const body = block(pt(c, 0, 0.6), 0.8, 0.12, 30, accent, lit);
    const glow = 0.2 + 0.2 * wave(2);
    onFace(body, 'v', len => {
      rect(3, -13, 17, 9, accent, glow + (lit ? 0.1 : 0), lit ? 0.9 : 0.6);
      line(11.5, -13, 11.5, -4, accent, lit ? 0.7 : 0.45);
      rect(23, -13, 6, 13, accent, 0.12, lit ? 0.9 : 0.6);
      dot(27.5, -6.5, 0.8, accent, 0.9);
      rect(4, -27, len - 8, 5, accent, 0.15, lit ? 0.7 : 0.45, 0.5);
    });
    onFace(shop, 'u', len => {
      rect(len * 0.3, -14, len * 0.4, 7, accent, glow * 0.7, lit ? 0.7 : 0.45);
    });
    const { a, b } = body, front = pt(c, 0, 0.6), stripes = 6;
    for (let i = 0; i < stripes; i++) {
      const u0 = -a + (2 * a * i) / stripes, u1 = -a + (2 * a * (i + 1)) / stripes;
      paintFace(outline([pt(front, u0, b, 19), pt(front, u1, b, 19), pt(front, u1, b + 0.2, 14), pt(front, u0, b + 0.2, 14)]),
        'top', accent, lit, i % 2 ? 1 : 2.5);
    }
  }

  // Stockroom → stockroom: roll-up door that slowly opens onto crates, plus a
  // stack of crates outside.
  function drawStockroom(sx, sy, accent, lit) {
    const c = [sx, sy];
    // Lean-to roof, high at the back and falling towards the right wall.
    const body = wedge(c, 0.7, 0.7, 32, 22, accent, lit);
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
    onFace(body, 'u', len => rect(len * 0.3, -18, len * 0.4, 5, accent, 0.25, lit ? 0.7 : 0.45));
    const crate = (u, v, lift) => {
      const blk = block(pt(c, u, v), 0.12, 0.12, 8, accent, lit, { lift, fillAlpha: 1.8 });
      onFace(blk, 'v', len => line(0, -4, len, -4, accent, lit ? 0.7 : 0.45, 0.6));
    };
    crate(0.86, -0.1, 0);
    crate(0.86, 0.25, 0);
    crate(0.86, 0.25, 8);
  }

  // Factory → a factory with a sawtooth roof, a round smokestack and a silo.
  function drawFactory(sx, sy, accent, lit) {
    const c = [sx, sy];
    const a = 0.75, b = 0.5, bh = 16, teeth = 3, rise = 8;
    // Stack and silo first, so the hall sits in front of their bases.
    const stack = cylinder(pt(c, -0.45, -0.3), 0.1, bh + rise + 14, accent, lit, { fillAlpha: 1.5 });
    for (let i = 0; i < 3; i++) {
      const phase = (animT * 0.35 + i / 3) % 1;
      dot(stack.x + 3 * phase + 1.5 * Math.sin(animT * 2 + i), stack.y - 3 - phase * 14,
        1.6 + phase * 3, accent, (1 - phase) * (lit ? 0.45 : 0.3));
    }
    cylinder(pt(c, 0.45, -0.72), 0.24, bh + 14, accent, lit);
    const hall = block(c, a, b, bh, accent, lit);
    onFace(hall, 'v', len => {
      for (let i = 0; i < 4; i++) rect(3 + i * (len - 4) / 4, -11, (len - 4) / 4 - 3, 6, accent, 0.2, lit ? 0.8 : 0.5, 0.5);
    });
    onFace(hall, 'u', len => rect(len / 2 - 5, -10, 10, 10, accent, 0.15, lit ? 0.9 : 0.6));
    // Each tooth slopes up along U and ends in a glazed wall facing +U.
    for (let i = 0; i < teeth; i++) {
      const u0 = -a + (2 * a * i) / teeth, u1 = -a + (2 * a * (i + 1)) / teeth;
      paintFace(outline([pt(c, u0, -b, bh), pt(c, u1, -b, bh + rise), pt(c, u1, b, bh + rise), pt(c, u0, b, bh)]),
        'top', accent, lit);
      paintFace(outline([pt(c, u1, -b, bh), pt(c, u1, -b, bh + rise), pt(c, u1, b, bh + rise), pt(c, u1, b, bh)]),
        'right', accent, lit, 1 + 1.5 * wave(1.5, i));
      paintFace(outline([pt(c, u0, b, bh), pt(c, u1, b, bh), pt(c, u1, b, bh + rise)]), 'left', accent, lit);
    }
  }

  add('building-a', drawBuildingA, { bh: 54, scale: 0.55, extraTop: 22, label: 'Building A' });
  add('building-b', drawBuildingB, { bh: 29, scale: 0.9, extraTop: 8, label: 'Building B' });
  add('bank', drawBank, { bh: 28, scale: 1, label: 'Bank' });
  add('storefront', drawStorefront, { bh: 30, scale: 0.8, label: 'Storefront' });
  add('stockroom', drawStockroom, { bh: 32, scale: 1, label: 'Stockroom' });
  add('factory', drawFactory, { bh: 38, scale: 1, extraTop: 14, label: 'Factory' });
})();
