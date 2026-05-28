(() => {
  const input = document.getElementById("dashboard-search-input");
  const list = document.getElementById("search-results");
  if (!input || !list) return;
  const chips = Array.from(document.querySelectorAll(".search-chip"));

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
    if (!q) {
      list.innerHTML = "";
      return;
    }
    if (!items.length) {
      list.innerHTML = `<li class="archive-item"><p class="page-lead">No matches.</p></li>`;
      return;
    }

    list.innerHTML = items
      .map((it) => {
        const titleHtml = highlight(it.title, q);
        const snippetHtml = it.snippet ? highlight(it.snippet, q) : "";

        return `
<li class="archive-item">
  <a class="archive-link" href="/instruments/${escapeHtml(it.slug)}">
    <h2 class="archive-title">${titleHtml}</h2>
    <p class="archive-meta">
      ${escapeHtml(it.version_count)} version${it.version_count === 1 ? "" : "s"}
      ${it.last_fetch_at ? `<span class="archive-sep">·</span> last fetch ${escapeHtml(it.last_fetch_at)}` : ""}
    </p>
    ${snippetHtml ? `<p class="search-snippet">${snippetHtml}</p>` : ""}
  </a>
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

  chips.forEach((btn) => {
    btn.addEventListener("click", () => {
      const q = (btn.getAttribute("data-q") || "").trim();
      if (!q) return;
      input.value = q;
      input.focus();
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
  });
})();

