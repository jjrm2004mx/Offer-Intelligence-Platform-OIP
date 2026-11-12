# RN-011 — Búsqueda particular por artículo (servicio a clientes)

```yaml
id: RN-011
titulo: Búsqueda particular por artículo (servicio a clientes)
grupo: común
estado: BORRADOR
version: 2
fecha: 2026-11-11
responsable: Jesús
revisor_negocio: Experto en negocios internacionales
depende_de: [RN-007, RN-010, RN-012, RN-013, RN-014, RN-015]
origen: Sesión 1 con el experto (2026-11-09) — DEC-110 a DEC-113
version_anterior: https://github.com/jjrm2004mx/Offer-Intelligence-Platform-OIP/blob/5a4744d15b2ac6439f2cd89d25cb377ab437ab36/docs/negocio/reglas/RN-011-busqueda-por-articulo.md
```

## 1. ¿Qué queremos lograr?
Que, cuando un cliente necesita un producto concreto que no encuentra (por ejemplo, un Nintendo Switch), OIP lo busque en los comercios y diga **dónde está más económico y disponible**, para que Jesús le ofrezca la mejor alternativa con su enlace. Responde **"¿dónde conviene comprarlo?"**; la pregunta "¿está barato?" es RN-012.

## 2. ¿Qué incluye y qué no?
**Incluye:**
- Que Jesús capture la solicitud del cliente en OIP, traduciendo su necesidad en **1 a 3 modelos** concretos (DEC-152).
- Buscar el artículo en los comercios del Inc. 1 (sección 4) y mostrar el precio de Amazon que capture Jesús (DEC-160).
- Comparar el **costo total** y la disponibilidad.
- Presentar las alternativas ordenadas, con enlaces, la calidad del precio de cada una (RN-012) y **sugerencias** relacionadas (DEC-139).

**No incluye (por ahora):**
- Que el cliente haga la solicitud directamente, por ejemplo por WhatsApp. Es **funcionalidad futura** (DEC-112).
- La búsqueda **por necesidad** automática (el cliente describe y OIP propone modelos). Es funcionalidad futura (DEC-152).
- Comprar automáticamente.
- Calcular margen de reventa: esta búsqueda **no** busca reventa (RN-001 a RN-009).
- Seguir buscando de forma automática durante días hasta que aparezca (posible mejora futura).

## 3. ¿Cómo funciona, en palabras?
1. El cliente le pide un artículo a Jesús.
2. Jesús lo captura en OIP: el modelo o los modelos (hasta 3), el código si lo tiene, cuántas piezas y si el cliente acepta usados o reacondicionados.
3. OIP lo busca en los comercios, con datos de no más de 1 hora (RN-010). Esta búsqueda pasa al frente de la fila de cada comercio. Si Jesús captura el precio de Amazon, se agrega.
4. OIP arma una lista: **primero las opciones que se pueden recomendar, de la de menor costo total a la de mayor**. Después, aparte, las demás, cada una con su motivo.
5. Jesús revisa la lista y le comparte al cliente la mejor opción y sus alternativas.

## 4. La regla

**Comercios del Inc. 1:** Home Depot, Walmart, Target, Best Buy, GameStop y Nintendo Store (DEC-132), en línea y, cuando aplique, en las **sucursales de la zona de San Diego** que Jesús tenga registradas. **Amazon**, solo con el precio que Jesús capture a mano, marcado "captura manual" (DEC-156, DEC-160). Solo tiendas de EE. UU., en USD.

**Costo total** (lo que ordena):

```
costo total = precio × piezas + envío del pedido
```

- **Impuesto de venta:** se muestra, pero **no ordena**: depende del código postal de entrega y casi nunca cambia el orden entre comercios.
- **Precio con membresía** (Prime, Target Circle, My Best Buy): se muestra marcado "requiere membresía"; ordena con el **precio normal**.
- **Cupones:** solo los que aparecen en la ficha del comercio.
- **Devolución y garantía:** se muestran como información; no se convierten a dinero.

**¿Cuándo se puede recomendar una opción?** Cuando cumple **todo**:
1. Mismo artículo: identificación **confirmada** (RN-013, niveles 1 y 2).
2. Condición aceptada por el cliente (RN-014); por defecto, solo **nuevo**.
3. **Disponible:** en línea, "disponible confirmada" (RN-007 §4.2); en tienda física, confianza **Alta o Media** (RN-007 §4.1).
4. Vende **el comercio o el fabricante**; un vendedor externo o un particular se muestra marcado y **no se recomienda por defecto** (DEC-135, RN-015).
5. No es un **canal especial** que pida una cuenta aparte (por ejemplo, Walmart Business): esos se muestran marcados "puede requerir cuenta especial".
6. Alcanza la **cantidad** de piezas pedida.

**Presentación:**

