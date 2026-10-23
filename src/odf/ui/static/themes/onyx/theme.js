// Tonal solids: icon faces are opaque shades of their accent with no
// outlines at all, told apart by tone alone like the theme's surfaces, and
// a lit icon is raised a step in tone.
ODF.registerTheme({
  faces: {
    fill: 'shade',
    shade:    { top: 0.22, left: -0.08, right: -0.3 },
    shadeLit: { top: 0.38, left: 0.06,  right: -0.16 },
    outline: 'none',
    detail: -0.6,
  },
});
