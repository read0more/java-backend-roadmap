'use strict';

const ROADMAP_STORAGE_PREFIX = 'java-backend-roadmap-';
const ROADMAP_THEME_KEY = `${ROADMAP_STORAGE_PREFIX}theme`;

function readRoadmapStorage(key) {
  const saved = localStorage.getItem(key);
  if (saved !== null || !key.startsWith(ROADMAP_STORAGE_PREFIX)) return saved;

  // Read progress and theme data saved before the site was renamed.
  const previousKey = 'kyh-roadmap-' + key.slice(ROADMAP_STORAGE_PREFIX.length);
  return localStorage.getItem(previousKey);
}

try {
  document.documentElement.dataset.theme = readRoadmapStorage(ROADMAP_THEME_KEY) || 'light';
} catch {}
