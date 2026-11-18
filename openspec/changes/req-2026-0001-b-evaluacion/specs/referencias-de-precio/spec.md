# Spec Delta

## Purpose

Referencias de precio de la parte B (precio habitual, precio de mercado hoy, mínimo de 60 días y precio de venta esperado en Amazon), el descuento real con su franja y la calidad del precio, según RN-002, RN-003 y RN-012 y los supuestos de REQ-2026-0001.

## ADDED Requirements

### Requirement: Sin historial suficiente no hay descuento real
Sin historial suficiente (5 observaciones en 3 días distintos, en 60 días, contando una por publicación y día) no hay precio habitual: el sistema SHALL dejar la oferta sin descuento real ni `nivel_calculado`, calcular la calidad del precio con los datos que haya y dar `REVISION_MANUAL` con `SIN HISTORIAL SUFICIENTE`. Sin historial, la calidad no pasa de "Precio competitivo" (RN-002 v2, RN-003 v2, RN-012 v1; S-22).

#### Scenario: B6 — Sin historial suficiente
- **GIVEN** un producto con 3 observaciones en 2 días, MSRP $199, oferta $169, y hoy otros 3 comercios a $179, $185 y $189
- **WHEN** se evalúa la oferta
- **THEN** no hay descuento real ni nivel (`nivel_calculado` no disponible)
- **AND** calidad **Precio competitivo** (169 ≤ 182.58)
- **AND** resultado **`REVISION_MANUAL`**, motivo `SIN HISTORIAL SUFICIENTE`

### Requirement: Franja del descuento real
El sistema SHALL calcular el descuento real contra el precio habitual y clasificarlo: < 20% descarta (`MERCADO YA BARATO`), de 20% a < 25% es `SOLO_REFERENCIA`, y ≥ 25% sigue. Con descuento de 20% a < 25% MUST NOT calcular unidades, días, rendimiento ni nivel (RN-003 v2; REQ §3.2 paso 4; DEC-198).

#### Scenario: B7 — Solo referencia
- **GIVEN** oferta $80, precio habitual $100
- **WHEN** se evalúa la oferta
- **THEN** real **20.0%**
- **AND** resultado **`SOLO_REFERENCIA`**
- **AND** no se calculan unidades, días, rendimiento ni nivel (el margen ajustado de un canal disponible se calcularía si hubiera datos del canal, EXT-004)

### Requirement: Precio de venta esperado en Amazon sin oferta hoy
El precio de venta esperado en Amazon SHALL ser el botón de compra; sin oferta nueva hoy, el precio habitual en Amazon (mediana de 60 días de las observaciones de Amazon, con historial suficiente), con la marca `SIN OFERTA HOY`. Con precio habitual, el descuento anunciado se considera comparado y, con menos de 2 comercios, la calidad no pasa de "Precio competitivo" (RN-002 v2, RN-012 v1; S-02, S-28).

#### Scenario: B14 — Sin oferta en Amazon hoy
- **GIVEN** los datos de B1, pero Amazon no tiene oferta nueva hoy; precio habitual en Amazon $125
- **WHEN** se evalúa la oferta
- **THEN** venta esperada **$125** con `SIN OFERTA HOY`
- **AND** mercado hoy $124 (Walmart, 1 comercio) → calidad **Precio competitivo** (hay precio habitual, así que el descuento anunciado se considera comparado, §13 S-28)
- **AND** comisión $18.75, costo de venta $34.75, neto $59.00; devoluciones $4.38, castigo $8.00, ajustado **$46.62 (149.2%)**; rendimiento 121.0%; total $139.86
- **AND** local 124 × 85% = $105.40 → $94.86, total $108.22
- **AND** diferencia 22.6% → resultado `NIVEL_ASIGNADO` = **Muy recomendable, Amazon** (ya no va a revisión, RN-002 · P5)

### Requirement: Precio habitual con observaciones diarias y episodio de liquidación
El sistema SHALL calcular el precio habitual con una observación por publicación y día (la última), con la mediana de los 60 días anteriores al día evaluado, sin incluir ese día (con número par, el promedio de las dos centrales, sin redondear). Cuando el precio de una publicación baja y queda bajo su habitual, MUST congelarlo en esa mediana durante el episodio, como máximo 30 días (RN-002 v2, RN-003 v2; DEC-201, DEC-224, DEC-226).

#### Scenario: B30 (base) — Precio habitual con observaciones crudas y liquidación escalonada
- **GIVEN** un producto nuevo que solo vende Home Depot Chula Vista (no está en Amazon ni en otros comercios), vendido por el comercio, con seguimiento diario desde el día −25 (día 0 = hoy)
- **AND** observaciones: días −25 a −15, $129 (el día −20 hay dos: $139 a las 10:00 y $129 a las 22:00); días −14 a −8, $99; días −7 a −1, $65; hoy, $35. Límite del episodio: 30 días
- **WHEN** se evalúa la oferta
- **THEN** una observación por día, la última: el día −20 cuenta $129. Días −25 a −15: 11 observaciones a $129 → habitual **$129**, con historial suficiente
- **AND** el día −14 el precio **baja** ($99 < $129 del día −15) y queda por debajo de su habitual → empieza el **episodio** (día 1) y el habitual de esta publicación se congela en **$129**, el valor con que se habría evaluado ese día (mediana de los días −25 a −15)
- **AND** cada oferta del episodio se evalúa contra $129: día −14, $99 → real **23.3%** (`SOLO_REFERENCIA`); día −7, $65 → **49.6%**; hoy, $35 → **72.9%**
- **AND** la mediana de 60 días sí incluye las observaciones del episodio, pero no la del día evaluado (§3.2 paso 3, punto 5): hoy sería **$99** (25 observaciones, días −25 a −1). Sin congelar, el real de hoy sería 64.6%: la liquidación bajaría su propio habitual

