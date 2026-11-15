"use client";

import { useSyncExternalStore } from "react";
import { Moon, Sun } from "lucide-react";
import { IconButton } from "./icon-button";

const KEY = "pulsr:theme";
const EVENT = "pulsr-theme-changed";
const snapshot = () => document.documentElement.dataset.theme === "light";
const serverSnapshot = () => false;

function subscribe(callback: () => void) {
  const storage = (event: StorageEvent) => {
    if (event.key === KEY || event.key === null) {
      document.documentElement.dataset.theme = event.newValue === "light" ? "light" : "dark";
      callback();
    }
  };
  window.addEventListener(EVENT, callback);
  window.addEventListener("storage", storage);
  return () => {
    window.removeEventListener(EVENT, callback);
    window.removeEventListener("storage", storage);
  };
}

export function ThemeToggle() {
  const light = useSyncExternalStore(subscribe, snapshot, serverSnapshot);
  const label = light ? "Switch to dark mode" : "Switch to light mode";
  return <IconButton label={label} aria-pressed={light} onClick={() => {
    const theme = light ? "dark" : "light";
    document.documentElement.dataset.theme = theme;
    try { localStorage.setItem(KEY, theme); } catch { /* Mode still works if storage is disabled. */ }
    window.dispatchEvent(new Event(EVENT));
  }}>
    {light ? <Moon size={18} aria-hidden="true" /> : <Sun size={18} aria-hidden="true" />}
  </IconButton>;
}
