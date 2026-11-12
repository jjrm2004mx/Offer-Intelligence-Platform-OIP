# RN-003 — Descuento real y descuentos falsos o engañosos

```yaml
id: RN-003
titulo: Descuento real y descuentos falsos o engañosos
grupo: común
estado: BORRADOR
version: 2
fecha: 2026-11-11
responsable: Jesús
revisor_negocio: Experto en negocios internacionales
depende_de: [RN-002, RN-013]
version_anterior: https://github.com/jjrm2004mx/Offer-Intelligence-Platform-OIP/blob/5a4744d15b2ac6439f2cd89d25cb377ab437ab36/docs/negocio/reglas/RN-003-descuentos-falsos.md
```

## 1. ¿Qué queremos lograr?
Que el sistema **no se deje engañar** por el "antes $200, ahora $20" de las tiendas. Lo que importa es el **descuento real** contra lo que el producto cuesta normalmente, y la **ventaja** contra lo que cobran hoy los demás, no el descuento que anuncia la tienda.

## 2. ¿Qué incluye y qué no?
**Incluye:**
- Calcular tres números: descuento anunciado, **descuento real** y **ventaja contra el mercado**.
- Marcar las ofertas con señales de engaño o con datos insuficientes.
- Servir de **filtro previo**: decidir qué ofertas vale la pena investigar.

**No incluye:**
- Clasificar la calidad del precio (RN-012).
- Decidir el nivel de la oportunidad de reventa (RN-009).
- Calcular ganancias (RN-001 y RN-005).
- Identificar el producto (RN-013): la marca "coincidencia dudosa" vive ahí.

## 3. ¿Cómo funciona, en palabras?
El descuento que anuncia la tienda **solo sirve para encontrar** candidatos: decide qué investigar, nunca califica. Después se calculan dos cosas distintas (DEC-128):
- **Descuento real:** cuánto bajó contra el **precio habitual** (RN-002).
- **Ventaja contra el mercado:** cuánto más barato está que el **precio de mercado hoy** (RN-002).

Además se compara el precio tachado con el **precio habitual** (o, si no lo hay, con el historial de la propia tienda): si el producto casi nunca costó el "precio antes", ese precio está inflado.

## 4. La regla

```
descuento anunciado (%)  = (1 − precio de oferta ÷ precio tachado) × 100
descuento real (%)       = (1 − precio de oferta ÷ precio habitual) × 100
ventaja contra mercado (%) = (1 − precio de oferta ÷ precio de mercado hoy) × 100
```

Los porcentajes se redondean a 2 decimales para mostrarlos, pero se comparan sin redondear.

**Filtro previo** (para no gastar consultas, RN-010): una oferta descubierta pasa a investigarse (buscar el mismo producto en otros comercios) si su identificación no es dudosa (RN-013) y cumple **una** de estas:
- descuento anunciado de **40% o más**, o de **30% o más** si es de una **marca reconocida de la lista prioritaria** (DEC-158);
- viene de una **página de campaña o folleto sin precio tachado** y es de una **categoría prioritaria de la temporada** (DEC-153) o está **por debajo del último precio que OIP observó** (DEC-157).

Las demás quedan registradas, sin investigar.

**Marcas** (una oferta puede tener varias):

| Marca | Cuándo se asigna | Qué provoca |
|---|---|---|
| **PRECIO ANTES INFLADO** | El precio tachado es más de **1.5 veces** el **precio habitual** (RN-002, DEC-129); si no hay precio habitual, más de 1.5 veces la mediana de 60 días de **esa misma tienda** | Se ignora el descuento anunciado y se muestra la advertencia |
| **DESCUENTO ANUNCIADO NO COMPROBADO** | El descuento anunciado supera al real en **más de 15 puntos**, o hay descuento anunciado y no hay precio habitual | Se muestra junto a la clasificación del precio (RN-012), sin cambiarla |
| **MERCADO YA BARATO** | El descuento real es **menor a 20%** | **Para reventa** (A): se descarta. Para calidad del precio (RN-012) y búsqueda por artículo (RN-011): no se descarta |
| **SIN HISTORIAL SUFICIENTE** | No hay precio habitual (RN-002) | No se calcula el descuento real; la reventa sigue por margen (RN-001) y la calidad del precio queda limitada (RN-012) |
| **COMPARACIÓN INSUFICIENTE** | No hay precio de mercado hoy (RN-002) | No se calcula la ventaja contra el mercado |
| **SIN REFERENCIA** | No hay precio habitual **ni** precio de mercado hoy | No se evalúa; queda para revisión manual, sin alerta |

