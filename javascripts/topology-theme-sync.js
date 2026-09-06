// Keeps the embedded topology demo (docs/assets/topology-demo/, see
// docs/index.md's "UI" section) in sync with the docs site's own
// light/dark toggle. It's a same-origin iframe, so this mirrors
// mkdocs-material's `data-md-color-scheme` on <body> into the iframe's
// own `odf-ui-theme` localStorage key — read by its initTheme() on
// load, avoiding a mismatched flash on first paint/reload — and, for a
// live toggle while the iframe is already open, calls its applyTheme()
// directly through contentWindow.
(function () {
  const iframe = document.querySelector(".topology-demo-frame");
  if (!iframe) return;

  const docsTheme = () =>
    document.body.getAttribute("data-md-color-scheme") === "slate" ? "dark" : "light";

  const sync = () => {
    const theme = docsTheme();
    localStorage.setItem("odf-ui-theme", theme);
    try {
      iframe.contentWindow.applyTheme(theme);
    } catch (err) {
      // Iframe hasn't finished loading yet — the localStorage write above
      // means its own initTheme() will still pick up the right theme.
    }
  };

  sync();
  new MutationObserver(sync).observe(document.body, {
    attributes: true,
    attributeFilter: ["data-md-color-scheme"],
  });
})();
