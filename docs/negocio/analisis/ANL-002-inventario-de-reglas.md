# ANL-002 — Inventario preliminar de reglas (comunes, Amazon FBM, venta personal)

```yaml
id: ANL-002
fecha: 2026-11-11
autor: Jesús (propuesta), con evaluación de Claude
estado: APROBADO (2026-11-11) — camino b, una sola serie RN-xxx y agrupación de §2.1 (DEC-143 a DEC-146). Las reglas se reescriben en la consolidación
relacionado: [ANL-001, pendientes-de-consolidacion.md]
```

## 1. Propuesta de Jesús (resumen fiel)

Las RN-001 a RN-009 **no se modifican**: se conservan como el grupo Amazon FBM. Se identifican reglas adicionales para incorporar después.

**Grupo A — Comunes (RC, propuestas):** RC-001 Identificación del producto · RC-002 Identificación de la fuente de compra · RC-003 Comparación de precios · RC-004 Validación de descuentos · RC-005 Precio histórico de referencia · RC-006 Disponibilidad del producto · RC-007 Condición del producto · RC-008 Autenticidad y procedencia · RC-009 Costo total de adquisición · RC-010 Confianza del vendedor · RC-011 Clasificación de oportunidad de compra · RC-012 Búsqueda de artículo específico (sin exigir descuento) · RC-013 Independencia entre compra y venta.

**Grupo B — Amazon FBM (existentes, sin cambios):** RN-001 a RN-009. RN-002, RN-003, RN-007 y RN-008 tienen aplicaciones más amplias, pero por ahora no se dividen, renumeran ni modifican.

**Grupo C — Venta personal (RP, propuestas):** RP-001 Precio esperado de venta personal · RP-002 Competencia local · RP-003 Margen neto de reventa personal · RP-004 Demanda local · RP-005 Tiempo estimado de comercialización · RP-006 Margen de negociación · RP-007 Costos de entrega · RP-008 Riesgo de comercialización personal · RP-009 Condición y depreciación · RP-010 Rentabilidad ajustada por tiempo · RP-011 Niveles de oportunidad personal · RP-012 Alertas de oportunidades personales · RP-013 Venta entre plataformas · RP-014 Validación de precio de venta efectivo.

Total: 36 entradas, que no son necesariamente 36 reglas independientes. Recomendación de Jesús: revisar cuáles son independientes, cuáles reutilizan conceptos y cuáles cambian solo de parámetros por canal, antes de formalizarlas. La búsqueda por artículo no exige pasar los umbrales de rentabilidad.

## 2. Evaluación de Claude

### 2.1 Cómo se agrupan (propuesta)

| Regla resultante | Junta | Tipo |
|---|---|---|
| **Comunes** | | |
| Identificación del producto | RC-001, RC-002 | Nueva (base en DEC-027 y DEC-134) |
| Condición y valor de usados | RC-007, RP-009 | Nueva |
| Precios de referencia | RN-002 (parte común), RC-003, RC-005 | Se amplía RN-002 |
| Calidad del precio y descuento real | RN-003, RC-004, RC-011 | Nueva RN-012 + RN-003 |
| Disponibilidad | RN-007, RC-006 | Se amplía RN-007 |
| Riesgo de compra y de venta | RC-008, RC-010, RP-008 | Nueva |
| Costo de adquisición y traslados | RN-008, RC-009, RP-007 | Se amplía RN-008 |
| Búsqueda por artículo | RN-011, RC-012 | **Ya existe** (RN-011) |
| Consulta responsable | RN-010 | Ya existe |
| **Amazon FBM** | | |
| Precio de venta en Amazon | RN-002 (parte Amazon) | Existente |
| Demanda en Amazon | RN-004 | Existente |
| Comisiones y restricciones | RN-006 | Existente |
| **Venta local** | | |
| Precio de venta local | RP-001, RP-002, RP-006, RP-014 | Nueva |
| Demanda local | RP-004 | Nueva |
| **Resultado, por canal** | | |
| Margen neto | RN-001, RP-003 | Se amplía RN-001 |
| Rentabilidad ajustada por tiempo | RN-005, RP-005, RP-010 | Se amplía RN-005 |
| Selección del mejor canal | RP-013 | Nueva |
| Niveles y alertas | RN-009, RP-011, RP-012 | Se amplía RN-009 |

RC-013 (independencia entre compra y venta) es un **principio de diseño**, no una regla: se registra como decisión.

Resultado: de 38 entradas (las 36 más RN-010 y RN-011, que ya existen y no aparecen en el inventario) a **unas 18 reglas**.

### 2.2 Observaciones

1. **El inventario omite RN-010 y RN-011**, que ya existen. RC-012 duplica a RN-011, que ya cumple la distinción señalada (dónde está más económico y disponible, sin exigir descuento).
2. **Conservar RN-001 a RN-009 sin cambios crea cuatro pares casi iguales:** RN-001/RP-003 (margen), RN-005/RP-010 (rentabilidad por tiempo), RN-009/RP-011 y RP-012 (niveles y alertas), RN-002/RP-001 (precio de venta). Son la misma fórmula con otros costos. Dos versiones de una fórmula tienden a separarse con el tiempo.
3. **Numeración:** una sola serie RN-xxx, con el grupo como campo (`grupo: común | amazon | local | resultado`), conserva la trazabilidad, porque issues, revisiones y decisiones ya citan RN-xxx.
