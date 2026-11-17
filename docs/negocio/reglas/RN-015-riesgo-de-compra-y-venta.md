# RN-015 — Riesgo de compra y de venta

```yaml
id: RN-015
titulo: Riesgo de compra y de venta
grupo: común
estado: BORRADOR
version: 1
fecha: 2026-11-16
responsable: Jesús
revisor_negocio: Experto en negocios internacionales
depende_de: [RN-013, RN-014]
origen: DEC-135, DEC-137, DEC-145; sesión 2, bloque 6 (RN-009 · P3); ejercicios CASO-001, CASO-005, CASO-006
```

> **Regla nueva.** Junta los riesgos que no son de precio: quién vende, de dónde viene el producto y qué productos se evitan siempre. La lista de "evitar siempre" es una **propuesta de Claude aceptada por Jesús** en la [sesión 2](/sesiones/sesion-2-respuestas.md), bloque 6; por validar con el experto.

## 1. ¿Qué queremos lograr?
Que una oferta con buenos números no oculte un riesgo de fraude, falsificación, robo, garantía o seguridad. Algunos casos van a revisión manual y otros se descartan siempre.

## 2. ¿Qué incluye y qué no?
**Incluye:**
- Riesgo del vendedor (comercio, vendedor externo, particular).
- Riesgo de procedencia.
- Productos que se evitan siempre.

**No incluye:**
- Restricciones de Amazon (RN-006): esas solo cierran el canal Amazon.

## 3. ¿Cómo funciona, en palabras?
Cuando vende el propio comercio, el riesgo es bajo. Un vendedor externo o un particular suben el riesgo: la oferta no se descarta, pero la revisa Jesús. Hay productos que se evitan siempre, aunque cumplan los números.

## 4. La regla

| Situación | Marca | Qué provoca |
|---|---|---|
| Vende un **vendedor externo** en el comercio | VENDEDOR EXTERNO | Revisión manual (DEC-137); en la búsqueda por artículo, "otras opciones" (DEC-135) |
| Canal especial (por ejemplo, Walmart Business) | PUEDE REQUERIR CUENTA ESPECIAL | Se muestra; no se recomienda por defecto |
| Compra a un **particular** | PARTICULAR | Inspección física obligatoria (RN-014) |
| Producto propenso a falsificación o robo (**baterías, herramientas, perfumes, relojes**) comprado a un particular o a un vendedor externo | RIESGO DE PROCEDENCIA | Revisión manual; exigir comprobante o factura |
| **Evitar siempre** (abajo) | EVITAR | **Descartada** en todos los canales |

**Evitar siempre**, aunque cumplan los números:
- Productos con **retiro del mercado** (recall) vigente.
- Productos **regulados:** armas y sus accesorios, medicamentos, suplementos, pesticidas.
- **Seguridad infantil:** asientos para auto, cunas.
- **Perfumes o relojes de marca de lujo de particulares sin comprobante.**

| Valor | Qué es | Valor inicial | ¿Confirmado? |
|---|---|---|---|
| Categorías con riesgo de procedencia | Lista | Baterías, herramientas, perfumes, relojes | **Propuesta (por aceptar)**, de CASO-005 y CASO-006 |
| Lista de evitar siempre | Lista | Ver arriba | Aceptado por Jesús (sesión 2) |

Las listas son configurables.

## 5. ¿Cómo sabremos que funciona? — Ejemplos con números

**Ejemplo A — Vendedor externo**
- Switch en Walmart en línea a $279 por un vendedor externo → VENDEDOR EXTERNO → revisión manual; en una búsqueda para cliente, "otras opciones".

**Ejemplo B — Baterías de un particular (CASO-005)**
- Baterías Milwaukee en OfferUp a $99, sin comprobante → PARTICULAR y RIESGO DE PROCEDENCIA → revisión manual con inspección.

**Ejemplo C — Evitar siempre**
- Asiento para auto con 70% de descuento real y margen de 60% → **EVITAR** → descartada.

## 6. ¿Qué información necesitamos?
- Vendedor de cada observación (RN-013).
- Categoría y si el producto tiene un retiro vigente.

## 7. ¿Qué obtenemos?
- Las marcas de riesgo y su efecto.

## 8. ¿Quién participa?
- El sistema marca.
- Jesús revisa y decide en los casos manuales.

## 9. ¿De qué depende?
- RN-013 (vendedor y categoría) y RN-014 (particulares).

## 10. Limitaciones
- La revisión de retiros del mercado depende de fuentes oficiales que OIP todavía no consulta; al inicio, la revisa Jesús.

## 11. ¿Qué pasa si…?
| Situación | Qué hace el sistema |
|---|---|
| No se sabe quién vende | Se trata como vendedor externo |
| Un producto entra en "evitar siempre" después de avisado | Se marca "ya no recomendado" en el tablero |

## 12. Preguntas para el experto
1. ¿Agregaría productos a la lista de "evitar siempre"?
2. ¿Qué otras categorías tienen riesgo de falsificación o robo?

## 13. Decisiones tomadas
| Fecha | Decisión | Quién |
|---|---|---|
| 2026-11-11 | Vendedor externo y canales especiales marcados y no recomendados (DEC-135) | Jesús |
| 2026-11-11 | Vendedor externo en la búsqueda de ofertas → revisión manual (DEC-137) | Jesús |
| 2026-11-16 | Lista de productos que se evitan siempre | Jesús (propuesta de Claude) |

## 14. Revisión de consistencia
- Última revisión: 2026-11-16 (v1) — APROBADO CON OBSERVACIONES
- Detalle: [revisiones/RN-015.md](/revisiones/RN-015.md)
