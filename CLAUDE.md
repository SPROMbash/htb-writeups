# CLAUDE.md — Agente de publicación de htb-writeups

Instrucciones permanentes para Claude Code al trabajar en este repositorio.

## Qué es este repo
`htb-writeups`: colección pública de writeups de máquinas de Hack The Box
(solo Starting Point y máquinas retiradas) + una web construida con MkDocs
Material que se despliega sola en GitHub Pages.

Fuente de verdad única: los archivos en `machines/`. GitHub y la web leen de ahí.

## Estructura
```
htb-writeups/
├── machines/
│   ├── index.md            # portada de la web (tabla de máquinas)
│   ├── tags.md             # índice de etiquetas (SO, dificultad)
│   └── <maquina>/
│       ├── README.md       # el writeup (con front-matter: title + tags)
│       └── images/         # capturas de esa máquina
├── mkdocs.yml              # configuración de la web
├── requirements.txt
├── .github/workflows/deploy.yml   # despliegue automático
└── CLAUDE.md
```

## Tu tarea principal: añadir un writeup
Cuando el usuario diga "añade el writeup de `<maquina>`" y te dé el contenido
(normalmente ya redactado y revisado en su proyecto de claude.ai):

1. Crea la carpeta `machines/<maquina-en-minusculas>/` con `README.md` e `images/`.
2. Añade al principio del README un front-matter:
   ```yaml
   ---
   title: <Maquina>
   tags:
     - <SO: Windows | Linux>
     - <Dificultad: Very Easy | Easy | Medium | Hard | Insane>
     - <Starting Point | Retired>
   ---
   ```
3. Pega el writeup tal cual debajo. **No reescribas ni inventes contenido.**
4. Actualiza la tabla de `machines/index.md` con una fila nueva
   (máquina, dificultad, SO, técnicas clave, fecha).
5. Muéstrame el `git diff`. Con mi OK explícito, haz commit y push.
6. El push dispara GitHub Actions y la web se actualiza sola en 1-2 min.

## Reglas de seguridad (innegociables)
- **Nunca** subas flags, hashes, contraseñas ni IPs reales: usa `<REDACTED>`
  o describe la ubicación. Solo contenido de Starting Point o máquinas retiradas.
- **Nunca** hagas `push` ni cambies la visibilidad de un repo sin mi aprobación.
- Nunca subas `.ovpn`, `.env` ni secretos (ya están en `.gitignore`).
- Antes de un cambio grande, explícame qué vas a tocar y por qué.
- Cambios pequeños, verificables y reversibles. Si hay duda, pregunta.

## Git
- Rama de trabajo: `main`.
- Mensajes de commit claros y en imperativo, p. ej.:
  `Add Responder writeup` / `Update machines index`.
- Comprueba `git status` y `git diff` antes de cada commit; enséñamelos.

## Dónde se crean los writeups
Los writeups se redactan y se revisan en el proyecto de claude.ai
("HTB WRITEUPS"), que tiene la plantilla, la base de conocimiento y el control
de calidad. Aquí, tu papel es **publicarlos y mantener la web**, no generarlos
desde cero salvo que te lo pida expresamente.
