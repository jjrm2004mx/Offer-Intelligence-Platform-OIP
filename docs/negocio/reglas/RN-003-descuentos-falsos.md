# RN-003 — Descuento real y descuentos falsos o engañosos

```yaml
id: RN-003
titulo: Descuento real y descuentos falsos o engañosos
grupo: común
estado: EN_REVISION
version: 2
fecha: 2026-11-16
responsable: Jesús
revisor_negocio: Experto en negocios internacionales
depende_de: [RN-002, RN-013]
```

> **Qué cambió en la v2 (2026-11-16):** el descuento real se mide **solo contra el precio habitual** (DEC-129, DEC-147); el mínimo para seguir evaluando sube a **25%**, con una franja de **20% a 24%** que solo se muestra como referencia (RN-003 · P1, P4); el factor de inflado de 1.5 se confirma y es configurable (RN-003 · P2). La v1 queda en el historial: [RN-003 v1](https://github.com/jjrm2004mx/Offer-Intelligence-Platform-OIP/blob/1c1d4e04d5e5e2401dbb565782bf11061d8813f7/docs/negocio/reglas/RN-003-descuentos-falsos.md).

## 1. ¿Qué queremos lograr?
Que el sistema **no se deje engañar** por el "antes $200, ahora $20" de las tiendas. Lo que importa es el **descuento real** contra lo que el producto cuesta normalmente, no el descuento que anuncia la tienda.

## 2. ¿Qué incluye y qué no?
**Incluye:**
- El filtro previo que decide qué ofertas vale la pena investigar.
- Calcular el descuento anunciado y el descuento real.
- Marcar las ofertas con señales de engaño o con datos insuficientes.
- Las tres franjas del descuento real: se descarta, solo referencia, sigue en evaluación.

**No incluye:**
- La calidad del precio para el consumidor (RN-012).
- Decidir el nivel de la oportunidad (RN-009).
- Calcular ganancias (RN-001 y RN-005).

## 3. ¿Cómo funciona, en palabras?
El descuento que anuncia la tienda solo sirve para **decidir qué investigar**; nunca califica la oferta. Después se calcula el descuento real contra el **precio habitual** (RN-002). Además se revisa el historial de la propia tienda: si casi nunca cobró el "precio antes", ese precio está inflado.

## 4. La regla

```
descuento anunciado (%) = (1 − precio de oferta ÷ precio tachado de la tienda) × 100
descuento real (%)      = (1 − precio de oferta ÷ precio habitual) × 100
```

**Filtro previo (descubrimiento):** se investigan las ofertas con descuento anunciado de **40% o más**, de marca reconocida y en una categoría acordada. Es necesario por el límite de consultas de RN-010. El filtro **no califica** la oferta.

**Franjas del descuento real:**

| Descuento real | Qué pasa |
|---|---|
| Menor de **20%** | Marca **MERCADO YA BARATO** → se descarta |
| De **20%** a menos de **25%** | Marca **SOLO REFERENCIA** → se ve en el tablero, no sigue a oportunidad |
| **25%** o más | Sigue en evaluación (RN-004 a RN-009) |

**Marcas** (una oferta puede tener varias):

| Marca | Cuándo se asigna | Qué provoca |
|---|---|---|
| **PRECIO ANTES INFLADO** | El precio tachado es más de **1.5 veces** el precio típico de esa misma tienda en **60 días** (mediana, con historial suficiente) | Se ignora el descuento anunciado; se muestra la advertencia |
| **MERCADO YA BARATO** | Descuento real menor de 20% | Se descarta |
| **SOLO REFERENCIA** | Descuento real de 20% a menos de 25% | Solo tablero |
| **SIN HISTORIAL SUFICIENTE** | No hay precio habitual (RN-002) | No se calcula descuento real; va a revisión manual sin aviso |
| **DESCUENTO ANUNCIADO NO COMPROBADO** | Hay precio tachado, pero no hay historial suficiente de esa tienda para comprobarlo | Se avisa en el tablero; no impide evaluar el descuento real |
| **COINCIDENCIA NO CONFIRMADA** | El producto no se identificó por código ni por modelo + marca (RN-013) | Se evalúa, pero va a revisión manual sin aviso |

| Valor | Qué es | Valor inicial | ¿Confirmado? |
|---|---|---|---|
| Factor de inflado | Veces sobre el precio típico de la tienda | 1.5, configurable | Experto (sesión 2) |
| Ventana del historial de la tienda | Días | 60 | Aceptado por Jesús (DEC-130) |
| Descuento real para descartar | Por debajo, se descarta | 20% | Experto y Jesús (sesión 2) |
| Descuento real para seguir evaluando | Desde aquí, sigue | 25% | Experto (sesión 2) |
| Descuento anunciado del filtro previo | Desde aquí se investiga | 40% | **Propuesta de Claude (por aceptar)**, de los ejercicios (CASO-003) |

Todos los valores son iniciales y configurables.

## 5. ¿Cómo sabremos que funciona? — Ejemplos con números

**Ejemplo A — La lámpara (descuento falso)**
- Walmart anuncia: antes $200, ahora $20 → descuento anunciado = (1 − 20 ÷ 200) × 100 = **90%** → pasa el filtro previo.
- Walmart la tuvo en unos $25 durante 60 días: 1.5 × 25 = 37.50, y 200 es mayor → **PRECIO ANTES INFLADO**.
- Precio habitual: $22 → descuento real = (1 − 20 ÷ 22) × 100 = **9.1%** → **MERCADO YA BARATO** → **descartada**.

**Ejemplo B — Taladro (anunciado exagerado, pero real)**
- Home Depot anuncia: antes $199, ahora $79 → anunciado **60.3%**.
- Precio habitual $149 → descuento real = (1 − 79 ÷ 149) × 100 = **47.0%** → 25% o más → sigue en evaluación.

**Ejemplo C — Sierra circular (descuento real fuerte)**
- Home Depot liquidación: antes $129, ahora $29 → anunciado **77.5%**.
- Precio habitual $119 → descuento real = (1 − 29 ÷ 119) × 100 = **75.6%** → sigue en evaluación.

**Ejemplo D — Solo referencia**
- Oferta $80, precio habitual $100 → descuento real = (1 − 80 ÷ 100) × 100 = **20.0%** → **SOLO REFERENCIA**: aparece en el tablero, no sigue.

**Ejemplo E — Sin historial suficiente**
- Producto con 3 observaciones en 2 días → **SIN HISTORIAL SUFICIENTE** → revisión manual, sin aviso.

## 6. ¿Qué información necesitamos?
- Precio de oferta y precio tachado que muestra la tienda.
- Historial de precios de esa tienda y precio habitual del producto (RN-002).
- Cómo se identificó el producto (RN-013).

## 7. ¿Qué obtenemos?
- Descuento anunciado, descuento real, su franja y las marcas que apliquen.

## 8. ¿Quién participa?
- El sistema calcula y marca.
- Jesús revisa manualmente las ofertas sin historial suficiente o con coincidencia no confirmada.

## 9. ¿De qué depende?
- RN-002 (precio habitual) y RN-013 (identificación).
- Del seguimiento de precios que el sistema hace de cada tienda.

## 10. Limitaciones
- Al arrancar no hay historial: durante los primeros días por producto no se puede afirmar un descuento real.

## 11. ¿Qué pasa si…?
| Situación | Qué hace el sistema |
|---|---|
| La tienda no muestra precio tachado | Descuento anunciado = no disponible; la oferta solo entra si se busca por otra vía (seguimiento de precio) |
| El precio de oferta es mayor que el habitual | Descuento real negativo → MERCADO YA BARATO |
| Hay menos de 5 observaciones en 60 días | SIN HISTORIAL SUFICIENTE |

## 12. Preguntas para el experto
1. ¿Le parece bien investigar solo ofertas con **40% o más** de descuento anunciado, de marca reconocida y categoría acordada? (propuesta)

## 13. Decisiones tomadas
| Fecha | Decisión | Quién |
|---|---|---|
| 2026-11-08 | El descuento anunciado solo sirve para descubrir candidatos; nunca decide | Jesús |
| 2026-11-11 | El descuento real se mide solo contra el precio habitual (DEC-129, DEC-147) | Jesús |
| 2026-11-16 | Menos de 20% se descarta; 20% a 24% solo referencia; 25% o más sigue | Experto y Jesús |
| 2026-11-16 | Factor de inflado 1.5, configurable | Experto |
| 2026-11-16 | No hay otras señales de descuento engañoso por ahora | Experto |

## 14. Revisión de consistencia
- Última revisión: 2026-11-16 (v2.1) — APROBADO CON OBSERVACIONES
- Detalle: [revisiones/RN-003.md](/revisiones/RN-003.md)
