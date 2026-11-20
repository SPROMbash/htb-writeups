"""
Hook de MkDocs: genera los datos de las máquinas a partir del front-matter.

MkDocs ejecuta este archivo DURANTE `mkdocs build` (está declarado en mkdocs.yml,
clave `hooks:`), así que el workflow de GitHub Actions no necesita ningún paso extra.

Flujo (en el orden en que MkDocs llama a cada evento):
  1. on_files:         lee el front-matter de cada machines/<maquina>/README.md
                       (title, tags, date, techniques) y lo normaliza.
  2. on_nav:           agrupa las máquinas del menú lateral en "Máquinas" (y por año
                       cuando hay muchas), para que el menú no crezca sin límite.
  3. on_page_markdown: cuelga los datos de cada writeup en page.meta (badges).
  4. on_page_context:  entrega a las plantillas el resumen (rejilla, estadísticas,
                       línea de tiempo, página de etiquetas).
  5. on_post_build:    escribe machines.json y htb-index.json (índice de Ctrl+K).

Añadir una máquina = crear su carpeta con front-matter. Nada más.
"""

from __future__ import annotations

import json
import logging
import os
import re
from collections import Counter
from datetime import date, datetime

from mkdocs.structure.nav import Section
from mkdocs.structure.pages import Page
from mkdocs.utils.meta import get_data

log = logging.getLogger("mkdocs.hooks.machines")

# Valores reconocidos en los tags. El orden es el que se usa en filtros y stats.
OS_VALUES = ("Linux", "Windows", "FreeBSD", "OpenBSD", "Android", "Other")
DIFFICULTIES = ("Very Easy", "Easy", "Medium", "Hard", "Insane")
PLATFORMS = ("Starting Point", "Retired")
DIFF_CLASS = {
    "Very Easy": "very-easy",
    "Easy": "easy",
    "Medium": "medium",
    "Hard": "hard",
    "Insane": "insane",
}
MESES = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")

# Una máquina es cualquier <carpeta>/README.md directamente bajo docs_dir (machines/).
MACHINE_PAGE = re.compile(r"^([^/]+)/README\.md$")

# A partir de cuántas máquinas el menú lateral se subdivide por año.
NAV_GROUP_BY_YEAR_FROM = 30

_machines: dict[str, dict] = {}
_summary: dict | None = None
_index: list[dict] = []


def _pick(tags: list[str], allowed: tuple[str, ...]) -> str | None:
    lowered = {t.lower(): t for t in allowed}
    for tag in tags:
        if tag.lower() in lowered:
            return lowered[tag.lower()]
    return None


def _parse_date(value) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        for fmt in ("%Y-%m-%d", "%Y-%m"):
            try:
                return datetime.strptime(value.strip(), fmt).date()
            except ValueError:
                pass
    return None


def _machine_from_meta(slug: str, meta: dict, url: str, where: str) -> dict:
    tags = [str(t) for t in (meta.get("tags") or [])]
    os_name = _pick(tags, OS_VALUES)
    difficulty = _pick(tags, DIFFICULTIES)
    platform = _pick(tags, PLATFORMS)
    when = _parse_date(meta.get("date"))
    techniques = meta.get("techniques") or ""
    if isinstance(techniques, (list, tuple)):
        techniques = " · ".join(str(t) for t in techniques)

    # Avisos (no rompen el despliegue; con `mkdocs build --strict` sí fallan,
    # que es justo lo que queremos al revisar en local).
    if not os_name:
        log.warning("%s: falta un tag de SO (%s)", where, ", ".join(OS_VALUES))
    if not difficulty:
        log.warning("%s: falta un tag de dificultad (%s)", where, ", ".join(DIFFICULTIES))
    if meta.get("date") is not None and not when:
        log.warning("%s: 'date' no tiene formato AAAA-MM-DD", where)
    elif not when:
        log.info("%s: sin 'date'; no aparecerá en la línea de tiempo", where)

    return {
        "slug": slug,
        "title": str(meta.get("title") or slug),
        "url": url,  # relativa a la raíz del sitio, p. ej. "responder/"
        "os": os_name or "Other",
        "difficulty": difficulty or "Unknown",
        "diff_class": DIFF_CLASS.get(difficulty or "", "unknown"),
        "platform": platform or "",
        "date": when.isoformat() if when else "",
        "month": when.strftime("%Y-%m") if when else "",
        "year": str(when.year) if when else "Sin fecha",
        "date_label": f"{when.day} {MESES[when.month - 1]} {when.year}" if when else "",
        "techniques": str(techniques),
        "technique_list": [t.strip() for t in str(techniques).split("·") if t.strip()],
    }


