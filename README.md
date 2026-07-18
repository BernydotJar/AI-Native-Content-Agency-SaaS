# Native / War Room

Webapp cinematográfica y sandbox local para representar una agencia de contenido AI-native de ocho agentes. El repositorio ya no es sólo una maqueta de frontend: contiene una experiencia React/TypeScript ejecutable, un runtime Python determinista con memoria SQLite y un corpus local de instrucciones, conocimiento y skills.

> Estado actual: prototipo local verificable con dos rutas de ejecución independientes. La UI simula campañas dentro del navegador; el runtime Python ejecuta un flujo determinista separado. No existe todavía transporte entre ambos. Ningún adaptador contacta servicios externos, publica contenido, renderiza media ni gasta presupuesto.

## Qué funciona hoy

- War Room responsive con estética obsidian/slate, partículas, glow cards, motion y transición circular de acento.
- Topología Fabric-style con sensor de entrada y ocho estaciones: CEO, Research, Strategist, Growth, Writer, Media, Risk y Publisher.
- Tres misiones de UI: video a paquete de entrega, imagen a manifiesto de motion y tesis a campaña orgánica + paid sandbox.
- Runtime TypeScript puro y determinista para mezclar señales mock de X, Facebook, TikTok e Instagram, aplicar skills y empaquetar artefactos de campaña sandbox.
- Inspector accesible por agente, outputs, progreso y Greenlight manual.
- Runtime Python de ocho agentes con artefactos, evidencia, traza, memoria SQLite y un límite duro entre Risk y Publisher.
- `DynamicSkillCreator` para crear borradores Markdown locales dentro de una raíz explícita, con validación de slug, protección contra traversal/symlinks y overwrite opt-in.
- Biblioteca local con instrucciones por agente, base de conocimiento y skills editoriales/de plataforma.
- Pruebas de interacción frontend y pruebas unitarias del runtime, memoria, fachada y creador de skills.

## Arquitectura real

```text
React 19 + TypeScript + Vite
├── UI cinematográfica y accesible
├── state machine de misiones en App.tsx
├── contratos/fixtures puros en src/lib/simulationRuntime.ts
└── sin fetch, WebSocket ni llamada al backend

agency.py
└── backend/agency_runtime (Python estándar)
    ├── orquestador secuencial de ocho agentes
    ├── Greenlight local antes de Publisher
    ├── SQLite Observe → Store → Search → Recall
    ├── adaptadores deterministas sandbox
    └── creador seguro de borradores de skill

Contenido operativo local
├── agents/*/instructions.md
├── knowledge/*.md
└── skills/*.md
```

La UI y Python modelan el mismo concepto, pero no comparten estado ni artefactos en tiempo de ejecución. Los archivos de `agents/`, `knowledge/` y `skills/` son fuentes locales auditables; el orquestador Python todavía no los carga automáticamente. Los roles y fixtures del backend están codificados y versionados en `backend/agency_runtime/`.

Consulta [docs/IMPLEMENTATION_AUDIT.md](docs/IMPLEMENTATION_AUDIT.md) para la matriz requisito → evidencia → estado y las desviaciones deliberadas respecto de la propuesta inicial.

## Stack

### Web

- React 19 + TypeScript
- Vite 8
- Tailwind CSS 4 mediante `@tailwindcss/vite`
- Lucide React
- Manrope Variable + JetBrains Mono Variable autoalojadas
- Vitest + Testing Library + jsdom

### Runtime local

- Python 3.9 o superior
- Biblioteca estándar para orquestación, modelos, CLI y SQLite
- `setuptools` para empaquetado opcional
- Sin dependencia de `agency_swarm` ni de un framework externo de agentes

Durante la implementación se consultó Context7 mediante su CLI para contrastar la integración oficial de Tailwind CSS 4 con Vite y la configuración vigente de Vitest 4. Esa consulta fue tooling de desarrollo; `Context7DocsTool` dentro del producto sigue siendo un adapter mock y no hace solicitudes remotas.

## Inicio local de la webapp

Requiere una versión moderna de Node.js compatible con Vite 8.

