---
title: Sobre mí
hide:
  - toc
---

<!--
  Página de presentación. Sustituye lo que está [ENTRE CORCHETES] por tus datos.
  Todo lo demás describe el proyecto, no a ti.
-->

<div class="htb-profile" markdown>
<div class="htb-profile__avatar" aria-hidden="true">[INICIALES]</div>
<div class="htb-profile__body" markdown>
<p class="htb-eyebrow">whoami</p>

# [TU NOMBRE]

[UNA LÍNEA SOBRE TI: a qué te dedicas o qué estudias, y qué te interesa de la ciberseguridad.]

<ul class="htb-profile__links">
  <li><strong>GitHub</strong> · [ENLACE A TU GITHUB]</li>
  <li><strong>LinkedIn</strong> · [ENLACE A TU LINKEDIN]</li>
  <li><strong>Otro enlace</strong> · [OPCIONAL: web, blog o contacto]</li>
</ul>
</div>
</div>

## El proyecto

Esta web reúne mis writeups de máquinas de **Hack The Box**: solo de *Starting Point*
y de máquinas retiradas, que son las que se pueden publicar. Cada writeup sigue la misma
estructura, de la enumeración inicial a la escalada de privilegios, y nunca incluye flags,
hashes ni contraseñas reales.

<div class="grid cards" markdown>

-   :material-file-document-multiple-outline: **Una sola fuente de verdad**

    Cada máquina es un archivo Markdown en `machines/`. GitHub y esta web leen los mismos archivos.

-   :material-chart-box-outline: **Datos generados, no escritos a mano**

    La rejilla y las estadísticas de la portada salen del front-matter de cada writeup durante el build.

-   :material-rocket-launch-outline: **Publicar es hacer push**

    GitHub Actions construye la web con MkDocs Material y la despliega en GitHub Pages.

</div>

[:material-cog-outline: Cómo está hecha esta web](how-it-works.md){ .md-button }
[:material-view-grid-outline: Ver las máquinas](index.md){ .md-button .md-button--primary }