#### Scenario: B30 (b) — El episodio termina a los 30 días y no empieza otro
- **GIVEN** los datos de B30, y el precio sigue a $35 hasta el día 26
- **WHEN** se evalúa la oferta
- **THEN** el día 15 (día 30 del episodio) todavía se evalúa contra $129 (72.9%)
- **AND** el día 16 (día 31) se evalúa contra la mediana normal: 41 observaciones (días −25 a 15) → **$65**, real **46.2%**
- **AND** el precio no vuelve a bajar, así que **no empieza otro episodio** (DEC-224) y la mediana sigue bajando: el día 25, 50 observaciones (días −25 a 24) → **$50**, real **30.0%**; el día 26, 51 observaciones (días −25 a 25) → **$35**, real **0.0%** → `MERCADO YA BARATO`

#### Scenario: B30 (c) — El precio vuelve al valor congelado
- **GIVEN** los datos de B30, y el día 5 vuelve a $129 (≥ $129 congelado)
- **WHEN** se evalúa la oferta
- **THEN** **termina** el episodio
- **AND** desde ahí se evalúa contra la mediana normal: 30 observaciones (días −25 a 4) → **$99**

#### Scenario: B30 (d) — Se congela la mediana, no el precio del día anterior
- **GIVEN** los datos del inicio de B30, pero el día −15 fue **$139**
- **WHEN** se evalúa la oferta
- **THEN** el día −14 baja ($99 < $139) y queda por debajo de su habitual
- **AND** el habitual se congela igual en **$129** (mediana de los días −25 a −15: diez a $129 y una a $139), **no** en $139 (DEC-226)
- **AND** el día −14 da **23.3%** (`SOLO_REFERENCIA`), no 28.8%

#### Scenario: B30 (e) — Baja sin observación del día anterior
- **GIVEN** los datos del inicio de B30, pero el día −15 **no tiene observación** (consulta bloqueada)
- **WHEN** se evalúa la oferta
- **THEN** el día −14 a $99 se compara con la **última observación anterior** de la publicación, los $129 del día −16 → **baja**
- **AND** queda por debajo de su habitual (mediana de los días −25 a −16: 10 observaciones a $129 → **$129**) → empieza el episodio y se congela en **$129**
- **AND** día −14 → **23.3%** (`SOLO_REFERENCIA`); hoy, $35 → **72.9%**
- **AND** la primera observación de la publicación (día −25) no tiene observación anterior: **no es baja** (DEC-226 c)

### Requirement: Comercio = cadena
Las sucursales y la tienda en línea de una cadena SHALL contar como un solo comercio: no cuentan como "otro comercio" entre sí ni para el precio de mercado hoy de una oferta de esa cadena ni para el mínimo de 2 comercios de RN-012. Excepción: en una liquidación en sucursal, el precio normal en línea de esa cadena MUST contar para el precio de mercado hoy (RN-002 v2 §4.1, RN-012 v1; S-03; DEC-216).

#### Scenario: B32 — Liquidación en sucursal: cuenta el precio en línea de la misma cadena
- **GIVEN** los datos de B1 (liquidación en Home Depot Chula Vista), y además homedepot.com vende el producto hoy a **$115**, precio normal, "disponible confirmada", vendido por el comercio; el precio habitual sigue en $119
- **WHEN** se evalúa la oferta
- **THEN** por la excepción de RN-002 §4.1, el precio en línea de la misma cadena **sí cuenta** para el precio de mercado hoy: mín(Amazon $119, Walmart $124, homedepot.com $115) = **$115**. Competencia más barata: no (115 ≥ 101.15)
- **AND** para el mínimo de 2 comercios de RN-012, homedepot.com **no cuenta** (comercio = cadena): siguen Amazon y Walmart. Calidad **Buena oferta** (29 ≤ 115 × 1.02 = 117.30)
- **AND** Amazon igual que B1: ajustado $44.73; 3 unidades; total **$134.19**
- **AND** local: 115 × 85% × 90% = 87.975 → **$87.98**; neto 87.98 − 31.25 − 9.50 = **$47.23 (151.1%)**; castigo $0 (87.98 < 109); 2 unidades; 30 días; rendimiento 151.1%; Muy recomendable; total **$94.46**. Marca `SIN COMPARABLES LOCALES`
- **AND** diferencia (134.19 − 94.46) ÷ 134.19 = 29.6% → **Amazon**. Resultado `NIVEL_ASIGNADO` = **Muy recomendable, Amazon**
- **AND** si la oferta de la sucursal **no** fuera liquidación, el precio de homedepot.com no contaría y el mercado hoy seguiría en $119 (D1)
