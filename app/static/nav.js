(() => {
  const header = document.querySelector(".site-topbar");
  const btn = document.querySelector(".nav-toggle");
  const menu = document.getElementById("topbar-menu");
  if (!header || !btn || !menu) return;

  function close() {
    header.classList.remove("is-open");
    btn.setAttribute("aria-expanded", "false");
  }

  btn.addEventListener("click", () => {
    const isOpen = header.classList.toggle("is-open");
    btn.setAttribute("aria-expanded", String(isOpen));
  });

  // Close on navigation.
  menu.addEventListener("click", (e) => {
    const a = e.target && e.target.closest ? e.target.closest("a") : null;
    if (a) close();
  });

  // Close if viewport changes back to desktop.
  window.addEventListener("resize", () => {
    if (window.matchMedia("(min-width: 768px)").matches) close();
  });
})();

