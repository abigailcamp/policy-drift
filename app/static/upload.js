/** Prefill upload form from UPLOAD_SOURCES JSON embedded in the page. */
(function () {
  const sources = window.UPLOAD_SOURCES || {};
  const select = document.getElementById("instrument_slug");
  const label = document.getElementById("version_label");
  const date = document.getElementById("effective_date");
  const url = document.getElementById("source_url");
  const guide = document.getElementById("upload-guide-panel");
  const frLink = document.getElementById("guide-fr-link");
  const guideTitle = document.getElementById("guide-title");
  const guideType = document.getElementById("guide-type");

  if (!select) return;

  function applySource(slug) {
    const meta = sources[slug];
    if (!meta) {
      if (guide) guide.hidden = true;
      return;
    }
    if (guide) guide.hidden = false;
    if (guideTitle) guideTitle.textContent = meta.title;
    if (guideType) {
      guideType.textContent =
        meta.type === "executive_order"
          ? "Executive order — copy from Federal Register"
          : "Public law — copy from GovInfo";
    }
    if (frLink) {
      frLink.href = meta.fr_url;
      frLink.textContent = "Open official source ↗";
    }
  }

  function fillDefaults() {
    const meta = sources[select.value];
    if (!meta) return;
    if (label && !label.value.trim()) label.value = meta.default_label;
    if (date && !date.value) date.value = meta.default_date;
    if (url && !url.value.trim()) url.value = meta.fr_url;
    applySource(select.value);
  }

  select.addEventListener("change", function () {
    applySource(select.value);
  });

  const fillBtn = document.getElementById("btn-fill-defaults");
  if (fillBtn) {
    fillBtn.addEventListener("click", function (e) {
      e.preventDefault();
      const meta = sources[select.value];
      if (!meta) return;
      if (label) label.value = meta.default_label;
      if (date) date.value = meta.default_date;
      if (url) url.value = meta.fr_url;
    });
  }

  const params = new URLSearchParams(window.location.search);
  const preselect = params.get("instrument");
  if (preselect && sources[preselect]) {
    select.value = preselect;
  }

  applySource(select.value);
})();
