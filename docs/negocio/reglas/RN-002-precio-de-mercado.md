# RN-002 — Precio de mercado y precio de venta esperado

```yaml
id: RN-002
titulo: Precio de mercado y precio de venta esperado
estado: BORRADOR
version: 1
fecha: 2026-11-08
responsable: Jesús
revisor_negocio: Experto en negocios internacionales
depende_de: []
```

## 1. ¿Qué queremos lograr?
Tener dos números confiables para cada producto: **cuánto cuesta normalmente en el mercado** (para saber si la oferta es barata de verdad) y **a cuánto lo podemos vender** (para calcular la ganancia).

## 2. ¿Qué incluye y qué no?
**Incluye:**
- Precio de Amazon de producto **nuevo**: el de hoy y el típico de los últimos 90 días (mediana).
- Precio de hoy del mismo producto en los otros comercios que sigue el sistema.

**No incluye:**
- Productos usados, reacondicionados o de "caja abierta".
- Paquetes de varias unidades o combos.
- El historial del comercio que publica la oferta (ese se usa en RN-003 para detectar descuentos falsos).
- Precios de Facebook Marketplace (fase posterior).

## 3. ¿Cómo funciona, en palabras?
- **Precio de mercado:** el precio más bajo al que un comprador común puede conseguir hoy el producto nuevo. Es contra lo que se compara la oferta.
- **Precio de venta esperado:** a cuánto podemos venderlo en Amazon siendo conservadores. Se toma el menor entre el precio de hoy y el típico de 90 días, para no contar con un precio alto que quizá no dure.

## 4. La regla

```
precio de mercado        = el MÁS BAJO entre:
                             · precio de hoy en Amazon (nuevo)
                             · mediana de 90 días en Amazon (nuevo)
                             · precio de hoy en otros comercios seguidos (nuevo, consultado hace ≤ 48 h)

precio de venta esperado = el MÁS BAJO entre:
                             · precio de hoy en Amazon (nuevo)
                             · mediana de 90 días en Amazon (nuevo)
```

"Mediana de 90 días" = el precio del medio cuando se ordenan todos los precios de esos 90 días. A diferencia del promedio, no se deja jalar por un día de precio rarísimo.

| Valor | Qué es | Valor inicial | ¿Confirmado? |
|---|---|---|---|
| Ventana de historial Amazon | Días para la mediana | 90 días | Por confirmar |
| Antigüedad máxima de otros comercios | Qué tan reciente debe ser el dato | 48 horas | Por confirmar |
| Fuente de datos Amazon | Servicio de historial de precios | Keepa | Sí |

## 5. ¿Cómo sabremos que funciona? — Ejemplos con números

**Ejemplo A — Taladro**
- Amazon hoy: $149. Mediana 90 días: $155. Walmart hoy (hace 6 h): $152. Mínimo de 90 días en Amazon: $139 (se usa en RN-005).
- Precio de mercado = mínimo(149, 155, 152) = **$149**.
- Precio de venta esperado = mínimo(149, 155) = **$149**.

**Ejemplo B — Otro comercio más barato que Amazon**
- Sierra: Amazon hoy $119, mediana 90 días $125, Target hoy $99.
- Precio de mercado = **$99** (cualquiera la consigue en Target a ese precio).
- Precio de venta esperado = mínimo(119, 125) = **$119**.
- Interpretación: comprar a $29 sigue siendo barato frente a $99, pero hay que tener presente que hay competencia barata fuera de Amazon.

**Ejemplo C — Dato viejo descartado**
- Target tenía la sierra a $90, pero el dato es de hace 4 días → **no se usa**. Precio de mercado = mínimo(119, 125) = $119.

## 6. ¿Qué información necesitamos?
- Código del producto (UPC/EAN) para encontrarlo en Amazon y en otros comercios.
- Historial de precios de Amazon (Keepa).
- Precios recientes de otros comercios (los obtiene el propio sistema).

## 7. ¿Qué obtenemos?
- Precio de mercado, precio de venta esperado, mínimo de 90 días en Amazon y de qué fuente salió cada uno.

## 8. ¿Quién participa?
- El sistema consulta y calcula.
- El experto valida que el criterio conservador sea el adecuado.

## 9. ¿De qué depende?
- De identificar correctamente el producto (mismo modelo, nuevo). Ver casos raros.

## 10. Limitaciones
- Keepa es un servicio de pago con un límite de consultas por minuto. Solo se consulta para ofertas que ya parecen interesantes.
- Algunos productos no se venden en Amazon.

## 11. ¿Qué pasa si…?
| Situación | Qué hace el sistema |
|---|---|
| El producto no está en Amazon | No hay precio de venta esperado → oferta "sin referencia" (RN-003) |
| No hay código UPC/EAN y se identificó solo por nombre | Se calcula, pero la oferta se marca "coincidencia dudosa" (RN-003) |
| Amazon tiene menos de 30 días de historial | Usa los días disponibles y lo marca como "historial corto" |
| Solo hay ofertas de Amazon usadas | Se ignoran; si no hay nuevo, queda "sin referencia" |

## 12. Preguntas para el experto
1. ¿Le parece correcto usar siempre el precio más bajo (criterio conservador), o en productos de mucha demanda conviene usar el típico de 90 días?
2. ¿90 días es buena ventana para ver el precio normal, o en temporada (Navidad, Black Friday) conviene acortarla?
3. Cuando otro comercio vende mucho más barato que Amazon (ejemplo B), ¿eso debería bajar la calificación de la oportunidad aunque se venda en Amazon?

## 13. Decisiones tomadas
| Fecha | Decisión | Quién |
|---|---|---|
| 2026-11-08 | La fuente del historial de Amazon es Keepa | Jesús |

## 14. Estado de inspección
- Última inspección: 2026-11-08 — APROBADO CON OBSERVACIONES
- Detalle: [inspecciones/RN-002.md](/inspecciones/RN-002.md)