| Valor | Qué es | Valor inicial | ¿Confirmado? |
|---|---|---|---|
| Factor de inflado | Veces sobre el precio habitual (o la mediana de la tienda) | 1.5 | Por confirmar |
| Ventana de la tienda | Días, solo si no hay precio habitual | 60 | Por confirmar |
| Descuento real mínimo para reventa | Por debajo, se descarta para reventa | 20% | Por confirmar |
| Diferencia para "no comprobado" | Puntos entre anunciado y real | 15 | Por confirmar |
| Descuento anunciado del filtro previo | Para investigar | 40% general · 30% marcas reconocidas de la lista prioritaria | Decidido (DEC-158); valores por confirmar con el experto |

## 5. ¿Cómo sabremos que funciona? — Ejemplos con números

**Ejemplo A — La lámpara (descuento falso; de la v1, recalculado)**
- Walmart anuncia: antes $200, ahora $20 → anunciado = (1 − 20 ÷ 200) × 100 = **90%**.
- Observaciones de 60 días en todos los comercios: $25, $25, $24, $22, $22, $23 → precio habitual = (23 + 24) ÷ 2 = **$23.50**.
- 1.5 × 23.50 = $35.25, y $200 > $35.25 → **PRECIO ANTES INFLADO**.
- Descuento real = (1 − 20 ÷ 23.50) × 100 = **14.89%** → **MERCADO YA BARATO** → **descartada para reventa**.
- 90 − 14.89 = 75.11 puntos → **DESCUENTO ANUNCIADO NO COMPROBADO**.

