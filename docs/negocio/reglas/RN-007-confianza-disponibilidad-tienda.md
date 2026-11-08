# RN-007 — Confianza del dato de disponibilidad en tienda

```yaml
id: RN-007
titulo: Confianza del dato de disponibilidad en tienda
estado: BORRADOR
version: 1
fecha: 2026-11-08
responsable: Jesús
revisor_negocio: Experto en negocios internacionales
depende_de: []
```

## 1. ¿Qué queremos lograr?
Evitar **viajes en vano**. Que la página de la tienda diga "disponible" no garantiza que el producto esté en el anaquel. El sistema debe decir qué tan confiable es el dato y cuándo se consultó.

## 2. ¿Qué incluye y qué no?
**Incluye:**
- Calificar la confianza del dato de disponibilidad de cada tienda física.
- Volver a consultar justo antes de salir.
- Registrar qué pasó en cada visita para aprender qué tiendas son confiables.

**No incluye:**
- Compras en línea (ahí la tienda confirma al pagar).
- El costo del viaje (RN-008).

## 3. ¿Cómo funciona, en palabras?
Cada dato de disponibilidad trae la hora en que se consultó y lo que dijo la tienda. Con eso se le pone una calificación: **Alta, Media o Baja**. Solo las calificaciones Alta y Media generan alerta. Antes de salir, Jesús puede pedir una nueva consulta con un botón. Después de cada visita, registra si encontró el producto.

## 4. La regla

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

| Valor | Qué es | Valor inicial | ¿Confirmado? |
|---|---|---|---|
| Ventana de Alta | Horas para cantidad exacta | 6 h | Por confirmar |
| Ventana sin número | Horas para "en existencia" | 12 h | Por confirmar |
| Límite general | Horas antes de ser Baja | 24 h | Por confirmar |
| Fallas para bajar nivel | "No encontrado" en las últimas 5 visitas | 2 | Por confirmar |

## 5. ¿Cómo sabremos que funciona? — Ejemplos con números

**Ejemplo A — Alta**
- Home Depot Chula Vista: "3 disponibles", consultado hace 2 horas → **Alta** → se alerta.

**Ejemplo B — Se degrada con el tiempo**
- El mismo dato, 8 horas después → **Media** → se alerta, mostrando "consultado hace 8 h".

**Ejemplo C — Baja por historial**
- Tienda con 2 "no encontrado" en sus últimas 5 visitas. Dato: "4 disponibles" hace 3 h → normalmente Alta, baja a **Media** por historial.

**Ejemplo D — Sin alerta**
- "Existencia limitada" hace 1 hora → **Baja** → no se alerta; aparece en el tablero.

## 6. ¿Qué información necesitamos?
- Respuesta de la página de la tienda (cantidad o texto) y hora de la consulta.
- Registro de visitas de Jesús.

## 7. ¿Qué obtenemos?
- Confianza (Alta/Media/Baja), antigüedad del dato e historial de aciertos por tienda.

## 8. ¿Quién participa?
- El sistema consulta y califica.
- Jesús pide la nueva consulta antes de salir y registra cada visita.

## 9. ¿De qué depende?
- De que la página de cada tienda muestre disponibilidad por sucursal.

## 10. Limitaciones
- Algunas liquidaciones solo se ven en la tienda y nunca aparecen en la página. Esas no las puede detectar el sistema.

## 11. ¿Qué pasa si…?
| Situación | Qué hace el sistema |
|---|---|
| La nueva consulta antes de salir falla | Mantiene la confianza anterior y avisa que no se pudo confirmar |
| La nueva consulta da Baja | Recomienda no viajar |
| Jesús no registra la visita | No cambia el historial de la tienda |
| Precio en tienda distinto al de la página | Se registra; si 2 de las últimas 5 visitas tienen precio distinto, se avisa |

## 12. Preguntas para el experto
1. Por su experiencia, ¿qué tan confiable suele ser la disponibilidad que muestran Home Depot, Walmart y Target para sus tiendas?
2. ¿Conviene llamar a la tienda para confirmar productos caros? Si sí, ¿a partir de qué ganancia?
3. ¿Los productos en liquidación se agotan más rápido? ¿Conviene acortar las ventanas para ellos?

## 13. Decisiones tomadas
| Fecha | Decisión | Quién |
|---|---|---|
| 2026-11-08 | Se incluyen compras en tienda física en la zona de San Diego | Jesús |

## 14. Revisión de consistencia
- Última revisión: 2026-11-08 — APROBADO CON OBSERVACIONES
- Detalle: [revisiones/RN-007.md](/revisiones/RN-007.md)
