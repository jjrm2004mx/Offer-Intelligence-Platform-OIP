# RN-007 — Disponibilidad del producto y confianza del dato

```yaml
id: RN-007
titulo: Disponibilidad del producto y confianza del dato
grupo: común
estado: BORRADOR
version: 2
fecha: 2026-11-11
responsable: Jesús
revisor_negocio: Experto en negocios internacionales
depende_de: [RN-013]
version_anterior: https://github.com/jjrm2004mx/Offer-Intelligence-Platform-OIP/blob/5a4744d15b2ac6439f2cd89d25cb377ab437ab36/docs/negocio/reglas/RN-007-confianza-disponibilidad-tienda.md
```

## 1. ¿Qué queremos lograr?
Saber si un producto **realmente se puede comprar**, venga de donde venga. En tienda física, para evitar **viajes en vano**: que la página diga "disponible" no garantiza que esté en el anaquel. En línea, para no recomendar algo agotado o sin confirmar (CASO-001). Con particulares, para no ir por una publicación que ya se vendió.

## 2. ¿Qué incluye y qué no?
**Incluye:**
- **Tienda física:** calificar la confianza del dato por sucursal, volver a consultar antes de salir y registrar cada visita (sin cambios de la v1).
- **En línea:** los estados de disponibilidad (nuevo en la v2).
- **Particulares:** la vigencia de la publicación (nuevo en la v2).

**No incluye:**
- El costo del viaje (RN-008).
- El riesgo del vendedor (RN-015).

## 3. ¿Cómo funciona, en palabras?
**Tienda física:** cada dato trae la hora de la consulta y lo que dijo la tienda, y con eso se califica **Alta, Media o Baja**. Solo Alta y Media generan alerta. Antes de salir, Jesús puede pedir una nueva consulta con un botón. Después de cada visita, registra si encontró el producto.

**En línea:** cada publicación tiene uno de cuatro estados. Solo "disponible confirmada" puede ser la opción recomendada en la búsqueda por artículo (RN-011).

**Particulares:** la publicación vale mientras sea reciente y Jesús confirme con el vendedor que sigue disponible.

## 4. La regla

### 4.1 Tienda física (igual que la v1)

| Lo que dice la tienda | Hace cuánto se consultó | Confianza |
|---|---|---|
| Cantidad exacta (ej. "4 disponibles") | 6 horas o menos | **Alta** |
| Cantidad exacta | más de 6 y hasta 24 horas | **Media** |
| "En existencia" o "pocas unidades", sin número | 12 horas o menos | **Media** |
| "En existencia" o "pocas unidades", sin número | más de 12 y hasta 24 horas | **Baja** |
| "Existencia limitada" | cualquier antigüedad | **Baja** |
| Cualquier dato | más de 24 horas | **Baja** |

**Ajuste por historial de la tienda:** si en las últimas 5 visitas a esa tienda hubo **2 o más** "no encontrado", la confianza de esa tienda baja **un nivel** (Alta → Media, Media → Baja).

**Alertas:** solo datos de confianza **Alta o Media** generan alerta de tienda física. Cada alerta muestra "consultado hace X horas".

**Registro de visita:** al volver, se marca una opción: *encontrado al precio* / *encontrado a otro precio* / *no encontrado*.

### 4.2 En línea (nuevo)

| Estado | Cuándo | ¿Puede ser la opción recomendada? |
|---|---|---|
| **Disponible confirmada** | La ficha dice "en existencia" **y** permite agregar al carrito, consultada hace **24 horas o menos** | Sí |
| **Existencia limitada** | La ficha dice "pocas unidades" o similar | No; se muestra con advertencia |
| **No confirmada** | No se pudo ver el estado, o el dato tiene más de 24 horas | No |
| **Agotado** | La ficha dice agotado o no permite comprar | No; se muestra al final |

### 4.3 Particulares (nuevo)

| Situación | Estado |
|---|---|
| Publicación vista o capturada hace **48 horas o menos**, y Jesús confirmó con el vendedor | **Vigente** |
| Publicación vista hace 48 horas o menos, sin confirmar | **Por confirmar** (no genera alerta) |
| Más de 48 horas, o el vendedor dijo que ya se vendió | **No vigente** |

| Valor | Qué es | Valor inicial | ¿Confirmado? |
|---|---|---|---|
| Ventana de Alta | Horas para cantidad exacta | 6 h | Por confirmar |
| Ventana sin número | Horas para "en existencia" | 12 h | Por confirmar |
| Límite general | Horas antes de ser Baja | 24 h | Por confirmar |
| Fallas para bajar nivel | "No encontrado" en las últimas 5 visitas | 2 | Por confirmar |
| Ventana en línea | Horas para "disponible confirmada" | 24 h | Por confirmar |
| Ventana de particulares | Horas de vigencia de una publicación | 48 h | Por confirmar |

