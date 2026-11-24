'use strict';

(() => {
  const sidebar = document.getElementById('sidebar');
  const dialog = document.getElementById('menu-dialog');
  const toggle = document.getElementById('menu-toggle');
  const close = document.getElementById('menu-close');
  const compact = window.matchMedia('(max-width: 1180px)');
  const preference = 'java-backend-roadmap-sidebar';
  let folded = false;
  try {
    folded = localStorage.getItem(preference) === 'folded';
  } catch {}

  function updateToggle() {
    const expanded = compact.matches ? dialog.open : !folded;
    toggle.setAttribute('aria-expanded', String(expanded));
    toggle.querySelector('.menu-label').textContent = expanded ? '목차 접기' : '목차 열기';
    document.body.classList.toggle('sidebar-folded', !compact.matches && folded);
  }

  function updateLayout() {
    const focusWasInside = sidebar.contains(document.activeElement);
    if (dialog.open) dialog.close();
    if (compact.matches) {
      toggle.setAttribute('aria-haspopup', 'dialog');
      dialog.append(sidebar);
    } else {
      toggle.removeAttribute('aria-haspopup');
      dialog.after(sidebar);
    }
    updateToggle();
    if (focusWasInside) toggle.focus({preventScroll: true});
  }

  toggle.hidden = false;
  updateLayout();
  compact.addEventListener('change', updateLayout);
  toggle.addEventListener('click', () => {
    if (compact.matches) {
      dialog.showModal();
      close.focus({preventScroll: true});
    } else {
      folded = !folded;
      try {
        localStorage.setItem(preference, folded ? 'folded' : 'expanded');
      } catch {}
    }
    updateToggle();
  });

  function dismissDrawer() {
    if (!dialog.open) return;
    dialog.close();
    updateToggle();
    toggle.focus({preventScroll: true});
  }

  close.addEventListener('click', dismissDrawer);
  dialog.addEventListener('cancel', event => {
    event.preventDefault();
    dismissDrawer();
  });
  dialog.addEventListener('close', updateToggle);
  let startedOnBackdrop = false;
  dialog.addEventListener('pointerdown', event => {
    startedOnBackdrop = event.target === dialog;
  });
  dialog.addEventListener('click', event => {
    if (startedOnBackdrop && event.target === dialog) dismissDrawer();
  });
  sidebar.addEventListener('click', event => {
    const link = event.target.closest('a[href]');
    if (!link || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    dismissDrawer();
    const href = link.getAttribute('href');
    if (!href.startsWith('#')) return;
    const target = document.getElementById(href.slice(1));
    if (!target) return;
    if (target.matches('details')) target.open = true;
    requestAnimationFrame(() => {
      const heading = target.querySelector('h1, h2, summary') || target;
      if (!heading.hasAttribute('tabindex') && !heading.matches('summary')) heading.tabIndex = -1;
      heading.focus({preventScroll: true});
    });
  });
  window.addEventListener('hashchange', dismissDrawer);
  window.addEventListener('pageshow', dismissDrawer);

  document.querySelector('.skip').addEventListener('click', event => {
    event.preventDefault();
    const main = document.getElementById('main');
    main.focus({preventScroll: true});
    main.scrollIntoView({block: 'start'});
  });

  const theme = document.getElementById('theme-toggle');
  function updateThemeButton() {
    const dark = document.documentElement.dataset.theme === 'dark';
    theme.textContent = dark ? '라이트 모드' : '다크 모드';
    theme.setAttribute('aria-label', theme.textContent + '로 전환');
  }
  theme.addEventListener('click', () => {
    const root = document.documentElement;
    root.dataset.theme = root.dataset.theme === 'dark' ? 'light' : 'dark';
    try {
      localStorage.setItem(ROADMAP_THEME_KEY, root.dataset.theme);
    } catch {}
    updateThemeButton();
  });
  updateThemeButton();

  const search = document.getElementById('nav-search');
  if (!search) return;
  const results = document.getElementById('nav-results');
  const groups = sidebar.querySelectorAll('.nav-group');
  const sources = document.querySelector('.pitfall-area')
    ? document.querySelectorAll('.pitfall-area .lesson-toc li > a')
    : sidebar.querySelectorAll('.nav-group a');
  search.addEventListener('input', () => {
    const query = search.value.trim().toLowerCase();
    const matches = query ? Array.from(sources).filter(link =>
      (link.textContent + ' ' + link.getAttribute('href')).toLowerCase().includes(query)
    ) : [];
    for (const group of groups) group.hidden = Boolean(query);
    results.hidden = !query;
    results.replaceChildren(...matches.map(link => link.cloneNode(true)));
    document.getElementById('nav-count').textContent = query
      ? (matches.length ? matches.length + '개 항목' : '검색 결과가 없습니다.') : '';
  });
})();
