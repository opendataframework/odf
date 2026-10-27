// Shop: a cash register, a clipboard, a delivery truck, foot traffic, a chat
// kiosk, a mailbox, a closing sign, a filing cabinet, an intake conveyor,
// map pins, a podium and a camera on a tripod.
(() => {
  const { SLOPE, pt, poly, line, rect, dot, block, onFace, wave } = ODF.iconKit;
  const add = (key, draw, meta) => ODF.registerIcon(key, draw, { group: 'Shop', ...meta });

  // Cash register → cash register on a counter, display ticking up, receipt
  // printing out the front.
  function drawRegister(sx, sy, accent, lit) {
    const c = [sx, sy];
    const counter = block(c, 0.55, 0.45, 14, accent, lit);
    onFace(counter, 'v', len => {
      line(3, -10, len - 3, -10, accent, lit ? 0.6 : 0.4);
      line(len / 2 - 3, -7, len / 2 + 3, -7, accent, lit ? 0.8 : 0.5, 1.1);
    });
    const top = [sx, sy - 14];
    const body = block(pt(top, 0.05, 0.05), 0.32, 0.28, 7, accent, lit, { fillAlpha: 1.4 });
    const display = block(pt(top, 0.05, -0.18), 0.3, 0.04, 9, accent, lit, { lift: 7, fillAlpha: 1.6 });
    onFace(display, 'v', len => {
      ctx.font = 'bold 5px monospace';
      ctx.textAlign = 'center';
      ctx.fillStyle = rgba(faceInk(accent), lit ? 1 : 0.8);
      if (lit) { ctx.shadowColor = accent; ctx.shadowBlur = 3; }
      ctx.fillText(`$${10 + (Math.floor(animT * 2) % 90)}`, len / 2, -2.5);
    });
    for (const u of [-0.12, 0.05, 0.22]) {
      for (const v of [0.08, 0.2]) {
        const p = pt(body.g, u, v, 7);
        ctx.fillStyle = rgba(faceInk(accent), lit ? 0.9 : 0.6);
        ctx.fillRect(p[0] - 0.6, p[1] - 0.6, 1.2, 1.2);
      }
    }
    onFace(body, 'v', len => {
      const L = 3 + 9 * ((animT * 0.35) % 1);
      rect(len * 0.35, -7 - L, len * 0.3, L, accent, 0.3, lit ? 0.9 : 0.6, 0.5);
      for (let y = -7 - L + 2; y < -8; y += 2) {
        line(len * 0.4, y, len * 0.6, y, accent, 0.5, 0.4);
      }
    });
  }

  // Clipboard → clipboard checklist on a stand; one row blinks as low stock.
  function drawClipboard(sx, sy, accent, lit) {
    const c = [sx, sy];
    const center = pt(c, 0, -0.05);
    block(c, 0.42, 0.34, 5, accent, lit);
    const board = block(center, 0.36, 0.035, 26, accent, lit, { lift: 5 });
    block(center, 0.1, 0.06, 3, accent, lit, { lift: 31, fillAlpha: 2 });
    onFace(board, 'v', len => {
      for (let i = 0; i < 4; i++) {
        const y = -19 + i * 5;
        const low = i === 2;
        const color = low ? ACCENT.alert : accent;
        const alpha = low ? 0.4 + 0.6 * wave(5) : (lit ? 0.85 : 0.6);
        rect(2, y - 2.5, 2.8, 2.8, color, low ? 0.25 * alpha : 0, alpha, 0.5);
        line(6.5, y - 1, len - 2, y - 1, color, alpha * 0.8, 0.6);
        if (!low) {
          ctx.save();
          ctx.strokeStyle = rgba(faceInk(accent), alpha);
          ctx.lineWidth = 0.6;
          ctx.beginPath();
          ctx.moveTo(2.5, y - 1.3);
          ctx.lineTo(3.3, y - 0.4);
          ctx.lineTo(4.7, y - 2.4);
          ctx.stroke();
          ctx.restore();
        }
      }
    });
  }

  // Delivery truck → delivery truck with spinning wheels and speed lines.
  function drawTruck(sx, sy, accent, lit) {
    const c = [sx, sy];
    for (let i = 0; i < 3; i++) {
      const phase = (animT * 1.5 + i / 3) % 1;
      const [x1, y1] = pt(c, -0.75 - phase * 0.3, -0.15 + i * 0.12, 8 + i * 5);
      const [x2, y2] = pt(c, -0.95 - phase * 0.3, -0.15 + i * 0.12, 8 + i * 5);
      line(x1, y1, x2, y2, accent, (1 - phase) * 0.5);
    }
    const cargo = block(pt(c, -0.2, 0), 0.48, 0.34, 20, accent, lit, { lift: 5 });
    onFace(cargo, 'v', len => {
      const x = len / 2 - 5;
      rect(x, -15, 10, 10, accent, 0.2, lit ? 0.85 : 0.55);
      line(x, -10, x + 10, -10, accent, lit ? 0.7 : 0.45, 0.6);
      line(x + 5, -15, x + 5, -5, accent, lit ? 0.7 : 0.45, 0.6);
    });
    const cab = block(pt(c, 0.5, 0), 0.2, 0.3, 14, accent, lit, { lift: 5 });
    onFace(cab, 'u', len => rect(len * 0.15, -12, len * 0.7, 5, accent, lit ? 0.45 : 0.3, lit ? 0.9 : 0.6));
    onFace(cab, 'v', len => rect(len * 0.3, -12, len * 0.5, 5, accent, lit ? 0.35 : 0.22, lit ? 0.9 : 0.6));
    for (const u of [-0.5, -0.05, 0.52]) {
      const [ox, oy] = pt(c, u, 0.34);
      const spin = -animT * 6;
      ctx.save();
      ctx.transform(1, SLOPE, 0, 1, ox, oy);
      ctx.beginPath();
      ctx.arc(0, -4, 4, 0, Math.PI * 2);
      ctx.fillStyle = rgba(accent, lit ? 0.35 : 0.25);
      ctx.fill();
      ctx.strokeStyle = rgba(accent, lit ? 0.95 : 0.7);
      ctx.lineWidth = 1;
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(-3 * Math.cos(spin), -4 - 3 * Math.sin(spin));
      ctx.lineTo(3 * Math.cos(spin), -4 + 3 * Math.sin(spin));
      ctx.stroke();
      ctx.restore();
    }
  }

  // A little upright person standing on screen point p, legs swinging.
  function person(p, accent, alpha, stride) {
    const [x, y] = p;
    line(x, y - 3.5, x - 1.4 * stride, y, accent, alpha, 1.1);
    line(x, y - 3.5, x + 1.4 * stride, y, accent, alpha, 1.1);
    line(x, y - 3.5, x, y - 7.5, accent, alpha, 1.4);
    dot(x, y - 9.3, 1.7, accent, alpha);
  }

  // Foot traffic → shop front with a lit door and customers walking in.
  function drawFootTraffic(sx, sy, accent, lit) {
    const c = [sx, sy];
    const shop = block(pt(c, -0.4, 0), 0.3, 0.6, 22, accent, lit);
    onFace(shop, 'u', len => {
      rect(len / 2 - 4, -13, 8, 13, accent, 0.25 + 0.25 * wave(2), lit ? 0.9 : 0.6);
      rect(len / 2 - 6, -18, 12, 3, accent, lit ? 0.5 : 0.35, lit ? 0.9 : 0.6, 0.5);
    });
    onFace(shop, 'v', len => rect(len * 0.25, -15, len * 0.5, 8, accent, 0.15, lit ? 0.7 : 0.45));
    // Customers head from the front-right towards the door (u = -0.1).
    const walkers = [0, 1, 2].map(i => {
      const t = (animT * 0.22 + i / 3) % 1;
      return { u: 0.95 - t * 1.05, v: [-0.12, 0.1, -0.02][i], t, i };
    }).sort((p, q) => (p.u + p.v) - (q.u + q.v));
    for (const { u, v, t, i } of walkers) {
      const fade = Math.min(1, t * 5, (1 - t) * 6);
      person(pt(c, u, v), accent, (lit ? 0.95 : 0.7) * fade, Math.sin(animT * 9 + i * 2));
    }
  }

  // Chat kiosk → a chat kiosk with a speech bubble that's typing.
  function drawChatKiosk(sx, sy, accent, lit) {
    const c = [sx, sy];
    block(c, 0.34, 0.34, 4, accent, lit);
    const [px, py] = pt(c, 0, 0, 4);
    line(px, py, px, py - 12, accent, lit ? 0.9 : 0.6, 1.4);
    const screen = block(c, 0.34, 0.05, 16, accent, lit, { lift: 14, fillAlpha: 1.6 });
    onFace(screen, 'v', len => {
      rect(2.5, -13.5, len * 0.55, 3, accent, lit ? 0.5 : 0.35, 0, 0.4);
      rect(len * 0.4 - 2.5, -8.5, len * 0.6, 3, accent, lit ? 0.8 : 0.55, 0, 0.4);
      rect(2.5, -3.5, len * 0.35 * (0.4 + 0.6 * wave(1.3)), 1.5, accent, lit ? 0.5 : 0.35, 0, 0.4);
    });
    // Speech bubble floating over the kiosk.
    const bob = 1.5 * Math.sin(animT * 1.8);
    const bx = sx - 2, by = sy - 52 + bob, w = 20, h = 10;
    ctx.save();
    ctx.beginPath();
    ctx.roundRect(bx, by, w, h, 3);
    ctx.moveTo(bx + 4, by + h);
    ctx.lineTo(bx + 2, by + h + 4);
    ctx.lineTo(bx + 8, by + h);
    ctx.fillStyle = rgba(accent, lit ? 0.25 : 0.15);
    ctx.fill();
    ctx.strokeStyle = rgba(accent, lit ? 0.95 : 0.65);
    ctx.lineWidth = 0.8;
    if (lit) { ctx.shadowColor = accent; ctx.shadowBlur = 5; }
    ctx.stroke();
    ctx.restore();
    for (let i = 0; i < 3; i++) {
      dot(bx + 5 + i * 5, by + h / 2, 1.2, accent, 0.3 + 0.7 * wave(6, -i * 0.9));
    }
  }

  // Mailbox → a mailbox on a post, letters dropping into the slot.
  function drawMailbox(sx, sy, accent, lit) {
    const c = [sx, sy];
    block(c, 0.18, 0.18, 2, accent, lit);
    const [px, py] = pt(c, 0, 0, 2);
    line(px, py, px, py - 12, accent, lit ? 0.9 : 0.6, 1.6);
    const box = block(c, 0.34, 0.2, 11, accent, lit, { lift: 14, fillAlpha: 1.4 });
    onFace(box, 'v', len => {
      rect(len * 0.25, -8, len * 0.5, 1.6, accent, lit ? 0.7 : 0.5, lit ? 0.9 : 0.6, 0.5);
      ctx.font = 'bold 4px monospace';
      ctx.textAlign = 'center';
      ctx.fillStyle = rgba(faceInk(accent), lit ? 0.9 : 0.65);
      ctx.fillText('PO', len / 2, -2);
    });
    // Flag on the side pops up when a letter goes in.
    const phase = (animT * 0.45) % 1;
    const raised = phase > 0.55 && phase < 0.9;
    onFace(box, 'u', len => {
      const fx = len - 3;
      line(fx, -3, fx, raised ? -16 : -8, accent, lit ? 0.9 : 0.65, 1);
      rect(fx, raised ? -16 : -8, 4, 3, ACCENT.alert, lit ? 0.9 : 0.7, 0, 0.4);
    });
    // Letter sliding down into the slot, then gone.
    if (phase < 0.55) {
      const drop = phase / 0.55;
      const slot = pt(box.g, 0, box.b, 8);
      const x = slot[0] - 7, y = slot[1] - 16 + drop * 12, w = 10, h = 6;
      ctx.save();
      ctx.beginPath();
      ctx.rect(x - 2, y - 2, w + 4, slot[1] - y + 1);
      ctx.clip();
      rect(x, y, w, h, accent, lit ? 0.35 : 0.25, lit ? 0.95 : 0.7, 0.6);
      line(x, y, x + w / 2, y + h / 2, accent, lit ? 0.8 : 0.55, 0.5);
      line(x + w, y, x + w / 2, y + h / 2, accent, lit ? 0.8 : 0.55, 0.5);
      ctx.restore();
    }
  }

  // Closing sign → a hanging shop sign that flips OPEN / CLOSED, under a moon.
  function drawClosingSign(sx, sy, accent, lit) {
    const c = [sx, sy];
    block(c, 0.5, 0.12, 2, accent, lit);
    // Everything else lives on one wall-plane, raised 2px off the ground.
    const frame = { g: [sx, sy - 2], a: 0.45, b: 0.05 };
    onFace(frame, 'v', len => {
      const alpha = lit ? 0.9 : 0.6;
      line(0, 0, 0, -30, accent, alpha, 1.3);
      line(len, 0, len, -30, accent, alpha, 1.3);
      line(-1, -28, len + 1, -28, accent, alpha, 1.3);
      const flip = Math.cos(animT * 0.9);
      const w = 28 * Math.max(Math.abs(flip), 0.06);
      const x = len / 2 - w / 2;
      line(len / 2 - 9, -28, x + w * 0.15, -22, accent, alpha * 0.8, 0.5);
      line(len / 2 + 9, -28, x + w * 0.85, -22, accent, alpha * 0.8, 0.5);
      rect(x, -22, w, 10, flip < 0 ? ACCENT.alert : accent, lit ? 0.3 : 0.2, alpha, 0.8);
      if (Math.abs(flip) > 0.3) {
        ctx.save();
        ctx.translate(len / 2, -15);
        ctx.scale(Math.abs(flip), 1);
        ctx.font = 'bold 5.5px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillStyle = rgba(faceInk(flip < 0 ? ACCENT.alert : accent), lit ? 1 : 0.8);
        ctx.fillText(flip < 0 ? 'CLOSED' : 'OPEN', 0, 0);
        ctx.restore();
      }
    });
    // Crescent moon: a disc with a bite taken out of it.
    const [mx, my] = [sx + 16, sy - 42 + 1.5 * Math.sin(animT)];
    ctx.save();
    ctx.beginPath();
    ctx.arc(mx, my, 5, 0, Math.PI * 2);
    ctx.moveTo(mx + 2.6 + 4.4, my - 1.6);
    ctx.arc(mx + 2.6, my - 1.6, 4.4, 0, Math.PI * 2, true);
    ctx.fillStyle = rgba(accent, lit ? 0.85 : 0.55);
    if (lit) { ctx.shadowColor = accent; ctx.shadowBlur = 6; }
    ctx.fill('evenodd');
    ctx.restore();
  }

  // Filing cabinet → a filing cabinet whose top drawer slides open and shut.
  function drawFilingCabinet(sx, sy, accent, lit) {
    const c = [sx, sy];
    const a = 0.34, b = 0.28;
    const body = block(c, a, b, 30, accent, lit);
    onFace(body, 'v', len => {
      [[-9, 7], [-18, 7], [-27.5, 7.5]].forEach(([y, h], i) => {
        rect(2.5, y, len - 5, h, accent, i === 2 ? 0.3 : 0.1, lit ? 0.8 : 0.5, 0.6);
        if (i < 2) line(len / 2 - 3, y + 2.5, len / 2 + 3, y + 2.5, accent, lit ? 0.9 : 0.6, 1.1);
      });
    });
    // The open drawer sticks out of the front (+V) wall.
    const out = 0.05 + 0.28 * wave(0.7);
    const drawer = block(pt(c, 0, b + out / 2), a - 0.04, out / 2, 7, accent, lit, { lift: 20.5, fillAlpha: 1.6 });
    onFace(drawer, 'v', len => line(len / 2 - 3, -3.5, len / 2 + 3, -3.5, accent, lit ? 1 : 0.7, 1.1));
    // Report sheets standing up in the drawer.
    for (const u of [-0.15, 0, 0.15]) {
      const [x1, y1] = pt(drawer.g, u, 0, 7), [x2, y2] = pt(drawer.g, u, 0, 11);
      line(x1, y1, x2, y2, accent, lit ? 0.8 : 0.55, 1.4);
    }
  }

  // Conveyor (intake) → a conveyor belt carrying crates into an intake bin.
  function drawConveyor(sx, sy, accent, lit) {
    const c = [sx, sy];
    for (const [u, v] of [[-0.7, -0.15], [-0.7, 0.15], [0.3, -0.15], [0.3, 0.15]]) {
      const [x1, y1] = pt(c, u, v), [x2, y2] = pt(c, u, v, 4);
      line(x1, y1, x2, y2, accent, lit ? 0.7 : 0.45, 1);
    }
    const belt = block(pt(c, -0.2, 0), 0.65, 0.18, 3, accent, lit, { lift: 4 });
    onFace(belt, 'v', len => {
      for (let i = 0; i < 8; i++) {
        const x = (i * (len / 8) + animT * 10) % len;
        line(x, -0.5, x, -2.5, accent, lit ? 0.6 : 0.4, 0.5);
      }
    });
    const crates = [0, 1, 2].map(i => -0.75 + ((animT * 0.25 + i / 3) % 1) * 1.1).sort((p, q) => p - q);
    for (const u of crates) {
      const fade = Math.min(1, (0.35 - u) * 6, (u + 0.75) * 8);
      const crate = block(pt(c, u, 0), 0.11, 0.11, 6, accent, lit,
        { lift: 7, fillAlpha: 1.8 * fade, strokeAlpha: fade });
      onFace(crate, 'v', len => line(1, -3, len - 1, -3, accent, (lit ? 0.7 : 0.45) * fade, 0.5));
    }
    const bin = block(pt(c, 0.62, 0), 0.2, 0.28, 16, accent, lit);
    onFace(bin, 'v', len => {
      ctx.font = 'bold 4px monospace';
      ctx.textAlign = 'center';
      ctx.fillStyle = rgba(faceInk(accent), lit ? 0.95 : 0.7);
      ctx.fillText('CSV', len / 2, -9);
      for (let i = 0; i < 2; i++) line(3, -5 + i * 2, len - 3, -5 + i * 2, accent, lit ? 0.6 : 0.4, 0.5);
    });
  }

  // A map pin standing on screen point p: a teardrop head over its tip.
  function pin(p, r, accent, alpha, bounce = 0) {
    const [x, y] = p;
    ctx.save();
    ctx.beginPath();
    ctx.ellipse(x, y, r * 0.8, r * 0.8 * SLOPE, 0, 0, Math.PI * 2);
    ctx.fillStyle = rgba(accent, alpha * 0.25);
    ctx.fill();
    const tip = y - bounce, hy = tip - r * 2.3;
    ctx.beginPath();
    ctx.moveTo(x, tip);
    ctx.arc(x, hy, r, Math.PI * 0.75, Math.PI * 0.25);
    ctx.closePath();
    ctx.fillStyle = rgba(accent, alpha * 0.55);
    ctx.fill();
    ctx.strokeStyle = rgba(accent, alpha);
    ctx.lineWidth = 0.9;
    ctx.stroke();
    ctx.restore();
    dot(x, hy, r * 0.38, accent, alpha);
  }

  // Map pins → a patch of town map with pins on it, one bouncing.
  function drawMapPins(sx, sy, accent, lit) {
    const c = [sx, sy];
    block(c, 0.65, 0.65, 2, accent, lit);
    const road = (u1, v1, u2, v2) => {
      const [x1, y1] = pt(c, u1, v1, 2), [x2, y2] = pt(c, u2, v2, 2);
      line(x1, y1, x2, y2, accent, lit ? 0.45 : 0.3, 1.6);
    };
    road(-0.65, 0.1, 0.65, 0.1);
    road(-0.2, -0.65, -0.2, 0.65);
    road(0.3, 0.1, 0.3, 0.65);
    const alpha = lit ? 1 : 0.75;
    pin(pt(c, 0.35, -0.35, 2), 2.6, accent, alpha * 0.8);
    pin(pt(c, -0.45, 0.4, 2), 2.6, accent, alpha * 0.8);
    pin(pt(c, 0.05, 0.3, 2), 3.8, accent, alpha, 3 * Math.abs(Math.sin(animT * 2.4)));
  }

  // Five-pointed star centred on (x, y).
  function star(x, y, r, accent, alpha) {
    const pts = [];
    for (let i = 0; i < 10; i++) {
      const angle = -Math.PI / 2 + (i * Math.PI) / 5;
      const radius = i % 2 ? r * 0.45 : r;
      pts.push([x + radius * Math.cos(angle), y + radius * Math.sin(angle)]);
    }
    poly(pts, accent, alpha * 0.7, alpha, { lw: 0.6 });
  }

  // Podium (star) → a winners' podium with a twinkling star over first place.
  function drawPodium(sx, sy, accent, lit) {
    const c = [sx, sy];
    const steps = [[-0.42, 13, '2'], [0, 19, '1'], [0.42, 9, '3']];
    for (const [u, h, label] of steps) {
      const step = block(pt(c, u, 0), 0.2, 0.32, h, accent, lit, { fillAlpha: label === '1' ? 1.8 : 1.2 });
      onFace(step, 'v', len => {
        ctx.font = 'bold 6px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillStyle = rgba(faceInk(accent), lit ? 1 : 0.75);
        ctx.fillText(label, len / 2, -h / 2 + 2);
      });
    }
    const [x, y] = pt(c, 0, 0, 19 + 9 + 1.5 * Math.sin(animT * 2));
    ctx.save();
    if (lit) { ctx.shadowColor = accent; ctx.shadowBlur = 6; }
    star(x, y, 4 + 0.8 * wave(3), accent, lit ? 1 : 0.75);
    ctx.restore();
  }

  // Photo camera → a camera on a tripod that fires its flash now and then.
  function drawPhotoCamera(sx, sy, accent, lit) {
    const c = [sx, sy];
    const head = pt(c, 0, 0, 14);
    for (const [u, v] of [[-0.32, 0.22], [0.32, 0.22], [0, -0.4]]) {
      const foot = pt(c, u, v);
      line(head[0], head[1], foot[0], foot[1], accent, lit ? 0.8 : 0.55, 1);
    }
    const body = block(c, 0.3, 0.18, 10, accent, lit, { lift: 14, fillAlpha: 1.5 });
    onFace(body, 'v', len => {
      ctx.beginPath();
      ctx.arc(len / 2, -5, 3.6, 0, Math.PI * 2);
      ctx.fillStyle = rgba(faceInk(accent), lit ? 0.3 : 0.2);
      ctx.fill();
      ctx.strokeStyle = rgba(faceInk(accent), lit ? 1 : 0.7);
      ctx.lineWidth = 1;
      ctx.stroke();
      dot(len / 2, -5, 1.4, accent, lit ? 0.9 : 0.6);
    });
    onFace(body, 'u', len => rect(len * 0.3, -8, len * 0.4, 4, accent, 0.2, lit ? 0.8 : 0.5, 0.5));
    const flash = block(pt(c, -0.14, 0), 0.08, 0.06, 3, accent, lit, { lift: 24, fillAlpha: 2 });
    const phase = (animT * 0.4) % 1;
    if (phase < 0.15) {
      const burst = 1 - phase / 0.15;
      const [fx, fy] = pt(flash.g, 0, 0, 5);
      ctx.save();
      ctx.shadowColor = accent;
      ctx.shadowBlur = 12 * burst;
      dot(fx, fy, 2.5 + 2 * burst, accent, 0.8 * burst);
      ctx.restore();
      for (let i = 0; i < 6; i++) {
        const angle = (i * Math.PI) / 3;
        line(fx + 4 * Math.cos(angle), fy + 4 * Math.sin(angle),
          fx + (6 + 5 * burst) * Math.cos(angle), fy + (6 + 5 * burst) * Math.sin(angle),
          accent, 0.8 * burst, 0.8);
      }
    }
  }

  add('register', drawRegister, { bh: 30, scale: 0.55, extraTop: 4, label: 'Cash register' });
  add('clipboard', drawClipboard, { bh: 34, scale: 0.42, label: 'Clipboard' });
  add('truck', drawTruck, { bh: 25, scale: 0.75, label: 'Delivery truck' });
  add('foot-traffic', drawFootTraffic, { bh: 22, scale: 0.9, label: 'Foot traffic' });
  add('chat-kiosk', drawChatKiosk, { bh: 30, scale: 0.5, extraTop: 18, label: 'Chat kiosk' });
  add('mailbox', drawMailbox, { bh: 25, scale: 0.45, extraTop: 10, label: 'Mailbox' });
  add('closing-sign', drawClosingSign, { bh: 30, scale: 0.6, extraTop: 14, label: 'Closing sign' });
  add('filing-cabinet', drawFilingCabinet, { bh: 30, scale: 0.55, label: 'Filing cabinet' });
  add('conveyor-intake', drawConveyor, { bh: 16, scale: 1, label: 'Conveyor (intake)' });
  add('map-pins', drawMapPins, { bh: 4, scale: 1.1, extraTop: 18, label: 'Map pins' });
  add('podium-star', drawPodium, { bh: 19, scale: 0.85, extraTop: 14, label: 'Podium (star)' });
  add('photo-camera', drawPhotoCamera, { bh: 24, scale: 0.5, extraTop: 12, label: 'Photo camera' });
})();
