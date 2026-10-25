// Flat grid, picked with `[ui] grid = "flat"`: a top-down schematic of the
// topology. Columns run right and rows down, on square cells marked only by
// a faint dot where a node snaps, and every node is a rounded square in its
// type's color with a small glyph on it, so a large topology reads at a
// glance. Customize picks another glyph from GLYPHS below, saved as the
// node's `flatIcon` (see GRID.iconField in app.js) so the isometric grid's
// `icon` is kept; a color override applies on both grids. Registers through
// ODF.registerGrid (see "Grids" in app.js), drawing with app.js's own
// helpers, so the theme's colors and icon face style still apply; its
// isometric-only hooks (emptyTile, groundShadow) don't.
(() => {
  const CELL = 72;       // cell width and height
  const HALF = CELL / 2;
  const NODE = 15;       // a node's half-size
  const DOT = 1.3;       // radius of an empty cell's dot
  const SWATCH = 12;     // a picker swatch's half-size

  function roundedSquare(sx, sy, half, r) {
    ctx.beginPath();
    ctx.roundRect(sx - half, sy - half, half * 2, half * 2, r);
  }

  // Glyph drawing: each glyph's draw(g) works in a unit box of [-1, 1] on
  // both axes, centered on the node, through these helpers. `g.k` maps a
  // unit length to pixels.
  function pen(sx, sy, k, ink) {
    const X = x => sx + x * k, Y = y => sy + y * k;
    return {
      k,
      line(...pts) {
        ctx.beginPath();
        ctx.moveTo(X(pts[0][0]), Y(pts[0][1]));
        for (const [x, y] of pts.slice(1)) ctx.lineTo(X(x), Y(y));
        ctx.stroke();
      },
      shape(pts) {
        ctx.beginPath();
        ctx.moveTo(X(pts[0][0]), Y(pts[0][1]));
        for (const [x, y] of pts.slice(1)) ctx.lineTo(X(x), Y(y));
        ctx.closePath();
        ctx.fill();
      },
      arc(x, y, r, a0 = 0, a1 = Math.PI * 2, fill = false) {
        ctx.beginPath();
        ctx.arc(X(x), Y(y), r * k, a0, a1);
        fill ? ctx.fill() : ctx.stroke();
      },
      ellipse(x, y, rx, ry, a0 = 0, a1 = Math.PI * 2) {
        ctx.beginPath();
        ctx.ellipse(X(x), Y(y), rx * k, ry * k, 0, a0, a1);
        ctx.stroke();
      },
      rect(x, y, w, h, fill = false) {
        ctx.beginPath();
        ctx.roundRect(X(x), Y(y), w * k, h * k, 0.12 * k);
        fill ? ctx.fill() : ctx.stroke();
      },
    };
  }

  const PI = Math.PI;
  // One glyph per exec type ('Defaults', drawn when a node has no flatIcon),
  // then a few more to pick from.
  const GLYPHS = {
    config: { label: 'Config sliders', group: 'Defaults', draw(g) {
      for (const [y, x] of [[-0.55, 0.3], [0, -0.35], [0.55, 0.1]]) {
        g.line([-0.8, y], [0.8, y]);
        g.arc(x, y, 0.17, 0, PI * 2, true);
      }
    } },
    component: { label: '@Component package', group: 'Defaults', draw(g) {
      g.rect(-0.75, -0.75, 1.5, 1.5);
      g.line([-0.75, -0.25], [0.75, -0.25]);
      g.line([-0.15, -0.75], [-0.15, -0.25], [0.15, -0.25], [0.15, -0.75]);
    } },
    repository: { label: '@Repository rack', group: 'Defaults', draw(g) {
      for (const y of [-0.8, -0.2, 0.4]) {
        g.rect(-0.75, y, 1.5, 0.42);
        g.arc(0.45, y + 0.21, 0.08, 0, PI * 2, true);
      }
    } },
    service: { label: '@Service broadcast', group: 'Defaults', draw(g) {
      g.arc(0, 0, 0.16, 0, PI * 2, true);
      for (const r of [0.45, 0.8]) {
        g.arc(0, 0, r, -PI / 4, PI / 4);
        g.arc(0, 0, r, PI * 3 / 4, PI * 5 / 4);
      }
    } },
    task: { label: '@Task cog', group: 'Defaults', draw(g) {
      for (let i = 0; i < 8; i++) {
        const a = (i * PI) / 4;
        g.line([Math.cos(a) * 0.5, Math.sin(a) * 0.5], [Math.cos(a) * 0.82, Math.sin(a) * 0.82]);
      }
      g.arc(0, 0, 0.52);
      g.arc(0, 0, 0.18);
    } },
    pipeline: { label: '@Pipeline chevrons', group: 'Defaults', draw(g) {
      g.line([-0.7, -0.6], [-0.1, 0], [-0.7, 0.6]);
      g.line([0.05, -0.6], [0.65, 0], [0.05, 0.6]);
    } },
    agent: { label: '@Agent eye', group: 'Defaults', draw(g) {
      g.ellipse(0, 0.55, 1.05, 0.95, PI * 1.22, PI * 1.78);
      g.ellipse(0, -0.55, 1.05, 0.95, PI * 0.22, PI * 0.78);
      g.arc(0, 0, 0.22, 0, PI * 2, true);
    } },
    function: { label: '@Function lambda', group: 'Defaults', draw(g) {
      g.line([-0.55, -0.8], [-0.25, -0.8], [0.6, 0.8]);
      g.line([0.08, -0.05], [-0.55, 0.8]);
    } },

    database: { label: 'Database', group: 'Symbols', draw(g) {
      g.ellipse(0, -0.55, 0.7, 0.25);
      g.ellipse(0, 0, 0.7, 0.25, 0, PI);
      g.ellipse(0, 0.55, 0.7, 0.25, 0, PI);
      g.line([-0.7, -0.55], [-0.7, 0.55]);
      g.line([0.7, -0.55], [0.7, 0.55]);
    } },
    cloud: { label: 'Cloud', group: 'Symbols', draw(g) {
      g.arc(-0.4, 0.15, 0.35, PI * 0.5, PI * 1.5);
      g.arc(0, -0.15, 0.45, PI * 1.1, PI * 1.95);
      g.arc(0.45, 0.15, 0.35, PI * 1.5, PI * 0.5);
      g.line([-0.4, 0.5], [0.45, 0.5]);
    } },
    bolt: { label: 'Bolt', group: 'Symbols', draw(g) {
      g.shape([[0.2, -0.9], [-0.5, 0.12], [-0.02, 0.12], [-0.2, 0.9], [0.5, -0.12], [0.02, -0.12]]);
    } },
    star: { label: 'Star', group: 'Symbols', draw(g) {
      const pts = [];
      for (let i = 0; i < 10; i++) {
        const a = -PI / 2 + (i * PI) / 5, r = i % 2 ? 0.38 : 0.85;
        pts.push([Math.cos(a) * r, Math.sin(a) * r + 0.06]);
      }
      g.shape(pts);
    } },
    flag: { label: 'Flag', group: 'Symbols', draw(g) {
      g.line([-0.55, 0.85], [-0.55, -0.8]);
      g.shape([[-0.55, -0.8], [0.7, -0.5], [-0.55, -0.15]]);
    } },
    lock: { label: 'Lock', group: 'Symbols', draw(g) {
      g.arc(0, -0.2, 0.38, PI, 0);
      g.line([-0.38, -0.2], [-0.38, 0]);
      g.line([0.38, -0.2], [0.38, 0]);
      g.rect(-0.62, 0, 1.24, 0.8, true);
    } },
    user: { label: 'User', group: 'Symbols', draw(g) {
      g.arc(0, -0.38, 0.32, 0, PI * 2, true);
      g.arc(0, 0.8, 0.7, PI, 0, true);
    } },
    chart: { label: 'Chart', group: 'Symbols', draw(g) {
      g.rect(-0.75, 0.1, 0.38, 0.7, true);
      g.rect(-0.19, -0.35, 0.38, 1.15, true);
      g.rect(0.37, -0.8, 0.38, 1.6, true);
    } },
  };

  // Draws a node's square and glyph `key` centered on (sx, sy), `half` across.
  function drawNode(key, sx, sy, half, accent, lit) {
    ICON_FRAME = { x: sx, top: sy - half, bottom: sy + half };
    try {
      paintFace(() => roundedSquare(sx, sy, half, half * 0.27), 'top', accent, lit, 2);
      const ink = faceInk(accent);
      ctx.save();
      ctx.strokeStyle = ink;
      ctx.fillStyle = ink;
      ctx.lineWidth = Math.max(1, half * 0.1);
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';
      GLYPHS[key].draw(pen(sx, sy, half * 0.55, ink));
      ctx.restore();
    } finally {
      ICON_FRAME = null;
    }
  }

  ODF.registerGrid('flat', {
    project(col, row) {
      return { x: col * CELL + ORIGIN_X, y: row * CELL + ORIGIN_Y };
    },
    cell(x, y) {
      return { col: Math.round((x - ORIGIN_X) / CELL), row: Math.round((y - ORIGIN_Y) / CELL) };
    },
    origin(midCol, midRow) {
      ORIGIN_X = CW / 2 - midCol * CELL;
      ORIGIN_Y = CH / 2 - midRow * CELL;
    },
    tilePath(sx, sy, s) {
      roundedSquare(sx, sy, (HALF - 4) * s, 6 * s);
    },
    emptyCell(sx, sy) {
      ctx.beginPath();
      ctx.arc(sx, sy, DOT, 0, Math.PI * 2);
      ctx.fillStyle = TILE_STROKE;
      ctx.fill();
    },
    drawNode(node, sx, sy, lit) {
      drawNode(iconKey(node), sx, sy, NODE, nodeAccent(node), lit);
    },
    extents() {
      return { top: NODE, bottom: NODE, half: NODE };
    },
    // nw/ne/se/sw grow MIN_COL/MIN_ROW/MAX_COL/MAX_ROW (see computeGridBounds),
    // which here are the left, top, right and bottom edges.
    gridArrows: {
      nw: ['←', 'Add cells (left edge)'],
      ne: ['↑', 'Add cells (top edge)'],
      sw: ['↓', 'Add cells (bottom edge)'],
      se: ['→', 'Add cells (right edge)'],
    },
    icons: GLYPHS,
    iconField: 'flatIcon',
    drawSwatch(key, x, y, accent) {
      drawNode(key, x, y - SWATCH, SWATCH, accent, false);
    },
  });
})();
