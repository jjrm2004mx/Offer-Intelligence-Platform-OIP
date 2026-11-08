# RN-001 — Margen neto de reventa

```yaml
id: RN-001
titulo: Margen neto de reventa
estado: BORRADOR
version: 1
fecha: 2026-11-08
responsable: Jesús
revisor_negocio: Experto en negocios internacionales
depende_de: [RN-002, RN-006]
```

## 1. ¿Qué queremos lograr?
Saber cuánto dinero se gana **de verdad** por cada unidad que se compra y revende, después de pagar todo lo que cuesta comprarla y venderla. Un descuento grande no sirve de nada si al final no queda ganancia.

## 2. ¿Qué incluye y qué no?
**Incluye:**
- Costo de comprar una unidad: precio, impuesto de venta y envío hacia mí (si lo hay).
- Costo de venderla en Amazon (vendiendo y enviando yo mismo, modalidad FBM): comisión de Amazon, envío al cliente y empaque.
- Un campo de "otros costos de venta" por si hace falta un ajuste manual (normalmente 0).

**No incluye:**
- El costo del viaje a la tienda física (eso lo calcula RN-008 por viaje completo, no por unidad).
- Devoluciones, tiempo de venta y riesgo de que baje el precio (eso lo ajusta RN-005).
- Costos de importación o de cruce para la venta (decisión tomada: fuera del modelo).
- Venta en Facebook Marketplace (fase posterior).

## 3. ¿Cómo funciona, en palabras?
Al precio al que esperamos vender le restamos todo lo que nos costó conseguir el producto y todo lo que cuesta venderlo. Lo que queda es el margen neto. Ese margen también se expresa como porcentaje de lo que invertimos al comprar.

## 4. La regla

```
costo de compra   = precio de oferta + impuesto de venta + envío hacia mí
costo de venta    = comisión de Amazon + envío al cliente + empaque + otros costos de venta
margen neto ($)   = precio de venta esperado − costo de compra − costo de venta
margen neto (%)   = margen neto ($) ÷ costo de compra × 100
```

- Todo se calcula en **dólares (USD)** y se redondea a centavos.
- El **precio de venta esperado** lo define RN-002.
- La **comisión de Amazon** y el **envío al cliente** los define RN-006.

| Valor | Qué es | Valor inicial | ¿Confirmado? |
|---|---|---|---|
| Impuesto de venta | % que cobra la tienda según su ubicación | 7.75% (ejemplo zona San Diego) | Por confirmar por tienda |
| Envío hacia mí | Costo de que me llegue el producto | $0 si recojo en tienda | Sí |
| Empaque | Caja, cinta, relleno por unidad | $1 a $2 según tamaño | Por confirmar |
| Otros costos de venta | Ajuste manual | $0 | Sí |

## 5. ¿Cómo sabremos que funciona? — Ejemplos con números

**Ejemplo A — Taladro (sí deja ganancia)**
- Compra en Home Depot: $79.00. Impuesto 7.75% = $6.12 → **costo de compra $85.12**.
- Venta esperada en Amazon: $149.00. Comisión 15% = $22.35. Envío al cliente $12.00. Empaque $2.00 → **costo de venta $36.35**.
- Margen neto = 149.00 − 85.12 − 36.35 = **$27.53**.
- Margen neto % = 27.53 ÷ 85.12 = **32.3%**.

**Ejemplo B — Lámpara (pierde dinero)**
- Compra en Walmart: $20.00. Impuesto 7.75% = $1.55 → **costo de compra $21.55**.
- Venta esperada en Amazon: $22.00. Comisión 15% = $3.30. Envío $8.00. Empaque $1.00 → **costo de venta $12.30**.
- Margen neto = 22.00 − 21.55 − 12.30 = **−$11.85** → se pierde dinero aunque la tienda anuncie 90% de descuento.

## 6. ¿Qué información necesitamos?
- Precio de oferta (de la tienda).
- Ubicación de la tienda, para el impuesto.
- Precio de venta esperado (RN-002).
- Categoría, peso aproximado y tamaño del producto, para comisión, envío y empaque (RN-006).

## 7. ¿Qué obtenemos?
- Costo de compra, costo de venta, margen neto en $ y en %, por unidad.

## 8. ¿Quién participa?
- El sistema calcula.
- Jesús define los valores de empaque y ajustes.
- El experto valida que no falte ningún costo.

## 9. ¿De qué depende?
- RN-002 (precio de venta esperado) y RN-006 (comisiones y envío).

## 10. Limitaciones
- Sin cuenta de vendedor de Amazon, las comisiones y envíos son **estimados** con una tabla manual. El resultado se marca como "margen estimado".

## 11. ¿Qué pasa si…?
| Situación | Qué hace el sistema |
|---|---|
| No hay precio de venta esperado | No calcula margen; la oferta queda "sin referencia" (RN-003) |
| No se conoce el impuesto de la tienda | Usa el valor por defecto de la zona y lo marca como estimado |
| No se conoce peso o tamaño | Usa el envío más caro de la tabla para no inflar el margen |
| El margen sale negativo | Se registra, pero nunca genera alerta |

## 12. Preguntas para el experto
1. ¿Falta algún costo de venta que se suela olvidar? Por ejemplo: comisión por cierre de venta, costo por guardar inventario, comisión del medio de pago.
2. ¿Conviene calcular el margen % sobre lo invertido (como aquí) o sobre el precio de venta?
3. ¿Qué empaque típico se usa para herramientas medianas y cuánto cuesta?

## 13. Decisiones tomadas
| Fecha | Decisión | Quién |
|---|---|---|
| 2026-11-08 | Costos de importación o cruce para la venta quedan fuera del modelo | Jesús |
| 2026-11-08 | Moneda única de cálculo: USD | Jesús |

## 14. Estado de inspección
- Última inspección: 2026-11-08 — APROBADO CON OBSERVACIONES
- Detalle: [inspecciones/RN-001.md](/inspecciones/RN-001.md)
