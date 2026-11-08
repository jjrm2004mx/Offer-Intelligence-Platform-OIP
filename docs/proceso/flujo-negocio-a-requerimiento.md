# Flujo de trabajo: del negocio al requerimiento aprobado

**Proyecto:** Offer Intelligence Platform (OIP)
**Etapa:** Capa de negocio → Capa de requerimiento
**Versión:** 1.0 — 2026-11-08
**Salida de la etapa:** un requerimiento (issue) con dictamen de inspección **CONTINUAR**, listo para análisis (OpenSpec).

---

## 1. Diagrama

```
 ┌─────────────────────────── CAPA NEGOCIO ───────────────────────────┐
 │                                                                     │
 │  ① Redactar / ajustar RN          (Jesús + Claude)                  │
 │        │  docs/negocio/reglas/RN-XXX.md  → PR → merge               │
 │        ▼                                                            │
 │  ② Revisión de consistencia       (oip-revisor-rn)                  │
 │        │  docs/negocio/revisiones/RN-XXX.md  (historial v1…vN)      │
 │        │  ¿errores de cálculo o contradicciones? ──sí──► vuelve a ①  │
 │        ▼                                                            │
 │  ③ Publicación                    (Vercel, automático al merge)     │
 │        │  https://oip-negocio.vercel.app                            │
 │        ▼                                                            │
 │  ④ Sesión con el experto          (Jesús + experto)  ◄── GATE       │
 │        │  responde citando "RN-00X · P#"                            │
 │        │  ¿cambios? ──sí──► ① con versión v+1 y "Decisiones tomadas"│
 │        ▼                                                            │
 └────────┼────────────────────────────────────────────────────────────┘
          ▼
 ┌──────────────────────── CAPA REQUERIMIENTO ────────────────────────┐
 │                                                                     │
 │  ⑤ Redactar / ajustar REQ         (Jesús + Claude)                  │
 │        │  Issue "Requerimiento" (plantilla), milestone, proyecto    │
 │        │  Referencia RN por ID + versión; escenarios con números    │
 │        ▼                                                            │
 │  ⑥ Revisión del solicitante       (Jesús)            ◄── GATE       │
 │        │  Nada se inspecciona sin el visto bueno de Jesús           │
 │        ▼                                                            │
 │  ⑦ Inspección formal              (oip-inspector, contexto aislado) │
 │        │  Issue "[INSPECCIÓN] REQ-…" (se actualiza, no se duplica)  │
 │        │  Comentario OIP_TRACE en el issue del REQ                  │
 │        ▼                                                            │
 │     ¿Dictamen?                                                      │
 │      ├─ RECHAZADO ──────────────► ⑤ (corregir) → ⑥ → ⑦ (v+1)        │
 │      ├─ APROBADO CON OBSERV. ──► ⑧ (observaciones se cierran        │
 │      │                              antes del merge final)          │
 │      └─ APROBADO ──────────────► ⑧                                  │
 │                                                                     │
 │  ⑧ Pasa a Análisis (oip-analista / OpenSpec)  → siguiente etapa     │
 └─────────────────────────────────────────────────────────────────────┘

  ↺ Si una RN cambia de versión después de ⑤:
    los REQ que la referencian se marcan "Requiere reinspección"
    → vuelven a ⑤ → ⑥ → ⑦
```

---

## 2. Pasos

| Paso | Responsable | Entrada | Salida / artefacto | Dónde se ve |
|---|---|---|---|---|
| ① Redactar / ajustar RN | Jesús + Claude | Necesidad de negocio, respuestas del experto | `docs/negocio/reglas/RN-XXX.md` con versión y "Decisiones tomadas" | Repo y Vercel |
| ② Revisión de consistencia | `oip-revisor-rn` | RN nueva o modificada | `docs/negocio/revisiones/RN-XXX.md`: dictamen, defectos, historial por versión, preguntas para el experto | Vercel |
| ③ Publicación | Vercel (automático) | Merge a `main` | Sitio actualizado | https://oip-negocio.vercel.app |
| ④ Sesión con el experto | Jesús + experto | Sitio, sobre todo "Preguntas consolidadas" | Respuestas citadas como `RN-00X · P#` | — |
| ⑤ Redactar / ajustar REQ | Jesús + Claude | RN vigentes | Issue con etiqueta `Requerimiento` (plantilla), milestone y proyecto | GitHub (privado) |
| ⑥ Visto bueno del solicitante | **Jesús** | Issue del REQ | Visto bueno explícito (en el chat o como comentario en el issue) | — |
| ⑦ Inspección formal | `oip-inspector` | Issue del REQ + RN referenciadas + arquitectura | Issue `[INSPECCIÓN] REQ-…` (etiqueta `Inspeccion`) y comentario `OIP_TRACE` en el REQ | GitHub |
| ⑧ Salida de la etapa | — | Dictamen con recomendación CONTINUAR | REQ listo para análisis | GitHub |

