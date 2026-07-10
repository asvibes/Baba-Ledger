// Light/dark theme, persisted (PRD 12.2), plus sidebar view switching.

(function () {
  const root = document.documentElement;
  const toggle = document.getElementById("theme-toggle");
  const STORAGE_KEY = "babas-ledger-theme";

  function applyTheme(theme) {
    if (theme === "dark") {
      root.setAttribute("data-theme", "dark");
    } else {
      root.removeAttribute("data-theme");
    }
  }

  let stored = null;
  try {
    stored = localStorage.getItem(STORAGE_KEY);
  } catch (e) {
    // localStorage can be unavailable (privacy mode, file:// in some
    // browsers); fall back to system preference for this session only.
  }

  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  const initial = stored || (prefersDark ? "dark" : "light");
  applyTheme(initial);

  toggle.addEventListener("click", () => {
    const isDark = root.getAttribute("data-theme") === "dark";
    const next = isDark ? "light" : "dark";
    applyTheme(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch (e) {
      // Non-fatal: theme just won't persist across reloads this session.
    }
  });
})();

// --- Sidebar navigation (PRD 12.2: Dashboard, Analyze, About) ---
(function () {
  const navItems = document.querySelectorAll(".nav-item");
  const views = document.querySelectorAll(".view");

  navItems.forEach((item) => {
    item.addEventListener("click", () => {
      navItems.forEach((n) => n.classList.remove("is-active"));
      item.classList.add("is-active");

      const target = item.dataset.view;
      views.forEach((view) => {
        view.classList.toggle("is-active", view.id === `view-${target}`);
      });
    });
  });
})();