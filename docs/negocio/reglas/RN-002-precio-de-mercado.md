# RN-002 — Precios de referencia y precio de venta esperado

```yaml
id: RN-002
titulo: Precios de referencia y precio de venta esperado
grupo: común (el precio de venta esperado es por canal)
estado: BORRADOR
version: 2
fecha: 2026-11-11
responsable: Jesús
revisor_negocio: Experto en negocios internacionales
depende_de: [RN-013, RN-014]
version_anterior: https://github.com/jjrm2004mx/Offer-Intelligence-Platform-OIP/blob/5a4744d15b2ac6439f2cd89d25cb377ab437ab36/docs/negocio/reglas/RN-002-precio-de-mercado.md
```

## 1. ¿Qué queremos lograr?
Tener, para cada producto, **referencias de precio separadas** que no se confundan entre sí: cuánto cuesta **hoy** en el mercado (para saber si un precio es competitivo), cuánto cuesta **normalmente** (para saber si hay descuento real) y **a cuánto se puede vender** en cada canal (para calcular la ganancia).

## 2. ¿Qué incluye y qué no?
**Incluye:**
- **Precio de mercado hoy:** lo que cobran hoy los otros comercios por el mismo producto.
- **Precio habitual:** lo que el producto ha costado normalmente, según el historial.
- **Mínimos:** de 90 días y de 12 meses.
- **Precio oficial del fabricante (MSRP)** y **precio tachado** del comercio, solo para los usos que se indican.
- **Precio de venta esperado en Amazon FBM.**
- Productos nuevos y, con su propia referencia, usados (RN-014).

**No incluye:**
- El precio de venta esperado en **venta local** (RN-016).
- Calificar el precio o el descuento (RN-003 y RN-012).
- Paquetes de varias unidades o combos distintos al producto (RN-013).

## 3. ¿Cómo funciona, en palabras?
Hay **cuatro referencias** y cada una sirve para algo distinto (DEC-129):

| Referencia | Sirve para | Nunca sirve para |
|---|---|---|
| **Precio de mercado hoy** | Medir la **competitividad** | Medir el descuento |
| **Precio habitual** | Medir el **descuento real** | — |
| **MSRP** (precio oficial) | Orientar cuando **no hay** precio habitual | Calcular un descuento |
| **Precio tachado** ("antes") | Comprobar si el anuncio está inflado (RN-003) | Calcular un descuento |

Los sitios de seguimiento de precios, comparadores y artículos de ofertas se muestran como **señal**, pero no entran a ninguna cuenta (DEC-154).

**Fuente del historial, por etapas** (DEC-123): primero el **historial propio de OIP**, reforzado con los precios de hoy de otros comercios; si todavía no hay historial propio, solo la comparación entre comercios. Después, las **APIs oficiales** de los comercios que las tengan. Al final, **Keepa**, solo para Amazon y solo como complemento (DEC-124).

## 4. La regla

**Publicación comparable** (la única que entra a las cuentas):
- mismo producto exacto (RN-013) y misma condición (RN-014);
- **vendida por el comercio**, no por un vendedor externo (DEC-135);
- no agotada;
- consultada hace **48 horas o menos**.

Las publicaciones que no cumplen se muestran aparte, con el motivo.

```
precio de mercado hoy = el MÁS BAJO de las publicaciones comparables de los OTROS comercios
                        (sin contar el comercio que publica la oferta)
                        · se necesitan al menos 2 comercios distintos;
                          con menos → "comparación insuficiente"

precio habitual       = mediana de las observaciones comparables de los últimos 60 días
                        (todos los comercios, sin contar las de hoy)
                        · se necesitan al menos 5 observaciones en al menos 3 días distintos;
                          con menos → "sin historial suficiente"
                        · si no hay historial propio suficiente y hay Keepa contratado (producto de Amazon):
                          mediana de 90 días de Amazon, marcada "fuente Keepa"

mínimo de 90 días     = el precio comparable más bajo observado en 90 días
mínimo de 12 meses    = el precio comparable más bajo observado en 12 meses (si hay 12 meses de historial)

precio de venta esperado en Amazon FBM = el MÁS BAJO entre:
                        · precio de hoy en Amazon (nuevo)
                        · precio habitual en Amazon (mediana de las observaciones de Amazon)
```

