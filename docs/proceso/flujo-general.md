# Flujo general de trabajo — OIP

**Proyecto:** Offer Intelligence Platform (OIP), herramienta personal y privada para detectar oportunidades de reventa.
**Versión:** 1.0 — 2026-11-08
**Documentos relacionados:**
- Detalle de la primera etapa: [`flujo-negocio-a-requerimiento.md`](flujo-negocio-a-requerimiento.md)
- Arquitectura técnica: [`../arquitectura/arquitectura-tecnica.md`](../arquitectura/arquitectura-tecnica.md) (archivo único vigente; versiones anteriores en su tabla "Archivo vigente")
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
| **Arquitectura** (`docs/arquitectura/`) | Stack (Python/FastAPI, Scrapy, Playwright, PostgreSQL/Timescale, Keepa —diferido, DEC-124—, Telegram), despliegue (Rocky + Podman Quadlets), protección de la IP de casa (`oip-egress`), los 4 repos base, los ADR | Jesús + Claude; lo revisa `oip-arquitecto` | Cuando una RN o un diseño contradice un ADR. **Vigente: v2.2** (2026-11-17; la v2.0 del 2026-11-16 consolidó el texto y lo alineó con las RN v2 y con DEC-123 a DEC-190; el historial, por enlaces permanentes, DEC-191) |
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
- **Al terminar las primeras RN validadas:** actualizar la **arquitectura a v1.3**. *(Hecho: v1.3 el 2026-11-09, v1.4 y v2.0 consolidada el 2026-11-16, con las RN v2.)*

### Etapa 3 — Arranque técnico (una sola vez)

| Pieza | Para qué |
|---|---|
| Estructura del repo (`src/`, `tests/`, `deploy/`) | Ordenar el código |
| `openspec init` con la arquitectura como contexto | Que cada propuesta y diseño respete las decisiones técnicas |
| `CLAUDE.md` | Reglas obligatorias para Claude: la cadena de trazabilidad, el stack y la seguridad |
| Agentes restantes en `.claude/agents/`: `oip-analista`, `oip-developer`, `oip-tester` (DEC-172) | Cada paso de la Etapa 4 con su responsable |
| Comandos `/oip:req`, `/oip:start`, `/oip:pr` | Mover el trabajo entre eslabones |
| Hook de commits | Bloquear commits sin `Refs: #N` y `Change: <id>` |
| Gates (GitHub Actions) | Pruebas y cobertura, calidad (ruff), seguridad (gitleaks, pip-audit, bandit, regla de egress), trazabilidad |
| GitHub Project "OIP" | Tablero visual de etapas (opcional, para aprender la herramienta) |

### Etapa 4 — Construcción, por cada REQ aprobado (con OpenSpec)

```
oip-analista     propose         proposal.md + specs + design.md + tasks.md             ◄── GATE: Jesús aprueba propuesta
                                 (escenarios = criterios del REQ; 1 tarea = 1 PR)
[oip-arquitecto]                 solo si el REQ toca un ADR: revisa design.md contra los ADR (DEC-172)
oip-developer    apply-change    rama feat/<N>-<id> + código + PR
oip-tester                       pruebas por escenario y revisión de seguridad (egress/IP, URLs,
                                 secretos, access_mode); reporta defectos sin tocar el código
Gates (Actions)                  pruebas, cobertura, calidad, seguridad (incl. regla de egress),
                                 trazabilidad                                            ◄── GATE: Jesús revisa PR
```

- **Modo completo:** para un REQ nuevo.
- **Modo ligero:** para ajustes (developer → tester → seguridad).
- **Regla clave:** cada criterio de aceptación del REQ se convierte en un escenario de OpenSpec, y cada escenario en una prueba.

### Etapa 5 — Cierre