# ---------------------------------------------------------------- eventos

def on_pre_build(config):
    # `mkdocs serve` reconstruye varias veces: empezamos siempre de cero.
    global _summary
    _machines.clear()
    _index.clear()
    _summary = None


def on_files(files, config):
    """Lee el front-matter de todas las máquinas antes de construir el menú."""
    for file in files.documentation_pages():
        match = MACHINE_PAGE.match(file.src_uri)
        if not match:
            continue
        try:
            _, meta = get_data(file.content_string)
        except Exception as exc:  # front-matter roto: avisamos y seguimos
            log.warning("%s: no se pudo leer el front-matter (%s)", file.src_uri, exc)
            meta = {}
        slug = match.group(1)
        _machines[slug] = _machine_from_meta(slug, meta or {}, file.url, file.src_uri)
    return files


def _flatten(items):
    for item in items:
        if isinstance(item, Page):
            yield item
        elif isinstance(item, Section):
            yield from _flatten(item.children)


def on_nav(nav, config, files):
    """Agrupa las máquinas del menú lateral bajo "Máquinas" (y por año si hay muchas).

    Junto con la función `navigation.prune` de Material, que solo pinta el grupo
    abierto, evita que cada página lleve dentro un menú con cientos de enlaces."""
    machine_pages, others = [], []
    for item in nav.items:
        # Sin `nav:` en mkdocs.yml, cada carpeta de máquina llega como una sección
        # con un único hijo (su README.md). Nos quedamos con la página.
        page = item
        if isinstance(item, Section) and len(item.children) == 1:
            page = item.children[0]
        if isinstance(page, Page) and MACHINE_PAGE.match(page.file.src_uri):
            machine_pages.append(page)
        else:
            others.append(item)
    if not machine_pages:
        return nav

    def info(p):
        return _machines.get(MACHINE_PAGE.match(p.file.src_uri).group(1), {})

    machine_pages.sort(key=lambda p: info(p).get("title", "").lower())
    machine_pages.sort(key=lambda p: info(p).get("date", ""), reverse=True)

    section = Section("Máquinas", [])
    if len(machine_pages) >= NAV_GROUP_BY_YEAR_FROM:
        years: dict[str, list] = {}
        for p in machine_pages:
            years.setdefault(info(p).get("year", "Sin fecha"), []).append(p)
        for year in sorted(years, reverse=True):
            sub = Section(f"{year} ({len(years[year])})", years[year])
            sub.parent = section
            for p in years[year]:
                p.parent = sub
            section.children.append(sub)
    else:
        section.children = machine_pages
        for p in machine_pages:
            p.parent = section

    # Orden: Inicio, Máquinas, y el resto de páginas tal cual estaban.
    position = 1 if others and isinstance(others[0], Page) and others[0].is_homepage else 0
    others.insert(position, section)
    nav.items = others

    # Recalcular la lista plana y los enlaces anterior/siguiente del pie.
    nav.pages = list(_flatten(nav.items))
    for i, p in enumerate(nav.pages):
        p.previous_page = nav.pages[i - 1] if i > 0 else None
        p.next_page = nav.pages[i + 1] if i + 1 < len(nav.pages) else None
    return nav


def on_page_markdown(markdown, page, config, files):
    match = MACHINE_PAGE.match(page.file.src_uri)
    if match and match.group(1) in _machines:
        page.meta["htb"] = _machines[match.group(1)]  # lo usa la cabecera de badges
    return markdown


