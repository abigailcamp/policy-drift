(() => {
  const input = document.getElementById("dashboard-search-input");
  const list = document.querySelector(".instrument-list");
  if (!input || !list) return;

  function escapeHtml(s) {
    return String(s)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function highlight(text, q) {
    const safe = escapeHtml(text || "");
    if (!q) return safe;
    const re = new RegExp(`(${q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "ig");
    return safe.replace(re, "<mark>$1</mark>");
  }

  function renderItems(items, q) {
    if (!items.length) {
      list.innerHTML = `<li class="instrument-item"><p class="page-lead">No matches.</p></li>`;
      return;
    }

    list.innerHTML = items
      .map((it) => {
        const titleHtml = highlight(it.title, q);
        const snippetHtml = it.snippet ? highlight(it.snippet, q) : "";
        const tags = (it.tags || []).map((t) => `<span class="tag-pill">${highlight(t, q)}</span>`).join("");
        const typePill = `<span class="tag-pill tag-pill--type">${escapeHtml(it.instrument_type.replaceAll("_", " "))}</span>`;
        const statusPill = it.last_fetch_status
          ? `<span class="tag-pill tag-pill--status tag-pill--${escapeHtml(it.last_fetch_status)}">${escapeHtml(it.last_fetch_status)}</span>`
          : "";

        return `
<li class="instrument-item">
  <h2 class="instrument-title"><a href="/instruments/${escapeHtml(it.slug)}">${titleHtml}</a></h2>
  <p class="instrument-meta instrument-meta--tags">
    ${typePill}
    ${tags}
  </p>
  <p class="instrument-meta">
    ${escapeHtml(it.version_count)} version${it.version_count === 1 ? "" : "s"}
    · last fetch ${escapeHtml(it.last_fetch_at || "never")}
    ${statusPill}
  </p>
  ${snippetHtml ? `<p class="search-snippet">${snippetHtml}</p>` : ""}
  <p class="item-actions">
    <a href="/instruments/${escapeHtml(it.slug)}">View timeline</a>
    <span class="sep">·</span>
    <a href="/admin/upload?instrument=${escapeHtml(it.slug)}">Upload text</a>
    <span class="sep">·</span>
    <a href="#" class="notify-link" data-instrument="${escapeHtml(it.slug)}">Notify me</a>
  </p>
</li>`;
      })
      .join("");
  }

  let t = null;
  let lastQ = "";

  async function runSearch(q) {
    const url = q ? `/api/search?q=${encodeURIComponent(q)}` : `/api/search?q=`;
    const resp = await fetch(url, { headers: { Accept: "application/json" } });
    if (!resp.ok) return;
    const data = await resp.json();
    renderItems(data.items || [], q);
  }

  input.addEventListener("input", () => {
    const q = input.value.trim();
    if (q === lastQ) return;
    lastQ = q;
    if (t) clearTimeout(t);
    t = setTimeout(() => runSearch(q), 180);
  });
})();

