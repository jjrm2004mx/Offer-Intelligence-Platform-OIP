# RN-018 — Selección del mejor canal de venta

```yaml
id: RN-018
titulo: Selección del mejor canal de venta
grupo: resultado
estado: BORRADOR
version: 1
fecha: 2026-11-16
responsable: Jesús
revisor_negocio: Experto en negocios internacionales
depende_de: [RN-004, RN-005, RN-006, RN-009, RN-017]
origen: DEC-140, DEC-145, DEC-146, DEC-151
```

> **Regla nueva.** Cada oportunidad se evalúa **por canal** y se elige el de mayor rentabilidad con posibilidad razonable de venta (DEC-140). El origen de compra y el canal de venta son **independientes** (DEC-146). Lo marcado como propuesta está **por aceptar**.

## 1. ¿Qué queremos lograr?
No descartar una oportunidad por exigirle el canal más costoso, y no mandar a Amazon algo que se vende mejor en persona, ni al revés.

## 2. ¿Qué incluye y qué no?
**Incluye:**
- Qué canales son viables para una oferta.
- Cómo se elige el mejor.

**No incluye:**
- Los cálculos de cada canal (RN-001, RN-005, RN-009).

## 3. ¿Cómo funciona, en palabras?
Se calculan los dos canales (Amazon y venta local). Los que no son viables se descartan. Entre los que tienen nivel, gana el que deja **más ganancia total en el lote**. Si casi empatan, gana el de mayor rendimiento mensual (el que recupera antes el dinero).

## 4. La regla

**Canal viable:**
- **Amazon:** demanda suficiente (RN-004), vendible (RN-006) y con nivel (RN-009).
- **Venta local:** demanda local no baja (RN-017), precio de venta local (RN-016) y con nivel (RN-009).

**Elección:**
1. Si ningún canal tiene nivel → la oferta queda sin nivel.
2. Si solo uno tiene nivel → ese.
3. Si los dos → el de **mayor ganancia total** = margen ajustado por unidad × unidades recomendadas (RN-005). Si la diferencia es **menor de 10%**, gana el de **mayor rendimiento mensual** (DEC-170).
- El tablero muestra **los dos canales** con sus números; el aviso usa el nivel del canal elegido.

| Valor | Qué es | Valor inicial | ¿Confirmado? |
|---|---|---|---|
| Criterio | Qué decide | Ganancia total; desempata el rendimiento mensual | Jesús (DEC-170) |
| Diferencia para desempatar | % de ganancia total | 10% | **Propuesta (por aceptar)** |

## 5. ¿Cómo sabremos que funciona? — Ejemplos con números

**Ejemplo A — Taladro → venta local**
- Amazon: sin nivel (margen ajustado 20.3%, RN-009 ejemplo B). Venta local: Vigilar, rendimiento 25.2% (RN-005, ejemplo C).
- Solo un canal con nivel → **venta local, Vigilar**.

**Ejemplo B — Sierra → Amazon** (situación base, RN-002 ejemplo B)
- Amazon: Muy recomendable; $44.73 × 3 unidades = **$134.19**; rendimiento 116.1%.
- Venta local, sin estimado de Jesús (RN-016): 119 × 85% = $101.15 → × 0.90 = $91.04; margen 91.04 − 31.25 − 9.50 = $50.29 (160.9%), Muy recomendable; demanda media → 2 unidades → **$100.58**; rendimiento 160.9%.
- Ganancia total: 134.19 contra 100.58 → diferencia 25.0% (más de 10%) → **Amazon, Muy recomendable**, aunque la venta local rinda más rápido.

**Ejemplo C — Casi empate**
- Amazon deja $100.00 en total (rendimiento 40.0%) y venta local $105.00 (rendimiento 60.0%): diferencia 5% (menor de 10%) → gana el de mayor rendimiento → **venta local**.

**Ejemplo D — Perfume restringido**
- Amazon no vendible (RN-006). Venta local con nivel Recomendable → **venta local**.

## 6. ¿Qué información necesitamos?
- Resultados de RN-004 a RN-009, RN-016 y RN-017 por canal.

## 7. ¿Qué obtenemos?
- Canal elegido, su nivel y los números de ambos canales.

## 8. ¿Quién participa?
- El sistema elige.
- Jesús puede escoger otro canal; queda registrado.

## 9. ¿De qué depende?
- RN-004, RN-005, RN-006, RN-009, RN-016 y RN-017.

## 10. Limitaciones
- El canal local siempre es estimado; el tablero lo marca así para que Jesús lo tome en cuenta.

## 11. ¿Qué pasa si…?
| Situación | Qué hace el sistema |
|---|---|
| Jesús elige otro canal | Se registra para calibrar |
| Los dos canales en revisión manual | La oferta va a revisión manual |
| Un canal en revisión manual y el otro con nivel | Se usa el canal con nivel; el otro se muestra como "por revisar" |

## 12. Preguntas para el experto
1. ¿Le parece bien elegir por ganancia total y desempatar por rendimiento cuando la diferencia es menor de 10%?

## 13. Decisiones tomadas
| Fecha | Decisión | Quién |
|---|---|---|
| 2026-11-11 | Cada oportunidad se evalúa por canal y se elige el de mayor rentabilidad (DEC-140) | Jesús |
| 2026-11-11 | Origen de compra y canal de venta independientes (DEC-146) | Jesús |
| 2026-11-11 | Inc. 1: Amazon FBM y venta local (DEC-151) | Jesús |
| 2026-11-16 | Se elige por ganancia total; el rendimiento mensual desempata (DEC-170) | Jesús |

## 14. Revisión de consistencia
- Última revisión: 2026-11-16 (v1) — RECHAZADO
- Detalle: [revisiones/RN-018.md](/revisiones/RN-018.md)