def _timeline(machines: list[dict]) -> dict:
    """Barras por mes (hasta 12 meses), por trimestre (hasta 4 años) o por año.

    Siempre se incluyen los periodos a cero para que la escala temporal sea real."""
    dated = [m for m in machines if m["month"]]
    if not dated:
        return {"unit": "", "buckets": [], "max": 0}
    first = min(m["month"] for m in dated)
    last = max(m["month"] for m in dated)
    y0, m0 = map(int, first.split("-"))
    y1, m1 = map(int, last.split("-"))
    months_span = (y1 - y0) * 12 + (m1 - m0) + 1

    if months_span <= 12:
        unit = "mes"
        key = lambda m: m["month"]
        keys, (y, mo) = [], (y0, m0)
        while (y, mo) <= (y1, m1):
            keys.append(f"{y:04d}-{mo:02d}")
            y, mo = (y + 1, 1) if mo == 12 else (y, mo + 1)

        def label(k, i):
            yy, mm = map(int, k.split("-"))
            return MESES[mm - 1], (str(yy) if i == 0 or mm == 1 else ""), f"{MESES[mm - 1]} {yy}"
    elif months_span <= 48:
        unit = "trimestre"
        key = lambda m: f"{m['month'][:4]}-T{(int(m['month'][5:]) - 1) // 3 + 1}"
        keys, (y, q) = [], (y0, (m0 - 1) // 3 + 1)
        while (y, q) <= (y1, (m1 - 1) // 3 + 1):
            keys.append(f"{y:04d}-T{q}")
            y, q = (y + 1, 1) if q == 4 else (y, q + 1)

        def label(k, i):
            yy, qq = k.split("-")
            return qq, (yy if i == 0 or qq == "T1" else ""), f"{qq} {yy}"
    else:
        unit = "año"
        key = lambda m: m["month"][:4]
        keys = [str(y) for y in range(y0, y1 + 1)]

        def label(k, i):
            return k, "", k

    counts = Counter(key(m) for m in dated)
    buckets = []
    for i, k in enumerate(keys):
        short, sub, full = label(k, i)
        buckets.append({"key": k, "label": short, "sub": sub, "full": full, "count": counts[k]})
    return {"unit": unit, "buckets": buckets, "max": max(b["count"] for b in buckets)}


def _build_summary(nav) -> dict:
    machines = sorted(_machines.values(), key=lambda m: m["title"].lower())
    machines.sort(key=lambda m: m["date"], reverse=True)  # más recientes primero
    total = len(machines)

    def breakdown(key, order):
        counts = Counter(m[key] for m in machines)
        names = [o for o in order if counts[o]] + sorted(k for k in counts if k not in order and k)
        return [
            {"name": n, "count": counts[n], "pct": round(counts[n] * 100 / total, 1) if total else 0,
             "diff_class": DIFF_CLASS.get(n, "unknown")}
            for n in names
        ]

    by_os = breakdown("os", OS_VALUES)
    by_difficulty = breakdown("difficulty", DIFFICULTIES)

    # Matriz SO × dificultad para la página de etiquetas
    pair = Counter((m["os"], m["difficulty"]) for m in machines)
    matrix_max = max(pair.values(), default=0)
    matrix = [
        {"os": o["name"], "cells": [
            {"difficulty": d["name"], "count": pair[(o["name"], d["name"])],
             "level": (round(4 * pair[(o["name"], d["name"])] / matrix_max) if matrix_max else 0)}
            for d in by_difficulty]}
        for o in by_os
    ]

    # Técnicas más frecuentes (nube de etiquetas), con tamaño en 4 niveles
    tech = Counter(t for m in machines for t in m["technique_list"])
    top = tech.most_common(60)
    tmax = top[0][1] if top else 1
    techniques = sorted(
        ({"name": n, "count": c, "level": 1 + round(3 * (c - 1) / max(tmax - 1, 1))} for n, c in top),
        key=lambda t: t["name"].lower(),
    )

    # Índice para la paleta Ctrl+K: máquinas + resto de páginas del menú.
    machine_urls = {m["url"] for m in machines}
    _index[:] = [
        {"kind": "Máquina", "label": m["title"], "url": m["url"],
         "meta": " · ".join(x for x in (m["os"], m["difficulty"]) if x),
         "keywords": m["techniques"]}
        for m in machines
    ]
    for p in getattr(nav, "pages", []) or []:
        if p.url in machine_urls:
            continue
        _index.append({"kind": "Sección", "label": p.title or p.url, "url": p.url,
                       "meta": "", "keywords": ""})

    return {
        "machines": machines,
        "total": total,
        "latest": machines[0] if machines else None,
        "by_os": by_os,
        "by_difficulty": by_difficulty,
        "by_platform": breakdown("platform", PLATFORMS),
        "timeline": _timeline(machines),
        "matrix": matrix,
        "techniques": techniques,
        "technique_total": len(tech),
        "page_size": 24,  # tarjetas visibles antes de "Mostrar más"
    }


def on_page_context(context, page, config, nav):
    # Aquí ya se han leído TODAS las páginas, así que el resumen está completo.
    global _summary
    if _summary is None:
        _summary = _build_summary(nav)
    context["htb"] = _summary
    return context


def on_post_build(config):
    if _summary is None:
        return
    site = config["site_dir"]
    public = [{k: v for k, v in m.items() if k != "technique_list"} for m in _summary["machines"]]
    with open(os.path.join(site, "machines.json"), "w", encoding="utf-8") as fh:
        json.dump(public, fh, ensure_ascii=False, indent=2)
    # La paleta Ctrl+K lo descarga una sola vez (en vez de ir dentro de cada página).
    with open(os.path.join(site, "htb-index.json"), "w", encoding="utf-8") as fh:
        json.dump(_index, fh, ensure_ascii=False, separators=(",", ":"))