| Grupo | Qué contiene | Orden |
|---|---|---|
| **Opciones recomendables** | Las que cumplen los 6 criterios | Por costo total, de menor a mayor. **La primera es la recomendada** |
| **Otras opciones** | Las demás, cada una con su motivo (agotado, no confirmada, vendedor externo, identificación no confirmada, cantidad insuficiente, canal especial…) | Por costo total, de menor a mayor |
| **También te puede interesar** | Sugerencias (DEC-139): otra generación del modelo, o una oferta relacionada con calidad "Buena oferta" o mejor (RN-012) | Por calidad del precio |

Las identificaciones de **coincidencia dudosa** (RN-013, nivel 4) no se muestran.

**Desempates** (mismo costo total), en orden: (1) mayor certeza de disponibilidad (en línea "disponible confirmada" o tienda Alta, antes que tienda Media); (2) menor plazo de entrega; (3) la consultada más recientemente; (4) orden alfabético del comercio.

**Cada opción muestra:** comercio (y sucursal si es tienda física), vendedor, condición, precio, envío, costo total, impuesto estimado, disponibilidad, hace cuánto se consultó, calidad del precio (RN-012), devolución y garantía, y el enlace.

| Valor | Qué es | Valor inicial | ¿Confirmado? |
|---|---|---|---|
| Antigüedad máxima del dato | Para esta búsqueda | 1 hora (RN-010) | Por confirmar |
| Modelos por solicitud | Máximo | 3 | DEC-152 |
| Condición por defecto | Si el cliente no dice | Solo nuevo | Por confirmar |
| Sucursales físicas | Cuáles se consultan | Las de la zona de San Diego registradas por Jesús | Por confirmar |

## 5. ¿Cómo sabremos que funciona? — Ejemplos con números

**Ejemplo A — Nintendo Switch (de la v1, corregido: datos de 1 hora o menos)**
Mismo código UPC, todos nuevos, vendidos por el comercio:

| Comercio | Precio | Envío | Total | Disponibilidad |
|---|---|---|---|---|
| Walmart, tienda Chula Vista | $299.00 | $0 | $299.00 | "En existencia", hace 40 min → Media |
| Walmart en línea | $329.00 | $0 | $329.00 | Disponible confirmada |
| Amazon (captura manual de Jesús) | $339.99 | $0 | $339.99 | Disponible, según Jesús |
| Walmart, tienda National City | $289.00 | $0 | $289.00 | "Existencia limitada" → Baja |
| Home Depot | — | — | — | No lo vende |

Resultado:
- **Opciones recomendables:** 1. **Walmart Chula Vista, $299.00 (recomendada)** · 2. Walmart en línea, $329.00 · 3. Amazon, $339.99.
- **Otras opciones:** Walmart National City, $289.00: más barata, pero con confianza Baja.
- La recomendada ahorra **$30.00** frente a la siguiente (329.00 − 299.00).

**Ejemplo B — Nada disponible (CASO-001)**
- Switch 2 Zelda: Walmart $459.99 de vendedor externo; Amazon y GameStop $499.99 sin disponibilidad confirmada; Walmart Business $519.00 con existencia limitada y canal especial; Best Buy, Target y Nintendo Store agotados.
- Resultado: **ninguna opción recomendable**. Aviso: *"No hay opción disponible confirmada; repetir la búsqueda más tarde"*. Todas aparecen en "Otras opciones" con su motivo.

**Ejemplo C — Empate en costo total**
- Walmart en línea $329.00 (disponible confirmada, entrega en 2 días) y Best Buy $329.00 (disponible confirmada, entrega en 4 días).
- Misma certeza → gana el menor plazo: **Walmart en línea** queda primero.

**Ejemplo D — Identificación no confirmada**
- Un comercio publica "Consola Switch OLED blanca" con modelo pero sin detalle del contenido, a $310.00. Nivel 3 de RN-013 → va a **"Otras opciones"** con el motivo "verificar que sea el mismo modelo". Ya no puede ser la recomendada.

**Ejemplo E — Varias piezas**
- El cliente pide **2** consolas. Walmart en línea: 329.00 × 2 + 0 = **$658.00**. Amazon: 339.99 × 2 + 0 = **$679.98**.
- Recomendada: Walmart en línea; ahorra **$21.98**. Una tienda con 1 sola pieza va a "Otras opciones" por "cantidad insuficiente".

**Ejemplo F — Membresía**
- Target muestra $319.00 con Target Circle y $329.00 normal. Ordena con **$329.00**; se muestra "con membresía: $319.00".

**Ejemplo G — Sugerencia (CASO-003)**
- El cliente pide los Bose QuietComfort de primera generación ($169). En "También te puede interesar": la segunda generación a $199, con la nota "$30 más; versión nueva".

## 6. ¿Qué información necesitamos?
- **Solicitud** (la captura Jesús):
  - Identificador del cliente: **solo un alias**, sin datos personales.
  - Descripción, modelo o modelos (hasta 3), código si lo hay, cantidad, condición aceptada, notas (color, versión) y fecha.
- **De los comercios:** precio, envío y plazo, vendedor, condición, disponibilidad en línea y por sucursal, precio con membresía, cupones de la ficha, devolución y garantía, enlace.
- **De Amazon:** precio, vendedor y disponibilidad, **capturados por Jesús**.

