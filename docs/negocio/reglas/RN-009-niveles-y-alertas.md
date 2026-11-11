# RN-009 — Niveles de oportunidad y alertas

```yaml
id: RN-009
titulo: Niveles de oportunidad y alertas
estado: BORRADOR
version: 1
fecha: 2026-11-08
responsable: Jesús
revisor_negocio: Experto en negocios internacionales
depende_de: [RN-001, RN-002, RN-003, RN-004, RN-005, RN-006, RN-007]
```

> **Por actualizar (v2, 2026-11-11).** Esta regla cambiará al terminar los ejercicios de comprobación: pasa a ser el eje 2 (**oportunidad de reventa**); el eje 1 es la nueva RN-012 (calidad del precio). Pendiente: vendedor externo en la búsqueda de ofertas. DEC-131. El texto de abajo sigue siendo la v1.

## 1. ¿Qué queremos lograr?
Clasificar cada oferta que sobrevivió a todos los filtros en un **nivel**, y avisar a Jesús en el momento adecuado: de inmediato las mejores y en resumen las demás. Sin llenarlo de avisos repetidos.

## 2. ¿Qué incluye y qué no?
**Incluye:**
- Condiciones para que una oferta sea oportunidad.
- Niveles y qué tipo de aviso genera cada uno.
- Cuándo no repetir un aviso.

**No incluye:**
- La decisión del viaje a tienda (RN-008), que se calcula aparte con las oportunidades que pasan aquí.

## 3. ¿Cómo funciona, en palabras?
Primero se revisa que la oferta no tenga ningún impedimento: descuento falso, demanda insuficiente, restricción de venta, coincidencia dudosa. Luego se le asigna el **nivel más alto cuyas dos condiciones cumpla**: descuento real mínimo y margen ajustado mínimo. Además debe dejar al menos **$10 por unidad**.

## 4. La regla

**Requisitos previos (todos):**
- Sin marcas MERCADO YA BARATO, SIN REFERENCIA ni COINCIDENCIA DUDOSA (RN-003).
- Demanda SUFICIENTE (RN-004).
- Vendible, con comisión conocida (RN-006).
- Margen ajustado ≥ **$10 por unidad** (RN-005).
- Si es tienda física: confianza Alta o Media (RN-007).

**Niveles** — se asigna el más alto cuyas dos condiciones se cumplan:

| Nivel | Descuento real (RN-003) | Margen ajustado % (RN-005) | Aviso |
|---|---|---|---|
| Excepcional | ≥ 80% | ≥ 50% | Inmediato |
| Muy buena | ≥ 70% | ≥ 40% | Inmediato |
| Buena | ≥ 50% | ≥ 30% | Resumen 2 veces al día |
| Interesante | ≥ 40% | ≥ 25% | Solo en el tablero |

Si no alcanza ni "Interesante" → no es oportunidad (queda registrada como evaluada).

**Orden:** dentro de cada nivel, las oportunidades se ordenan por **rendimiento mensual** (RN-005), de mayor a menor.

**No repetir avisos:** la misma oferta no se vuelve a avisar en **24 horas**, salvo que suba de nivel o su precio baje **5% o más**.

| Valor | Qué es | Valor inicial | ¿Confirmado? |
|---|---|---|---|
| Margen mínimo por unidad | $ | $10 | Por confirmar |
| Umbrales por nivel | Ver tabla | Ver tabla | Por confirmar |
| Horarios del resumen | 2 veces al día | 8:00 y 18:00 (Tijuana) | Decisión de Jesús |
| Ventana sin repetir | Horas | 24 h | Decisión de Jesús |
| Baja de precio para repetir | % | 5% | Decisión de Jesús |

## 5. ¿Cómo sabremos que funciona? — Ejemplos con números

**Ejemplo A — Sierra circular → Muy buena (aviso inmediato)**
- Descuento real 75.6%, margen ajustado 146.9% ($45.92 por unidad), demanda suficiente, vendible, confianza Alta.
- Excepcional exige ≥ 80% de descuento real ✗. Muy buena: 75.6% ≥ 70% ✓ y 146.9% ≥ 40% ✓ → **Muy buena** → aviso inmediato.

**Ejemplo B — Taladro → no es oportunidad**
- Descuento real 47.0%, margen ajustado 22.1% ($18.80 por unidad).
- Interesante exige ≥ 40% ✓ y ≥ 25% ✗ → **no alcanza ningún nivel**, aunque la tienda anunciara 60%.

**Ejemplo C — Lámpara → descartada antes de los niveles**
- Marca MERCADO YA BARATO (RN-003) → no pasa los requisitos previos.

**Ejemplo D — Descuento alto, margen moderado**
- Descuento real 82%, margen ajustado 35%, $22 por unidad.
- Excepcional: 82% ✓ pero 35% < 50% ✗. Muy buena: ✓ pero 35% < 40% ✗. Buena: 82% ≥ 50% ✓ y 35% ≥ 30% ✓ → **Buena** → va al resumen.

**Ejemplo E — No repetir**
- La sierra se avisó a las 10:00. A las 14:00 el precio sigue igual → no se avisa otra vez. A las 16:00 baja de $29 a $27 (6.9%) → **sí se vuelve a avisar**.

## 6. ¿Qué información necesitamos?
- Resultados de RN-001 a RN-007.

## 7. ¿Qué obtenemos?
- Nivel de cada oportunidad, el aviso correspondiente (mensaje al celular de Jesús) y su lugar en el tablero.

## 8. ¿Quién participa?
- El sistema clasifica y avisa.
- Jesús recibe los avisos y decide.
- El experto valida los umbrales.

## 9. ¿De qué depende?
- De todas las RN anteriores.

## 10. Limitaciones
- Los umbrales son iniciales. Se ajustarán con los resultados reales de compra y venta.

## 11. ¿Qué pasa si…?
| Situación | Qué hace el sistema |
|---|---|
| Falla el envío del aviso | Reintenta; si sigue fallando, queda visible en el tablero |
| La oportunidad desaparece (se agotó o subió el precio) | Se marca "ya no disponible" en el tablero; no se avisa |
| Muchas oportunidades al mismo tiempo (más de 10 inmediatas en una hora) | Se agrupan en un solo aviso |

## 12. Preguntas para el experto
1. ¿Le parecen bien los umbrales de cada nivel? ¿Pondría más exigencia en descuento o en margen?
2. ¿$10 por unidad es un mínimo razonable, o depende del precio del producto?
3. ¿Algún tipo de producto que, aunque cumpla los números, usted evitaría siempre?

## 13. Decisiones tomadas
| Fecha | Decisión | Quién |
|---|---|---|
| 2026-11-08 | Los avisos llegan por mensaje al celular (Telegram) y además se ven en un tablero | Jesús |

## 14. Revisión de consistencia
- Última revisión: 2026-11-08 — APROBADO CON OBSERVACIONES
- Detalle: [revisiones/RN-009.md](/revisiones/RN-009.md)
