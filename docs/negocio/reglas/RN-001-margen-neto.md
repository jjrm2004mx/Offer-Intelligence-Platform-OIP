# RN-001 — Margen neto de reventa, por canal

```yaml
id: RN-001
titulo: Margen neto de reventa, por canal
grupo: resultado
estado: BORRADOR
version: 2
fecha: 2026-11-11
responsable: Jesús
revisor_negocio: Experto en negocios internacionales
depende_de: [RN-002, RN-006, RN-008, RN-016]
version_anterior: https://github.com/jjrm2004mx/Offer-Intelligence-Platform-OIP/blob/5a4744d15b2ac6439f2cd89d25cb377ab437ab36/docs/negocio/reglas/RN-001-margen-neto.md
```

## 1. ¿Qué queremos lograr?
Saber cuánto dinero se gana **de verdad** por cada unidad que se compra y revende, después de pagar todo lo que cuesta comprarla y venderla. Un descuento grande no sirve de nada si al final no queda ganancia. En la v2, el margen se calcula **para cada canal de venta** (Amazon FBM y venta local) con **una sola fórmula**: lo que cambia son los costos de venta (DEC-143).

## 2. ¿Qué incluye y qué no?
**Incluye:**
- Costo de comprar una unidad: precio, impuesto de venta y envío hacia mí (si lo hay).
- Costo de venderla **en Amazon** (vendiendo y enviando yo mismo, modalidad FBM): comisión de Amazon, envío al cliente y empaque.
- Costo de venderla **en venta local** (nuevo en la v2): entrega al comprador, acondicionamiento y comisión de la plataforma si la hubiera.
- Un campo de "otros costos de venta" por si hace falta un ajuste manual (normalmente 0).

**No incluye:**
- El costo del viaje a la tienda física (eso lo calcula RN-008 por viaje completo, no por unidad).
- Devoluciones, tiempo de venta y riesgo de que baje el precio (eso lo ajusta RN-005).
- Costos de importación o de cruce para la venta (decisión tomada: fuera del modelo).
- Elegir el canal: lo hace RN-018 con el resultado de esta regla y de RN-005.

## 3. ¿Cómo funciona, en palabras?
Al precio al que esperamos vender le restamos todo lo que nos costó conseguir el producto y todo lo que cuesta venderlo. Lo que queda es el margen neto. Ese margen también se expresa como porcentaje de lo que invertimos al comprar.

## 4. La regla

```
costo de compra   = precio de oferta + impuesto de venta + envío hacia mí
                    (es el "costo de adquisición por unidad" de RN-008)

costo de venta, según el canal:
  Amazon FBM      = comisión de Amazon + envío al cliente + empaque + otros costos de venta
  venta local     = costo de entrega (RN-008) + acondicionamiento + comisión de la plataforma
                    + otros costos de venta
margen neto ($)   = precio de venta esperado − costo de compra − costo de venta
margen neto (%)   = margen neto ($) ÷ costo de compra × 100
```

- Todo se calcula en **dólares (USD)** y se redondea a centavos.
- El **precio de venta esperado** lo define RN-002 para Amazon y RN-016 para venta local.
- El **costo de entrega** lo define RN-008 (mismas tarifas del viaje, DEC-148).
- La **comisión de Amazon** y el **envío al cliente** los define RN-006.

| Valor | Qué es | Valor inicial | ¿Confirmado? |
|---|---|---|---|
| Impuesto de venta | % que cobra la tienda según su ubicación | 7.75% (ejemplo zona San Diego) | Por confirmar por tienda |
| Envío hacia mí | Costo de que me llegue el producto | $0 si recojo en tienda | Sí |
| Empaque | Caja, cinta, relleno por unidad | $1 a $2 según tamaño | Por confirmar |
| Otros costos de venta | Ajuste manual | $0 | Sí |
| Acondicionamiento | Limpieza o revisión antes de vender (sobre todo usados) | $0 nuevo; $2 usado | Por confirmar |
| Comisión de la plataforma local | Venta en persona en OfferUp o Marketplace | $0 | Por confirmar |

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