## 7. ¿Qué obtenemos?
- La lista de alternativas ordenada, con la opción recomendada y las sugerencias, lista para compartir.
- Un registro de la búsqueda: qué se pidió, cuándo y qué se encontró.

## 8. ¿Quién participa?
- **Cliente:** pide el artículo a Jesús (en el Inc. 1 no usa OIP).
- **Jesús:** captura la solicitud y el precio de Amazon, revisa el resultado y responde al cliente.
- **OIP:** busca, compara y ordena.

## 9. ¿De qué depende?
- RN-007 (disponibilidad), RN-010 (límites y frescura de 1 hora), RN-012 (calidad del precio), RN-013 (mismo artículo), RN-014 (condición) y RN-015 (vendedor y riesgo).
- Del mismo motor de búsqueda que la búsqueda automatizada (DEC-114).

## 10. Limitaciones
- Solo encuentra lo que publican en línea los comercios que sigue OIP. Una existencia que solo se ve en el anaquel no aparece.
- La disponibilidad en tienda es un dato publicado, no una garantía (RN-007).
- El precio de Amazon depende de que Jesús lo capture.

## 11. ¿Qué pasa si…?
| Situación | Qué hace OIP |
|---|---|
| No se encuentra el artículo en ningún comercio | Resultado "sin resultados" y sugerencia de revisar la descripción o el modelo |
| Un comercio está en pausa por bloqueo (RN-010) | Se indica "no consultado (en pausa)" para ese comercio y se consultan los demás |
| La descripción es ambigua (por ejemplo, "Switch" sin modelo) | Se presentan los modelos encontrados, por separado, para que Jesús confirme con el cliente |
| El cliente pide varias piezas y una tienda tiene menos | "Cantidad insuficiente" en "Otras opciones" |
| Un comercio no muestra resultado | Se indica "sin resultado en este comercio" |
| Jesús no captura el precio de Amazon | Amazon no aparece; se indica "Amazon no consultado" |

## 12. Preguntas para el experto
1. *(De la v1)* ¿El impuesto debería sumarse al precio total? (En la v2 se muestra, pero no ordena.)
2. *(De la v1)* Si la opción más barata está en una tienda física, ¿Jesús va por ella y se la entrega al cliente (y entonces cuenta el costo del viaje, RN-008), o solo le comparte el enlace?
3. *(De la v1)* ¿Se incluyen productos reacondicionados si son mucho más baratos, o siempre solo nuevos? (En la v2: solo si el cliente acepta.)
4. *(De la v1)* ¿Cómo se cobra este servicio (tarifa fija, porcentaje)? ¿Debe OIP calcularlo?
5. *(De la v1, respondida en parte)* Comercios: en la v2 se agregan Target, Best Buy, GameStop y Nintendo Store. ¿Faltan otros?
6. *(De la v1)* **Interpretación por confirmar:** "primero el más económico, segundo que esté disponible" se aplica como *la más económica **entre las disponibles***. ¿Es lo que se busca?

## 13. Decisiones tomadas
| Fecha | Decisión | Quién |
|---|---|---|
| 2026-11-09 | La búsqueda por artículo es un servicio a clientes y es necesaria | Jesús |
| 2026-11-09 | Entra en el Incremento 1 | Jesús |
| 2026-11-09 | El cliente pide a Jesús y Jesús captura en OIP; la solicitud directa (WhatsApp) es futura | Jesús |
| 2026-11-09 | Criterios: primero el más económico, segundo que esté disponible | Jesús |
| 2026-11-11 | Comercios nuevos, solo EE. UU. y USD (DEC-132) | Jesús |
| 2026-11-11 | Vendedor externo y canales especiales marcados, no recomendados (DEC-135) | Jesús |
| 2026-11-11 | Sugerencias según el artículo (DEC-139) | Jesús |
| 2026-11-11 | Búsqueda por necesidad: Jesús la traduce en 1 a 3 modelos (DEC-152) | Jesús |
| 2026-11-11 | Amazon con captura manual de Jesús (DEC-160) | Jesús |

**Cambios de la v2 contra la v1:** se corrigen los defectos D-001 a D-009 de la revisión (dato de 4 horas en el ejemplo A, confianza en línea, fuente de Amazon, identificación por nombre, varias piezas, redacción de DEC-113, sucursales, desempates, "Amazon (nuevo)"). D-010 quedó resuelto con la arquitectura v1.3. Se agregan los criterios de recomendación (vendedor, condición, canal especial, cantidad), el costo total con impuesto, membresías, cupones y garantía, las sugerencias y los comercios nuevos.

## 14. Revisión de consistencia
- Última revisión: 2026-11-11 (v2) — **APROBADO CON OBSERVACIONES**. Revisión anterior: 2026-11-09 (v1) — APROBADO CON OBSERVACIONES.
- Detalle: [revisiones/RN-011.md](/revisiones/RN-011.md)