## 5. ¿Cómo sabremos que funciona? — Ejemplos con números

**Ejemplo A — Alta (de la v1)**
- Home Depot Chula Vista: "3 disponibles", consultado hace 2 horas → **Alta** → se alerta.

**Ejemplo B — Se degrada con el tiempo (de la v1)**
- El mismo dato, 8 horas después → **Media** → se alerta, mostrando "consultado hace 8 h".

**Ejemplo C — Baja por historial (de la v1)**
- Tienda con 2 "no encontrado" en sus últimas 5 visitas. Dato: "4 disponibles" hace 3 h → normalmente Alta, baja a **Media** por historial.

**Ejemplo D — Sin alerta (de la v1)**
- "Existencia limitada" hace 1 hora → **Baja** → no se alerta; aparece en el tablero.

**Ejemplo E — En línea (CASO-001 y CASO-003)**
- Bose en Best Buy: "en existencia" y se puede agregar al carrito, hace 3 h → **disponible confirmada**.
- Switch 2 Zelda en Amazon: sin estado visible → **no confirmada**. En Best Buy: **agotado**. Resultado de RN-011: ninguna opción recomendada.

**Ejemplo F — Particular (CASO-006)**
- DEWALT DCF840 en OfferUp, visto hace 5 h, sin hablar con el vendedor → **por confirmar**. Jesús le escribe y confirma → **vigente**.

## 6. ¿Qué información necesitamos?
- Tienda física: respuesta de la página por sucursal (cantidad o texto) y hora de la consulta; registro de visitas de Jesús.
- En línea: texto de disponibilidad, si el botón de compra está activo, y hora.
- Particulares: fecha de la publicación o de la captura, y la confirmación de Jesús.

## 7. ¿Qué obtenemos?
- Tienda física: confianza (Alta/Media/Baja), antigüedad del dato e historial de aciertos por tienda.
- En línea: estado de disponibilidad.
- Particulares: vigencia.

## 8. ¿Quién participa?
- El sistema consulta y califica.
- Jesús pide la nueva consulta antes de salir, registra cada visita y confirma con los particulares.

## 9. ¿De qué depende?
- De que la página de cada tienda muestre disponibilidad por sucursal.
- RN-013 (que sea el mismo producto).

## 10. Limitaciones
- Algunas liquidaciones solo se ven en la tienda y nunca aparecen en la página. Esas no las puede detectar el sistema.
- "Agregar al carrito" no garantiza que el pedido se surta: la tienda confirma al pagar.

## 11. ¿Qué pasa si…?
| Situación | Qué hace el sistema |
|---|---|
| La nueva consulta antes de salir falla | Mantiene la confianza anterior y avisa que no se pudo confirmar |
| La nueva consulta da Baja | Recomienda no viajar |
| Jesús no registra la visita | No cambia el historial de la tienda |
| Precio en tienda distinto al de la página | Se registra; si 2 de las últimas 5 visitas tienen precio distinto, se avisa |
| La ficha en línea no muestra estado | No confirmada |
| El particular no responde | Se queda "por confirmar" hasta que pasen 48 h; luego, no vigente |

## 12. Preguntas para el experto
1. *(De la v1)* Por su experiencia, ¿qué tan confiable suele ser la disponibilidad que muestran Home Depot, Walmart y Target para sus tiendas?
2. *(De la v1)* ¿Conviene llamar a la tienda para confirmar productos caros? Si sí, ¿a partir de qué ganancia?
3. *(De la v1)* ¿Los productos en liquidación se agotan más rápido? ¿Conviene acortar las ventanas para ellos?
4. ¿24 horas es buena ventana para dar por confirmada la disponibilidad en línea?
5. ¿Cuánto suele durar disponible una publicación buena en OfferUp o Marketplace? ¿48 horas es razonable?

## 13. Decisiones tomadas
| Fecha | Decisión | Quién |
|---|---|---|
| 2026-11-08 | Se incluyen compras en tienda física en la zona de San Diego | Jesús |
| 2026-11-11 | Estados de disponibilidad en línea (DEC-134) | Jesús |
| 2026-11-11 | Particulares con captura manual (DEC-150) | Jesús |

**Cambios de la v2 contra la v1:** la regla de tienda física queda **igual**; se agregan los estados en línea (§4.2) y la vigencia de publicaciones de particulares (§4.3), con sus ejemplos E y F. La v1 excluía las compras en línea; ya no.

## 14. Revisión de consistencia
- Última revisión: 2026-11-11 (v2) — **APROBADO CON OBSERVACIONES**. Revisión anterior: 2026-11-08 (v1) — APROBADO CON OBSERVACIONES.
- Detalle: [revisiones/RN-007.md](/revisiones/RN-007.md)
