# RN-011 — Búsqueda particular por artículo (servicio a clientes)

```yaml
id: RN-011
titulo: Búsqueda particular por artículo (servicio a clientes)
estado: BORRADOR
version: 1
fecha: 2026-11-09
responsable: Jesús
revisor_negocio: Experto en negocios internacionales
depende_de: [RN-007, RN-010]
origen: Sesión 1 con el experto (2026-11-09) — DEC-110 a DEC-113
```

## 1. ¿Qué queremos lograr?
Que, cuando un cliente necesita un producto concreto que no encuentra (por ejemplo, un Nintendo Switch), OIP lo busque en los comercios y diga **dónde está más económico y disponible**, para que Jesús le ofrezca la mejor alternativa con su enlace.

## 2. ¿Qué incluye y qué no?
**Incluye:**
- Que Jesús capture la solicitud del cliente en OIP.
- Buscar el artículo en los comercios que sigue OIP y en Amazon.
- Comparar precios y disponibilidad.
- Presentar las alternativas ordenadas, con enlaces.

**No incluye (por ahora):**
- Que el cliente haga la solicitud directamente, por ejemplo por WhatsApp. Es **funcionalidad futura** (DEC-112).
- Comprar automáticamente.
- Calcular margen de reventa: esta búsqueda **no** busca reventa. Esa es la búsqueda automatizada (RN-001 a RN-009).
- Seguir buscando de forma automática durante días hasta que aparezca (posible mejora futura).

## 3. ¿Cómo funciona, en palabras?
1. El cliente le pide un artículo a Jesús.
2. Jesús lo captura en OIP: qué artículo, con el modelo o código si lo tiene, y cuántas piezas.
3. OIP lo busca en los comercios, con datos de no más de 1 hora (RN-010).
4. OIP arma una lista: **primero las opciones disponibles, de la más económica a la más cara**. Después, aparte, las que no están disponibles o cuya disponibilidad es dudosa.
5. Jesús revisa la lista y le comparte al cliente la mejor opción y sus alternativas.

## 4. La regla

**Criterios, en orden de importancia** (DEC-113):
1. **Más económico:** se compara el **precio total** = precio + envío (si lo hay).
2. **Disponible:** solo cuentan como disponibles:
   - En línea: el comercio lo muestra disponible para envío o recolección.
   - En tienda física: disponibilidad con confianza **Alta o Media** (RN-007).

**Presentación:**

| Grupo | Qué contiene | Orden |
|---|---|---|
| **Opciones disponibles** | Las que cumplen el criterio 2 | Por precio total, de menor a mayor. **La primera es la recomendada** |
| **Otras opciones** | No disponibles, con confianza Baja o sin dato | Por precio total, marcadas con el motivo |

**Desempates** (mismo precio total): primero la de mayor confianza; después, la consultada más recientemente.

**Mismo artículo:** solo se comparan productos que son el mismo artículo. Si se identificó por código (UPC/EAN) es seguro. Si se identificó solo por nombre, se muestra con la advertencia **"verificar que sea el mismo modelo"**. Versiones distintas (color, paquete con accesorios, capacidad) se tratan como artículos distintos.

**Cada opción muestra:** comercio (y sucursal si es tienda física), precio, envío, precio total, disponibilidad, confianza, hace cuánto se consultó y el enlace.

| Valor | Qué es | Valor inicial | ¿Confirmado? |
|---|---|---|---|
| Antigüedad máxima del dato | Para esta búsqueda | 1 hora (RN-010) | Por confirmar |
| Comercios consultados | Inc. 1 | Home Depot, Walmart y Amazon (nuevo) | Por confirmar |
| Productos usados o reacondicionados | ¿Se incluyen? | No | Por confirmar |
| Impuesto | ¿Entra en el precio total? | No (es similar entre comercios de la misma zona) | Por confirmar |

## 5. ¿Cómo sabremos que funciona? — Ejemplos con números

**Ejemplo A — Nintendo Switch (hay varias opciones)**

Datos encontrados (mismo código UPC, todos nuevos):

| Comercio | Precio | Envío | Total | Disponibilidad | Confianza |
|---|---|---|---|---|---|
| Walmart, tienda Chula Vista | $299.00 | $0 | $299.00 | "En existencia", hace 4 h | Media |
| Walmart en línea | $329.00 | $0 | $329.00 | Disponible para envío | Alta |
| Amazon | $339.99 | $0 | $339.99 | Disponible | Alta |
| Walmart, tienda National City | $289.00 | $0 | $289.00 | "Existencia limitada" | Baja |
| Home Depot | — | — | — | No lo vende | — |

Resultado:
- **Opciones disponibles:**
  1. **Walmart Chula Vista, $299.00 (recomendada)**
  2. Walmart en línea, $329.00
  3. Amazon, $339.99
