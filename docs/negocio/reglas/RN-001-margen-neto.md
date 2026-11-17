# RN-001 — Margen neto de reventa, por canal

```yaml
id: RN-001
titulo: Margen neto de reventa, por canal
grupo: resultado
estado: EN_REVISION
version: 2
fecha: 2026-11-16
responsable: Jesús
revisor_negocio: Experto en negocios internacionales
depende_de: [RN-002, RN-006, RN-008, RN-016]
```

> **Qué cambió en la v2 (2026-11-16):** el canal de venta es un parámetro (Amazon FBM o venta local, DEC-143, DEC-151); la cuota mensual de Amazon es gasto fijo; el margen % sigue sobre lo invertido; el envío al cliente en Amazon va incluido en el precio; compras en línea a un PO Box en San Diego. Respuestas de la [sesión 2](/sesiones/sesion-2-respuestas.md), bloque 1. La v1 queda en el historial: [RN-001 v1](https://github.com/jjrm2004mx/Offer-Intelligence-Platform-OIP/blob/1c1d4e04d5e5e2401dbb565782bf11061d8813f7/docs/negocio/reglas/RN-001-margen-neto.md).

## 1. ¿Qué queremos lograr?
Saber cuánto dinero se gana **de verdad** por cada unidad que se compra y revende, después de pagar todo lo que cuesta comprarla y venderla, **en cada canal de venta**. Un descuento grande no sirve de nada si al final no queda ganancia.

## 2. ¿Qué incluye y qué no?
**Incluye:**
- Costo de comprar una unidad: precio, impuesto de venta y envío hacia mí (si lo hay).
- Costo de venderla, según el canal:
  - **Amazon FBM** (vendo y envío yo): comisión de Amazon, envío al cliente y empaque.
  - **Venta local** (OfferUp, Facebook Marketplace y venta personal, DEC-151): costo de entrega (RN-008).
- Un campo de "otros costos de venta" por canal, para ajustes manuales (normalmente 0).

**No incluye:**
- El costo del viaje a la tienda física (RN-008 lo calcula por viaje completo, no por unidad).
- Devoluciones, tiempo de venta y riesgo de que baje el precio (RN-005).
- La **cuota mensual de la cuenta de vendedor de Amazon**: es un gasto fijo del negocio y no se reparte por unidad (RN-001 · P5).
- Costos de importación o de cruce para la venta (fuera del modelo, C-14).
- Elegir el canal: lo hace RN-018.

## 3. ¿Cómo funciona, en palabras?
Al precio al que esperamos vender en un canal le restamos todo lo que nos costó conseguir el producto y todo lo que cuesta venderlo **en ese canal**. Lo que queda es el margen neto del canal. Se expresa también como porcentaje de lo que invertimos al comprar. La misma fórmula sirve para los dos canales; solo cambian los costos de venta.

## 4. La regla

```
costo de compra        = precio de compra + impuesto de venta + envío hacia mí

costo de venta (canal) = Amazon FBM:  comisión de Amazon + envío al cliente + empaque + otros
                         Venta local: costo de entrega (RN-008) + otros

margen neto ($)        = precio de venta esperado (canal) − costo de compra − costo de venta (canal)
margen neto (%)        = margen neto ($) ÷ costo de compra × 100
```

- Todo en **dólares (USD)**. Cada monto se redondea a centavos y el medio centavo sube (0.005 → 0.01).
- **Precio de venta esperado:** Amazon, RN-002; venta local, RN-016 (siempre marcado "estimado").
- **Comisión y envío al cliente en Amazon:** RN-006. En Amazon el envío va **incluido en el precio** (RN-006 · P5): el comprador no lo paga aparte y lo absorbe el margen.
- **Venta local:** en la venta local el envío y la forma de entrega se acuerdan con el cliente (RN-006 · P5); por defecto se usa el costo de entrega de RN-008.
- **Margen % sobre lo invertido** (RN-001 · P2, confirmado por el experto).
- **Compras de particulares** (RN-014): el traslado para recoger el producto entra en el costo de compra (RN-008, doble traslado).

| Valor | Qué es | Valor inicial | ¿Confirmado? |
|---|---|---|---|
| Impuesto de venta | % que cobra la tienda según su ubicación | 7.75% (ejemplo zona San Diego) | Por confirmar por tienda |
| Envío hacia mí (en línea) | Las compras en línea llegan a un **PO Box en San Diego** | Según la tienda; $0 si el envío es gratis | Experto (sesión 2); **dirección del PO Box pendiente** |
| Envío hacia mí (tienda física) | Recojo en tienda | $0 | Sí |
| Empaque (Amazon) | Caja, cinta, relleno por unidad | $1 hasta 1 kg, $2 más de 1 kg (provisional) | **PENDIENTE** (RN-001 · P3, P4) |
| Otros costos de venta | Ajuste manual por canal | $0 | Sí; el experto indica que pueden aparecer otros con la práctica (RN-001 · P1) |
| Cuota mensual de Amazon | Cuenta profesional | Gasto fijo, fuera del margen por unidad | Experto (sesión 2) |

Todos los valores son **iniciales y configurables** (criterio general de la sesión 2).

## 5. ¿Cómo sabremos que funciona? — Ejemplos con números

**Ejemplo A — Taladro en Amazon (sí deja ganancia)**
- Compra en Home Depot: $79.00. Impuesto 7.75% = $6.12 → **costo de compra $85.12**.
- Venta esperada en Amazon: $149.00. Comisión 15% = $22.35. Envío al cliente (incluido en el precio) $12.00. Empaque $2.00 → **costo de venta $36.35**.
- Margen neto = 149.00 − 85.12 − 36.35 = **$27.53**.
- Margen neto % = 27.53 ÷ 85.12 = **32.3%**.

**Ejemplo B — Lámpara en Amazon (pierde dinero)**
- Compra en Walmart: $20.00. Impuesto 7.75% = $1.55 → **costo de compra $21.55**.
- Venta esperada en Amazon: $22.00. Comisión 15% = $3.30. Envío $8.00. Empaque $1.00 → **costo de venta $12.30**.
- Margen neto = 22.00 − 21.55 − 12.30 = **−$11.85** → se pierde dinero aunque la tienda anuncie 90% de descuento.

**Ejemplo C — El mismo taladro en venta local**
- Costo de compra: **$85.12** (igual que A).
- Precio de venta local esperado (RN-016, ejemplo A): **$116.10**, estimado.
- Costo de entrega (RN-008): 10 km y 30 minutos = 10 × 0.20 + 0.5 × 15 = **$9.50**. Otros: $0 → **costo de venta $9.50**.
- Margen neto = 116.10 − 85.12 − 9.50 = **$21.48** → 21.48 ÷ 85.12 = **25.2%**, marcado "estimado".

## 6. ¿Qué información necesitamos?
- Precio de compra y ubicación de la tienda (impuesto).
- Precio de venta esperado por canal (RN-002, RN-016).
- Categoría, peso y tamaño del producto (RN-006).
- Distancia y tiempo de entrega para la venta local (RN-008).

## 7. ¿Qué obtenemos?
- Por canal: costo de compra, costo de venta y margen neto en $ y en %, por unidad.

## 8. ¿Quién participa?
- El sistema calcula.
- Jesús define empaque, ajustes y el precio local estimado.
- El experto valida que no falte ningún costo.

## 9. ¿De qué depende?
- RN-002 (precio de venta en Amazon), RN-006 (comisiones y envío), RN-008 (entrega local y traslados) y RN-016 (precio de venta local).

## 10. Limitaciones
- Sin cuenta de vendedor de Amazon, comisiones y envíos son **estimados** con una tabla manual; el resultado se marca "margen estimado".
- El margen en venta local siempre es estimado, porque su precio de venta lo es (RN-016).

## 11. ¿Qué pasa si…?
| Situación | Qué hace el sistema |
|---|---|
| No hay precio de venta esperado en un canal | No calcula el margen de ese canal; se evalúan los demás (RN-018) |
| No se conoce el impuesto de la tienda | Usa el valor por defecto de la zona y lo marca como estimado |
| No se conoce peso o tamaño | Usa el envío más caro de la tabla para no inflar el margen (RN-006) |
| El margen sale negativo | Se registra, pero nunca genera aviso |
| No está definido el empaque | Usa el valor provisional y marca "empaque por confirmar" |

## 12. Preguntas para el experto
1. ¿Qué empaque se usa y cuánto cuesta? ¿Bastan dos precios por peso o hace falta un tercer tamaño? (pendiente de la sesión 2)
2. ¿Cuál será la dirección del PO Box y tiene costo por paquete recibido? (pendiente de la sesión 2)

## 13. Decisiones tomadas
| Fecha | Decisión | Quién |
|---|---|---|
| 2026-11-08 | Costos de importación o cruce para la venta quedan fuera del modelo | Jesús |
| 2026-11-08 | Moneda única de cálculo: USD | Jesús |
| 2026-11-11 | El canal de venta es parámetro de la regla: Amazon FBM y venta local (DEC-140, DEC-143, DEC-151) | Jesús |
| 2026-11-11 | Costo de entrega en venta local con las tarifas de RN-008 (DEC-142, DEC-148) | Jesús |
| 2026-11-16 | Compras en línea a un PO Box en San Diego (dirección pendiente) | Experto |
| 2026-11-16 | Por ahora no falta ningún costo de venta; pueden agregarse con la práctica | Experto |
| 2026-11-16 | La cuota mensual de Amazon es gasto fijo, fuera del margen por unidad | Experto |
| 2026-11-16 | El margen % se calcula sobre lo invertido | Experto |
| 2026-11-16 | Envío al cliente: incluido en el precio en Amazon; según acuerdo en venta local | Experto y Jesús |

## 14. Revisión de consistencia
- Última revisión: 2026-11-16 (v2) — APROBADO CON OBSERVACIONES
- Detalle: [revisiones/RN-001.md](/revisiones/RN-001.md)
