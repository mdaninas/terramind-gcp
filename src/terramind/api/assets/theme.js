"use strict";

(() => {
  const storageKey = "terramind.theme";
  const choices = new Set(["system", "light", "dark"]);
  const systemTheme = window.matchMedia("(prefers-color-scheme: dark)");
  let preference = "system";
  let memoryOnlyPreference = false;

  const readPreference = () => {
    try {
      const stored = window.localStorage.getItem(storageKey);
      return choices.has(stored) ? stored : "system";
    } catch {
      return preference;
    }
  };

  const applyTheme = () => {
    const dark = preference === "dark" || (preference === "system" && systemTheme.matches);
    document.documentElement.dataset.theme = dark ? "dark" : "light";
    document.documentElement.dataset.themePreference = preference;
    document.querySelectorAll("[data-theme-select]").forEach(control => {
      control.value = preference;
    });
  };

  preference = readPreference();
  applyTheme();

  document.addEventListener("DOMContentLoaded", () => {
    applyTheme();
    document.querySelectorAll("[data-theme-select]").forEach(control => {
      control.disabled = false;
      control.addEventListener("change", () => {
        preference = choices.has(control.value) ? control.value : "system";
        try {
          window.localStorage.setItem(storageKey, preference);
          memoryOnlyPreference = false;
        } catch {
          // Theme selection still works when browser storage is unavailable.
          memoryOnlyPreference = true;
        }
        applyTheme();
      });
    });
  });

  systemTheme.addEventListener("change", () => {
    if (preference === "system") applyTheme();
  });

  window.addEventListener("pageshow", () => {
    if (!memoryOnlyPreference) preference = readPreference();
    applyTheme();
  });

  window.addEventListener("storage", event => {
    if (event.key === storageKey || event.key === null) {
      preference = choices.has(event.newValue) ? event.newValue : "system";
      memoryOnlyPreference = false;
      applyTheme();
    }
  });
})();