```
merge → openspec-archive-change (plantilla de resumen; sin agente documentador, DEC-172) → openspec/specs/ actualizadas (CÓMO)
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
     └──────────── resumen para negocio ◄── archive-change ◄┘
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
| `oip-analista` | 4 | `proposal.md`, specs, `design.md` y `tasks.md` (absorbe analista, arquitecto y techlead) | ✅ Listo (Etapa 3) |
| `oip-developer` | 4 | Implementación con la skill `openspec-apply-change` | ✅ Listo (Etapa 3) |
| `oip-tester` | 4 | Pruebas por escenario y revisión de seguridad (absorbe seguridad) | ✅ Listo (Etapa 3) |
| `oip-arquitecto` | 4 | Revisión independiente de `design.md` contra los ADR | **Se crea la primera vez que un REQ toque un ADR** (previsto: REQ-2026-0003, conectores) |
| ~~`oip-negocio`~~, ~~`oip-techlead`~~, ~~`oip-seguridad`~~, ~~`oip-documentador`~~ | — | Absorbidos: la RN se redacta en el chat; `tasks.md` lo hace el analista; seguridad, el tester y los gates; el cierre, la skill `openspec-archive-change` | No se crean (DEC-172) |
| **OpenSpec** | 4–5 | Especificación técnica por cambio (el plano). Versión 2.1.0, con skills en lugar de comandos `/opsx:*` (DEC-192) | ✅ Instalado (Etapa 3 mínima) |
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

## 10. Estado actual (2026-11-17)

| Etapa | Estado |
|---|---|
| 1. Negocio | RN-001 a RN-011 v2 y RN-012 a RN-018 v1 publicadas; revisión de consistencia v2.1 sin defectos ALTA. Sesiones 1 y 2 con el experto hechas; **pendiente la sesión 3** (validar DEC-159 a DEC-167, empaques y PO Box) |
| 2. Requerimiento | REQ-2026-0001 (#2) **v2.9**; reinspección v11 (#3) **APROBADO → CONTINUAR**, sin defectos abiertos (D-001 a D-055 corregidos). #2 y #3 en la columna "Análisis" del Project |
| — | Arquitectura **v2.2** (2026-11-17, PR #25): v2.0 consolidada (DEC-191), contrato de ingesta 3.0 (v2.1, PR #24) y 3.1, redondeo, nivel del aviso y capturas de Jesús (DEC-221 a DEC-223) |
| 3. Arranque técnico | **Etapa 3 mínima hecha (2026-11-17, EXT-001):** los 5 agentes (PR #18), OpenSpec 2.1.0, `CLAUDE.md`, `src/` y `tests/`, `pyproject.toml` (pytest y ruff), hook de commits, gates de GitHub Actions y reglas `deny` (DEC-192 a DEC-196). Pendiente para la Etapa 3 completa: gitleaks y umbral de cobertura, comandos `/oip:*`, `deploy/` y separación Core / Worker (DEC-173, antes de la primera línea del Worker) |
| 4–6 | No iniciado. Siguiente: **análisis de la parte B** con `oip-analista` (G3), con el criterio de DEC-228: un cambio de OpenSpec con cinco capacidades y tareas de 4 a 8 h |
| Tablero | GitHub Project "OIP" creado (Requerimiento → Inspección → Análisis → Desarrollo → Hecho) |
| Infraestructura | Vercel ✅ · VPS por contratar (2 vCPU / 4 GB para arrancar, DEC-127) · Keepa diferido (DEC-124) |

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

---

## 12. Guía personal de trabajo con Claude (2026-11-16)

### 12.1 Entradas externas

| Entrada | Cómo se usa | Dónde vive |
|---|---|---|
| **Diseño de estilo** (cómo debe verse el sistema) | Se convierte en una **guía de estilo** (colores, tipografía, componentes, ejemplos de pantallas). La citan el analista en cada propuesta con interfaz, el developer al construir y el tester al verificar. En el Inc. 1 aplica al **formato de los avisos de Telegram** (la interfaz es Metabase); completa desde el Inc. 2 (interfaz propia) | `docs/diseno/` |
| **Arquitectura GemIA (stack de tickets)** | **Resuelta (2026-11-16):** analizada en `docs/arquitectura/insumos/referencia-stack-tickets.md`; su encaje quedó decidido en DEC-173 a DEC-183 y se anota en la v1.4. Es un **insumo, no un reemplazo**. Se compara punto por punto contra la v1.3, los ADR, el registro de decisiones y las RN v2: qué conviene adoptar, qué choca con un ADR y por qué. Con lo que apruebe Jesús sale la **v1.4**, sin borrar contenido | `docs/arquitectura/` |

### 12.2 Modelo y esfuerzo por actividad fuerte

Antes de cada actividad, Claude avisa cuál toca para ajustar el selector. Fable 5.2 estuvo incluido en el plan solo hasta el 16-nov-2026 (consume el uso más rápido que Opus); desde entonces, la opción para lo más pesado es Opus con esfuerzo alto.

| Actividad | Modelo | Esfuerzo | Por qué |
|---|---|---|---|
| Análisis de la arquitectura GemIA (stack de tickets, hecho) y redacción de la v1.4 | **Fable 5.2** (hasta el 16-nov-2026); después, Opus | **Alto** | Cruzar contra ADR, decisiones y RN v2; un error ahí se arrastra a todo el código |
| Reescritura de reglas de negocio y revisión de consistencia | Opus | **Alto** | Fórmulas encadenadas entre reglas; hay que rehacer todas las cuentas |
| Guía de estilo a partir del diseño | Opus o Sonnet | Medio | Extraer y ordenar; el criterio lo pone Jesús |
| Redacción del REQ (v2 en adelante) | Opus (Fable 5.2 si sigue disponible) | **Alto** | Escenarios con números que deben cuadrar con todas las reglas |
| Inspección del REQ (`oip-inspector`) | Opus | **Alto** | Contexto aislado; es el gate formal |
| Arranque técnico (Etapa 3) | Opus | Medio | Mucha configuración; las instrucciones de los agentes nuevos piden cuidado |
| Propuesta OpenSpec (`oip-analista`) | Opus | Alto | Traduce criterios del REQ a escenarios y diseño |
| Codificación (`oip-developer`) | Sonnet u Opus | Medio | Tareas acotadas (1 tarea = 1 PR) con pruebas por escenario |
| Pruebas (`oip-tester`) | Sonnet | Medio | Mecánico una vez que los escenarios están bien escritos |
| Capturas, preguntas y ajustes pequeños | Cualquiera | Bajo | Transcribir y ordenar |
