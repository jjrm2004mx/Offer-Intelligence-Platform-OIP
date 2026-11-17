# RN-007 — Confianza de la disponibilidad (tienda física y en línea)

```yaml
id: RN-007
titulo: Confianza de la disponibilidad
grupo: común
estado: EN_REVISION
version: 2
fecha: 2026-11-16
responsable: Jesús
revisor_negocio: Experto en negocios internacionales
depende_de: [RN-010]
```

> **Qué cambió en la v2 (2026-11-16):** "pocas unidades" y "existencia limitada" se toman como **probablemente ya no hay**; en **liquidación** los tiempos se reducen a la mitad; castigo a una tienda con **al menos 3 visitas** y recuperación con 3 aciertos seguidos; regla para **llamar a la tienda**; se agregan los **estados de disponibilidad en línea** (DEC-134) y "recoger en tienda" (RN-011 · P7). Propuestas de Claude aceptadas por Jesús, [sesión 2](/sesiones/sesion-2-respuestas.md), bloque 7; por validar con el experto. La v1 queda en el historial: [RN-007 v1](https://github.com/jjrm2004mx/Offer-Intelligence-Platform-OIP/blob/1c1d4e04d5e5e2401dbb565782bf11061d8813f7/docs/negocio/reglas/RN-007-confianza-disponibilidad-tienda.md).

## 1. ¿Qué queremos lograr?
Evitar **viajes en vano** y recomendaciones de productos que ya no hay. Que la página diga "disponible" no garantiza que el producto esté en el anaquel. El sistema debe decir qué tan confiable es el dato y cuándo se consultó.

## 2. ¿Qué incluye y qué no?
**Incluye:**
- Calificar la confianza del dato de disponibilidad de cada tienda física.
- Los estados de disponibilidad en línea.
- Volver a consultar justo antes de salir y, en casos de mucha ganancia, llamar a la tienda.
- Registrar qué pasó en cada visita para aprender qué tiendas son confiables.

**No incluye:**
- El costo del viaje (RN-008).

## 3. ¿Cómo funciona, en palabras?
Cada dato de disponibilidad trae la hora en que se consultó y lo que dijo la tienda. Con eso se le pone una calificación: **Alta, Media o Baja**. Solo Alta y Media generan aviso. Antes de salir, **siempre** se vuelve a consultar (RN-010). Si el viaje deja mucha ganancia, conviene llamar. Después de cada visita, Jesús registra si encontró el producto. Al principio no se distingue entre comercios: cada tienda se califica con sus propias visitas.

## 4. La regla

**4.1 Tienda física**

| Lo que dice la tienda | Antigüedad del dato (normal) | En liquidación | Confianza |
|---|---|---|---|
| Cantidad exacta (ej. "4 disponibles") | 6 h o menos | 3 h o menos | **Alta** |
| Cantidad exacta | más de 6 y hasta 24 h | más de 3 y hasta 12 h | **Media** |
| "En existencia", sin número | 12 h o menos | 6 h o menos | **Media** |
| "En existencia", sin número | más de 12 y hasta 24 h | más de 6 y hasta 12 h | **Baja** |
| "Pocas unidades" o "existencia limitada" | 2 h o menos → **Media**; más de 2 h → **Baja** | Igual | Media / Baja |
| Cualquier dato | más de 24 h | más de 12 h | **Baja** |

**Ajuste por historial de la tienda:** con **al menos 3 visitas** registradas, si hubo **2 o más "no encontrado"** entre las últimas 5, la confianza de esa tienda baja **un nivel** (Alta → Media, Media → Baja). La tienda **recupera** su nivel con **3 "encontrado" seguidos**.

**Llamar a la tienda antes de salir** cuando la ganancia total del viaje (RN-008) sea de **$100 o más**, o cuando la confianza sea **Media** y la ganancia del viaje sea de **$50 o más**. Si la tienda confirma, la confianza pasa a **Alta por 2 horas** y la visita se registra como "confirmado por llamada".

**Calificación por comercio:** con **5 o más visitas** a las tiendas de un comercio se puede fijar una confianza propia de ese comercio.

**4.2 En línea** (DEC-134)

| Estado | Cuándo | Cuenta como disponible |
|---|---|---|
| **Disponible confirmada** | La ficha dice "en existencia" **y** permite agregar al carrito | Sí |
| **Existencia limitada** | La ficha lo indica | No (se muestra aparte) |
| **No confirmada** | Falta alguna de las dos señales | No |
| **Agotado** | La ficha lo indica | No |

**Recoger en tienda** con pedido en línea: en la confianza se trata como **compra en línea** (la tienda confirma el pedido), pero **suma el costo del viaje** (RN-008) si Jesús va por él.

| Valor | Qué es | Valor inicial | ¿Confirmado? |
|---|---|---|---|
| Ventanas normales | Alta / sin número / límite | 6 h / 12 h / 24 h | Por confirmar |
| Ventanas en liquidación | La mitad | 3 h / 6 h / 12 h | Aceptado por Jesús |
| "Pocas unidades" Media hasta | Horas | 2 h | Aceptado por Jesús |
| Visitas mínimas para castigar | Registradas | 3 | Aceptado por Jesús |
| Fallas para bajar nivel | "No encontrado" en las últimas 5 | 2 | Aceptado por Jesús |
| Aciertos para recuperar | Seguidos | 3 | Aceptado por Jesús |
| Llamar si la ganancia del viaje es | $ | $100; o $50 con confianza Media | Aceptado por Jesús |

Todos los valores son iniciales y configurables.

## 5. ¿Cómo sabremos que funciona? — Ejemplos con números

**Ejemplo A — Alta**
- Home Depot Chula Vista: "3 disponibles", consultado hace 2 horas → **Alta** → se avisa.

**Ejemplo B — Se degrada con el tiempo**
- El mismo dato, 8 horas después → **Media**, mostrando "consultado hace 8 h".

**Ejemplo C — Liquidación**
- "5 disponibles" en liquidación, consultado hace 4 horas → en liquidación la Alta dura 3 h → **Media**.

**Ejemplo D — Pocas unidades**
- "Existencia limitada" hace 1 hora → **Media**. El mismo dato hace 3 horas → **Baja** → no se avisa; aparece en el tablero.

**Ejemplo E — Castigo por historial**
- Tienda con 4 visitas y 2 "no encontrado". Dato: "4 disponibles" hace 3 h → normalmente Alta, baja a **Media**.
- Con 2 visitas y 2 "no encontrado" **no** se castiga todavía: faltan visitas.
- Después, 3 "encontrado" seguidos → recupera su nivel.

**Ejemplo F — Llamar**
- Viaje por la sierra con ganancia de **$79.19** (RN-008, ejemplo A) y confianza Media: $79.19 ≥ $50 → se recomienda llamar. La tienda confirma → **Alta por 2 horas**.
- Con confianza Alta, el mismo viaje no requiere llamada: $79.19 < $100.

## 6. ¿Qué información necesitamos?
- Respuesta de la página de la tienda (cantidad o texto), si es liquidación y hora de la consulta.
- En línea: si dice "en existencia" y si permite agregar al carrito.
- Registro de visitas y llamadas de Jesús.

## 7. ¿Qué obtenemos?
- Confianza (Alta/Media/Baja), estado en línea, antigüedad del dato, recomendación de llamar e historial de aciertos por tienda.

## 8. ¿Quién participa?
- El sistema consulta y califica.
- Jesús llama cuando se recomienda, y registra cada visita.

## 9. ¿De qué depende?
- De que la página de cada tienda muestre disponibilidad por sucursal.
- RN-010 (re-consulta antes de salir y límites).

## 10. Limitaciones
- Algunas liquidaciones solo se ven en la tienda y nunca aparecen en la página. Esas no las puede detectar el sistema.

## 11. ¿Qué pasa si…?
| Situación | Qué hace el sistema |
|---|---|
| La nueva consulta antes de salir falla | Mantiene la confianza anterior y avisa que no se pudo confirmar |
| La nueva consulta da Baja | Recomienda no viajar |
| Jesús no registra la visita | No cambia el historial de la tienda |
| Precio en tienda distinto al de la página | Se registra; si 2 de las últimas 5 visitas tienen precio distinto, se avisa |
| No se sabe si es liquidación | Se usan las ventanas normales |

## 12. Preguntas para el experto
1. ¿Le parece bien tomar "pocas unidades" como "probablemente ya no hay" después de 2 horas? (propuesta aceptada por Jesús)
2. ¿Le parece bien reducir a la mitad los tiempos en liquidación? (propuesta aceptada por Jesús)
3. ¿Llamar a la tienda desde $100 de ganancia del viaje? (propuesta aceptada por Jesús)

## 13. Decisiones tomadas
| Fecha | Decisión | Quién |
|---|---|---|
| 2026-11-08 | Se incluyen compras en tienda física en la zona de San Diego | Jesús |
| 2026-11-11 | Estados de disponibilidad en línea (DEC-134) | Jesús |
| 2026-11-16 | Al inicio no se distingue por comercio; se califica con visitas | Jesús (propuesta de Claude) |
| 2026-11-16 | "Pocas unidades" = probablemente ya no hay (Media hasta 2 h) | Jesús (propuesta de Claude) |
| 2026-11-16 | Castigo con al menos 3 visitas; recuperación con 3 aciertos | Jesús (propuesta de Claude) |
| 2026-11-16 | Llamar con ganancia del viaje de $100, o $50 con confianza Media | Jesús (propuesta de Claude) |
| 2026-11-16 | Liquidación: tiempos a la mitad | Jesús (propuesta de Claude) |
| 2026-11-16 | Recoger en tienda: confianza de compra en línea, más el costo del viaje | Jesús (propuesta de Claude) |

## 14. Revisión de consistencia
- Última revisión: ver `revisiones/RN-007.md` (columna v2)
- Detalle: [revisiones/RN-007.md](/revisiones/RN-007.md)
