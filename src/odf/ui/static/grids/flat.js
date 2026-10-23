// Flat grid, picked with `[ui] grid = "flat"`: a top-down schematic of the
// topology. Columns run right and rows down, on square cells marked only by
// a faint dot where a node snaps, and every node is the same rounded square
// in its type's color, so a large topology reads at a glance. Nodes can't be
// customized here; their icon and color overrides stay saved for the
// isometric grid. Registers through ODF.registerGrid (see "Grids" in
// app.js), drawing with app.js's own helpers, so the theme's colors and icon
// face style still apply; its isometric-only hooks (emptyTile,
// groundShadow) don't.
(() => {
  const CELL = 72;       // cell width and height
  const HALF = CELL / 2;
  const NODE = 15;       // a node's half-size
  const DOT = 1.3;       // radius of an empty cell's dot

  function roundedSquare(sx, sy, half, r) {
    ctx.beginPath();
    ctx.roundRect(sx - half, sy - half, half * 2, half * 2, r);
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
      ICON_FRAME = { x: sx, top: sy - NODE, bottom: sy + NODE };
      try {
        paintFace(() => roundedSquare(sx, sy, NODE, 4), 'top', nodeAccent(node), lit, 2);
      } finally {
        ICON_FRAME = null;
      }
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
    customizable: false,
  });
})();
