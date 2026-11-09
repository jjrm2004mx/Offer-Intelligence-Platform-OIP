# Flujo general de trabajo — OIP

**Proyecto:** Offer Intelligence Platform (OIP), herramienta personal y privada para detectar oportunidades de reventa.
**Versión:** 1.0 — 2026-11-08
**Documentos relacionados:**
- Detalle de la primera etapa: [`flujo-negocio-a-requerimiento.md`](flujo-negocio-a-requerimiento.md)
- Arquitectura técnica: [`../arquitectura/OIP_Arquitectura_Tecnica_Integrada_v1.2.md`](../arquitectura/OIP_Arquitectura_Tecnica_Integrada_v1.2.md)
- Reglas de negocio publicadas: https://oip-negocio.vercel.app

---

## 1. Vista de una página

```
                    ┌──────────────────────────────────────────────────────────┐
  DOCUMENTOS BASE   │  Arquitectura v1.x (ADR, stack, 4 repos, seguridad)       │
  (marco fijo)      │  Reglas de negocio RN-xxx (validadas con el experto)      │
                    └───────────────┬──────────────────────────────────────────┘
                                    │ se consultan en todas las etapas
                                    ▼
 ETAPA 1  NEGOCIO        RN → revisión de consistencia → Vercel → experto        (sin código)
 ETAPA 2  REQUERIMIENTO  REQ (issue) → tu visto bueno → inspección formal        (sin código)
 ETAPA 3  ARRANQUE       una sola vez: repo + OpenSpec + CLAUDE.md + agentes + gates
 ETAPA 4  CONSTRUCCIÓN   por cada REQ aprobado, con OpenSpec:
                         análisis → diseño → tareas → desarrollo → pruebas → seguridad → PR
 ETAPA 5  CIERRE         merge → archivo OpenSpec (specs vivas) → resumen para negocio
 ETAPA 6  OPERACIÓN      despliegue en Rocky (Podman Quadlets) → uso real → resultados
                                    │
                                    └─► los resultados reales calibran las RN (vuelve a la Etapa 1)
```

**Tres ideas que lo sostienen todo:**
1. **Primero el qué, después el cómo.** Las RN y el REQ definen qué y por qué; OpenSpec y el código definen cómo.
2. **Un solo hilo de trazabilidad.** El ID del requerimiento (`REQ-AAAA-NNNN`) viaja por todos los artefactos.
3. **Nada se borra ni se duplica.** Todo se versiona (v1, v2…) y deja historial.

---

## 2. Documentos base (el marco fijo)

| Documento | Qué define | Quién lo cambia | Cuándo |
|---|---|---|---|
| **Arquitectura** (`docs/arquitectura/`) | Stack (Python/FastAPI, Scrapy, Playwright, PostgreSQL/Timescale, Keepa, Telegram), despliegue (Rocky + Podman Quadlets), protección de la IP de casa (`oip-egress`), los 4 repos base, los ADR | Jesús + Claude; lo revisa `oip-arquitecto` | Cuando una RN o un diseño contradice un ADR. **Pendiente: v1.3** para alinearla con las RN validadas |
| **Reglas de negocio** (`docs/negocio/reglas/`) | Cómo se calcula el margen, qué es un descuento falso, niveles, etc. | Jesús + experto | Después de cada sesión con el experto |

**Prioridad:** en reglas de negocio mandan las RN. En decisiones técnicas manda la arquitectura.

---

## 3. Etapas

### Etapa 1 — Negocio (sin código)

```
Redactar RN → oip-revisor-rn (consistencia) → publicar en Vercel → sesión con el experto → ¿cambios? → RN v+1
```

- **Salida:** RN validadas por el experto.
- **Gate humano:** Jesús aprueba lo acordado con el experto.
- **Detalle:** ver `flujo-negocio-a-requerimiento.md`.

### Etapa 2 — Requerimiento (sin código)

