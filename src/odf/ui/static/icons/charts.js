// Charts: a billboard on two posts whose board shows one animated chart —
// scatter, curves, lines, bars, a donut, a heatmap, a KPI, a matrix or a
// histogram. Every icon here shares the one frame and differs only in the
// face drawn on its board.
(() => {
  const { pt, poly, line, path, rect, dot, block, onFace, wave, strong } = ODF.iconKit;
  const add = (key, draw, meta) => ODF.registerIcon(key, draw, { group: 'Charts', ...meta });

  // Builds a draw function for a billboard showing `face(len, accent, lit)`,
  // which draws in the board's own flat coordinates (see onFace).
  function billboard(face) {
    return (sx, sy, accent, lit) => {
      const c = [sx, sy];
      block(c, 0.45, 0.16, 3, accent, lit);
      for (const u of [-0.28, 0.28]) {
        const [x1, y1] = pt(c, u, 0, 3), [x2, y2] = pt(c, u, 0, 14);
        line(x1, y1, x2, y2, accent, strong(lit), 1.2);
      }
      const board = block(c, 0.62, 0.05, 22, accent, lit, { lift: 14 });
      onFace(board, 'v', len => face(len, accent, lit));
    };
  }

  // Plot area shared by the axis-based faces: x and y in 0..1 mapped onto
  // the board, plus the two axis lines.
  const plotX = len => x => 4 + x * (len - 7);
  const plotY = y => -4 - y * 15;
  function axes(len, accent, lit) {
    line(2.5, -3, len - 2, -3, accent, lit ? 0.7 : 0.45);
    line(2.5, -3, 2.5, -20, accent, lit ? 0.7 : 0.45);
  }

  // A dot riding a curve, glowing when lit.
  function marker(x, y, accent, lit) {
    ctx.save();
    if (lit) { ctx.shadowColor = accent; ctx.shadowBlur = 5; }
    dot(x, y, 1.8, accent, lit ? 1 : 0.8);
    ctx.restore();
  }

  // The points of a line through `ys` revealed left to right, then held.
  function revealed(ys, X, Y) {
    const steps = (ys.length - 1) * Math.min(1, (animT * 0.3) % 1.3);
    const points = [];
    for (let i = 0; i <= Math.floor(steps); i++) points.push([X(i / (ys.length - 1)), Y(ys[i])]);
    const i = Math.floor(steps), f = steps - i;
    if (i < ys.length - 1) points.push([X((i + f) / (ys.length - 1)), Y(ys[i] + (ys[i + 1] - ys[i]) * f)]);
    return points;
  }

  // Scatter → pulsing points around a falling fitted line.
  function scatterFace(len, accent, lit) {
    const X = plotX(len), Y = plotY;
    axes(len, accent, lit);
    const points = [[0.05, 0.9], [0.15, 0.7], [0.25, 0.8], [0.35, 0.55], [0.45, 0.62],
      [0.55, 0.4], [0.65, 0.5], [0.75, 0.25], [0.85, 0.35], [0.95, 0.12]];
    points.forEach(([x, y], i) => dot(X(x), Y(y), 1 + 0.5 * wave(2, i * 0.8), accent, lit ? 0.9 : 0.65));
    line(X(0), Y(0.88), X(1), Y(0.15), accent, lit ? 1 : 0.75, 1);
  }

  // Curve → a decaying curve with a marker travelling along it.
  function curveFace(len, accent, lit) {
    const X = plotX(len), Y = plotY;
    axes(len, accent, lit);
    const curve = x => 0.08 + 0.85 / (1 + 6 * x);
    path(Array.from({ length: 16 }, (_, i) => [X(i / 15), Y(curve(i / 15))]), accent, lit ? 1 : 0.75, 1);
    const t = (animT * 0.25) % 1;
    marker(X(t), Y(curve(t)), accent, lit);
  }

  // Lines → three series drawing themselves in.
  function linesFace(len, accent, lit) {
    const X = plotX(len), Y = plotY;
    axes(len, accent, lit);
    const series = [[0.3, 0.35, 0.6, 0.5, 0.4, 0.8, 0.45], [0.7, 0.65, 0.75, 0.9, 0.7, 0.6, 0.55], [0.15, 0.2, 0.25, 0.2, 0.3, 0.5, 0.3]];
    series.forEach((ys, s) => path(revealed(ys, X, Y), accent, [1, 0.65, 0.4][s] * (lit ? 1 : 0.75), 0.9));
  }

  // Bars → four vertical bars breathing on a baseline.
  function barsFace(len, accent, lit) {
    const heights = [0.45, 0.8, 0.6, 1];
    line(2, -3, len - 2, -3, accent, lit ? 0.7 : 0.45);
    heights.forEach((base, i) => {
      const h = 15 * base * (0.8 + 0.2 * Math.sin(animT * 2 + i * 1.3));
      rect(3.5 + i * 5, -3 - h, 3.4, h, accent, lit ? 0.6 : 0.4, lit ? 0.9 : 0.6, 0.5);
    });
  }

  // Paired bars → an outlined bar with a filled one inside its share.
  function pairsFace(len, accent, lit) {
    const pairs = [[0.9, 0.35], [0.6, 0.4], [1, 0.65]];
    line(2, -3, len - 2, -3, accent, lit ? 0.7 : 0.45);
    pairs.forEach(([outer, share], i) => {
      const h = 15 * outer * (0.9 + 0.1 * Math.sin(animT * 1.5 + i));
      const x = 3 + i * 7;
      rect(x, -3 - h, 3, h, accent, 0.08, lit ? 0.8 : 0.5, 0.5);
      rect(x + 3.2, -3 - h * share, 3, h * share, accent, lit ? 0.7 : 0.5, lit ? 0.9 : 0.6, 0.5);
    });
  }

  // Heatmap → a grid of cells, two columns running hot.
  function heatmapFace(len, accent) {
    const cols = 6, rows = 4, w = (len - 5) / cols, h = 4;
    for (let col = 0; col < cols; col++) {
      const peak = col === 1 ? 1 : col === 3 ? 0.7 : 0.25;
      for (let row = 0; row < rows; row++) {
        const heat = peak * (0.6 + 0.4 * wave(1.6, col * 0.9 + row * 1.7));
        rect(2.5 + col * w, -19 + row * h, w - 0.8, h - 0.8, accent, 0.1 + 0.75 * heat, 0, 0.3);
      }
    }
  }

  // KPI → a figure ticking up, a trend arrow and a sparkline.
  function kpiFace(len, accent, lit) {
    ctx.save();
    ctx.font = 'bold 7px monospace';
    ctx.textAlign = 'left';
    ctx.fillStyle = rgba(accent, lit ? 1 : 0.85);
    if (lit) { ctx.shadowColor = accent; ctx.shadowBlur = 3; }
    ctx.fillText(`$${(1200 + (Math.floor(animT * 7) % 800)).toLocaleString('en-US')}`, 3, -12);
    ctx.restore();
    poly([[len - 8, -12], [len - 3, -12], [len - 5.5, -17]], accent, lit ? 0.8 : 0.6, lit ? 1 : 0.7);
    const spark = [0.2, 0.5, 0.35, 0.7, 0.55, 0.9];
    const shift = wave(1.2) * 0.1;
    for (let i = 1; i < spark.length; i++) {
      const x = (j) => 3 + j * ((len - 6) / (spark.length - 1));
      line(x(i - 1), -3 - 6 * (spark[i - 1] + shift), x(i), -3 - 6 * (spark[i] + shift),
        accent, lit ? 0.9 : 0.6, 0.8);
    }
  }

  // Donut → three segments of a slowly spinning ring.
  function donutFace(len, accent, lit) {
    const shares = [0.45, 0.3, 0.25], alphas = [0.95, 0.6, 0.3];
    let start = animT * 0.6;
    ctx.lineWidth = 3;
    shares.forEach((share, i) => {
      const end = start + share * Math.PI * 2;
      ctx.beginPath();
      ctx.arc(len / 2, -11, 6.5, start + 0.08, end - 0.08);
      ctx.strokeStyle = rgba(accent, alphas[i] * (lit ? 1 : 0.75));
      ctx.stroke();
      start = end;
    });
  }

  // Matrix → a 2×2 grid with a strong diagonal.
  function matrixFace(len, accent, lit) {
    const w = (len - 9) / 2;
    [[0, 0, 0.75], [1, 0, 0.15], [0, 1, 0.15], [1, 1, 0.6]].forEach(([col, row, fill], i) => {
      rect(4 + col * (w + 1), -20 + row * 8.5, w, 7.5, accent, fill * (0.75 + 0.25 * wave(2, i)), lit ? 0.9 : 0.65, 0.5);
    });
  }

  // Plateau curve → a curve that holds high, then drops off at the far end,
  // with a marker sliding back and forth along it.
  function plateauFace(len, accent, lit) {
    const X = plotX(len), Y = plotY;
    axes(len, accent, lit);
    const curve = x => 0.95 - 0.85 * Math.pow(x, 6);
    path(Array.from({ length: 16 }, (_, i) => [X(i / 15), Y(curve(i / 15))]), accent, lit ? 1 : 0.75, 1);
    const t = 0.55 + 0.4 * wave(0.8);
    marker(X(t), Y(curve(t)), accent, lit);
  }

  // Ranked bars → horizontal bars, longest first.
  function rankedFace(len, accent, lit) {
    axes(len, accent, lit);
    [0.9, 0.7, 0.5, 0.35, 0.25].forEach((w, i) => {
      rect(4, -19 + i * 3.2, (len - 8) * w * (0.9 + 0.1 * wave(2, i)), 2, accent, (lit ? 0.9 : 0.65) * 0.7, 0, 0.4);
    });
  }

  // Histogram → two humps, the left one fainter.
  function histFace(len, accent, lit) {
    axes(len, accent, lit);
    const alpha = lit ? 0.9 : 0.65;
    [0.95, 0.5, 0.2, 0.08, 0.05, 0.1, 0.3, 0.7].forEach((h, i, all) => {
      const w = (len - 8) / all.length;
      const tall = 15 * h * (0.9 + 0.1 * wave(2, i));
      rect(4 + i * w, -3.5 - tall, w - 0.8, tall, accent, i < 4 ? alpha * 0.4 : alpha * 0.85, 0, 0.4);
    });
  }

  // Dip line → a single line that dips in the middle, drawing itself in.
  function dipFace(len, accent, lit) {
    const X = plotX(len), Y = plotY;
    axes(len, accent, lit);
    path(revealed([0.85, 0.9, 0.88, 0.4, 0.35, 0.9, 0.92], X, Y), accent, lit ? 1 : 0.75, 1);
  }

  const meta = label => ({ bh: 36, scale: 0.62, label: `Billboard (${label})` });

  add('billboard-scatter', billboard(scatterFace), meta('scatter'));
  add('billboard-curve', billboard(curveFace), meta('curve'));
  add('billboard-lines', billboard(linesFace), meta('lines'));
  add('billboard-bars', billboard(barsFace), meta('bars'));
  add('billboard-pairs', billboard(pairsFace), meta('paired bars'));
  add('billboard-heatmap', billboard(heatmapFace), meta('heatmap'));
  add('billboard-kpi', billboard(kpiFace), meta('KPI'));
  add('billboard-donut', billboard(donutFace), meta('donut'));
  add('board-matrix', billboard(matrixFace), meta('matrix'));
  add('board-curve', billboard(plateauFace), meta('plateau curve'));
  add('board-bars', billboard(rankedFace), meta('ranked bars'));
  add('board-hist', billboard(histFace), meta('histogram'));
  add('board-lines', billboard(dipFace), meta('dip line'));
})();
