# ANL-001 — Modelo de compra, abastecimiento y comercialización

```yaml
id: ANL-001
fecha: 2026-11-11
autor: Jesús (análisis compartido en la sesión de ejercicios)
estado: EN ANÁLISIS (las decisiones se toman en la consolidación)
casos_relacionados: [CASO-005, CASO-006]
```

> Resumen fiel del análisis de Jesús (secciones 1 a 6) y observaciones de Claude (sección 7). Nada de esto cambia todavía las reglas.

## 1. Visión

OIP pasa de buscar ofertas en tiendas en línea a ser una plataforma de **inteligencia de oportunidades comerciales**: identificar **dónde conviene comprar** un artículo, venga de donde venga, y después **cuál es el mejor canal para venderlo**. Responde cuatro preguntas:

- ¿Qué artículo conviene comprar?
- ¿Dónde conviene comprarlo?
- ¿Dónde conviene venderlo?
- ¿Cuánto dinero se puede ganar realmente y en cuánto tiempo?

## 2. Tres funcionalidades de búsqueda

| Funcionalidad | Qué busca | Dónde busca | Objetivo | Equivale a |
|---|---|---|---|---|
| **F1. Búsqueda de ofertas** | Descuentos reales y oportunidades de compra | Tiendas en línea y físicas | Comprar por debajo del valor comercial para revender | Funcionalidad A (DEC-110) |
| **F2. Artículo específico** | Un producto que una persona necesita | Tiendas en línea, físicas y marketplaces | Localizar, comparar precio, disponibilidad y condiciones | Funcionalidad B (DEC-110) |
| **F3. Plataformas de particulares** | Productos que publican personas | OfferUp, Facebook Marketplace y similares | Precio pedido por debajo del valor comercial | **Nueva** |

Comparten información y mecanismos de evaluación.

## 3. Matriz de abastecimiento y comercialización

**El origen de compra y el canal de venta son independientes.** Cualquier origen (tienda en línea, tienda física, OfferUp, Facebook Marketplace, particular o contacto directo) puede combinarse con cualquier canal (Amazon, OfferUp, Facebook Marketplace, venta personal directa). Ninguna regla debe obligar a vender en la plataforma donde se compró; vender en Amazon un artículo comprado a un particular exige cumplir sus políticas de condición, autenticidad y documentación.

## 4. Dos procesos

**A. Adquisición:** precio solicitado, valor comercial, precio histórico, disponibilidad, **condición** (nuevo, usado, reacondicionado, caja abierta), identificación (modelo, marca, SKU, UPC/EAN, características), **riesgo de compra** (autenticidad, funcionamiento, procedencia, entrega) y costo de adquisición (precio, impuestos, traslado, otros). Resultado: **oportunidad potencial de adquisición**, no una recomendación de compra definitiva.

**B. Comercialización**, por canal:

| Canal | Qué considera |
|---|---|
| Amazon FBM | Comisión, envío, empaque, restricciones, competencia |
| OfferUp | Publicaciones comparables, competencia local, entrega |
| Facebook Marketplace | Precio local, competencia, entrega |
| Venta personal | Lo que un comprador pagaría, negociación, entrega |

Resultado: **rentabilidad estimada por canal**. Gana el mejor resultado ajustado por **costos, tiempo y riesgo**, no el precio de venta más alto.

## 5. Reglas en tres grupos

| Grupo | Alcance |
|---|---|
| Comunes | Identificación, comparación de precios, condición, autenticidad, costo de adquisición, riesgo |
| Comercialización Amazon | RN-001 a RN-009 actuales, con sus particularidades |
| Comercialización personal | Rentabilidad sin comisiones de Amazon, competencia local, negociación, entrega, demanda local, tiempo de venta, riesgo |

Algunos conceptos de RN-001 a RN-009 se reutilizan (el margen neto), pero el precio de venta esperado cambia por canal, el BSR no representa la demanda de OfferUp, las comisiones de Amazon no aplican a la venta personal y el traslado pesa más en operaciones locales.

## 6. Tres resultados distintos

1. **Oportunidad de compra:** precio atractivo frente al valor comercial.
2. **Oportunidad de reventa:** existe un canal rentable.
3. **Oportunidad de inversión:** además, tiempo, liquidez y riesgo justifican el dinero. $50 en tres meses no equivale a $30 en tres días.

## 7. Observaciones de Claude

1. **La mayor parte ya tiene lugar en el diseño.** "Oportunidad de inversión" es el **rendimiento mensual** de RN-005. Con una compra de $70: $50 en 90 días = 71.43% × 30 ÷ 90 = **23.81% al mes**; $30 en 3 días = 42.86% × 30 ÷ 3 = **428.57% al mes**. La regla ya distingue los dos casos.
2. **No todas las RN actuales son de Amazon.** RN-003 (descuentos falsos), RN-007 (disponibilidad en tienda), RN-008 (traslado), RN-010 (consulta responsable) y RN-011 (búsqueda por artículo) son **comunes**. Las propias de Amazon son RN-006 y la parte de Amazon de RN-001, RN-002 y RN-004.
3. **Alcance del Inc. 1:** la matriz completa son 20 combinaciones. Propuesta: tres orígenes (tienda en línea, tienda física y **particulares por captura manual**) y dos canales (**Amazon FBM** calculado y **venta local**, que agrupa OfferUp, Facebook Marketplace y venta personal con precio estimado). Las tres comparten casi los mismos costos al entregar en persona.
4. **Valor comercial según condición:** un usado se compara contra usados comparables, de preferencia ventas concretadas (CASO-006).
5. **F2 con particulares:** recomendarle a un cliente que compre a un particular traslada a él el riesgo de procedencia y funcionamiento; debería ir marcado y no recomendarse por defecto, igual que el vendedor externo (DEC-135).
6. **Amazon con usados:** vender usado en Amazon tiene requisitos por categoría; queda "por confirmar" por canal (RN-006).