```
Redactar REQ (issue) → visto bueno de Jesús → oip-inspector → ¿dictamen?
      RECHAZADO → corregir → visto bueno → reinspección
      APROBADO / CON OBSERVACIONES → Etapa 4
```

- **Salida:** issue `Requerimiento` con un issue `[INSPECCIÓN]` que recomienda **CONTINUAR**.
- **Gate humano:** visto bueno de Jesús antes de cada inspección.
- **Al terminar las primeras RN validadas:** actualizar la **arquitectura a v1.3**.

### Etapa 3 — Arranque técnico (una sola vez)

| Pieza | Para qué |
|---|---|
| Estructura del repo (`src/`, `tests/`, `deploy/`) | Ordenar el código |
| `openspec init` con la arquitectura como contexto | Que cada propuesta y diseño respete las decisiones técnicas |
| `CLAUDE.md` | Reglas obligatorias para Claude: la cadena de trazabilidad, el stack y la seguridad |
| Agentes restantes en `.claude/agents/` | Cada paso de la Etapa 4 con su responsable |
| Comandos `/oip:req`, `/oip:start`, `/oip:pr` | Mover el trabajo entre eslabones |
| Hook de commits | Bloquear commits sin `Refs: #N` y `Change: <id>` |
| Gates (GitHub Actions) | Pruebas y cobertura, calidad (ruff), seguridad (gitleaks, pip-audit, bandit, regla de egress), trazabilidad |
| GitHub Project "OIP" | Tablero visual de etapas (opcional, para aprender la herramienta) |

### Etapa 4 — Construcción, por cada REQ aprobado (con OpenSpec)

```
oip-analista     /opsx:propose   proposal.md + specs (escenarios = criterios del REQ)   ◄── GATE: Jesús aprueba propuesta
oip-arquitecto                   design.md (verifica ADR; si cambia uno → arquitectura v+1)
oip-techlead                     tasks.md (1 tarea = 1 PR, Definition of Done, dependencias)
oip-developer    /opsx:apply     rama feat/<N>-<id> + código + PR
oip-tester                       pruebas por escenario; reporta defectos sin tocar el código
oip-seguridad                    revisa egress/IP, URLs, secretos, cambios de access_mode
Gates (Actions)                  pruebas, cobertura, calidad, seguridad, trazabilidad   ◄── GATE: Jesús revisa PR
```

- **Modo completo:** para un REQ nuevo.
- **Modo ligero:** para ajustes (developer → tester → seguridad).
- **Regla clave:** cada criterio de aceptación del REQ se convierte en un escenario de OpenSpec, y cada escenario en una prueba.

### Etapa 5 — Cierre

```
merge → oip-documentador → /opsx:archive → openspec/specs/ actualizadas (CÓMO)
                                         → resumen para negocio en docs/negocio/ (QUÉ) → Vercel
```

- El experto ve en Vercel **qué quedó funcionando**, en lenguaje llano.
- El issue del REQ se cierra y en el tablero pasa a "Hecho".

### Etapa 6 — Operación

- Despliegue en **Rocky Linux con Podman rootless y Quadlets**. Todo el scraping sale por **`oip-egress`** (VPS → proxy) y nunca por la IP de casa.
- Lo que realmente compras, vendes y encuentras en tienda se registra (`opportunity_outcome`, `store_visit`).
- Esos resultados **calibran las RN**: umbrales, tasas, días de venta. Cualquier ajuste vuelve a la **Etapa 1**.

---

## 4. Hilo de trazabilidad

```
RN-003 (v2) ──► REQ-2026-0001 (#2) ──► [INSPECCIÓN] (#3) ──► OIP_TRACE
     │                 │
     │                 └──► openspec/changes/<id>/  (proposal → specs → design → tasks)
     │                              │
     │                              └──► rama feat/2-<id> ──► commits (Refs: #2, Change: <id>)
     │                                          │
     │                                          └──► PR (Closes #2) ──► pruebas ↔ escenarios
     │                                                     │
     └──────────── resumen para negocio ◄── /opsx:archive ◄┘
```

