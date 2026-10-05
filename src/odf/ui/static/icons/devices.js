// Devices: field hardware and comms gear — controllers, sensors, radios,
// cameras, aircraft, gateways and actuators.
(() => {
  const { pt, line, dot, block, wave, strong } = ODF.iconKit;
  const add = (key, draw, meta) => ODF.registerIcon(key, draw, { group: 'Devices', ...meta });

  // Controller → gamepad body as a small docked box, d-pad + buttons on its face
  function drawController(sx, sy, accent, lit) {
    const bh = 7, scale = 0.65;
    const { w2, h2 } = drawBox(sx, sy, bh, accent, lit, scale);
    const topY = sy - bh;

    const bodyW2 = w2 * 0.92, bodyH2 = h2 * 0.92, bodyBh = 6;
    isoBox(sx, topY, bodyW2, bodyH2, bodyBh, accent, lit, { fillAlpha: 1.2, strokeAlpha: 1.15 });
    const cy = topY - bodyBh;

    ctx.save();
    ctx.strokeStyle = rgba(accent, lit ? 0.95 : 0.8);
    ctx.lineWidth = 1.3;
    if (lit) { ctx.shadowColor = accent; ctx.shadowBlur = 4; }
    ctx.beginPath(); ctx.moveTo(sx - w2 * 0.32, cy); ctx.lineTo(sx - w2 * 0.12, cy); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(sx - w2 * 0.22, cy - 3.5); ctx.lineTo(sx - w2 * 0.22, cy + 3.5); ctx.stroke();
    ctx.fillStyle = rgba(accent, lit ? 0.85 : 0.6);
    ctx.beginPath(); ctx.arc(sx + w2 * 0.18, cy - 2.5, 1.8, 0, Math.PI * 2); ctx.fill();
    ctx.beginPath(); ctx.arc(sx + w2 * 0.3, cy + 2, 1.8, 0, Math.PI * 2); ctx.fill();
    ctx.restore();
  }

  // Sensor → small raised pod with a pulsing dot and radiating ping arcs
  function drawSensor(sx, sy, accent, lit) {
    const bh = 6, scale = 0.5;
    const { h2 } = drawBox(sx, sy, bh, accent, lit, scale);
    const topY = sy - bh;

    const podW2 = TW2 * scale * 0.5, podH2 = h2 * 0.5, podBh = 5;
    isoBox(sx, topY, podW2, podH2, podBh, accent, lit, { fillAlpha: 1.2, strokeAlpha: 1.15 });
    const cy = topY - podBh - podH2 * 0.3;

    const pulse = (Math.sin(animT * 3) + 1) / 2;
    ctx.save();
    ctx.beginPath();
    ctx.arc(sx, cy, 2.6, 0, Math.PI * 2);
    ctx.fillStyle = rgba(accent, 0.8 + 0.2 * pulse);
    ctx.shadowColor = accent;
    ctx.shadowBlur = 5 + 3 * pulse;
    ctx.fill();
    ctx.strokeStyle = rgba(accent, 0.55 + 0.3 * pulse);
    ctx.lineWidth = 1.4;
    for (const r of [7, 13]) {
      ctx.beginPath();
      ctx.arc(sx, cy, r, -Math.PI * 0.75, -Math.PI * 0.25);
      ctx.stroke();
    }
    ctx.restore();
  }

  // Radio → docked base, tapered mast, broadcast arcs (on-air motif)
  function drawRadio(sx, sy, accent, lit) {
    const bh = 8, scale = 0.5;
    drawBox(sx, sy, bh, accent, lit, scale);
    const topY = sy - bh;

    const baseW2 = TW2 * scale * 0.55, baseH2 = TH2 * scale * 0.55, baseBh = 6;
    isoBox(sx, topY, baseW2, baseH2, baseBh, accent, lit, { fillAlpha: 1.2, strokeAlpha: 1.15 });
    const mastTop = topY - baseBh, tipY = mastTop - 18;

    ctx.save();
    ctx.strokeStyle = rgba(accent, lit ? 0.95 : 0.8);
    ctx.lineWidth = 1.4;
    if (lit) { ctx.shadowColor = accent; ctx.shadowBlur = 5; }
    ctx.beginPath(); ctx.moveTo(sx, mastTop); ctx.lineTo(sx, tipY); ctx.stroke();
    ctx.fillStyle = rgba(accent, lit ? 0.95 : 0.8);
    ctx.beginPath(); ctx.arc(sx, tipY, 2, 0, Math.PI * 2); ctx.fill();
    ctx.lineWidth = 1.2;
    for (const r of [6, 11]) {
      ctx.beginPath(); ctx.arc(sx, tipY, r, -Math.PI / 4, Math.PI / 4); ctx.stroke();
      ctx.beginPath(); ctx.arc(sx, tipY, r, Math.PI * 0.75, Math.PI * 1.25); ctx.stroke();
    }
    ctx.restore();
  }

  // Walkie-talkie → tall handset body standing directly on the ground, a
  // tapered antenna, a channel knob, a speaker grille and a status LED.
  function drawWalkieTalkie(sx, sy, accent, lit) {
    const w2 = TW2 * 0.34, h2 = TH2 * 0.34, bh = 28;
    isoBox(sx, sy, w2, h2, bh, accent, lit);
    const topY = sy - bh;

    // Antenna: thick base tapering to a thin tip, angled back off the top
    const abx = sx - w2 * 0.1, aby = topY - h2 * 0.55;
    const atx = abx + w2 * 0.5, aty = aby - 22;
    const mx = abx + (atx - abx) * 0.35, my = aby + (aty - aby) * 0.35;
    ctx.save();
    ctx.strokeStyle = rgba(accent, lit ? 0.95 : 0.8);
    ctx.lineCap = 'round';
    if (lit) { ctx.shadowColor = accent; ctx.shadowBlur = 4; }
    ctx.lineWidth = 2.4;
    ctx.beginPath(); ctx.moveTo(abx, aby); ctx.lineTo(mx, my); ctx.stroke();
    ctx.lineWidth = 1.1;
    ctx.beginPath(); ctx.moveTo(mx, my); ctx.lineTo(atx, aty); ctx.stroke();
    ctx.restore();

    // Channel knob on the top face
    isoDisc(sx + w2 * 0.15, topY + h2 * 0.05, w2 * 0.28, accent, lit,
      { fillAlpha: lit ? 0.4 : 0.28, strokeAlpha: lit ? 0.9 : 0.7, lineWidth: 1.1 });

    // Speaker grille on the front-right face
    ctx.save();
    ctx.strokeStyle = rgba(accent, lit ? 0.7 : 0.45);
    ctx.lineWidth = 0.9;
    for (const f of [0.32, 0.46, 0.6]) {
      ctx.beginPath();
      ctx.moveTo(sx + w2 * 0.3, topY + bh * f);
      ctx.lineTo(sx + w2 * 0.82, topY + bh * f + w2 * 0.12);
      ctx.stroke();
    }
    ctx.restore();

    // Blinking status LED
    const blink = (Math.sin(animT * 4 + sx) + 1) / 2 > 0.5;
    ctx.save();
    ctx.beginPath();
    ctx.arc(sx + w2 * 0.55, topY + bh * 0.16, 1.6, 0, Math.PI * 2);
    ctx.fillStyle = blink ? '#5fd48a' : 'rgba(95,212,138,0.25)';
    if (blink) { ctx.shadowColor = '#5fd48a'; ctx.shadowBlur = 4; }
    ctx.fill();
    ctx.restore();
  }

  // Camera → wall-mounted bullet-style surveillance camera: a short post,
  // a horizontal barrel, a lens with a sun-shield, and a blinking IR light.
  function drawCamera(sx, sy, accent, lit) {
    const postW2 = TW2 * 0.14, postH2 = TH2 * 0.14, postBh = 15;
    isoBox(sx, sy, postW2, postH2, postBh, accent, lit);
    const postTopY = sy - postBh;

    const barrelW2 = TW2 * 0.42, barrelH2 = TH2 * 0.22, barrelBh = 12;
    const barrelX = sx + TW2 * 0.12, barrelY = postTopY + TH2 * 0.06;
    isoBox(barrelX, barrelY, barrelW2, barrelH2, barrelBh, accent, lit, { fillAlpha: 1.15, strokeAlpha: 1.1 });
    const barrelTopY = barrelY - barrelBh;

    // Lens at the barrel's far end
    const lensCx = barrelX + barrelW2, lensCy = barrelY - barrelBh * 0.5;
    ctx.save();
    ctx.strokeStyle = rgba(accent, lit ? 0.95 : 0.8);
    ctx.lineWidth = 1.3;
    if (lit) { ctx.shadowColor = accent; ctx.shadowBlur = 4; }
    ctx.beginPath(); ctx.arc(lensCx, lensCy, 4, 0, Math.PI * 2); ctx.stroke();
    ctx.beginPath(); ctx.arc(lensCx, lensCy, 1.7, 0, Math.PI * 2);
    ctx.fillStyle = rgba(accent, lit ? 0.5 : 0.35);
    ctx.fill();

    // Sun-shield hood above the lens
    ctx.lineWidth = 1.3;
    ctx.beginPath(); ctx.moveTo(lensCx - 5, lensCy - 4); ctx.lineTo(lensCx + 3, lensCy - 6.5); ctx.stroke();
    ctx.restore();

    // Blinking IR/rec status light on top of the barrel
    const blink = (Math.sin(animT * 5 + sx) + 1) / 2 > 0.5;
    ctx.save();
    ctx.beginPath();
    ctx.arc(barrelX - barrelW2 * 0.5, barrelTopY - 2, 1.6, 0, Math.PI * 2);
    ctx.fillStyle = blink ? '#e2564f' : 'rgba(226,86,79,0.25)';
    if (blink) { ctx.shadowColor = '#e2564f'; ctx.shadowBlur = 4; }
    ctx.fill();
    ctx.restore();
  }

  // Drone → small quadcopter: a hub sitting directly on the ground, four arms
  // reaching out to elevated rotor discs, a camera ball slung underneath.
  function drawDrone(sx, sy, accent, lit) {
    const hubW2 = TW2 * 0.26, hubH2 = TH2 * 0.26, hubBh = 8;
    isoBox(sx, sy, hubW2, hubH2, hubBh, accent, lit);
    const armY = sy - hubBh * 1.15;

    ctx.save();
    ctx.strokeStyle = rgba(accent, lit ? 0.95 : 0.8);
    ctx.lineWidth = 1.5;
    if (lit) { ctx.shadowColor = accent; ctx.shadowBlur = 4; }
    const arms = [[-1, -0.65], [1, -0.65], [-1, 0.65], [1, 0.65]];
    const armLen = TW2 * 0.6, armSpread = TH2 * 0.3;
    for (const [dx, dy] of arms) {
      const tx = sx + dx * armLen, ty = armY + dy * armSpread;
      ctx.beginPath(); ctx.moveTo(sx, armY); ctx.lineTo(tx, ty); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(tx, ty); ctx.lineTo(tx, ty - 4); ctx.stroke();
      isoDisc(tx, ty - 4, 6, accent, lit, { fillAlpha: lit ? 0.14 : 0.08, strokeAlpha: lit ? 0.85 : 0.6, lineWidth: 1 });
    }
    ctx.restore();

    isoDisc(sx, sy + hubH2 * 0.3, hubW2 * 0.32, accent, lit,
      { fillAlpha: lit ? 0.5 : 0.35, strokeAlpha: lit ? 0.9 : 0.7, lineWidth: 1 });
  }

  // Plane → small fixed-wing UAV: a stout fuselage (body) with long, thin
  // wings clearly bigger and flatter than it — not matched bars crossing.
  function drawPlane(sx, sy, accent, lit) {
    const bh = 12;
    const fuseW2 = TW2 * 0.24, fuseH2 = TH2 * 0.9;
    isoBox(sx, sy, fuseW2, fuseH2, bh, accent, lit);
    const topY = sy - bh;

    const wingW2 = TW2 * 1.35, wingH2 = TH2 * 0.14, wingBh = 3;
    isoBox(sx, sy - bh * 0.6, wingW2, wingH2, wingBh, accent, lit, { fillAlpha: 0.8, strokeAlpha: 0.9 });

    const tailW2 = TW2 * 0.15, tailH2 = TH2 * 0.15, tailBh = 10;
    isoBox(sx, topY - fuseH2 * 0.72, tailW2, tailH2, tailBh, accent, lit, { fillAlpha: 1.1, strokeAlpha: 1.1 });

    // Propeller: two thin crossed blades at the nose, no ellipses
    const noseX = sx, noseY = topY + fuseH2 - 1, pr = 6.5;
    ctx.save();
    ctx.strokeStyle = rgba(accent, lit ? 0.95 : 0.8);
    ctx.lineWidth = 1.3;
    ctx.lineCap = 'round';
    if (lit) { ctx.shadowColor = accent; ctx.shadowBlur = 4; }
    ctx.beginPath(); ctx.moveTo(noseX - pr * 0.3, noseY - pr); ctx.lineTo(noseX + pr * 0.3, noseY + pr); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(noseX + pr, noseY - pr * 0.25); ctx.lineTo(noseX - pr, noseY + pr * 0.25); ctx.stroke();
    ctx.restore();
    ctx.save();
    ctx.beginPath(); ctx.arc(noseX, noseY, 1.4, 0, Math.PI * 2);
    ctx.fillStyle = rgba(accent, lit ? 0.9 : 0.6);
    ctx.fill();
    ctx.restore();
  }

  // Satellite → central bus standing on the ground, two solar-panel wings on
  // thin struts, and a dish mast on top.
  function drawSatellite(sx, sy, accent, lit) {
    const busW2 = TW2 * 0.22, busH2 = TH2 * 0.22, busBh = 14;
    isoBox(sx, sy, busW2, busH2, busBh, accent, lit);
    const busTopY = sy - busBh;
    const midY = sy - busBh * 0.5;

    const panelW2 = TW2 * 0.32, panelH2 = TH2 * 0.5, panelBh = 2;
    for (const side of [-1, 1]) {
      const px = sx + side * (busW2 + panelW2 + 6);
      isoBox(px, midY, panelW2, panelH2, panelBh, accent, lit, { fillAlpha: 0.75, strokeAlpha: 0.9 });
      ctx.save();
      ctx.strokeStyle = rgba(accent, lit ? 0.8 : 0.55);
      ctx.lineWidth = 1.1;
      ctx.beginPath();
      ctx.moveTo(sx + side * busW2, midY - panelBh);
      ctx.lineTo(px - side * panelW2, midY - panelBh);
      ctx.stroke();
      ctx.restore();
    }

    const dishCx = sx, dishCy = busTopY - busH2 * 0.2;
    ctx.save();
    ctx.strokeStyle = rgba(accent, lit ? 0.95 : 0.8);
    ctx.lineWidth = 1.4;
    if (lit) { ctx.shadowColor = accent; ctx.shadowBlur = 4; }
    ctx.beginPath(); ctx.moveTo(dishCx, dishCy); ctx.lineTo(dishCx, dishCy - 8); ctx.stroke();
    ctx.beginPath(); ctx.arc(dishCx, dishCy - 13, 6, Math.PI * 0.1, Math.PI * 0.9); ctx.stroke();
    ctx.restore();
  }

  // Gateway → docked body block, two antenna prongs, wifi broadcast arcs
  function drawGateway(sx, sy, accent, lit) {
    const bh = 8, scale = 0.55;
    const { w2 } = drawBox(sx, sy, bh, accent, lit, scale);
    const topY = sy - bh;

    const bodyW2 = w2 * 0.9, bodyH2 = TH2 * scale * 0.9, bodyBh = 6;
    isoBox(sx, topY, bodyW2, bodyH2, bodyBh, accent, lit, { fillAlpha: 1.15, strokeAlpha: 1.1 });
    const bodyTopY = topY - bodyBh;

    ctx.save();
    ctx.strokeStyle = rgba(accent, lit ? 0.95 : 0.8);
    ctx.lineWidth = 1.4;
    if (lit) { ctx.shadowColor = accent; ctx.shadowBlur = 4; }
    for (const dx of [-bodyW2 * 0.35, bodyW2 * 0.35]) {
      ctx.beginPath(); ctx.moveTo(sx + dx, bodyTopY); ctx.lineTo(sx + dx, bodyTopY - 11); ctx.stroke();
    }
    ctx.restore();

    const blink = (Math.sin(animT * 6 + sx) + 1) / 2 > 0.5;
    ctx.save();
    ctx.lineWidth = 1.2;
    ctx.strokeStyle = rgba(accent, blink ? 0.95 : 0.45);
    if (blink) { ctx.shadowColor = accent; ctx.shadowBlur = 5; }
    for (const r of [5, 9]) {
      ctx.beginPath(); ctx.arc(sx, bodyTopY - 16, r, Math.PI * 1.2, Math.PI * 1.8); ctx.stroke();
    }
    ctx.restore();
  }

  // Robot arm → docked base block, two-segment articulated arm, gripper jaws
  function drawRobotArm(sx, sy, accent, lit) {
    const bh = 8, scale = 0.5;
    const { w2 } = drawBox(sx, sy, bh, accent, lit, scale);
    const topY = sy - bh;

    const baseW2 = w2 * 0.6, baseH2 = TH2 * scale * 0.6, baseBh = 7;
    isoBox(sx, topY, baseW2, baseH2, baseBh, accent, lit, { fillAlpha: 1.2, strokeAlpha: 1.15 });

    const base = { x: sx, y: topY - baseBh };
    const joint = { x: base.x + 11, y: base.y - 17 };
    const tip = { x: joint.x - 5, y: joint.y - 15 };
    ctx.save();
    ctx.strokeStyle = rgba(accent, lit ? 0.95 : 0.8);
    ctx.lineWidth = 2.1;
    ctx.lineCap = 'round';
    if (lit) { ctx.shadowColor = accent; ctx.shadowBlur = 5; }
    ctx.beginPath();
    ctx.moveTo(base.x, base.y); ctx.lineTo(joint.x, joint.y); ctx.lineTo(tip.x, tip.y);
    ctx.stroke();
    ctx.fillStyle = rgba(accent, lit ? 0.9 : 0.7);
    ctx.beginPath(); ctx.arc(base.x, base.y, 2.6, 0, Math.PI * 2); ctx.fill();
    ctx.beginPath(); ctx.arc(joint.x, joint.y, 2.2, 0, Math.PI * 2); ctx.fill();
    ctx.lineWidth = 1.6;
    const angle = Math.atan2(tip.y - joint.y, tip.x - joint.x);
    for (const s of [-1, 1]) {
      const a = angle + s * 0.65;
      ctx.beginPath();
      ctx.moveTo(tip.x, tip.y);
      ctx.lineTo(tip.x + Math.cos(a) * 7, tip.y + Math.sin(a) * 7);
      ctx.stroke();
    }
    ctx.restore();
  }

  // Pump / valve → docked base block, P&ID-style gate-valve glyph + handle
  function drawPumpValve(sx, sy, accent, lit) {
    const bh = 8, scale = 0.55;
    const { w2 } = drawBox(sx, sy, bh, accent, lit, scale);
    const topY = sy - bh;

    const baseW2 = w2 * 0.5, baseH2 = TH2 * scale * 0.5, baseBh = 6;
    isoBox(sx, topY, baseW2, baseH2, baseBh, accent, lit, { fillAlpha: 1.2, strokeAlpha: 1.15 });
    const cy = topY - baseBh - 6;

    ctx.save();
    ctx.strokeStyle = rgba(accent, lit ? 0.95 : 0.8);
    ctx.fillStyle = rgba(accent, lit ? 0.26 : 0.18);
    ctx.lineWidth = 1.5;
    if (lit) { ctx.shadowColor = accent; ctx.shadowBlur = 5; }
    ctx.beginPath();
    ctx.moveTo(sx - 9, cy - 5); ctx.lineTo(sx, cy); ctx.lineTo(sx - 9, cy + 5); ctx.closePath();
    ctx.fill();
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(sx + 9, cy - 5); ctx.lineTo(sx, cy); ctx.lineTo(sx + 9, cy + 5); ctx.closePath();
    ctx.fill();
    ctx.stroke();
    ctx.lineWidth = 1.6;
    ctx.beginPath(); ctx.moveTo(sx, cy); ctx.lineTo(sx, cy - 11); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(sx - 5, cy - 11); ctx.lineTo(sx + 5, cy - 11); ctx.stroke();
    ctx.restore();
  }

  // Radio mast → a radio mast sending out messages.
  function drawMast(sx, sy, accent, lit) {
    const c = [sx, sy];
    block(c, 0.42, 0.42, 5, accent, lit);
    const [bx, by] = pt(c, 0, 0, 5), top = by - 30;
    for (const dx of [-5, 5]) line(bx + dx, by, bx, top, accent, strong(lit), 1);
    for (const y of [8, 16, 23]) line(bx - 5 + y * 0.16, by - y, bx + 5 - y * 0.16, by - y, accent, lit ? 0.6 : 0.4, 0.6);
    ctx.save();
    if (lit) { ctx.shadowColor = accent; ctx.shadowBlur = 5; }
    dot(bx, top, 1.8, accent, 1);
    for (let i = 0; i < 3; i++) {
      const t = (animT * 0.5 + i / 3) % 1;
      ctx.strokeStyle = rgba(accent, (1 - t) * (lit ? 0.9 : 0.6));
      ctx.lineWidth = 0.8;
      for (const [from, to] of [[-0.6, 0.6], [Math.PI - 0.6, Math.PI + 0.6]]) {
        ctx.beginPath();
        ctx.arc(bx, top, 3 + t * 13, from, to);
        ctx.stroke();
      }
    }
    ctx.restore();
  }

  // Radar → a radar station with a sweeping beam.
  function drawRadar(sx, sy, accent, lit) {
    const c = [sx, sy];
    block(c, 0.5, 0.5, 10, accent, lit);
    const [cx, cy] = pt(c, 0, 0, 22);
    line(cx, cy + 12, cx, cy, accent, strong(lit), 1.3);
    ctx.save();
    ctx.translate(cx, cy);
    ctx.scale(1, 0.55);
    if (lit) { ctx.shadowColor = accent; ctx.shadowBlur = 6; }
    for (const r of [5, 10, 15]) {
      ctx.beginPath();
      ctx.arc(0, 0, r, 0, Math.PI * 2);
      ctx.strokeStyle = rgba(accent, r === 15 ? strong(lit) : 0.35);
      ctx.lineWidth = r === 15 ? 1 : 0.6;
      ctx.stroke();
    }
    const angle = animT * 1.6;
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.arc(0, 0, 15, angle - 0.7, angle);
    ctx.closePath();
    ctx.fillStyle = rgba(accent, lit ? 0.35 : 0.2);
    ctx.fill();
    ctx.beginPath();
    ctx.arc(7, -5, 1.6, 0, Math.PI * 2);
    ctx.fillStyle = rgba(accent, 0.3 + 0.7 * wave(4));
    ctx.fill();
    ctx.restore();
  }

  add('controller', drawController, { bh: 7, scale: 0.65, extraTop: 10, label: 'Controller' });
  add('sensor', drawSensor, { bh: 6, scale: 0.5, extraTop: 16, label: 'Sensor' });
  add('radio', drawRadio, { bh: 8, scale: 0.5, extraTop: 24, label: 'Radio' });
  add('walkie-talkie', drawWalkieTalkie, { bh: 30, scale: 0.4, extraTop: 28, label: 'Walkie-talkie' });
  add('camera', drawCamera, { bh: 16, scale: 0.6, extraTop: 6, label: 'Camera' });
  add('drone', drawDrone, { bh: 8, scale: 0.8, extraTop: 4, label: 'Drone' });
  add('plane', drawPlane, { bh: 12, scale: 1.4, extraTop: 6, label: 'Plane' });
  add('satellite', drawSatellite, { bh: 14, scale: 1.05, extraTop: 4, label: 'Satellite' });
  add('gateway', drawGateway, { bh: 8, scale: 0.55, extraTop: 22, label: 'Gateway' });
  add('robot-arm', drawRobotArm, { bh: 8, scale: 0.5, extraTop: 36, label: 'Robot arm' });
  add('pump-valve', drawPumpValve, { bh: 8, scale: 0.55, extraTop: 14, label: 'Pump / valve' });
  add('mast', drawMast, { bh: 5, scale: 0.8, extraTop: 34, label: 'Radio mast' });
  add('radar', drawRadar, { bh: 10, scale: 0.8, extraTop: 22, label: 'Radar' });
})();
