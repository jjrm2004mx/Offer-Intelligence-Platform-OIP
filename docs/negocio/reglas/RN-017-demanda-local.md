# RN-017 — Demanda local

```yaml
id: RN-017
titulo: Demanda local
grupo: local
estado: BORRADOR
version: 1
fecha: 2026-11-16
responsable: Jesús
revisor_negocio: Experto en negocios internacionales
depende_de: [RN-016]
origen: DEC-145, DEC-151
```

> **Regla nueva.** No hay datos automáticos de demanda local; en el Inc. 1 la fija Jesús por categoría y se ajusta con lo que realmente venda. Todo el contenido es **propuesta de Claude, por aceptar**.

## 1. ¿Qué queremos lograr?
Saber si un producto se vende rápido en la zona antes de comprarlo para venta local, y cuántos días tardará.

## 2. ¿Qué incluye y qué no?
**Incluye:**
- Demanda local por categoría: alta, media o baja.
- Días de venta por unidad.

**No incluye:**
- La demanda en Amazon (RN-004).

## 3. ¿Cómo funciona, en palabras?
Jesús califica una vez cada categoría según su experiencia; esa calificación dice cuántos días tarda en venderse una unidad. Con los resultados reales (cuánto tardó cada venta) se va corrigiendo.

## 4. La regla

| Demanda local | Días de venta por unidad | Canal local |
|---|---|---|
| **Alta** | 7 | Viable |
| **Media** | 14 | Viable |
| **Baja** | — | **No viable** |

```
ventas locales al mes = 30 ÷ días de venta por unidad, redondeado hacia abajo   (lo usa RN-005)
```

- Valor inicial por categoría: **media**, hasta que Jesús la cambie.
- Si hay muchas publicaciones comparables activas en la zona (**más de 10**), la demanda baja un nivel: hay mucha competencia.
- Con **5 o más ventas reales** en una categoría, los días de venta pasan a ser la mediana de esas ventas.

| Valor | Qué es | Valor inicial | ¿Confirmado? |
|---|---|---|---|
| Días por unidad | Alta / media | 7 / 14 | **Propuesta (por aceptar)** |
| Demanda inicial | Por categoría | Media | **Propuesta (por aceptar)** |
| Competencia que baja la demanda | Publicaciones comparables activas | más de 10 | **Propuesta (por aceptar)** |
| Ventas para recalibrar | Por categoría | 5 | **Propuesta (por aceptar)** |

Todos los valores son iniciales y configurables.

## 5. ¿Cómo sabremos que funciona? — Ejemplos con números

**Ejemplo A — Taladro (herramientas, media)**
- 14 días por unidad → 30 ÷ 14 = **2** ventas locales al mes (lo usa RN-005, ejemplo C).

**Ejemplo B — Mucha competencia**
- Herramientas en alta, pero hay 14 publicaciones comparables activas → baja a **media**.

**Ejemplo C — Recalibrar**
- 5 ventas reales de herramientas en 5, 8, 10, 12 y 20 días → mediana **10** días por unidad.

## 6. ¿Qué información necesitamos?
- Calificación de Jesús por categoría.
- Número de publicaciones comparables en la zona (las captura Jesús).
- Resultados reales de venta.

## 7. ¿Qué obtenemos?
- Demanda local, días de venta por unidad y ventas locales al mes.

## 8. ¿Quién participa?
- Jesús califica y registra ventas.
- El sistema calcula.

## 9. ¿De qué depende?
- RN-016 (zona y comparables).

## 10. Limitaciones
- Es una estimación hasta que haya ventas reales.

## 11. ¿Qué pasa si…?
| Situación | Qué hace el sistema |
|---|---|
| Categoría sin calificar | Usa "media" |
| No se sabe cuántas publicaciones hay | No ajusta por competencia |

## 12. Preguntas para el experto
1. ¿Cuánto suele tardar en venderse en persona una herramienta o un electrónico de precio medio?

## 13. Decisiones tomadas
| Fecha | Decisión | Quién |
|---|---|---|
| 2026-11-11 | Demanda local como regla aparte del grupo "venta local" (DEC-145) | Jesús |

## 14. Revisión de consistencia
- Última revisión: ver `revisiones/RN-017.md`
- Detalle: [revisiones/RN-017.md](/revisiones/RN-017.md)