```bash
npm install
npm run dev
```

Vite mostrará la URL disponible, normalmente `http://localhost:5173`.

Comandos web:

```bash
npm run dev       # servidor de desarrollo
npm run build     # TypeScript + bundle de producción
npm run lint      # análisis estático con Oxlint
npm test          # pruebas de interacción y runtime TS
npm run preview   # previsualizar dist/
```

## Ejecutar el sandbox Python

La fachada `agency.py` añade `backend/` al path local y no requiere instalación editable para la demo.

```bash
python3 agency.py demo
python3 agency.py demo --approve --json
python3 agency.py demo --reject
```

Sin una decisión, el flujo termina en `awaiting_greenlight` y Publisher permanece en `waiting_greenlight`. `--approve` crea sólo un manifiesto sandbox en memoria; `--reject` bloquea Publisher. Para verificar persistencia SQLite local se puede suministrar una ruta explícita:

```bash
python3 agency.py demo --db /tmp/native-agency-memory.sqlite3 --json
```

Pruebas del backend:

```bash
cd backend
python3 -m unittest discover -s tests -v
```

## Agentes, conocimiento y skills

La secuencia canónica es:

1. CEO define objetivo, audiencia y restricciones.
2. Research produce evidencia sintética con procedencia.
3. Strategist convierte el contexto en decisiones de canal.
4. Growth proyecta un envelope de adquisición sandbox.
5. Writer prepara el copy deck.
6. Media prepara planes de video e imagen; no renderiza archivos.
7. Risk valida el paquete y habilita la decisión humana.
8. Publisher sólo empaqueta después del Greenlight.

El contrato operativo y sus límites están en [agency_manifesto.md](agency_manifesto.md). Las instrucciones por rol viven en `agents/`; el conocimiento trazable en `knowledge/`; y los playbooks editoriales y de plataforma en `skills/`.

`DynamicSkillCreator` está implementado y probado como utilidad Python local. Puede escribir un `.md` validado dentro de una raíz elegida por el llamador, pero todavía no tiene comando CLI, pantalla web ni integración automática con el orquestador.

## Greenlight

Hay dos gates locales, no conectados entre sí:

- En la web, las tareas de Publisher quedan diferidas después de Risk hasta que una persona activa Greenlight. Revocarlo durante la ejecución cancela timers pendientes y marca Publisher para atención.
- En Python, `AgencyOrchestrator.start()` se detiene antes de Publisher. `approve()` registra revisor, nota y decisión y permite crear un manifiesto sandbox; `reject()` mantiene el empaquetador sin invocar.

En ninguno de los dos casos Greenlight equivale a publicar, comprar medios ni autorizar una API externa.

## Límites de integración

Las siguientes capacidades son contratos mock o representaciones visuales, no conexiones activas:

- Meta Ads MCP y gasto publicitario;
- APIs de X, LinkedIn, Facebook, TikTok, Instagram o cualquier publisher;
- navegador/Puppeteer, GitHub y Context7 durante el runtime de producto;
- generación, edición o lectura real de video e imagen;
- FastAPI, REST, SSE o WebSocket entre frontend y Python;
- autenticación, autorización, secrets management y tenancy;
- PostgreSQL, almacenamiento de objetos y sincronización cloud;
- ingestión automática de `agents/`, `knowledge/` y `skills/` por el orquestador.

Antes de activar servicios externos deben añadirse contratos versionados, autenticación, idempotencia, reintentos acotados, auditoría, revocación y un gate de aprobación ligado a la versión exacta de los artefactos.

## Verificación

Gate ejecutado el 17 de julio de 2026 en el entorno local del repositorio:

```bash
rtk test npm run lint
rtk test npm test
rtk test npm run build

cd backend
python3 -m unittest discover -s tests -v
cd ..
python3 agency.py demo --approve --json
```

La demo JSON reporta de forma explícita cero llamadas de red, navegaciones, cambios en GitHub, renders, publicaciones y gasto publicitario. El browser integrado no expuso una instancia durante este cierre, por lo que la QA visual interactiva quedó pendiente.
