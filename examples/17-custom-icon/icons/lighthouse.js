// Custom topology icon, loaded into the dev UI via this example's
// config.toml (`[ui] icon-scripts`). Draws a lighthouse — tapered tower,
// lamp room, and a beam that sweeps a full turn over time — using the same
// shared primitives (drawBox/isoBox, rgba, ctx, animT) and `(sx, sy, accent,
// lit)` signature as every built-in icon in odf/ui/static/index.html, so it
// renders at the same fidelity and reacts to the same lit/theme state.
//
// Once loaded, "lighthouse" shows up as a swatch in every node's icon
// picker (click a node, then "Customize") — it's not tied to any
// particular exec type, unlike the six built-in per-type defaults.
function drawLighthouse(sx, sy, accent, lit) {
  const bh = 8, scale = 0.4;
  const { w2 } = drawBox(sx, sy, bh, accent, lit, scale);
  const baseTopY = sy - bh;

  // Tapered tower: two stacked boxes, the upper one narrower, standing in
  // for a single tapered silhouette without a dedicated primitive for it.
  const towerW2 = w2 * 0.7, towerH2 = TH2 * scale * 0.7, towerBh = 22;
  isoBox(sx, baseTopY, towerW2, towerH2, towerBh, accent, lit, { fillAlpha: 1.1, strokeAlpha: 1.05 });
  const towerTopY = baseTopY - towerBh;

  const roomW2 = towerW2 * 0.75, roomH2 = towerH2 * 0.75, roomBh = 8;
  isoBox(sx, towerTopY, roomW2, roomH2, roomBh, accent, lit, { fillAlpha: 1.25, strokeAlpha: 1.2 });
  const lampY = towerTopY - roomBh - 2;

  // Rotating beam — a single line whose angle advances with animT, plus a
  // faint back-sweep trail so the sweep direction reads clearly.
  const angle = (animT * 1.5) % (Math.PI * 2);
  ctx.save();
  ctx.lineCap = "round";
  if (lit) { ctx.shadowColor = accent; ctx.shadowBlur = 6; }
  for (const trail of [0, 0.35, 0.7]) {
    const a = angle - trail;
    ctx.strokeStyle = rgba(accent, (lit ? 0.85 : 0.5) * (1 - trail / 0.7) ** 2);
    ctx.lineWidth = 1.3;
    ctx.beginPath();
    ctx.moveTo(sx, lampY);
    ctx.lineTo(sx + Math.cos(a) * 18, lampY + Math.sin(a) * 7);
    ctx.stroke();
  }
  ctx.restore();

  ctx.save();
  ctx.beginPath();
  ctx.arc(sx, lampY, 2.4, 0, Math.PI * 2);
  ctx.fillStyle = rgba(accent, 0.95);
  ctx.shadowColor = accent;
  ctx.shadowBlur = 6;
  ctx.fill();
  ctx.restore();
}

window.ODF.registerIcon("lighthouse", drawLighthouse, {
  bh: 8,
  scale: 0.4,
  extraTop: 38,
  label: "Lighthouse",
});
