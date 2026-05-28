(() => {
  const wrap = document.querySelector(".nav-admin");
  const btn = document.querySelector(".nav-admin-btn");
  const menu = document.getElementById("admin-menu");
  if (!wrap || !btn || !menu) return;

  function close() {
    wrap.classList.remove("is-open");
    btn.setAttribute("aria-expanded", "false");
  }

  btn.addEventListener("click", (e) => {
    e.preventDefault();
    const isOpen = wrap.classList.toggle("is-open");
    btn.setAttribute("aria-expanded", String(isOpen));
  });

  document.addEventListener("click", (e) => {
    if (wrap.contains(e.target)) return;
    close();
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") close();
  });
})();

