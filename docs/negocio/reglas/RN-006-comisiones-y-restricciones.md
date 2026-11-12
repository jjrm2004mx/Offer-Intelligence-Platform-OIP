# RN-006 — Comisiones, envío y restricciones de venta en Amazon

```yaml
id: RN-006
titulo: Comisiones, envío y restricciones de venta en Amazon
grupo: amazon
estado: BORRADOR
version: 2
fecha: 2026-11-11
responsable: Jesús
revisor_negocio: Experto en negocios internacionales
depende_de: [RN-013, RN-014]
version_anterior: https://github.com/jjrm2004mx/Offer-Intelligence-Platform-OIP/blob/5a4744d15b2ac6439f2cd89d25cb377ab437ab36/docs/negocio/reglas/RN-006-comisiones-y-restricciones.md
```

> **Cuándo aplica (v2).** Esta regla da los costos y restricciones **del canal Amazon FBM**. La tabla es manual y puede mantenerse desde ya, pero el margen en Amazon solo se calcula cuando haya precio de venta de Amazon (API oficial o Keepa, DEC-156). Los costos de venta local están en RN-001 y RN-016.

## 1. ¿Qué queremos lograr?
Saber **cuánto cobra Amazon y cuánto cuesta enviar** cada producto, y **si realmente se puede vender**. Algunas categorías requieren permiso de Amazon y algunos productos se consideran peligrosos para envío.

## 2. ¿Qué incluye y qué no?
**Incluye:**
- Comisión de Amazon por categoría.
- Costo de envío al cliente según peso y tamaño (vendiendo y enviando yo mismo, FBM).
- Lista de categorías y productos con restricción.

**No incluye:**
- Envío a bodegas de Amazon (modalidad FBA): no se usará al inicio.
- Venta local: OfferUp, Facebook Marketplace o venta directa (RN-001, RN-008 y RN-016).

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
| Productos **usados**, caja abierta o reacondicionados (RN-014) | Amazon exige requisitos de condición por categoría y algunas no aceptan usados | Por confirmar por categoría |

**Productos voluminosos o pesados** (refrigeradores, lavadoras y similares): **excluidos en el Inc. 1** en todos los canales (DEC-159).

## 5. ¿Cómo sabremos que funciona? — Ejemplos con números

**Ejemplo A — Taladro (2 kg)**
- Categoría herramientas: comisión 149 × 15% = **$22.35**. Envío (1 a 3 kg): **$12**. Sin restricción → vendible.

**Ejemplo B — Sierra circular (4 kg)**
- Comisión 119 × 15% = **$17.85**. Envío (3 a 6 kg): **$14**. Vendible.

**Ejemplo C — Perfume con 70% de descuento real**
- Categoría perfumes → posible material peligroso, sin aprobación → **NO VENDIBLE EN AMAZON (POR AHORA)**. No se alerta, aunque el margen sea alto.

**Ejemplo D — Comisión por definir**
- Reloj con categoría "por definir" → no se calcula margen; se marca "comisión desconocida" y no se alerta.

**Ejemplo E — Baterías de litio (CASO-005 y CASO-007, nuevo)**
- Baterías DEWALT o Milwaukee → posible material peligroso → **NO VENDIBLE EN AMAZON (POR AHORA)**. La oportunidad se evalúa solo en venta local.

**Ejemplo F — Usado (CASO-006, nuevo)**
- DEWALT DCF840 usado → "usado, requisitos por confirmar" → no vendible en Amazon hasta confirmarlo; se evalúa en venta local.

## 6. ¿Qué información necesitamos?
- Categoría del producto en Amazon, peso y tamaño aproximados, marca y condición (RN-014).

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
| 2026-11-11 | Canales por oportunidad; Amazon FBM se activa con fuente de Amazon (DEC-140, DEC-156) | Jesús |
| 2026-11-11 | Voluminosos excluidos en el Inc. 1 (DEC-159) | Jesús |

**Cambios de la v2 contra la v1:** la regla queda en el grupo `amazon`; se agregan la restricción de usados, la exclusión de voluminosos y los ejemplos E y F. Tablas, ejemplos A a D y preguntas, iguales que la v1.

## 14. Revisión de consistencia
- Última revisión: 2026-11-08 (v1) — APROBADO CON OBSERVACIONES. **La v2 está pendiente de revisión.**
- Detalle: [revisiones/RN-006.md](/revisiones/RN-006.md)
