# RN-017 — Demanda local

```yaml
id: RN-017
titulo: Demanda local
grupo: local
estado: BORRADOR
version: 1
fecha: 2026-11-11
responsable: Jesús
revisor_negocio: Experto en negocios internacionales
depende_de: [RN-013, RN-016]
```

## 1. ¿Qué queremos lograr?
Saber si un producto **se puede vender en venta local** y en cuánto tiempo, sin el ranking de ventas de Amazon (que no representa la demanda de OfferUp o de los contactos de Jesús, y que además no se consulta, DEC-156).

## 2. ¿Qué incluye y qué no?
**Incluye:**
- Señales de demanda local: ventas concretadas, competencia en la zona, reseñas en comercios y el historial de ventas de Jesús.
- Días estimados de venta local, que usa RN-005.

**No incluye:**
- La demanda en Amazon (RN-004).
- El precio de venta (RN-016).

## 3. ¿Cómo funciona, en palabras?
La mejor señal es que el producto **ya se vendió**: ventas concretadas registradas o ventas del propio Jesús. Después cuenta cuánta competencia hay en la zona: si hay demasiadas publicaciones iguales, el mercado está saturado. Las reseñas en los comercios solo ayudan como complemento: dicen que el producto es popular, no que se esté vendiendo ahora. Con todo eso se asigna una de cuatro clases, y cada una trae sus días estimados de venta.

## 4. La regla

| Clase | Cuándo | Días estimados de venta | Efecto |
|---|---|---|---|
| **SATURADA** | Más de **10** publicaciones comparables activas en la zona | — | **Se descarta** para venta local |
| **PROBADA** | Al menos **3** ventas concretadas comparables en 90 días (DEC-161), **o** Jesús ya vendió ese producto antes en menos de 14 días | 7 | Normal |
| **PROBABLE** | Sin ventas registradas, pero con señales complementarias: al menos 1,000 reseñas en un comercio, o reseñas que crecieron 2% o más en 30 días | 14 | Normal |
| **DESCONOCIDA** | Ninguna de las anteriores | 30 | Nivel máximo **C** en RN-009 (sin aviso inmediato) |

- Se asigna la **primera** que se cumpla, en el orden de la tabla.
- Las **reseñas** nunca bastan solas para "probada" (DEC-128): son popularidad.
- Con el tiempo, el **historial de ventas de Jesús** (qué se vendió, a cuánto y en cuántos días) reemplaza a las estimaciones.

| Valor | Qué es | Valor inicial | ¿Confirmado? |
|---|---|---|---|
| Publicaciones para saturación | Comparables activas en la zona | 10 | Por confirmar |
| Ventas concretadas para "probada" | En 90 días | 3 | Por confirmar |
| Reseñas para "probable" | En un comercio | 1,000 | Por confirmar |
| Crecimiento de reseñas | En 30 días | 2% | Por confirmar |
| Días por clase | Probada / probable / desconocida | 7 / 14 / 30 | Por confirmar |

## 5. ¿Cómo sabremos que funciona? — Ejemplos con números

**Ejemplo A — Probada**
- Baterías DEWALT: 3 ventas concretadas en eBay en 90 días ($105, $110, $115) y 4 publicaciones en la zona → **PROBADA**, 7 días.

**Ejemplo B — Probable por reseñas (CASO-004)**
- Ninja BN701: sin ventas registradas; 19,780 reseñas en Amazon → **PROBABLE**, 14 días.

**Ejemplo C — Probable por crecimiento**
- Producto con 600 reseñas hace 30 días y 615 hoy: (615 − 600) ÷ 600 = **2.5%** ≥ 2% → **PROBABLE**.

**Ejemplo D — Saturada**
- 14 publicaciones iguales en la zona → **SATURADA** → descartada para venta local, aunque tenga ventas.

**Ejemplo E — Desconocida (CASO-006)**
- DEWALT DCF840 usado: sin ventas ni publicaciones registradas y sin reseñas del usado → **DESCONOCIDA**, 30 días, nivel máximo C.

## 6. ¿Qué información necesitamos?
- Ventas concretadas comparables (captura de Jesús).
- Publicaciones comparables activas en la zona (captura de Jesús).
- Reseñas por comercio y su valor de hace 30 días.
- Historial de ventas de Jesús.

## 7. ¿Qué obtenemos?
- Clase de demanda local, días estimados de venta y las señales usadas.

## 8. ¿Quién participa?
- El sistema clasifica.
- Jesús registra publicaciones, ventas concretadas y sus propias ventas.

## 9. ¿De qué depende?
- RN-013 (comparables) y RN-016 (zona).
- La usan RN-005, RN-009 y RN-018.

## 10. Limitaciones
- Al inicio casi todo será **desconocida**: es esperado y por eso limita el nivel.
- Las reseñas de un comercio pueden mezclar varias versiones de un producto.

## 11. ¿Qué pasa si…?
| Situación | Qué hace el sistema |
|---|---|
| Hay ventas concretadas pero la zona está saturada | Saturada gana: se descarta para venta local |
| Las reseñas no tienen dato de hace 30 días | No se calcula el crecimiento |
| Jesús vendió el producto, pero tardó más de 14 días | No cuenta como probada; sus días reales se usan como estimación |

## 12. Preguntas para el experto
1. ¿Cuántas publicaciones iguales en la zona considera "demasiadas"?
2. ¿Cuánto tarda en venderse en persona un producto con buena demanda?
3. ¿Qué otra señal de demanda local usaría?

## 13. Decisiones tomadas
| Fecha | Decisión | Quién |
|---|---|---|
| 2026-11-11 | Descuento, competitividad y demanda son indicadores distintos; reseñas = popularidad (DEC-128) | Jesús |
| 2026-11-11 | Ventas concretadas de eBay como dato (DEC-161) | Jesús |

## 14. Revisión de consistencia
- Última revisión: pendiente.
- Detalle: `revisiones/RN-017.md` (por crear)