| Eslabón | Lleva el ID por medio de |
|---|---|
| RN | Versión en el archivo y referencia desde el REQ |
| REQ | Título `[REQ-AAAA-NNNN]` |
| Inspección | Título `[INSPECCIÓN] REQ-…` y comentario `OIP_TRACE` |
| OpenSpec | `proposal.md` cita `Issue: #N` y cada requisito cita su RN |
| Rama | `feat/<N>-<id>` |
| Commits | Trailers `Refs: #N` y `Change: <id>` |
| PR | `Closes #N` y la lista de escenarios cubiertos |
| Pruebas | Marca `@scenario("…")` por escenario |

---

## 5. Agentes y herramientas

| Agente / herramienta | Etapa | Hace | Estado |
|---|---|---|---|
| `oip-revisor-rn` | 1 | Revisa la consistencia de las RN y redacta preguntas para el experto | ✅ Listo |
| `oip-inspector` | 2 | Inspección formal del REQ (14 criterios) | ✅ Listo |
| `oip-negocio` | 1 | Convierte notas en una RN con la plantilla | Pendiente (Etapa 3) |
| `oip-analista` | 4 | `proposal.md` + specs | Pendiente (Etapa 3) |
| `oip-arquitecto` | 4 | `design.md` y revisión de ADR | Pendiente (Etapa 3) |
| `oip-techlead` | 4 | `tasks.md` | Pendiente (Etapa 3) |
| `oip-developer` | 4 | Implementación con `/opsx:apply` | Pendiente (Etapa 3) |
| `oip-tester` | 4 | Pruebas por escenario | Pendiente (Etapa 3) |
| `oip-seguridad` | 4 | Revisión de egress/IP, URLs y secretos | Pendiente (Etapa 3) |
| `oip-documentador` | 5 | Archivo y resumen para negocio | Pendiente (Etapa 3) |
| **OpenSpec** | 4–5 | Especificación técnica por cambio (el plano) | Se instala en la Etapa 3 |
| **GitHub Issues** | 2–5 | REQ, inspecciones, trazas | ✅ En uso |
| **GitHub Project** | Todas | Tablero de etapas (el semáforo) | Lo crea Jesús |
| **Vercel** | 1 y 5 | Sitio del experto (`docs/negocio/`) | ✅ Publicado |
| **Claude Code** | Todas | Ejecuta los agentes y comandos | ✅ En uso |

---

## 6. Gates humanos (las únicas decisiones que no delega el sistema)

| # | Momento | Quién decide |
|---|---|---|
| G1 | Aceptar lo acordado con el experto en las RN | Jesús |
| G2 | Visto bueno al REQ antes de inspeccionar | Jesús |
| G3 | Aprobar la propuesta de OpenSpec antes de construir | Jesús |
| G4 | Revisar y hacer merge del PR | Jesús |
| G5 | Activar stealth en un comercio (`access_mode`) | Jesús |

---

## 7. Plan de requerimientos y los 4 repos base

| REQ | Qué | RN | Repos base | Incremento |
|---|---|---|---|---|
| **REQ-2026-0001** | Motor de oportunidades (ofertas en línea) | RN-001…006, 009 | Ninguno (lógica + Keepa) | 1 |
| PoC-A | Experimento de bloqueo por tienda (vía VPS) | — | scrapy-playwright (+ script Puppeteer) | 1 |
| **REQ-2026-0003** | Conectores Home Depot y Walmart | — | **Scrapy**, **scrapy-playwright** | 1 |
| PoC-D | Comparación de seguimiento sobre 50 URLs | — | **PriceStalker** (entra solo si gana) | 1 |
| **REQ-2026-0004** | Avisos por Telegram | RN-009 (avisos) | — | 1 |
| **REQ-2026-0002** | Tienda física y viaje | RN-007, RN-008 | — | 2 |
| Por definir | Monitoreo de páginas de liquidación | — | **changedetection.io** | 3 |
| Por definir | Facebook Marketplace, Amazon SP-API | — | — | 3 |

