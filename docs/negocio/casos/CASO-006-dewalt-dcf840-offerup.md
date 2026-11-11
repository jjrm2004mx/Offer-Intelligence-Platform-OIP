# CASO-006 — Atornillador de impacto DEWALT DCF840 en OfferUp (compra a particular)

```yaml
id: CASO-006
tipo: búsqueda de ofertas (A) con fuente de abastecimiento entre particulares
fecha_del_ejercicio: 2026-11-11
moneda: USD
comercios: solo EE. UU.
reglas_que_prueba: [RN-001, RN-002, RN-005, RN-008, RN-009; DEC-140, DEC-141, DEC-142]
estado: EN ANÁLISIS (las decisiones se toman al terminar los ejercicios)
```

> Datos del ejercicio. **No se verificaron**, ni siquiera que la publicación siga disponible.

## 1. La idea nueva

OfferUp (y plataformas parecidas) no solo es **canal de venta**: también es **fuente de abastecimiento**. La oportunidad no nace del descuento de una tienda, sino de la **diferencia entre lo que pide un particular y el valor comercial del producto**. OIP distingue:

- **Fuente de abastecimiento:** tiendas en línea, tiendas físicas, OfferUp, Facebook Marketplace, otras plataformas de particulares.
- **Canal de venta:** Amazon, OfferUp, Facebook Marketplace, venta directa.

No es necesario vender en la misma plataforma donde se compra.

## 2. Datos encontrados

| Fuente | Presentación | Precio |
|---|---|---|
| OfferUp, San Diego | DCF840, brushless 20V, con batería 2 Ah y cargador; **estado sin confirmar** | $70 (pedido) |
| Lowe's | DCF840D1, con batería, cargador y bolsa, **nuevo** | $179.00 |
| The Power Tool Store | Kit DCF840C2, **nuevo** | $169.99 |

Diferencia anunciada contra Lowe's: 60.89%. Las presentaciones **no son idénticas**.

## 3. Resultado esperado

- **No es comparable contra el precio nuevo.** Lo de OfferUp es, casi seguro, **usado**; el valor comercial de un usado es el precio de **usados comparables**, no el de una tienda. El 60.89% no mide la oportunidad.
- **Margen con las tarifas de OIP** (venta hipotética de $120, que hay que respaldar con usados comparables): compra $70, recoger 30 min y 10 km = $9.50, entregar = $9.50 (DEC-142). Margen **$31.00** (44.29% sobre la compra), no $50.
- **Resultado: "por investigar, requiere inspección física".** Antes de comprar: funcionamiento, salud de la batería, autenticidad, procedencia y contenido exacto.

## 4. Huecos que descubrió (pendientes de decisión)

1. **Fuentes de abastecimiento entre particulares** (OfferUp, Marketplace): ¿entran al alcance y cómo? Mismos problemas que Marketplace como canal (DEC-140): sin API pública, condiciones de uso, datos personales de los vendedores y protección de la IP (DEC-041).
2. **Productos usados:** las reglas suponen producto **nuevo** (RN-002). Hace falta un valor de referencia para usados, de preferencia de **ventas concretadas** y no de precios pedidos.
3. **Estado del producto** como dato obligatorio (nuevo, abierto, usado, para piezas).
4. **Inspección física** como paso obligatorio antes de comprar a un particular.
5. **Doble traslado:** comprar y vender a particulares cuesta tiempo en los dos extremos.
6. **Riesgo de procedencia** (herramientas robadas o falsificadas), igual que CASO-005.
7. **Contenido exacto del kit:** cuarto caso con este patrón (edición, kit, generación, contenido).