**Ejemplo B — Rotomartillo (RN-002, ejemplo A)**
- Home Depot: antes $249, ahora $150 → anunciado = **39.76%**. Pasa el filtro previo solo si la marca está en la lista prioritaria (30%); si no, se evalúa igual cuando llega por búsqueda por artículo o captura manual.
- Precio habitual $200 → descuento real = (1 − 150 ÷ 200) × 100 = **25.00%**.
- Precio de mercado hoy $150 → ventaja = **0.00%** (empata con Lowe's).
- 39.76 − 25.00 = 14.76 puntos → **no** se marca "no comprobado".

**Ejemplo C — Bose QuietComfort (CASO-003, historial supuesto)**
- Best Buy: antes $359, ahora $169 → anunciado = **52.92%**.
- Precio habitual $169 → descuento real = **0.00%** → **MERCADO YA BARATO** (no sirve para reventa).
- 52.92 − 0 = 52.92 puntos → **DESCUENTO ANUNCIADO NO COMPROBADO**.
- Precio de mercado hoy $169 (Amazon) → ventaja = **0.00%**.

**Ejemplo D — Producto sin historial (CASO-002)**
- DEWALT ATOMIC: antes $249, ahora $169 → anunciado = 32.13%. Sin historial y sin otros comercios → **SIN REFERENCIA** → revisión manual, sin alerta.

**Ejemplo E — Sierra circular en liquidación (de la v1; la usan RN-005, RN-008 y RN-009)**
- Home Depot: antes $129, ahora $29 → anunciado = **77.52%** → pasa el filtro previo.
- Precio habitual $119 y precio de mercado hoy $119.
- Descuento real = (1 − 29 ÷ 119) × 100 = **75.63%**; ventaja = **75.63%** → sigue en evaluación de reventa.
- 77.52 − 75.63 = 1.89 puntos → el anuncio es honesto.

## 6. ¿Qué información necesitamos?
- Precio de oferta y precio tachado de la publicación.
- Precio habitual y precio de mercado hoy (RN-002).
- Historial de 60 días de la misma tienda (solo si no hay precio habitual).
- Categoría del producto y resultado de la identificación (RN-013).

## 7. ¿Qué obtenemos?
- Descuento anunciado, descuento real, ventaja contra el mercado y las marcas que apliquen.
- Si la oferta pasa el filtro previo.

## 8. ¿Quién participa?
- El sistema calcula y marca.
- Jesús revisa manualmente las ofertas "sin referencia".

## 9. ¿De qué depende?
- RN-002 (precio habitual y de mercado hoy) y RN-013 (identificación).
- Del historial que el sistema junta de cada tienda.

## 10. Limitaciones
- Al arrancar no hay historial: los primeros días casi todo será "sin historial suficiente", y la protección principal es la ventaja contra el mercado.
- El filtro previo puede dejar fuera ofertas reales con poco descuento anunciado; por eso la búsqueda por artículo y la captura manual no pasan por él.

## 11. ¿Qué pasa si…?
| Situación | Qué hace el sistema |
|---|---|
| La tienda no muestra precio tachado | Descuento anunciado = no disponible. Pasa el filtro previo solo si viene de una página de campaña o folleto y cumple DEC-157, o si llega por captura manual o búsqueda por artículo |
| El precio de oferta es mayor que el habitual | Descuento real negativo → MERCADO YA BARATO |
| El precio de oferta es mayor que el de mercado hoy | Ventaja negativa: hay otro comercio más barato |
| No hay precio habitual y la tienda tiene menos de 5 observaciones en 60 días | No se evalúa "precio antes inflado" |

## 12. Preguntas para el experto
1. *(De la v1)* ¿20% de descuento real es un buen mínimo para reventa, o debería ser más (25%, 30%)?
2. *(De la v1)* ¿1.5 veces el precio habitual (o el típico de la tienda) es un buen umbral para llamar "inflado" al precio antes?
3. *(De la v1)* ¿Conoce otras señales comunes de descuento engañoso? Por ejemplo, precio por unidad mayor en el "paquete con descuento".
4. ¿40% de descuento anunciado es un buen filtro para decidir qué investigar?
5. ¿15 puntos de diferencia es razonable para marcar un anuncio como "no comprobado"?

## 13. Decisiones tomadas
| Fecha | Decisión | Quién |
|---|---|---|
| 2026-11-08 | El descuento anunciado solo sirve para descubrir candidatos; nunca decide | Jesús |
| 2026-11-11 | Descuento, competitividad y demanda son indicadores distintos (DEC-128) | Jesús |
| 2026-11-11 | El descuento real solo se calcula contra el precio habitual (DEC-129, DEC-147) | Jesús |

**Cambios de la v2 contra la v1:** el descuento real se calcula contra el precio habitual, no contra el "precio de mercado" único; se agrega la ventaja contra el mercado; nuevas marcas "descuento anunciado no comprobado" y "comparación insuficiente"; "sin historial de tienda" pasa a "sin historial suficiente"; "mercado ya barato" descarta solo para reventa; "coincidencia dudosa" pasa a RN-013; se agrega el filtro previo. El ejemplo B de la v1 (taladro $79) se reemplaza; la sierra se conserva como ejemplo E.

## 14. Revisión de consistencia
- Última revisión: 2026-11-11 (v2.1) — **APROBADO CON OBSERVACIONES**: continuar a requerimiento; las preguntas abiertas se responden antes de cerrar el desarrollo. Revisiones anteriores: 2026-11-11 (v2) — RECHAZADO; 2026-11-08 (v1) — APROBADO CON OBSERVACIONES.
- Detalle: [revisiones/RN-003.md](/revisiones/RN-003.md)