- **Otras opciones:** Walmart National City, $289.00. Es más barata, pero tiene "existencia limitada" (confianza Baja), así que no se recomienda.
- La recomendada ahorra $30.00 frente a la siguiente opción (329.00 − 299.00).

**Ejemplo B — Nada disponible**
- Solo aparece una opción: en una tienda, con "existencia limitada" (confianza Baja).
- Resultado: **sin opciones disponibles**. La lista muestra esa opción en "Otras opciones" y un aviso: *"No hay opción disponible confirmada; repetir la búsqueda más tarde"*.

**Ejemplo C — Empate en precio**
- Walmart en línea a $329.00 (confianza Alta, consultado hace 10 min) y Amazon a $329.00 (confianza Alta, consultado hace 40 min).
- Misma confianza, así que gana la más reciente: **Walmart en línea** queda primero.

**Ejemplo D — Identificado solo por nombre**
- Un comercio publica "Consola Switch OLED blanca" sin código, a $310.00, disponible.
- Aparece en "Opciones disponibles" en su lugar por precio, con la advertencia **"verificar que sea el mismo modelo"**.

## 6. ¿Qué información necesitamos?
- **Solicitud** (la captura Jesús):
  - Identificador del cliente: **solo un alias**, sin datos personales.
  - Descripción del artículo, modelo o código (si lo hay), cantidad, notas (color, versión) y fecha.
- **De los comercios:** precio, envío, disponibilidad en línea y por tienda, enlace.
- **De Amazon:** precio de producto nuevo y disponibilidad.

## 7. ¿Qué obtenemos?
- La lista de alternativas ordenada, con la opción recomendada, lista para que Jesús se la comparta al cliente.
- Un registro de la búsqueda: qué se pidió, cuándo y qué se encontró.

## 8. ¿Quién participa?
- **Cliente:** pide el artículo a Jesús (en el Inc. 1 no usa OIP).
- **Jesús:** captura la solicitud, revisa el resultado y responde al cliente.
- **OIP:** busca, compara y ordena.

## 9. ¿De qué depende?
- RN-007 (confianza de disponibilidad en tienda).
- RN-010 (límites de consulta y frescura de 1 hora).
- Del mismo motor de búsqueda que la búsqueda automatizada (DEC-114).

## 10. Limitaciones
- Solo encuentra lo que publican en línea los comercios que sigue OIP. Una existencia que solo se ve en el anaquel no aparece.
- La disponibilidad en tienda es un dato publicado, no una garantía (RN-007).

## 11. ¿Qué pasa si…?
| Situación | Qué hace OIP |
|---|---|
| No se encuentra el artículo en ningún comercio | Resultado "sin resultados" y sugerencia de revisar la descripción o el modelo |
| Un comercio está en pausa por bloqueo (RN-010) | Se indica "no consultado (en pausa)" para ese comercio y se consultan los demás |
| La descripción es ambigua (por ejemplo, "Switch" sin modelo) | Se presentan los modelos encontrados, por separado, para que Jesús confirme con el cliente |
| El cliente pide varias piezas y una tienda tiene menos | Se muestra la cantidad publicada; si no alcanza, se marca "cantidad insuficiente" |

## 12. Preguntas para el experto
1. ¿El impuesto debería sumarse al precio total, o basta con precio + envío?
2. Si la opción más barata está en una tienda física, ¿Jesús va por ella y se la entrega al cliente (y entonces cuenta el costo del viaje, RN-008), o solo le comparte el enlace?
3. ¿Se incluyen productos reacondicionados si son mucho más baratos, o siempre solo nuevos?
4. ¿Cómo se cobra este servicio (tarifa fija, porcentaje)? ¿Debe OIP calcularlo?
5. Además de Home Depot, Walmart y Amazon, ¿qué comercios conviene consultar para este servicio (por ejemplo, tiendas de electrónica)?
6. **Interpretación por confirmar:** la regla dice "primero el más económico, segundo que esté disponible". Aquí se aplicó así: *se recomienda la más económica **entre las disponibles***. Una opción más barata pero con disponibilidad dudosa se muestra aparte y no se recomienda (ejemplo A, National City). ¿Es lo que se busca?

## 13. Decisiones tomadas
| Fecha | Decisión | Quién |
|---|---|---|
| 2026-11-09 | La búsqueda por artículo es un servicio a clientes y es necesaria | Jesús |
| 2026-11-09 | Entra en el Incremento 1 | Jesús |
| 2026-11-09 | El cliente pide a Jesús y Jesús captura en OIP; la solicitud directa (WhatsApp) es futura | Jesús |
| 2026-11-09 | Criterios: primero el más económico, segundo que esté disponible | Jesús |

## 14. Revisión de consistencia
- Última revisión: 2026-11-09 — APROBADO CON OBSERVACIONES
- Detalle: [revisiones/RN-011.md](/revisiones/RN-011.md)