---

## 3. Artefactos y su ciclo de vida

| Artefacto | Identificador | Estados | Cómo cambia |
|---|---|---|---|
| Regla de negocio | `RN-001`… | BORRADOR → EN_REVISION → APROBADA → REEMPLAZADA | Se edita el archivo, se sube la `version` y se registra en "Decisiones tomadas" |
| Revisión de consistencia | `revisiones/RN-XXX.md` | Por versión: v1, v2… | Se agrega una columna al historial de defectos; nunca se borra la anterior |
| Requerimiento | `REQ-AAAA-NNNN` (issue) | Abierto → inspeccionado → CONTINUAR | Se **edita el mismo issue** y se agrega un comentario explicando qué cambió y por qué |
| Inspección | `[INSPECCIÓN] REQ-…` (issue) | v1, v2… | El agente **actualiza el mismo issue**: nueva columna en el historial y nueva traza `OIP_TRACE` |

**Hilo de trazabilidad:** `RN-XXX (vN)` → `REQ-AAAA-NNNN` → issue de inspección → `OIP_TRACE` → (siguiente etapa) cambio OpenSpec → rama/PR → código.

---

## 4. Dictámenes

| Dictamen | Condición | Siguiente paso |
|---|---|---|
| **APROBADO** | Controles previos OK, los 14 criterios CUMPLE o NO APLICA, sin defectos ALTA ni MEDIA abiertos | ⑧ Análisis |
| **APROBADO CON OBSERVACIONES** | Sin defectos ALTA abiertos y ningún NO CUMPLE en los criterios 4, 5, 12, 13 ni 14 | ⑧ Análisis. Las observaciones se cierran antes del merge final |
| **RECHAZADO** | Cualquier otro caso | ⑤ Corregir → ⑥ → ⑦ (reinspección v+1) |

---

## 5. Reglas de la etapa

1. **El experto solo ve la capa de negocio.** Nunca issues ni términos técnicos.
2. **Nada se borra ni se duplica.** RN, revisiones, REQ e inspecciones se versionan, con historial de defectos por columna.
3. **Dos gates humanos:** Jesús aprueba lo acordado con el experto (④) y da el visto bueno al REQ antes de inspeccionarlo (⑥).
4. **El inspector trabaja aislado:** no participa en la redacción del REQ, para no calificar su propio trabajo.
5. **Un REQ nunca apunta a una RN vieja.** Si una RN cambia de versión, los REQ que la referencian se reinspeccionan.
6. **Las RN prevalecen sobre la arquitectura** en reglas de negocio. Si difieren, se actualiza el documento técnico.

---

## 6. Cuando el experto pide cambios

1. Se actualiza la RN: versión v+1 y la decisión registrada con fecha. Luego PR y merge, y Vercel se actualiza solo.
2. `oip-revisor-rn` revisa solo las RN modificadas y agrega la columna vN a su historial.
3. Se editan los REQ afectados (los que referencian esa RN): versiones de RN, escenarios y supuestos, con un comentario de qué cambió.
4. Jesús da el visto bueno (⑥).
5. `oip-inspector` reinspecciona y actualiza el mismo issue de inspección (columna vN y nueva traza `OIP_TRACE`).

> **Propuesta pendiente de aprobación:** una GitHub Action que detecte el cambio de versión de una RN y ponga la etiqueta **"Requiere reinspección"**, con un comentario, en los REQ que la referencian.

---

## 7. Agentes de la etapa

| Agente | Archivo | Qué hace | Qué no hace |
|---|---|---|---|
| `oip-revisor-rn` | `.claude/agents/oip-revisor-rn.md` | Revisa la consistencia de las RN: cuentas, contradicciones y ambigüedades, y redacta preguntas para el experto | No aprueba requerimientos |
| `oip-inspector` | `.claude/agents/oip-inspector.md` | Inspección formal del REQ (14 criterios, controles previos, verificación de escenarios), con issue de inspección y traza | No modifica el REQ ni el repositorio; no diseña |

---

## 8. Estado actual (2026-11-08)

| Paso | Estado |
|---|---|
| ① RN-001…RN-009 | v1 publicadas |
| ② Revisión de consistencia | v1: 9/9 aprobado con observaciones |
| ③ Sitio | Publicado |
| ④ Sesión con el experto | **Pendiente** |
| ⑤ REQ-2026-0001 (#2) | v1 redactado; correcciones de autor pendientes |
| ⑥ Visto bueno de Jesús | **Pendiente** |
| ⑦ Inspección (#3) | v1: **RECHAZADO** (1 ALTA, 11 MEDIA, 7 BAJA). Se ejecutó antes del paso ⑥ |
| ⑧ Análisis | — |