"Mediana" = el precio del medio al ordenar todos los precios. A diferencia del promedio, no se deja jalar por un día de precio rarísimo (DEC-130). Por eso los números de OIP pueden diferir un poco de los de sitios externos, que suelen usar el promedio.

| Valor | Qué es | Valor inicial | ¿Confirmado? |
|---|---|---|---|
| Antigüedad máxima | Para que una publicación cuente hoy | 48 h | Por confirmar |
| Comercios mínimos | Para tener precio de mercado hoy | 2 | Por confirmar |
| Ventana del precio habitual | Días de historial propio | 60 días | Aceptado por Jesús (DEC-130), validar con el experto |
| Historial suficiente | Observaciones / días distintos | 5 / 3 | Aceptado por Jesús (DEC-130), validar con el experto |
| Ventana Keepa | Días, solo si se contrata | 90 días | Por confirmar |

## 5. ¿Cómo sabremos que funciona? — Ejemplos con números

**Ejemplo A — Taladro: el descuento real ya no se oculta**
- Oferta: Home Depot $150. Precio tachado: $249.
- Hoy, publicaciones comparables de otros comercios: Lowe's $150 (hace 6 h), Amazon $189, Walmart $195.
- Observaciones de los últimos 60 días: $199, $205, $200, $198, $210, $200 (6 observaciones en 5 días).
- Precio de mercado hoy = mínimo(150, 189, 195) = **$150**.
- Precio habitual = mediana(198, 199, 200, 200, 205, 210) = (200 + 200) ÷ 2 = **$200**.
- Con la v1, el "precio de mercado" habría sido el más bajo de todo, $150, y el descuento real habría dado 0%. Con la v2, RN-003 mide el descuento contra $200: **25%**, y la competitividad contra $150: empata con Lowe's.

**Ejemplo B — Vendedor externo excluido**
- Walmart publica el mismo taladro a $140, pero lo vende un **vendedor externo**. No cuenta para el precio de mercado hoy; se muestra aparte como "vendedor externo". El precio de mercado hoy sigue siendo **$150**.

**Ejemplo C — Producto nuevo en el mercado (CASO-001)**
- Switch 2, edición Zelda: sin historial propio y con todas las publicaciones agotadas o sin disponibilidad confirmada.
- Precio de mercado hoy: **comparación insuficiente**. Precio habitual: **sin historial suficiente**.
- Se muestra el MSRP ($519.99) como orientación. No se calcula descuento.

**Ejemplo D — Dato viejo descartado**
- Target tenía el taladro a $139, pero el dato es de hace 4 días → **no se usa**.

**Ejemplo E — Precio de venta esperado en Amazon**
- Amazon hoy: $189. Observaciones de Amazon en 60 días: $195, $199, $189, $199, $195 → mediana **$195**.
- Precio de venta esperado = mínimo(189, 195) = **$189**.

## 6. ¿Qué información necesitamos?
- Identificación del producto (RN-013) y su condición (RN-014).
- Precios de hoy de cada comercio, con vendedor, disponibilidad y hora de consulta (DEC-134).
- Historial propio de OIP (se construye con el tiempo).
- MSRP del fabricante, con fuente y fecha.
- Precio tachado de la publicación.
- Keepa o APIs oficiales, solo cuando se contraten (DEC-123, DEC-124).

## 7. ¿Qué obtenemos?
- Precio de mercado hoy (y qué comercio lo tiene), precio habitual, mínimos de 90 días y de 12 meses, MSRP, precio tachado y precio de venta esperado en Amazon.
- De qué fuente salió cada uno y las marcas "comparación insuficiente" o "sin historial suficiente".