**Ejemplo C — Baterías DEWALT en venta local (nuevo; CASO-007, datos supuestos)**
- Compra en Home Depot: $79.00 + impuesto $6.12 → **costo de compra $85.12** (RN-008, ejemplo D).
- Venta local esperada: **$102.60** (RN-016, ejemplo A). Entrega en Tijuana: **$9.50** (RN-008, ejemplo F). Nuevo, sin acondicionamiento ni comisión.
- Margen neto = 102.60 − 85.12 − 9.50 = **$7.98** → 7.98 ÷ 85.12 = **9.38%**.
- En Amazon no se puede vender: baterías de litio (RN-006, ejemplo E).

## 6. ¿Qué información necesitamos?
- Precio de oferta (de la tienda).
- Ubicación de la tienda, para el impuesto.
- Precio de venta esperado (RN-002).
- Categoría, peso aproximado y tamaño del producto, para comisión, envío y empaque (RN-006).
- Para venta local: precio esperado (RN-016), ubicación del comprador (RN-008) y condición del producto (RN-014).

## 7. ¿Qué obtenemos?
- Costo de compra y, **por cada canal**, costo de venta y margen neto en $ y en %, por unidad.

## 8. ¿Quién participa?
- El sistema calcula.
- Jesús define los valores de empaque y ajustes.
- El experto valida que no falte ningún costo.

## 9. ¿De qué depende?
- RN-002 y RN-016 (precio de venta esperado), RN-006 (comisiones y envío de Amazon) y RN-008 (costo de adquisición y de entrega).

## 10. Limitaciones
- Sin cuenta de vendedor de Amazon, las comisiones y envíos son **estimados** con una tabla manual. El resultado se marca como "margen estimado".

## 11. ¿Qué pasa si…?
| Situación | Qué hace el sistema |
|---|---|
| No hay precio de venta esperado | No calcula margen; la oferta queda "sin referencia" (RN-003) |
| No se conoce el impuesto de la tienda | Usa el valor por defecto de la zona y lo marca como estimado |
| No se conoce peso o tamaño | Usa el envío más caro de la tabla para no inflar el margen |
| El margen sale negativo | Se registra, pero nunca genera alerta |
| No hay fuente de precio de Amazon (DEC-156) | No se calcula el margen en Amazon; solo el de venta local |
| No hay precio de venta local (RN-016) | No se calcula el margen local; revisión manual |

## 12. Preguntas para el experto
1. ¿Falta algún costo de venta que se suela olvidar? Por ejemplo: comisión por cierre de venta, costo por guardar inventario, comisión del medio de pago.
2. ¿Conviene calcular el margen % sobre lo invertido (como aquí) o sobre el precio de venta?
3. ¿Qué empaque típico se usa para herramientas medianas y cuánto cuesta?

## 13. Decisiones tomadas
| Fecha | Decisión | Quién |
|---|---|---|
| 2026-11-08 | Costos de importación o cruce para la venta quedan fuera del modelo | Jesús |
| 2026-11-08 | Moneda única de cálculo: USD | Jesús |
| 2026-11-11 | Canales por oportunidad: Amazon FBM y venta local (DEC-140, DEC-151) | Jesús |
| 2026-11-11 | Una sola fórmula, con el canal como parámetro (DEC-143) | Jesús |

**Cambios de la v2 contra la v1:** el costo de venta pasa a depender del canal; se agregan los costos de venta local y el ejemplo C. Fórmulas y ejemplos A y B de Amazon, iguales que la v1.

## 14. Revisión de consistencia
- Última revisión: 2026-11-08 (v1) — APROBADO CON OBSERVACIONES. **La v2 está pendiente de revisión.**
- Detalle: [revisiones/RN-001.md](/revisiones/RN-001.md)
