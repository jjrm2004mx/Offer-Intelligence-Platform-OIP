# RN-006 — Comisiones, envío y restricciones de venta en Amazon

```yaml
id: RN-006
titulo: Comisiones, envío y restricciones de venta en Amazon
grupo: amazon
estado: EN_REVISION
version: 2
fecha: 2026-11-16
responsable: Jesús
revisor_negocio: Experto en negocios internacionales
depende_de: [RN-002, RN-013]
```

> **Qué cambió en la v2 (2026-11-16):** comisiones y envíos **confirmados** por el experto (pueden cambiar); las categorías que faltaban se llenan con la tabla que publica Amazon; envío por **peso y tamaño**, cotizando con 2 o 3 paqueterías lo que no esté definido; envío **incluido en el precio**; restricciones en tres niveles (categoría, marca, producto). **Cambio importante:** un producto restringido en Amazon **ya no se descarta**: se evalúa en venta local (RN-018). Respuestas de la [sesión 2](/sesiones/sesion-2-respuestas.md), bloques 1 y 6. La v1 queda en el historial: [RN-006 v1](https://github.com/jjrm2004mx/Offer-Intelligence-Platform-OIP/blob/1c1d4e04d5e5e2401dbb565782bf11061d8813f7/docs/negocio/reglas/RN-006-comisiones-y-restricciones.md).

## 1. ¿Qué queremos lograr?
Saber **cuánto cobra Amazon y cuánto cuesta enviar** cada producto, y **si realmente se puede vender en Amazon**. Algunas categorías, marcas o productos requieren permiso de Amazon y algunos se consideran peligrosos para envío.

## 2. ¿Qué incluye y qué no?
**Incluye:**
- Comisión de Amazon por categoría.
- Costo de envío al cliente con FBM.
- Restricciones de venta en Amazon.

**No incluye:**
- Envío a bodegas de Amazon (FBA): no se usa al inicio.
- Costos de la venta local (RN-001, RN-008).
- Productos que se evitan siempre, en cualquier canal (RN-015).

## 3. ¿Cómo funciona, en palabras?
Mientras no exista cuenta de vendedor, el sistema usa una **tabla manual** de comisiones, envíos y restricciones. Cuando exista la cuenta, consultará los datos exactos directo con Amazon y la tabla quedará de respaldo. Un producto que no se puede vender en Amazon no se tira: se revisa si conviene venderlo localmente.

## 4. La regla

**4.1 Comisión de Amazon** = precio de venta × % de la categoría (mínimo $0.30 por unidad).

| Categoría | Comisión | ¿Confirmado? |
|---|---|---|
| Herramientas | 15% | Experto (sesión 2) |
| Hogar e iluminación | 15% | Experto (sesión 2) |
| Tecnología (electrónica de consumo) | 8% | Tabla publicada por Amazon |
| Consolas de videojuegos | 8% | Tabla publicada por Amazon |
| Videojuegos y accesorios | 15% | Tabla publicada por Amazon |
| Juguetes | 15% | Tabla publicada por Amazon |
| Relojes | 16% hasta $1,500; 3% sobre el excedente | Tabla publicada por Amazon |
| Joyería | 20% hasta $250; 5% sobre el excedente | Tabla publicada por Amazon |
| Perfumes y belleza | 8% hasta $10; 15% si el precio es mayor de $10 | Tabla publicada por Amazon |

**4.2 Envío al cliente (FBM)**, incluido en el precio de venta (RN-006 · P5):

```
peso a cobrar = el MAYOR entre el peso real con empaque y el peso por tamaño de la caja
                (largo × ancho × alto ÷ divisor de la paquetería)
```

| Peso a cobrar | Envío estimado | ¿Confirmado? |
|---|---|---|
| hasta 1 kg | $8 | Experto (sesión 2) |
| 1 a 3 kg | $12 | Experto (sesión 2) |
| 3 a 6 kg | $14 | Experto (sesión 2) |
| más de 6 kg, o sin medidas | Cotizar en línea con **2 o 3 paqueterías** y tomar la más barata | Experto (sesión 2) |

**4.3 Restricciones en Amazon**

| Nivel | Ejemplos | ¿Confirmado? |
|---|---|---|
| **Categoría** | Joyería fina, relojes, belleza y salud (incluye perfumes), juguetes en temporada navideña | Aceptado por Jesús; confirmar en Seller Central |
| **Marca** | Lista que crece con cada caso; Amazon no publica una lista oficial | Aceptado por Jesús |
| **Producto** | Un producto restringido aunque su categoría y marca estén abiertas | Aceptado por Jesús |
| **Material peligroso** | Perfumes, aerosoles, baterías de litio (CASO-005): revisión de Amazon y reglas de la paquetería | Aceptado por Jesús |
| **Usados** | Joyería, relojes y belleza usados no se venden en Amazon como usados | Aceptado por Jesús |
| **Fuera del alcance inicial** | Productos con caducidad: alimentos, suplementos, cosméticos | Aceptado por Jesús |

- Con cuenta de vendedor: se verifica cada producto antes de comprar. Sin cuenta: se marca **"posible restricción en Amazon"**.
- Para obtener permiso, Amazon suele pedir facturas de mayorista o fabricante; **un ticket de tienda normalmente no basta** (por confirmar en Seller Central).
- Si el producto está restringido y no hay permiso: **NO VENDIBLE EN AMAZON (POR AHORA)** → el canal Amazon no es viable y **se evalúa la venta local** (RN-018). Solo queda fuera si tampoco ahí es viable.

Todos los valores son iniciales y configurables. La tabla se revisa cada 3 meses (propuesta de la v1).

## 5. ¿Cómo sabremos que funciona? — Ejemplos con números

**Ejemplo A — Taladro (2 kg, caja chica)**
- Herramientas: comisión 149 × 15% = **$22.35**. Envío (1 a 3 kg): **$12**. Sin restricción → vendible.

**Ejemplo B — Sierra circular (4 kg)**
- Comisión 119 × 15% = **$17.85**. Envío (3 a 6 kg): **$14**. Vendible.

**Ejemplo C — Perfume con 70% de descuento real**
- Belleza y material peligroso, sin permiso → **NO VENDIBLE EN AMAZON (POR AHORA)** → se evalúa en venta local.

**Ejemplo D — Reloj de $200**
- Comisión 200 × 16% = **$32.00**. Categoría restringida: sin permiso → se evalúa en venta local.

**Ejemplo E — Collar de $300**
- Comisión = 250 × 20% + 50 × 5% = 50.00 + 2.50 = **$52.50**.

**Ejemplo F — Lámpara grande y ligera**
- Pesa 2 kg, pero por el tamaño de su caja la paquetería cobra como 5 kg → peso a cobrar **5 kg** → envío **$14**, no $12.

## 6. ¿Qué información necesitamos?
- Categoría del producto en Amazon, peso, medidas de la caja y marca.
- Si existe, la respuesta de Amazon sobre si se puede vender (con cuenta de vendedor).

## 7. ¿Qué obtenemos?
- Comisión en $, envío en $ y si es vendible en Amazon o el motivo de la restricción.

## 8. ¿Quién participa?
- Jesús mantiene la tabla manual.
- El experto valida porcentajes y restricciones.
- Amazon da los datos exactos cuando haya cuenta.

## 9. ¿De qué depende?
- De la cuenta de vendedor para pasar de "estimado" a "exacto".
- De identificar el producto, su estado y su categoría (RN-013).

## 10. Limitaciones
- Las comisiones y restricciones de Amazon cambian; la tabla debe revisarse periódicamente.

## 11. ¿Qué pasa si…?
| Situación | Qué hace el sistema |
|---|---|
| Categoría sin comisión definida | No calcula el canal Amazon; marca "comisión desconocida" |
| No se conocen peso o medidas | Usa el envío más caro de la tabla, o cotiza si puede pasar de 6 kg |
| Producto restringido pero ya hay permiso | Se trata como vendible |
| Restringido y sin permiso | Canal Amazon no viable; se evalúa la venta local |

## 12. Preguntas para el experto
1. ¿Las categorías que llenamos con la tabla publicada por Amazon le parecen correctas para su experiencia?
2. ¿Confirma que, con un ticket de tienda, normalmente no se obtiene permiso en categorías restringidas?

## 13. Decisiones tomadas
| Fecha | Decisión | Quién |
|---|---|---|
| 2026-11-08 | Se vende con FBM (envío propio), no FBA | Jesús |
| 2026-11-16 | Comisiones y envíos confirmados; pueden cambiar | Experto |
| 2026-11-16 | Envío incluido en el precio en Amazon | Jesús |
| 2026-11-16 | Envío por peso y tamaño; cotizar con 2 o 3 paqueterías lo no definido | Experto |
| 2026-11-16 | Restricciones en tres niveles; restringido en Amazon → se evalúa venta local | Jesús (propuesta de Claude) |
| 2026-11-16 | Material peligroso, caducidad, usados en categorías sensibles y juguetes en temporada | Jesús (propuesta de Claude) |

## 14. Revisión de consistencia
- Última revisión: 2026-11-16 (v2) — APROBADO CON OBSERVACIONES
- Detalle: [revisiones/RN-006.md](/revisiones/RN-006.md)
