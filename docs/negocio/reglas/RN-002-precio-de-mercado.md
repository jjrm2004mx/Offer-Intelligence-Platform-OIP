# RN-002 — Referencias de precio y precio de venta en Amazon

```yaml
id: RN-002
titulo: Referencias de precio y precio de venta en Amazon
grupo: común (referencias) · amazon (precio de venta)
estado: EN_REVISION
version: 2
fecha: 2026-11-16
responsable: Jesús
revisor_negocio: Experto en negocios internacionales
depende_de: [RN-013]
```

> **Qué cambió en la v2 (2026-11-16):** se separan **cuatro referencias de precio** (DEC-129) y dos de ellas se usan para cosas distintas: el **precio habitual** mide el descuento y el **precio de mercado hoy** mide la competitividad (DEC-147). La fuente es el **historial propio de OIP** más la comparación entre comercios; Keepa queda diferido (DEC-123, DEC-124). El precio de venta en Amazon es el **del botón de compra** y, sin oferta hoy, el **histórico** (RN-002 · P4, P5). Un comercio mucho más barato que Amazon **baja la calificación** (RN-002 · P3). La v1 queda en el historial: [RN-002 v1](https://github.com/jjrm2004mx/Offer-Intelligence-Platform-OIP/blob/1c1d4e04d5e5e2401dbb565782bf11061d8813f7/docs/negocio/reglas/RN-002-precio-de-mercado.md).

## 1. ¿Qué queremos lograr?
Tener números confiables para cada producto: **cuánto cuesta normalmente** (para saber si la oferta es barata de verdad), **cuánto cuesta hoy en otros comercios** (para saber si hay competencia más barata) y **a cuánto lo podemos vender en Amazon** (para calcular la ganancia). Sin confundir nunca un precio sugerido o anunciado con el precio al que realmente se vende.

## 2. ¿Qué incluye y qué no?
**Incluye:**
- Las cuatro referencias de precio y cuándo se usa cada una.
- El precio de venta esperado en **Amazon**.
- De qué fuente sale cada dato.

**No incluye:**
- El precio de venta en venta local (RN-016).
- Productos usados o reacondicionados: su valor de referencia lo define RN-014.
- Paquetes de varias unidades o combos distintos del producto exacto (RN-013).
- Sitios de seguimiento de precios, comparadores y artículos editoriales como fuente de precio: **solo son señal** (DEC-154).

## 3. ¿Cómo funciona, en palabras?
Hay cuatro precios que se parecen pero dicen cosas distintas:
- El **precio sugerido del fabricante (MSRP)**: lo que el fabricante dice que debería costar.
- El **precio tachado** del comercio ("antes $199"): lo que la tienda dice que costaba.
- El **precio de mercado hoy**: lo más barato que un comprador consigue hoy en otros comercios.
- El **precio habitual**: lo que el producto cuesta normalmente, según lo que OIP ha visto durante 60 días.

El descuento real solo se mide contra el **precio habitual**. El precio de mercado hoy dice si hay alguien vendiendo más barato. El MSRP solo se usa cuando todavía no hay historial. El precio tachado nunca es referencia.

## 4. La regla

**4.1 Las cuatro referencias**

| Referencia | Cómo se obtiene | Para qué se usa |
|---|---|---|
| **Precio habitual** | **Mediana** de las observaciones de los últimos **60 días** del mismo producto, nuevo, vendido por el propio comercio, en los comercios que sigue OIP (incluido Amazon). Requiere **al menos 5 observaciones en al menos 3 días distintos** (DEC-130) | Descuento real (RN-003) |
| **Precio de mercado hoy** | El **más bajo** de hoy (dato de **48 horas o menos**) del mismo producto, nuevo, vendido por el comercio y **disponible**, en los comercios que sigue OIP, **sin contar la oferta evaluada**. En una liquidación en sucursal, el precio normal en línea de esa misma cadena **sí cuenta** (RN-002 · P6) | Competitividad (§4.3 y RN-012) |
| **MSRP** | Precio sugerido del fabricante, con fuente y fecha | Solo sin historial suficiente; con él, la calidad del precio no pasa de "Precio competitivo" (RN-012) |
| **Precio tachado** | El "antes" que muestra el comercio | **Nunca es referencia.** Solo se compara contra el precio habitual de esa tienda para detectar descuentos inflados (RN-003) |

**4.2 Precio de venta esperado en Amazon**

```
precio de venta esperado (Amazon) = precio del vendedor que gana el botón de compra hoy
                                    (sin oferta nueva hoy: precio habitual en Amazon, marcado "sin oferta hoy")
mínimo de 60 días (Amazon)        = el precio más bajo observado en Amazon en 60 días (lo usa RN-005)
```

- El botón de compra es el precio que ve casi todo comprador, por eso es el **realista para vender** (RN-002 · P4).
- Sin oferta nueva hoy en Amazon, se usa el **precio histórico** (precio habitual en Amazon) y se marca "sin oferta hoy" (RN-002 · P5). Cambia la v1, que mandaba a revisión manual.

**4.3 Competencia más barata (afecta la calificación en Amazon)**

```
COMPETENCIA MÁS BARATA = precio de mercado hoy < precio de venta esperado (Amazon) × (1 − 15%)
```

- Si se cumple, la oportunidad **en el canal Amazon baja un nivel** (RN-009). El comprador puede conseguirlo bastante más barato fuera de Amazon, así que ese precio de venta es menos seguro (RN-002 · P3).

| Valor | Qué es | Valor inicial | ¿Confirmado? |
|---|---|---|---|
| Ventana del precio habitual | Días | 60 | Aceptado por Jesús (DEC-130); validar con el experto |
| Historial suficiente | Observaciones y días distintos | 5 en 3 días | Aceptado por Jesús (DEC-130) |
| Antigüedad del precio de mercado hoy | Horas | 48 | Por confirmar |
| Precio de venta en Amazon | Qué precio se toma | Botón de compra | Experto (sesión 2) |
| Sin oferta en Amazon hoy | Qué se hace | Precio histórico | Experto (sesión 2) |
| Umbral de competencia más barata | % bajo el precio de venta en Amazon | 15% | **Propuesta nueva de Claude (por aceptar)**; el experto respondió "sí baja" sin dar umbral |
| Fuente de datos | Etapas | Historial propio + comparación → APIs oficiales → Keepa al final | DEC-123, DEC-124 |

Todos los valores son iniciales y configurables.

## 5. ¿Cómo sabremos que funciona? — Ejemplos con números

**Ejemplo A — Taladro**
- Observaciones de 60 días (Home Depot, Walmart, Amazon): 8 observaciones en 6 días distintos; mediana **$149** → precio habitual $149.
- Hoy: Amazon, botón de compra $149; Walmart $152 (hace 6 h). Oferta evaluada: Home Depot $79.
- Precio de mercado hoy = mínimo(149, 152) = **$149**. Precio de venta esperado (Amazon) = **$149**. Mínimo de 60 días en Amazon: **$139**.
- Competencia más barata: 149 < 149 × 0.85 = 126.65 → no.

**Ejemplo B — Sierra circular con un comercio más barato**
- Precio habitual: **$119** (mediana de 60 días, historial suficiente).
- Hoy: Amazon, botón de compra $119; Target $99 (hace 10 h).
- Precio de mercado hoy = **$99**. Precio de venta esperado (Amazon) = **$119**.
- Competencia más barata: 99 < 119 × 0.85 = 101.15 → **sí** → en Amazon baja un nivel (RN-009, ejemplo F).
- El descuento real se sigue midiendo contra el habitual de $119, no contra los $99 (DEC-147).

**Ejemplo C — Dato viejo descartado**
- Target tenía la sierra a $90, pero el dato es de hace 4 días → **no cuenta** para el precio de mercado hoy.

**Ejemplo D — Sin oferta en Amazon hoy**
- Amazon no tiene oferta nueva hoy; su precio habitual es $150 → precio de venta esperado **$150**, marcado "sin oferta hoy".

**Ejemplo E — Sin historial suficiente**
- Producto nuevo en el sistema: 3 observaciones en 2 días → **sin historial suficiente**. Solo hay MSRP $199. No se calcula descuento real (RN-003); la calidad del precio no pasa de "Precio competitivo" (RN-012).

## 6. ¿Qué información necesitamos?
- Identificación exacta del producto (RN-013).
- Observaciones de precio que registra OIP en cada consulta, con comercio, vendedor, disponibilidad y fecha (DEC-134).
- MSRP con fuente y fecha, cuando exista.

## 7. ¿Qué obtenemos?
- Precio habitual, precio de mercado hoy, precio de venta esperado en Amazon, mínimo de 60 días en Amazon, marca COMPETENCIA MÁS BARATA y la fuente de cada uno.

## 8. ¿Quién participa?
- El sistema consulta y calcula.
- El experto valida criterios y umbrales.

## 9. ¿De qué depende?
- De identificar correctamente el producto: mismo modelo, versión, contenido y estado (RN-013).
- De que OIP lleve su propio historial (DEC-123).

## 10. Limitaciones
- Durante los primeros días no hay historial propio: el descuento real no se puede afirmar.
- Algunos productos no se venden en Amazon; entonces solo aplica la venta local (RN-018).

## 11. ¿Qué pasa si…?
| Situación | Qué hace el sistema |
|---|---|
| El producto no está en Amazon | No hay precio de venta en Amazon; se evalúa solo la venta local |
| Se identificó solo por nombre | Se calcula, pero la comparación queda "no confirmada" (RN-013) |
| Ningún otro comercio tiene dato de 48 h o menos | No hay precio de mercado hoy; no se evalúa la competencia más barata |
| Solo hay ofertas de vendedores externos | No cuentan para las referencias; se muestran aparte (DEC-135, DEC-137) |

## 12. Preguntas para el experto
1. ¿Le parece bien que "mucho más barato" sea **15% o más** por debajo del precio de venta en Amazon? (umbral propuesto tras su respuesta a RN-002 · P3)
2. ¿60 días es buena ventana para el precio habitual? (DEC-130, aceptado por Jesús)

## 13. Decisiones tomadas
| Fecha | Decisión | Quién |
|---|---|---|
| 2026-11-08 | La fuente del historial de Amazon es Keepa | Jesús (**reemplazada** el 2026-11-11 por DEC-123 y DEC-124) |
| 2026-11-11 | Fuente por etapas: historial propio + comparación entre comercios → APIs oficiales → Keepa al final (DEC-123, DEC-124) | Jesús |
| 2026-11-11 | Cuatro referencias de precio; el descuento real solo contra el habitual (DEC-129, DEC-147) | Jesús |
| 2026-11-11 | Historial suficiente: mediana de 60 días, 5 observaciones en 3 días (DEC-130) | Jesús |
| 2026-11-11 | Sitios de seguimiento y comparadores solo como señal (DEC-154) | Jesús |
| 2026-11-16 | Un comercio mucho más barato que Amazon baja la calificación | Experto |
| 2026-11-16 | Precio de venta en Amazon = el del botón de compra | Experto y Jesús |
| 2026-11-16 | Sin oferta en Amazon hoy se usa el precio histórico | Experto |
| 2026-11-16 | En liquidación de sucursal, el precio en línea de la misma cadena cuenta como precio de mercado | Experto |

## 14. Revisión de consistencia
- Última revisión: ver `revisiones/RN-002.md` (columna v2)
- Detalle: [revisiones/RN-002.md](/revisiones/RN-002.md)
