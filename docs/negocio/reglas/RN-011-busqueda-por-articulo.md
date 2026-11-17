# RN-011 — Búsqueda particular por artículo (servicio a clientes)

```yaml
id: RN-011
titulo: Búsqueda particular por artículo (servicio a clientes)
grupo: común
estado: EN_REVISION
version: 2
fecha: 2026-11-16
responsable: Jesús
revisor_negocio: Experto en negocios internacionales
depende_de: [RN-007, RN-008, RN-010, RN-012, RN-013, RN-014]
origen: Sesión 1 con el experto (2026-11-09) — DEC-110 a DEC-113
```

> **Qué cambió en la v2 (2026-11-16):** comercios ampliados (DEC-132); vendedor externo y canales especiales marcados y no recomendados (DEC-135); estado del producto (DEC-149); de 1 a 3 modelos por solicitud (DEC-152); sugerencias (DEC-139); comparadores solo como señal (DEC-154); el impuesto **se muestra pero no ordena**; precio de Amazon del **botón de compra**; "disponible" en línea solo si permite agregar al carrito; solo por nombre **va aparte**; reglas para **varias piezas**; dos modalidades de servicio; tiendas de **Zona 1 y 2**; respuesta en 1 hora; el cobro lo define Jesús. Propuestas de Claude aceptadas por Jesús como valores iniciales configurables, [sesión 2](/sesiones/sesion-2-respuestas.md), bloque 11. La v1 queda en el historial: [RN-011 v1](https://github.com/jjrm2004mx/Offer-Intelligence-Platform-OIP/blob/1c1d4e04d5e5e2401dbb565782bf11061d8813f7/docs/negocio/reglas/RN-011-busqueda-por-articulo.md).

## 1. ¿Qué queremos lograr?
Que, cuando un cliente necesita un producto concreto (por ejemplo, un Nintendo Switch), OIP lo busque en los comercios y diga **dónde está más económico y disponible**, para que Jesús le ofrezca la mejor alternativa con su enlace, o se lo compre y entregue.

## 2. ¿Qué incluye y qué no?
**Incluye:**
- Que Jesús capture la solicitud: traduce lo que necesita el cliente en **1 a 3 modelos** (DEC-152).
- Buscar el artículo en los comercios que sigue OIP: **Home Depot, Walmart, Amazon, Best Buy, Target, GameStop y Nintendo Store**; solo tiendas de EE. UU., en USD (DEC-132).
- Comparar precios, envío y disponibilidad, y presentar las alternativas ordenadas, con enlaces.
- Mostrar la **calidad del precio** de cada opción (RN-012, eje 1; DEC-131).
- Sugerir ofertas o alternativas relacionadas que OIP ya detectó (DEC-139).

**No incluye (por ahora):**
- Que el cliente haga la solicitud directamente (WhatsApp): funcionalidad futura (DEC-112).
- Búsqueda por necesidad automática: futura (DEC-152).
- Comprar automáticamente.
- Calcular margen de reventa (búsqueda automatizada, RN-001 a RN-009).
- Calcular el cobro del servicio: lo define Jesús, fuera de OIP (RN-011 · P4).

## 3. ¿Cómo funciona, en palabras?
1. El cliente le pide un artículo a Jesús.
2. Jesús lo captura: modelo o código, cuántas piezas, qué estados acepta el cliente (por defecto, solo nuevo) y la modalidad del servicio.
3. OIP lo busca, con datos de no más de 1 hora (RN-010). El cliente pasa primero que la búsqueda automatizada.
4. OIP arma la lista: **primero las opciones disponibles, de la más económica a la más cara**; aparte, las que no están disponibles, con disponibilidad dudosa, de vendedor externo o identificadas solo por nombre.
5. Jesús revisa y responde al cliente, de preferencia en **1 hora** y como máximo el mismo día.

## 4. La regla

**4.1 Criterios, en orden de importancia** (DEC-113, RN-011 · P6):
1. **Más económico:** se ordena por **precio total = precio + envío**, por el total del pedido. El **impuesto se muestra, pero no ordena**, porque depende del código postal de entrega (RN-011 · P1).
2. **Disponible:** se recomienda la más económica **entre las disponibles**:
   - En línea: estado **disponible confirmada** (RN-007: "en existencia" y permite agregar al carrito).
   - Recoger en tienda: como en línea; si Jesús va por él, suma el viaje (RN-008).
   - Tienda física: confianza **Alta o Media** (RN-007).

**4.2 Precio de Amazon:** el del vendedor que gana el **botón de compra**, de 1 hora o menos (RN-011 · P8).

**4.3 Presentación**

| Grupo | Qué contiene | Orden |
|---|---|---|
| **Opciones disponibles** | Cumplen 4.1, mismo artículo confirmado por código, vendidas por el comercio, en un estado que el cliente acepta | Por precio total. **La primera es la recomendada** |
| **Otras opciones** | No disponibles; confianza Baja o sin dato; **vendedor externo** (DEC-135); **identificadas solo por nombre** hasta que Jesús las verifique (RN-011 · P9); "puede requerir cuenta especial" (Walmart Business); **"requiere membresía"**; piezas insuficientes | Por precio total, cada una con su motivo |

- **Cupones:** solo los que aparecen en la ficha del comercio.
- **Devolución y garantía:** se muestran como información.
- **Desempates** (mismo precio total): menor envío → mayor confianza → consultada más recientemente.
- **Estado del producto** (RN-014): se muestra en cada opción; solo se recomiendan los estados que el cliente acepta.
- **Comparadores y sitios de seguimiento:** solo señal; cada precio se confirma en la ficha del comercio (DEC-133, DEC-154).

**4.4 Varias piezas** (RN-011 · P10)
- Se compara el **total del pedido con envío**.
- Una opción **sin suficientes piezas va aparte**, marcada "solo N piezas".
- Se vale juntar piezas en **máximo 2 comercios**, como opción adicional, solo si ahorra **10% o más** frente a la mejor opción en un solo comercio.

**4.5 Modalidad del servicio** (RN-011 · P2)

| Modalidad | Cuándo por defecto | Qué se suma |
|---|---|---|
| **Solo enlace** | La recomendada es en línea | Nada |
| **Jesús compra y entrega** | La recomendada es en tienda física | Viaje (RN-008) y entrega (DEC-142) |

**4.6 Tiendas físicas a revisar:** las de **Zona 1 y Zona 2** (hasta 40 km de la garita, RN-008), **máximo 5 por comercio**, ordenadas por cercanía a la garita, para no exceder RN-010.

**4.7 Ahorro:** OIP muestra el **ahorro** de la recomendada frente a la siguiente opción, para respaldar la tarifa que Jesús decida.

**Cada opción muestra:** comercio y sucursal, vendedor, estado, precio, envío, total, impuesto estimado, disponibilidad, confianza, calidad del precio (RN-012), hace cuánto se consultó y el enlace.

| Valor | Qué es | Valor inicial | ¿Confirmado? |
|---|---|---|---|
| Antigüedad máxima del dato | Para esta búsqueda | 1 hora (RN-010) | Aceptado por Jesús |
| Comercios | Inc. 1 | Home Depot, Walmart, Amazon, Best Buy, Target, GameStop, Nintendo Store | DEC-132 |
| Estados aceptados | Por defecto | Solo nuevo; el cliente puede aceptar otros | DEC-149; **por defecto propuesto por Claude (por aceptar)** |
| Impuesto | ¿Ordena? | Se muestra, no ordena | Aceptado por Jesús |
| Juntar piezas | Comercios / ahorro mínimo | 2 / 10% | Aceptado por Jesús |
| Tiendas por comercio | Máximo | 5, Zonas 1 y 2 | Aceptado por Jesús |
| Tiempo de respuesta | Objetivo / máximo | 1 hora / mismo día | Aceptado por Jesús |

Todos los valores son iniciales y configurables.

## 5. ¿Cómo sabremos que funciona? — Ejemplos con números

**Ejemplo A — Nintendo Switch (hay varias opciones)**

Datos encontrados (mismo código UPC, todos nuevos, vendidos por el comercio):

| Comercio | Precio | Envío | Total | Disponibilidad | Confianza |
|---|---|---|---|---|---|
| Walmart, tienda Chula Vista | $299.00 | $0 | $299.00 | "En existencia", hace 40 min | Media |
| Walmart en línea | $329.00 | $0 | $329.00 | Disponible confirmada | Alta |
| Amazon (botón de compra) | $339.99 | $0 | $339.99 | Disponible confirmada | Alta |
| Walmart, tienda National City | $289.00 | $0 | $289.00 | "Existencia limitada", hace 3 h | Baja |
| Home Depot | — | — | — | No lo vende | — |

Resultado:
- **Opciones disponibles:** 1. **Walmart Chula Vista, $299.00 (recomendada)**, modalidad "Jesús compra y entrega"; 2. Walmart en línea, $329.00; 3. Amazon, $339.99.
- **Otras opciones:** Walmart National City, $289.00: más barata, pero con confianza Baja.
- Ahorro de la recomendada frente a la siguiente: 329.00 − 299.00 = **$30.00**. A eso se le suman viaje y entrega, que Jesús considera al fijar su tarifa.

**Ejemplo B — Nada disponible**
- Solo una opción, con "existencia limitada" hace 3 h (Baja) → **sin opciones disponibles**; aviso "repetir la búsqueda más tarde".

**Ejemplo C — Empate en precio**
- Walmart en línea $329.00 con envío $0 (Alta, hace 10 min) y Amazon $329.00 con envío $0 (Alta, hace 40 min). Mismo envío y confianza → gana la más reciente: **Walmart en línea**.

**Ejemplo D — Identificado solo por nombre**
- "Consola Switch OLED blanca" sin código, a $310.00, disponible → va a **Otras opciones**, marcada "verificar que sea el mismo modelo", aunque sea más barata que la recomendada.

**Ejemplo E — Varias piezas**
- El cliente pide 3. Comercio A tiene 3 a $100 c/u, envío $0 → total $300. Comercio B tiene 2 a $85, y C tiene 1 a $95, envío $0 → total combinado $265: ahorra 35 ÷ 300 = **11.7%** ≥ 10% → se muestra como opción adicional. Comercio B solo, con 2 piezas → "solo 2 piezas", aparte.

**Ejemplo F — Vendedor externo**
- En Walmart en línea, un vendedor externo ofrece $279.00 → **Otras opciones**, marcada "vendedor externo", no recomendada.

## 6. ¿Qué información necesitamos?
- **Solicitud** (la captura Jesús): alias del cliente (sin datos personales), 1 a 3 modelos o códigos, cantidad, estados aceptados, notas, modalidad y fecha.
- **De los comercios:** precio, envío, vendedor, estado, disponibilidad en línea y por tienda, membresías, cupones de la ficha y enlace.

## 7. ¿Qué obtenemos?
- La lista de alternativas ordenada, con la recomendada, su ahorro y sugerencias relacionadas, lista para compartir.
- Un registro de la búsqueda: qué se pidió, cuándo y qué se encontró.

## 8. ¿Quién participa?
- **Cliente:** pide el artículo a Jesús.
- **Jesús:** captura, revisa, verifica las opciones identificadas por nombre, responde y fija su tarifa.
- **OIP:** busca, compara y ordena.

## 9. ¿De qué depende?
- RN-007 (disponibilidad), RN-008 (zonas, viaje y entrega), RN-010 (límites y frescura), RN-012 (calidad del precio), RN-013 (identificación) y RN-014 (estado).

## 10. Limitaciones
- Solo encuentra lo que publican en línea los comercios que sigue OIP.
- La disponibilidad en tienda es un dato publicado, no una garantía (RN-007).

## 11. ¿Qué pasa si…?
| Situación | Qué hace OIP |
|---|---|
| No se encuentra el artículo en ningún comercio | "Sin resultados" y sugerencia de revisar el modelo |
| Un comercio está en pausa por bloqueo (RN-010) | "No consultado (en pausa)" para ese comercio; se consultan los demás |
| La descripción es ambigua | Se presentan los modelos encontrados por separado para que Jesús confirme |
| No se cumple la hora de respuesta | Se avisa a Jesús; el resultado parcial queda disponible |

## 12. Preguntas para el experto
1. ¿Le parece bien que, por defecto, solo se recomiende producto **nuevo**, salvo que el cliente acepte otros estados? (propuesta)
2. ¿Juntar piezas en 2 comercios solo si ahorra 10% o más? (propuesta aceptada por Jesús)

## 13. Decisiones tomadas
| Fecha | Decisión | Quién |
|---|---|---|
| 2026-11-09 | La búsqueda por artículo es un servicio a clientes y es necesaria | Jesús |
| 2026-11-09 | Entra en el Incremento 1 | Jesús |
| 2026-11-09 | El cliente pide a Jesús y Jesús captura en OIP; la solicitud directa (WhatsApp) es futura | Jesús |
| 2026-11-09 | Criterios: primero el más económico, segundo que esté disponible | Jesús |
| 2026-11-11 | Comercios ampliados (DEC-132); vendedor externo y canales especiales marcados (DEC-135); usados con estado (DEC-149); 1 a 3 modelos (DEC-152); sugerencias (DEC-139) | Jesús |
| 2026-11-16 | Se recomienda la más económica entre las disponibles | Jesús (propuesta de Claude) |
| 2026-11-16 | El impuesto se muestra, no ordena | Jesús (propuesta de Claude) |
| 2026-11-16 | Precio de Amazon del botón de compra, 1 hora | Jesús (propuesta de Claude) |
| 2026-11-16 | Disponible en línea = en existencia y carrito; recoger en tienda como en línea más viaje | Jesús (propuesta de Claude) |
| 2026-11-16 | Solo por nombre va aparte hasta verificar | Jesús (propuesta de Claude) |
| 2026-11-16 | Varias piezas: total del pedido; insuficientes aparte; máximo 2 comercios con 10% de ahorro | Jesús (propuesta de Claude) |
| 2026-11-16 | Modalidades "solo enlace" y "Jesús compra y entrega" | Jesús (propuesta de Claude) |
| 2026-11-16 | Tiendas de Zonas 1 y 2, máximo 5 por comercio | Jesús (propuesta de Claude) |
| 2026-11-16 | Respuesta en 1 hora, máximo el mismo día | Jesús (propuesta de Claude) |
| 2026-11-16 | El cobro lo define Jesús; OIP muestra el ahorro | Jesús (propuesta de Claude) |

## 14. Revisión de consistencia
- Última revisión: 2026-11-16 (v2) — RECHAZADO
- Detalle: [revisiones/RN-011.md](/revisiones/RN-011.md)
