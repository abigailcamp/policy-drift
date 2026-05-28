(() => {
  const modal = document.getElementById("notify-modal");
  const form = document.getElementById("notify-form");
  const emailInput = document.getElementById("notify-email");
  const instrumentInput = document.getElementById("notify-instrument");
  const messageEl = document.getElementById("notify-message");
  const submitBtn = document.getElementById("notify-submit");

  if (!modal || !form || !emailInput || !instrumentInput || !messageEl || !submitBtn) return;

  function openModal(instrumentSlug) {
    instrumentInput.value = instrumentSlug;
    messageEl.textContent = "";
    submitBtn.disabled = false;
    try {
      modal.showModal();
      emailInput.focus();
    } catch {
      // If <dialog> unsupported, just bail silently.
    }
  }

  document.addEventListener("click", (e) => {
    const a = e.target && e.target.closest ? e.target.closest(".notify-link") : null;
    if (!a) return;
    e.preventDefault();
    const slug = a.getAttribute("data-instrument");
    if (!slug) return;
    openModal(slug);
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const payload = {
      instrument_slug: instrumentInput.value,
      email: emailInput.value.trim(),
    };

    if (!payload.instrument_slug || !payload.email) return;
    submitBtn.disabled = true;
    messageEl.textContent = "Saving…";

    try {
      const resp = await fetch("/subscribe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) {
        messageEl.textContent = data.detail || "Could not subscribe.";
        submitBtn.disabled = false;
        return;
      }
      messageEl.textContent = data.message || "Subscribed.";
      setTimeout(() => {
        try {
          modal.close();
        } catch {}
      }, 650);
    } catch {
      messageEl.textContent = "Network error.";
      submitBtn.disabled = false;
    }
  });
})();

