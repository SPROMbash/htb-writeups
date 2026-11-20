"""
Hook de MkDocs: genera los datos de las máquinas a partir del front-matter.

MkDocs ejecuta este archivo DURANTE `mkdocs build` (está declarado en mkdocs.yml,
clave `hooks:`), así que el workflow de GitHub Actions no necesita ningún paso extra.

Flujo:
  1. on_page_markdown: por cada machines/<maquina>/README.md lee su front-matter
     (title, tags, date, techniques) y lo normaliza.
  2. on_page_context: entrega a las plantillas un resumen (máquinas, estadísticas,
     línea de tiempo e índice para la paleta Ctrl+K).
  3. on_post_build: escribe también site/machines.json (por si quieres reutilizarlo).

Añadir una máquina = crear su carpeta con front-matter. Nada más.
"""

from __future__ import annotations

import json
import logging
import os
import re
from collections import Counter
from datetime import date, datetime

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

_machines: dict[str, dict] = {}
_summary: dict | None = None


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


# ---------------------------------------------------------------- eventos

def on_pre_build(config):
    # `mkdocs serve` reconstruye varias veces: empezamos siempre de cero.
    global _summary
    _machines.clear()
    _summary = None


def on_page_markdown(markdown, page, config, files):
    match = MACHINE_PAGE.match(page.file.src_uri)
    if not match:
        return markdown

    slug = match.group(1)
    meta = page.meta or {}
    tags = [str(t) for t in (meta.get("tags") or [])]
    where = page.file.src_uri

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

    data = {
        "slug": slug,
        "title": str(meta.get("title") or page.title or slug),
        "url": page.url,  # relativa a la raíz del sitio, p. ej. "responder/"
        "os": os_name or "Other",
        "difficulty": difficulty or "Unknown",
        "diff_class": DIFF_CLASS.get(difficulty or "", "unknown"),
        "platform": platform or "",
        "date": when.isoformat() if when else "",
        "month": when.strftime("%Y-%m") if when else "",
        "date_label": f"{when.day} {MESES[when.month - 1]} {when.year}" if when else "",
        "techniques": str(techniques),
    }
    _machines[slug] = data
    page.meta["htb"] = data  # lo usa la cabecera de badges del writeup
    return markdown


def _build_summary(nav) -> dict:
    machines = sorted(_machines.values(), key=lambda m: m["title"].lower())
    machines.sort(key=lambda m: m["date"], reverse=True)  # más recientes primero
    total = len(machines)

    def breakdown(key, order):
        counts = Counter(m[key] for m in machines)
        names = [o for o in order if counts[o]] + sorted(k for k in counts if k not in order and k)
        return [
            {"name": n, "count": counts[n], "pct": round(counts[n] * 100 / total, 1) if total else 0}
            for n in names
        ]

    # Línea de tiempo: todos los meses entre la primera y la última máquina
    # (incluidos los meses a cero, para que la escala temporal sea real).
    months = sorted({m["month"] for m in machines if m["month"]})
    timeline = []
    if months:
        y, mo = map(int, months[0].split("-"))
        y_end, mo_end = map(int, months[-1].split("-"))
        counts = Counter(m["month"] for m in machines if m["month"])
        while (y, mo) <= (y_end, mo_end):
            key = f"{y:04d}-{mo:02d}"
            timeline.append({"key": key, "label": f"{MESES[mo - 1]} {str(y)[2:]}", "count": counts[key]})
            y, mo = (y + 1, 1) if mo == 12 else (y, mo + 1)
        timeline = timeline[-12:]  # como mucho, el último año

    # Índice para la paleta Ctrl+K: máquinas + resto de páginas del menú.
    machine_urls = {m["url"] for m in machines}
    index = [
        {"kind": "Máquina", "label": m["title"], "url": m["url"],
         "meta": " · ".join(x for x in (m["os"], m["difficulty"]) if x),
         "keywords": m["techniques"]}
        for m in machines
    ]
    for p in getattr(nav, "pages", []) or []:
        if p.url in machine_urls:
            continue
        index.append({"kind": "Sección", "label": p.title or p.url, "url": p.url,
                      "meta": "", "keywords": ""})

    return {
        "machines": machines,
        "total": total,
        "latest": machines[0] if machines else None,
        "by_os": breakdown("os", OS_VALUES),
        "by_difficulty": breakdown("difficulty", DIFFICULTIES),
        "by_platform": breakdown("platform", PLATFORMS),
        "timeline": timeline,
        "timeline_max": max((t["count"] for t in timeline), default=0),
        # "</" escapado para que el JSON pueda ir dentro de <script> sin cerrarlo.
        "index_json": json.dumps(index, ensure_ascii=False).replace("</", r"<\/"),
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
    path = os.path.join(config["site_dir"], "machines.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(_summary["machines"], fh, ensure_ascii=False, indent=2)
