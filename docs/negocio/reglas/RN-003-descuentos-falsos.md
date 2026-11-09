# RN-003 — Detección de descuentos falsos o engañosos

```yaml
id: RN-003
titulo: Detección de descuentos falsos o engañosos
estado: BORRADOR
version: 1
fecha: 2026-11-08
responsable: Jesús
revisor_negocio: Experto en negocios internacionales
depende_de: [RN-002]
```

## 1. ¿Qué queremos lograr?
Que el sistema **no se deje engañar** por el "antes $200, ahora $20" de las tiendas. Lo que importa es el **descuento real** contra el precio de mercado, no el descuento que anuncia la tienda.

## 2. ¿Qué incluye y qué no?
**Incluye:**
- Calcular el descuento anunciado y el descuento real.
- Marcar las ofertas con señales de engaño o con datos insuficientes.

**No incluye:**
- Decidir el nivel de la oportunidad (RN-009).
- Calcular ganancias (RN-001 y RN-005).

## 3. ¿Cómo funciona, en palabras?
El descuento que anuncia la tienda solo sirve para **encontrar** candidatos. Después se calcula el descuento real comparando con el precio de mercado (RN-002). Además se revisa el propio historial de la tienda: si casi nunca cobró el "precio antes", ese precio está inflado.

## 4. La regla

```
descuento anunciado (%) = (1 − precio de oferta ÷ "precio antes" de la tienda) × 100
descuento real (%)      = (1 − precio de oferta ÷ precio de mercado) × 100
```

Marcas que se asignan (una oferta puede tener varias):

| Marca | Cuándo se asigna | Qué provoca |
|---|---|---|
| **PRECIO ANTES INFLADO** | El "precio antes" es más de **1.5 veces** el precio típico que esa misma tienda cobró en los últimos **60 días** | Se ignora el descuento anunciado; se muestra la advertencia |
| **MERCADO YA BARATO** | El descuento real es **menor a 20%** | Se descarta: no es oportunidad |
| **SIN REFERENCIA** | No hay precio de mercado o de venta (RN-002) | No se evalúa; queda para revisión manual, sin alerta |
| **COINCIDENCIA DUDOSA** | El producto se identificó solo por nombre, sin código UPC/EAN | Se evalúa, pero nunca genera alerta automática; requiere revisión manual |
| **SIN HISTORIAL DE TIENDA** | El sistema todavía no tiene 60 días de datos de esa tienda para ese producto | No se puede evaluar "precio antes inflado"; se avisa |

| Valor | Qué es | Valor inicial | ¿Confirmado? |
|---|---|---|---|
| Factor de inflado | Veces sobre el precio típico de la tienda | 1.5 | Por confirmar |
| Ventana del historial de la tienda | Días | 60 | Por confirmar |
| Descuento real mínimo | Por debajo, se descarta | 20% | Por confirmar |

## 5. ¿Cómo sabremos que funciona? — Ejemplos con números

**Ejemplo A — La lámpara (descuento falso)**
- Walmart anuncia: antes $200, ahora $20 → descuento anunciado = (1 − 20 ÷ 200) × 100 = **90%**.
- Walmart la tuvo en unos $25 durante los últimos 60 días. 1.5 × 25 = 37.50, y 200 es mayor que 37.50 → **PRECIO ANTES INFLADO**.
- Precio de mercado (Amazon): $22 → descuento real = (1 − 20 ÷ 22) × 100 = **9.1%** → **MERCADO YA BARATO** → **descartada**.

**Ejemplo B — Taladro (descuento anunciado exagerado, pero real)**
- Home Depot anuncia: antes $199, ahora $79 → descuento anunciado = **60.3%**.
- Precio de mercado: $149 → descuento real = (1 − 79 ÷ 149) × 100 = **47.0%** → pasa el mínimo de 20%, sigue en evaluación.

**Ejemplo C — Sierra circular (descuento real fuerte)**
- Home Depot liquidación: antes $129, ahora $29 → anunciado **77.5%**.
- Precio de mercado: $119 → descuento real = (1 − 29 ÷ 119) × 100 = **75.6%** → sigue en evaluación.

## 6. ¿Qué información necesitamos?
- Precio de oferta y "precio antes" que muestra la tienda.
- Historial de precios de esa tienda para ese producto (lo junta el sistema con el tiempo).
- Precio de mercado (RN-002).
- Cómo se identificó el producto (con código o solo por nombre).

## 7. ¿Qué obtenemos?
- Descuento anunciado, descuento real y las marcas que apliquen.

## 8. ¿Quién participa?
- El sistema calcula y marca.
- Jesús revisa manualmente las ofertas "sin referencia" y "coincidencia dudosa".

## 9. ¿De qué depende?
- RN-002 (precio de mercado).
- Del seguimiento de precios que el sistema hace de cada tienda (sin él no existe el historial de 60 días).

## 10. Limitaciones
- Al arrancar no hay historial de tiendas: la marca "precio antes inflado" no funcionará los primeros 60 días por producto. Mientras tanto, el descuento real contra el mercado es la protección principal.

## 11. ¿Qué pasa si…?
| Situación | Qué hace el sistema |
|---|---|
| La tienda no muestra "precio antes" | Descuento anunciado = no disponible; se evalúa solo el real |
| El precio de oferta es mayor que el de mercado | Descuento real negativo → MERCADO YA BARATO |
| Hay muy pocos datos en 60 días (menos de 5 consultas) | Se trata como SIN HISTORIAL DE TIENDA |

## 12. Preguntas para el experto
1. ¿20% de descuento real es un buen mínimo para seguir evaluando, o debería ser más (25%, 30%)?
2. ¿1.5 veces el precio típico de la tienda es un buen umbral para llamar "inflado" al precio antes?
3. ¿Conoce otras señales comunes de descuento engañoso que convenga detectar? Por ejemplo, precio por unidad mayor en el "paquete con descuento".

## 13. Decisiones tomadas
| Fecha | Decisión | Quién |
|---|---|---|
| 2026-11-08 | El descuento anunciado solo sirve para descubrir candidatos; nunca decide | Jesús |

## 14. Revisión de consistencia
- Última revisión: 2026-11-08 — APROBADO CON OBSERVACIONES
- Detalle: [revisiones/RN-003.md](/revisiones/RN-003.md)