## 8. ¿Quién participa?
- El sistema consulta y calcula.
- El experto valida las ventanas y los mínimos.

## 9. ¿De qué depende?
- RN-013 (mismo producto exacto) y RN-014 (misma condición).
- RN-010 (límites de consulta), que define cuántos comercios se pueden consultar por producto.
- La fuente de precios de Amazon en la etapa 1 (pregunta 4).

## 10. Limitaciones
- Los primeros días **no hay historial propio**: el precio habitual no existe y el descuento real no se puede afirmar. Es esperado (DEC-130).
- El mínimo de 12 meses necesita un año de historial; antes de eso solo existe si se contrata Keepa, y solo para Amazon.
- Keepa refleja Amazon, no el mercado completo.

## 11. ¿Qué pasa si…?
| Situación | Qué hace el sistema |
|---|---|
| Solo un comercio, además del que oferta, tiene el producto | "Comparación insuficiente"; se muestra el precio, pero no hay precio de mercado hoy |
| No hay historial suficiente | "Sin historial suficiente"; se muestra el MSRP si existe |
| El producto no está en Amazon | No hay precio de venta esperado en Amazon; queda el canal local (RN-016) |
| Solo hay publicaciones de vendedores externos | Comparación insuficiente; se muestran aparte |
| La identificación es dudosa (RN-013) | La publicación no cuenta como comparable |
| El MSRP no se encuentra | Se omite; no bloquea nada |

## 12. Preguntas para el experto
1. ¿Le parece correcto separar el precio de hoy (competitividad) del precio habitual (descuento)?
2. ¿60 días y 5 observaciones en 3 días es buena base para el precio habitual? ¿En temporada conviene acortar la ventana?
3. ¿2 comercios son suficientes para hablar de "precio de mercado"?
4. *(Para Jesús)* En la etapa 1, sin Keepa, ¿OIP consulta la página de Amazon como a cualquier otro comercio, con los límites de RN-010? DEC-023 eligió Keepa para no consultar Amazon directamente.
5. *(De la v1)* ¿Usar siempre el precio más bajo como precio de venta esperado (criterio conservador), o en productos de mucha demanda conviene el habitual?
6. *(De la v1)* Cuando otro comercio vende mucho más barato que Amazon, ¿eso debería bajar la calificación de la oportunidad aunque se venda en Amazon? (En la v2, la competencia fuera de Amazon se ve en el precio de mercado hoy.)

## 13. Decisiones tomadas
| Fecha | Decisión | Quién |
|---|---|---|
| 2026-11-08 | La fuente del historial de Amazon es Keepa (DEC-023) | Jesús |
| 2026-11-11 | Keepa diferido; fuente por etapas: historial propio + otros comercios → APIs oficiales → Keepa (DEC-123, DEC-124) | Jesús |
| 2026-11-11 | Cuatro referencias separadas; el descuento solo contra el habitual (DEC-129) | Jesús |
| 2026-11-11 | Precio habitual: mediana de 60 días, con 5 observaciones en 3 días (DEC-130) | Jesús |
| 2026-11-11 | Se separan el precio de hoy y el habitual (DEC-147) | Jesús |
| 2026-11-11 | Sitios de seguimiento, comparadores y artículos: solo señal (DEC-154) | Jesús |

**Cambios de la v2 contra la v1:** el "precio de mercado" único se divide en precio de mercado hoy y precio habitual; se agregan mínimos, MSRP y precio tachado con usos definidos; cuentan solo publicaciones comparables (vendedor, disponibilidad, condición); la fuente pasa a ser por etapas; el precio de venta local se mueve a RN-016. Los ejemplos A, B y C de la v1 (taladro, sierra, dato viejo) se reemplazan por A a E.

## 14. Revisión de consistencia
- Última revisión: 2026-11-08 (v1) — APROBADO CON OBSERVACIONES. **La v2 está pendiente de revisión.**
- Detalle: [revisiones/RN-002.md](/revisiones/RN-002.md)