**Orden:** REQ-0001 va primero porque no hace scraping: se prueba sin riesgo de bloqueos ni de exponer la IP. PoC-A va antes de escribir REQ-0003, porque su resultado define cómo se accede a cada tienda.

---

## 8. Cuando algo cambia

| Cambia… | Qué se actualiza | Reinspección |
|---|---|---|
| Una **RN** (por el experto o por resultados reales) | RN v+1 → revisión de consistencia → REQ afectados (mismo issue) | Sí, sobre el mismo issue de inspección |
| Un **REQ** antes de construir | Mismo issue + comentario de cambios | Sí |
| Un **REQ** ya en construcción | Nuevo cambio de OpenSpec (delta) ligado al mismo REQ | Sí, del REQ |
| Un **ADR** de arquitectura | Arquitectura v+1 con su justificación; `oip-arquitecto` revisa los diseños afectados | No (no es un REQ) |
| El **acceso** a una tienda (bloqueos) | `access_mode` de la tienda (G5); queda registrado y medido | No |

> **Propuesta pendiente de aprobación:** GitHub Action que etiquete "Requiere reinspección" los REQ cuando cambia la versión de una RN que referencian.

---

## 9. Dónde vive cada cosa

| Qué | Dónde | Quién lo ve |
|---|---|---|
| Reglas de negocio y revisiones | `docs/negocio/` → Vercel | Jesús y experto |
| Arquitectura | `docs/arquitectura/` | Jesús |
| Procesos (este documento) | `docs/proceso/` | Jesús |
| REQ e inspecciones | GitHub Issues (repo privado) | Jesús |
| Especificaciones técnicas | `openspec/` (después de la Etapa 3) | Jesús y Claude |
| Agentes | `.claude/agents/` | Claude Code |
| Código y pruebas | `src/`, `tests/` (después de la Etapa 3) | Jesús y Claude |
| Tablero | GitHub Project "OIP" | Jesús |

---

## 10. Estado actual (2026-11-08)

| Etapa | Estado |
|---|---|
| 1. Negocio | RN-001…009 v1 publicadas; revisión de consistencia v1 hecha. **Pendiente: sesión con el experto** |
| 2. Requerimiento | REQ-2026-0001 (#2) v1; inspección v1 (#3) **RECHAZADO**. Pendiente: correcciones de autor → tu visto bueno → (después del experto) reinspección v2 |
| — | Arquitectura v1.3 pendiente (alinear con las RN validadas) |
| 3. Arranque técnico | No iniciado |
| 4–6 | No iniciado |
| Tablero | Lo crea Jesús (guía entregada) |
| Infraestructura | Vercel ✅ · VPS para `oip-egress` pendiente · Keepa pendiente de contratar |

---

## 11. Glosario rápido

| Término | Significado |
|---|---|
| **RN** | Regla de negocio: el conocimiento del negocio, en lenguaje llano |
| **REQ** | Requerimiento formal (issue): la necesidad que el sistema debe cubrir |
| **Inspección** | Revisión formal del REQ con 14 criterios; dictamen APROBADO / CON OBSERVACIONES / RECHAZADO |
| **OpenSpec** | Herramienta de especificación por cambio: propuesta, specs, diseño, tareas, archivo |
| **ADR** | Decisión de arquitectura registrada, con su motivo |
| **Gate** | Punto de control: humano (tu decisión) o automático (GitHub Action) |
| **OIP_TRACE** | Comentario oculto en un issue que registra qué agente hizo qué, sobre qué y con qué resultado |
| **`oip-egress`** | Contenedor por el que sale todo el scraping; protege la IP de casa |
| **GitHub Project** | Tablero de seguimiento por etapas, separado del repositorio |
