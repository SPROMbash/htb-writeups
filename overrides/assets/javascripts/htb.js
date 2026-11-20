/* HTB Writeups · interacción del rediseño (vanilla, sin dependencias)
 *
 * Material usa "navegación instantánea": al cambiar de página no recarga, solo
 * sustituye el contenido. Por eso hay dos partes:
 *   - setupOnce():  lo que vive toda la sesión (paleta Ctrl+K, botón en la cabecera)
 *   - setupPage():  lo que hay que enganchar en cada página nueva (filtros, scroll...)
 * `document$` es el observable de Material que avisa cada vez que hay página nueva.
 */
(() => {
  'use strict';

  const $ = (sel, ctx = document) => ctx.querySelector(sel);
  const $$ = (sel, ctx = document) => [...ctx.querySelectorAll(sel)];
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  const isMac = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const norm = (s) => String(s).toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');

  /* Raíz del sitio, calculada una vez: __config.base es la ruta relativa
     de la página inicial a la raíz (p. ej. "." o ".."). */
  const siteRoot = (() => {
    try {
      const cfg = JSON.parse($('#__config').textContent);
      return new URL(cfg.base.replace(/\/?$/, '/'), location.href);
    } catch (e) {
      return new URL('./', location.href);
    }
  })();

  /* Navega como si se pulsara un enlace normal: así la navegación instantánea
     de Material lo intercepta y no recarga la página entera. */
  const go = (url) => {
    const a = document.createElement('a');
    a.href = url.href;
    a.style.display = 'none';
    ($('.md-content') || document.body).appendChild(a);
    a.click();
    // Material procesa el clic de forma asíncrona: si quitamos el enlace al
    // instante, cambia el contenido pero no la URL. Lo retiramos un poco después.
    setTimeout(() => a.remove(), 2000);
  };

  /* =================== PALETA DE COMANDOS (Ctrl/Cmd+K) =================== */
  function setupPalette() {
    const dialog = $('#htb-palette');
    if (!dialog || typeof dialog.showModal !== 'function') return null;
    const input = $('#htb-palette-input');
    const list = $('#htb-palette-list');

    /* El índice (htb-index.json) lo genera el hook. Se descarga UNA vez, en un
       momento libre tras cargar la página, en vez de ir dentro de cada página. */
    const actions = [{ kind: 'Acción', label: 'Cambiar tema claro / oscuro', meta: '', hay: 'tema claro oscuro modo dark light theme', run: toggleTheme }];
    let items = actions.slice();
    let loading = null;
    const loadIndex = () => loading || (loading = fetch(new URL('htb-index.json', siteRoot))
      .then((r) => (r.ok ? r.json() : []))
      .catch(() => [])
      .then((data) => {
        items = data.map((i) => ({ ...i, href: new URL(i.url, siteRoot), hay: norm(`${i.label} ${i.meta} ${i.keywords}`) })).concat(actions);
        if (dialog.open) draw();
      }));
    (window.requestIdleCallback || ((fn) => setTimeout(fn, 1500)))(loadIndex);

    let shown = [];
    let sel = 0;
    let opener = null;
    let pending = null;

    const highlight = (label, q) => {
      if (!q) return esc(label);
      const i = norm(label).indexOf(q);
      if (i < 0) return esc(label);
      return esc(label.slice(0, i)) + '<mark>' + esc(label.slice(i, i + q.length)) + '</mark>' + esc(label.slice(i + q.length));
    };

    const draw = () => {
      const raw = input.value.trim();
      const q = norm(raw);
      const words = q.split(/\s+/).filter(Boolean);
      shown = items.filter((i) => words.every((w) => i.hay.includes(w)));
      if (raw) shown.push({ kind: 'Texto', label: `Buscar «${raw}» en todos los writeups`, meta: 'buscador', run: () => openSearch(raw) });
      sel = Math.min(sel, Math.max(0, shown.length - 1));
      list.innerHTML = shown.length
        ? shown.map((i, n) => `<li role="option" id="htb-opt-${n}" data-n="${n}" aria-selected="${n === sel}">
              <span class="htb-palette__kind">${esc(i.kind)}</span>
              <span class="htb-palette__label">${i.kind === 'Texto' ? esc(i.label) : highlight(i.label, words[0] || '')}</span>
              <span class="htb-palette__meta">${esc(i.meta || '')}</span></li>`).join('')
        : `<li aria-disabled="true">${items.length <= actions.length ? 'Cargando índice…' : 'Escribe para buscar'}</li>`;
      input.setAttribute('aria-activedescendant', shown.length ? `htb-opt-${sel}` : '');
      const active = list.querySelector('[aria-selected="true"]');
      if (active) active.scrollIntoView({ block: 'nearest' });
    };

    const choose = (item) => {
      if (!item) return;
      pending = item;
      dialog.close();  // la acción se ejecuta en el evento 'close', con el diálogo ya cerrado
    };

    const open = (prefill = '') => {
      if (dialog.open) return;
      loadIndex();
      opener = document.activeElement;
      input.value = prefill;
      sel = 0;
      draw();
      dialog.showModal();
      input.focus();
    };

    input.addEventListener('input', () => { sel = 0; draw(); });
    input.addEventListener('keydown', (e) => {
      if (!shown.length) return;
      if (e.key === 'ArrowDown') { e.preventDefault(); sel = (sel + 1) % shown.length; draw(); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); sel = (sel - 1 + shown.length) % shown.length; draw(); }
      else if (e.key === 'Enter') { e.preventDefault(); choose(shown[sel]); }
    });
    list.addEventListener('click', (e) => {
      const li = e.target.closest('li[data-n]');
      if (li) choose(shown[Number(li.dataset.n)]);
    });
    list.addEventListener('mousemove', (e) => {
      const li = e.target.closest('li[data-n]');
      if (li && Number(li.dataset.n) !== sel) { sel = Number(li.dataset.n); draw(); }
    });
    // Clic en el fondo oscuro = cerrar
    dialog.addEventListener('click', (e) => { if (e.target === dialog) dialog.close(); });
    dialog.addEventListener('close', () => {
      const item = pending;
      pending = null;
      if (!item) { if (opener && document.contains(opener)) opener.focus(); return; }
      // Navegar con el modal aún abierto confunde a la navegación instantánea
      // (cambia el contenido pero no la URL); esperamos al siguiente ciclo.
      setTimeout(() => (item.run ? item.run() : go(item.href)), 0);
    });

    document.addEventListener('keydown', (e) => {
      if ((e.ctrlKey || e.metaKey) && !e.altKey && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        e.stopPropagation();
        if (dialog.open) dialog.close();
        else open();
      }
    }, true);

    return { open };
  }

  /* Abre el buscador de texto completo de Material con una consulta. */
  function openSearch(query) {
    const toggle = $('[data-md-toggle="search"]');
    const field = $('[data-md-component="search-query"]');
    if (!toggle || !field) return;
    toggle.checked = true;
    toggle.dispatchEvent(new Event('change'));
    setTimeout(() => {
      field.value = query;
      field.focus();
      field.dispatchEvent(new Event('input', { bubbles: true }));
      field.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true }));
    }, 50);
  }

  /* Cambia el tema pulsando el propio interruptor de Material (así lo recuerda). */
  function toggleTheme() {
    const inputs = $$('input[name="__palette"]');
    if (!inputs.length) return;
    const current = inputs.findIndex((i) => i.checked);
    const next = inputs[(current + 1) % inputs.length];
    const label = $(`label[for="${next.id}"]`) || $(`label[for="${inputs[current]?.id}"]`);
    if (label) label.click();
  }

  /* Botón "Ctrl K" junto al buscador de la cabecera (la cabecera no se recarga). */
  function setupHeaderButton(palette) {
    if (!palette || $('.htb-kbtn')) return;
    const anchor = $('.md-header__inner .md-search') || $('.md-header__source');
    if (!anchor) return;
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'htb-kbtn';
    btn.setAttribute('aria-label', 'Saltar a una máquina o sección');
    btn.title = 'Saltar a una máquina o sección';
    btn.innerHTML = `<kbd>${isMac ? '⌘' : 'Ctrl'}</kbd><kbd>K</kbd>`;
    btn.addEventListener('click', () => palette.open());
    anchor.after(btn);
  }

  /* =================== POR PÁGINA =================== */

  // Filtros en vivo de la portada (+ paginación "Mostrar más" y filtros desde la URL)
  function setupFilters() {
    const grid = $('.htb-grid');
    if (!grid) return;
    const cards = $$('.htb-card', grid);
    const empty = $('[data-htb-empty]', grid);
    const count = $('[data-htb-count]');
    const search = $('#htb-filter-q');
    const more = $('[data-htb-more]');
    const pageSize = Number(more && more.dataset.pageSize) || 24;
    const state = { os: '', difficulty: '', q: '' };
    let limit = pageSize;

    const plural = (n) => `${n} máquina${n === 1 ? '' : 's'}`;
    const apply = () => {
      const filtered = Boolean(state.os || state.difficulty || state.q);
      let matches = 0;
      cards.forEach((card) => {
        const ok = (!state.os || card.dataset.os === state.os) &&
          (!state.difficulty || card.dataset.difficulty === state.difficulty) &&
          (!state.q || norm(card.dataset.search).includes(state.q));
        const show = ok && matches < limit;
        if (ok) matches += 1;
        card.hidden = !show;
        if (show) card.classList.add('is-in');
      });
      const shown = Math.min(matches, limit);
      if (empty && cards.length) empty.hidden = matches > 0;
      if (count) {
        count.textContent = shown < matches
          ? `Mostrando ${shown} de ${plural(matches)}${filtered ? ` · ${cards.length} en total` : ''}`
          : `${matches} de ${plural(cards.length)}`;
      }
      if (more) {
        const rest = matches - shown;
        more.hidden = rest <= 0;
        more.querySelector('button').textContent = `Mostrar ${Math.min(pageSize, rest)} más · quedan ${rest}`;
      }
    };
    const refilter = () => { limit = pageSize; apply(); };

    const press = (group, value) => {
      const chips = $$('.htb-chip', group);
      const target = chips.find((c) => c.dataset.value === value) || chips[0];
      chips.forEach((c) => c.setAttribute('aria-pressed', String(c === target)));
      return target.dataset.value;
    };

    $$('[data-htb-filter]').forEach((group) => {
      const key = group.dataset.htbFilter;
      group.addEventListener('click', (e) => {
        const chip = e.target.closest('.htb-chip');
        if (!chip) return;
        state[key] = press(group, chip.dataset.value);
        refilter();
      });
    });
    if (search) search.addEventListener('input', () => { state.q = norm(search.value.trim()); refilter(); });

    if (more) more.querySelector('button').addEventListener('click', () => {
      // Al mostrar más, el foco pasa a la primera tarjeta nueva (útil con teclado).
      const before = cards.filter((c) => !c.hidden).length;
      limit += pageSize;
      apply();
      const next = cards.filter((c) => !c.hidden)[before];
      if (next) next.focus({ preventScroll: true });
    });

    const reset = $('[data-htb-reset]', grid);
    if (reset) reset.addEventListener('click', () => {
      state.os = state.difficulty = state.q = '';
      if (search) search.value = '';
      $$('[data-htb-filter]').forEach((g) => press(g, ''));
      refilter();
    });

    // Filtros que llegan en la URL desde Etiquetas o los badges: ?os=Linux&difficulty=Hard&q=ssh
    const params = new URLSearchParams(location.search);
    $$('[data-htb-filter]').forEach((group) => {
      const key = group.dataset.htbFilter;
      if (params.has(key)) state[key] = press(group, params.get(key));
    });
    if (params.has('q') && search) {
      search.value = params.get('q');
      state.q = norm(search.value.trim());
    }
    apply();
  }

  // Aparición suave al hacer scroll (solo si se permite el movimiento)
  let revealObserver = null;
  function setupReveal() {
    const targets = $$('.htb-reveal:not(.is-in)');
    if (reduceMotion.matches || !('IntersectionObserver' in window)) {
      targets.forEach((el) => el.classList.add('is-in'));
      return;
    }
    document.documentElement.classList.add('htb-motion');
    if (revealObserver) revealObserver.disconnect();
    revealObserver = new IntersectionObserver((entries, obs) => {
      entries.forEach((entry, i) => {
        if (!entry.isIntersecting) return;
        const el = entry.target;
        el.style.transitionDelay = `${Math.min(i, 6) * 60}ms`;
        el.classList.add('is-in');
        obs.unobserve(el);
        // Tras aparecer, devolvemos al elemento sus transiciones normales de hover.
        setTimeout(() => { el.style.transitionDelay = ''; el.classList.remove('htb-reveal'); }, 900);
      });
    }, { threshold: 0.08, rootMargin: '0px 0px -40px 0px' });
    targets.forEach((el) => revealObserver.observe(el));
  }

  // Barra de progreso de lectura en los writeups
  let progressBar = null;
  let onScroll = null;
  function setupProgress() {
    const header = $('.md-header');
    if (!header) return;
    if (!progressBar) {
      progressBar = document.createElement('div');
      progressBar.className = 'htb-progress';
      progressBar.setAttribute('aria-hidden', 'true');
      header.appendChild(progressBar);
    }
    if (onScroll) window.removeEventListener('scroll', onScroll);
    const isWriteup = Boolean($('.htb-meta'));
    progressBar.hidden = !isWriteup;
    if (!isWriteup) return;
    const article = $('.md-content__inner');
    let ticking = false;
    onScroll = () => {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(() => {
        const rect = article.getBoundingClientRect();
        const total = rect.height - window.innerHeight;
        const p = total > 0 ? Math.min(1, Math.max(0, -rect.top / total)) : 1;
        progressBar.style.setProperty('--p', p.toFixed(3));
        ticking = false;
      });
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
  }

  function setupPage(palette) {
    $$('[data-htb-palette]').forEach((btn) => {
      btn.addEventListener('click', () => palette && palette.open());
    });
    $$('.htb-kbd-shortcut').forEach((k) => { k.textContent = isMac ? '⌘ K' : 'Ctrl K'; });
    setupFilters();
    setupReveal();
    setupProgress();
  }

  /* =================== ARRANQUE =================== */
  const palette = setupPalette();
  setupHeaderButton(palette);
  if (window.document$ && typeof window.document$.subscribe === 'function') {
    window.document$.subscribe(() => setupPage(palette));
  } else {
    document.addEventListener('DOMContentLoaded', () => setupPage(palette));
  }
})();
