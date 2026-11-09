# RN-006 — Comisiones, envío y restricciones de venta

```yaml
id: RN-006
titulo: Comisiones, envío y restricciones de venta
estado: BORRADOR
version: 1
fecha: 2026-11-08
responsable: Jesús
revisor_negocio: Experto en negocios internacionales
depende_de: []
```

## 1. ¿Qué queremos lograr?
Saber **cuánto cobra Amazon y cuánto cuesta enviar** cada producto, y **si realmente se puede vender**. Algunas categorías requieren permiso de Amazon y algunos productos se consideran peligrosos para envío.

## 2. ¿Qué incluye y qué no?
**Incluye:**
- Comisión de Amazon por categoría.
- Costo de envío al cliente según peso y tamaño (vendiendo y enviando yo mismo, FBM).
- Lista de categorías y productos con restricción.

**No incluye:**
- Envío a bodegas de Amazon (modalidad FBA): no se usará al inicio.
- Facebook Marketplace (fase posterior).

## 3. ¿Cómo funciona, en palabras?
Mientras no exista cuenta de vendedor, el sistema usa una **tabla manual** de comisiones, envíos y restricciones. Cuando exista la cuenta, consultará los datos exactos directo con Amazon y la tabla quedará como respaldo.

## 4. La regla

**Comisión de Amazon** = precio de venta × % de la categoría.

| Categoría | Comisión | ¿Confirmado? |
|---|---|---|
| Herramientas | 15% | Por confirmar |
| Hogar e iluminación | 15% | Por confirmar |
| Tecnología | Por definir | Por confirmar |
| Juguetes | Por definir | Por confirmar |
| Relojes | Por definir | Por confirmar |
| Joyería | Por definir | Por confirmar |
| Perfumes y belleza | Por definir | Por confirmar |

**Envío al cliente (FBM)**, según peso con empaque:

| Peso | Envío estimado | ¿Confirmado? |
|---|---|---|
| hasta 1 kg | $8 | Por confirmar |
| 1 a 3 kg | $12 | Por confirmar |
| 3 a 6 kg | $14 | Por confirmar |
| más de 6 kg | Revisar manualmente | — |

**Restricciones** — si un producto cae aquí y no hay aprobación, se marca **NO VENDIBLE EN AMAZON (POR AHORA)**: no genera alerta, pero se muestra en el tablero con el motivo.

| Caso | Tipo de restricción | ¿Confirmado? |
|---|---|---|
| Joyería | Puede requerir aprobación de Amazon | Por confirmar |
| Relojes | Puede requerir aprobación de Amazon | Por confirmar |
| Perfumes, aerosoles, baterías de litio | Pueden considerarse material peligroso | Por confirmar |
| Marcas con venta restringida | Requieren autorización de la marca | Lista por construir |

## 5. ¿Cómo sabremos que funciona? — Ejemplos con números

**Ejemplo A — Taladro (2 kg)**
- Categoría herramientas: comisión 149 × 15% = **$22.35**. Envío (1 a 3 kg): **$12**. Sin restricción → vendible.

**Ejemplo B — Sierra circular (4 kg)**
- Comisión 119 × 15% = **$17.85**. Envío (3 a 6 kg): **$14**. Vendible.

**Ejemplo C — Perfume con 70% de descuento real**
- Categoría perfumes → posible material peligroso, sin aprobación → **NO VENDIBLE EN AMAZON (POR AHORA)**. No se alerta, aunque el margen sea alto.

**Ejemplo D — Comisión por definir**
- Reloj con categoría "por definir" → no se calcula margen; se marca "comisión desconocida" y no se alerta.

## 6. ¿Qué información necesitamos?
- Categoría del producto en Amazon, peso y tamaño aproximados, marca.

## 7. ¿Qué obtenemos?
- Comisión en $, envío en $, y si es vendible o el motivo de la restricción.

## 8. ¿Quién participa?
- Jesús mantiene la tabla manual.
- El experto ayuda a validar porcentajes y restricciones.
- Amazon (cuando haya cuenta) da los datos exactos.

## 9. ¿De qué depende?
- De tener la cuenta de vendedor para pasar de "estimado" a "exacto".

## 10. Limitaciones
- Las comisiones y restricciones de Amazon cambian. La tabla manual debe revisarse periódicamente (propuesta: cada 3 meses).

## 11. ¿Qué pasa si…?
| Situación | Qué hace el sistema |
|---|---|
| Categoría sin comisión definida | No calcula margen; marca "comisión desconocida"; sin alerta |
| No se conoce el peso | Usa el envío más caro de la tabla (o revisión manual si puede pasar de 6 kg) |
| Producto restringido pero ya hay aprobación | Se trata como vendible |

## 12. Preguntas para el experto
1. ¿Puede confirmar o corregir las comisiones por categoría, sobre todo tecnología, juguetes, relojes, joyería y perfumes?
2. ¿Qué categorías o marcas suele ver restringidas para vendedores nuevos?
3. ¿Los costos de envío estimados se acercan a lo que se paga normalmente?
4. ¿Recomienda alguna otra restricción importante (productos de temporada, alimentos, productos con fecha de caducidad)?

## 13. Decisiones tomadas
| Fecha | Decisión | Quién |
|---|---|---|
| 2026-11-08 | Se vende con FBM (envío propio), no FBA | Jesús |

## 14. Revisión de consistencia
- Última revisión: 2026-11-08 — APROBADO CON OBSERVACIONES
- Detalle: [revisiones/RN-006.md](/revisiones/RN-006.md)
