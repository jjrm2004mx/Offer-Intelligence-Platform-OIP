# Spec Delta

## Purpose

Resultado de cada evaluación de la parte B: todos los motivos, el motivo principal y el resultado con la precedencia de REQ-2026-0001 §3.2.4, el `nivel_calculado` y el registro de evaluación, y la reevaluación de las oportunidades abiertas cuando cambia una referencia de precio.

## ADDED Requirements

### Requirement: Precedencia, motivo principal y todos los motivos
El sistema SHALL reunir todos los motivos de §3.2.3 y decidir el resultado con la precedencia DESCARTADA > SOLO_REFERENCIA > REVISION_MANUAL > nivel; el motivo principal MUST ser el primero que aplique en el orden de §3.2.3. Todos los motivos se guardan en el registro de evaluación, con los datos de REQ §7 (RN-009 v2; S-18; DEC-198).

#### Scenario: B3 — Lámpara → descartada
- **GIVEN** Walmart en línea, hogar e iluminación, 0.8 kg, código confirmado, $20.00 con tachado $200.00; precio típico de Walmart en 60 días $25 (historial suficiente); precio habitual $22; hoy solo Amazon $22; sin mínimo de 60 días en Amazon; ranking 420,000, 6 vendedores; sin estimado local de Jesús y **sin comparables locales**
- **WHEN** se evalúa
- **THEN** anunciado 90.0%; `PRECIO ANTES INFLADO` (200 > 37.50); real **9.1%** → `MERCADO YA BARATO`
- **AND** calidad **Descuento cuestionable**
- **AND** compra $21.55. Neto Amazon (informativo): comisión $3.30 + envío $8 + empaque $1 → **−$11.85**. Neto local: 22 × 85% = $18.70 → $16.83 → **−$14.22**
- **AND** marca `DEMANDA INSUFICIENTE EN AMAZON` (420,000 > 168,440) → Amazon cerrado
- **AND** venta local disponible, sin techo (marca `SIN COMPARABLES LOCALES`, RN-016 §11): ajustado aunque no haya descuento real (EXT-004): castigo 10% × 16.83 = **$1.68** (sin mínimo de 60 días) → **−$15.90**. No se calculan unidades, días, rendimiento ni nivel
- **AND** ajustado < 0 en el único canal disponible y ningún canal por revisar → `MARGEN NEGATIVO`
- **AND** resultado **`DESCARTADA`**, motivo principal `MERCADO YA BARATO` (va antes en §3.2.3); también se guarda `MARGEN NEGATIVO`

#### Scenario: B29 — Sin historial y margen negativo → descartada
- **GIVEN** los datos de B23, pero el producto es nuevo en el sistema: 3 observaciones en 2 días, sin precio habitual ni mínimo de 60 días en Amazon
- **WHEN** se evalúa la oferta
- **THEN** sin descuento real (`SIN HISTORIAL SUFICIENTE`); calidad **Precio competitivo** (79 ≤ 149 × 1.02 = 151.98; sin historial no pasa de aquí)
- **AND** Amazon cerrado (`DEMANDA INSUFICIENTE EN AMAZON`, 200,000 > 168,440)
- **AND** local (disponible): compra **$85.12**; pedido $95 → venta **$85.50**; neto 85.50 − 85.12 − 9.50 = **−$9.12**; sin mínimo de 60 días → castigo 10% × 85.50 = **$8.55**; ajustado **−$17.67 (−20.8%)**, calculado aunque no haya descuento real (EXT-004). Sin unidades, días, rendimiento ni `nivel_calculado`
- **AND** ajustado < 0 en el único canal disponible y ningún canal por revisar → `MARGEN NEGATIVO`
- **AND** resultado **`DESCARTADA`**, motivo principal `MARGEN NEGATIVO`; también se guarda `SIN HISTORIAL SUFICIENTE`

### Requirement: Margen negativo descarta
Con margen ajustado < 0 en todos los canales disponibles y ningún canal por revisar, el sistema SHALL dar `DESCARTADA` con `MARGEN NEGATIVO`, haya o no descuento real. El margen ajustado MUST calcularse siempre en un canal disponible (RN-001 v2, RN-005 v2, RN-009 v2, RN-016 v1; S-11; DEC-198).

#### Scenario: B23 — Margen negativo
- **GIVEN** los datos de B2, con ranking 200,000 y estimado local de Jesús $95
- **WHEN** se evalúa la oferta
- **THEN** Amazon cerrado
- **AND** local: pedido $95 → venta **$85.50**; neto 85.50 − 85.12 − 9.50 = **−$9.12**; castigo $0; ajustado −$9.12
- **AND** resultado **`DESCARTADA`**, motivo `MARGEN NEGATIVO`

### Requirement: Sin canal disponible descarta
Con los dos canales cerrados (ninguno disponible ni por revisar), el sistema SHALL dar `DESCARTADA` con `SIN CANAL DISPONIBLE` (RN-004 v2, RN-009 v2, RN-017 v1, RN-018 v1; S-11).

#### Scenario: B22 — Sin canal disponible
- **GIVEN** los datos de B2, con ranking 200,000 y demanda local de herramientas **baja**
- **WHEN** se evalúa la oferta
- **THEN** Amazon cerrado (`DEMANDA INSUFICIENTE EN AMAZON`, 200,000 > 168,440) y local cerrado
- **AND** real 47.0% (sigue)
- **AND** resultado **`DESCARTADA`**, motivo `SIN CANAL DISPONIBLE`

### Requirement: Revisión manual con nivel calculado
Una oferta identificada solo por nombre SHALL dar `REVISION_MANUAL` con `COINCIDENCIA NO CONFIRMADA`, sin aviso. `nivel_calculado` (nivel de RN-009 §4.3 con el mínimo por unidad y la baja por competencia más barata, sin los demás requisitos de canal) MUST guardarse siempre que se pueda calcular, también en `REVISION_MANUAL` (RN-009 v2 §4.1, RN-013 v1; DEC-202).

#### Scenario: B5 — Coincidencia no confirmada → revisión
- **GIVEN** los datos de B1, pero la publicación no trae código ni modelo (solo nombre)
- **WHEN** se evalúa la oferta
- **THEN** las métricas son las de B1
- **AND** motivo `COINCIDENCIA NO CONFIRMADA`; `nivel_calculado` = Muy recomendable (Amazon)
- **AND** resultado **`REVISION_MANUAL`**, sin aviso

### Requirement: Vendedor externo y riesgo de procedencia
Si vende un tercero en el comercio, o no se sabe quién vende, el sistema SHALL agregar `VENDEDOR EXTERNO`; baterías, herramientas, perfumes o relojes de particular o vendedor externo MUST agregar `RIESGO DE PROCEDENCIA`. Los dos llevan a `REVISION_MANUAL` (RN-009 v2, RN-012 v1, RN-015 v1; S-21; DEC-137).

#### Scenario: B8 — Vendedor externo → revisión
- **GIVEN** los mismos precios, producto y datos de Amazon de B1, pero la oferta es **en línea** en homedepot.com (envío al PO Box, disponible confirmada) y la vende un vendedor externo
- **WHEN** se evalúa la oferta
- **THEN** las cuentas por unidad son las de B1
- **AND** motivos `VENDEDOR EXTERNO` y `RIESGO DE PROCEDENCIA` (herramientas)
- **AND** calidad **Descuento cuestionable** (vendedor externo sin confirmar, RN-012); `nivel_calculado` = Muy recomendable (Amazon)
- **AND** resultado **`REVISION_MANUAL`**, motivo principal `VENDEDOR EXTERNO`

### Requirement: Demanda desconocida sin otro canal con nivel
Con Amazon por revisar y ningún otro canal con nivel, el sistema SHALL dar `REVISION_MANUAL` con `DEMANDA DESCONOCIDA`. En el canal por revisar MUST calcular el margen ajustado y `nivel_calculado` informativo, sin unidades, días ni rendimiento (RN-004 v2, RN-009 v2; S-30).

#### Scenario: B11 — Demanda desconocida sin otro canal → revisión
- **GIVEN** los datos de B10 (a), y además Jesús calificó herramientas con demanda local **baja**
- **WHEN** se evalúa la oferta
- **THEN** local cerrado
- **AND** Amazon por revisar: margen ajustado $44.73 (143.1%), `nivel_calculado` = **Muy recomendable** (Amazon), sin unidades, días ni rendimiento
- **AND** resultado **`REVISION_MANUAL`**, motivo `DEMANDA DESCONOCIDA`

### Requirement: Compra a particular con inspección
La compra a un particular SHALL dar `PARTICULAR` (inspección física obligatoria) y `REVISION_MANUAL`. El costo de compra MUST incluir la recogida y no lleva impuesto; el usado usa el valor de referencia de RN-014 en lugar del precio habitual, solo se evalúa en venta local y su calidad del precio no aplica (RN-001 v2, RN-008 v2, RN-014 v1, RN-015 v1, RN-016 v1; S-05, S-12, S-13, S-14; DEC-215).

#### Scenario: B18 — Particular → revisión con inspección
- **GIVEN** captura manual de un atornillador DEWALT DCF840 usado, de un particular en San Diego, $70, modelo + marca y mismo contenido; usados comparables (precios pedidos) $120, $130 y $140; recogida $9.50; sin estimado de Jesús; **sin datos de Amazon** (ni ficha ni mínimo de 60 días)
- **WHEN** se evalúa la oferta
- **THEN** valor de referencia 130 × 85% = **$110.50**; real **36.7%**. Compra 70 + 9.50 = **$79.50** (sin impuesto). Calidad del precio: **no aplica** (usado, EXT-031)
- **AND** Amazon cerrado (usado). Local: pedido mín(110.50, 120) → venta **$99.45**; neto $10.45; castigo 10% = $9.95 (sin mínimo de 60 días en Amazon, S-05); ajustado $0.50 → sin nivel
- **AND** motivos `PARTICULAR` y `RIESGO DE PROCEDENCIA` → resultado **`REVISION_MANUAL`**, motivo principal `PARTICULAR`

### Requirement: Evitar siempre descarta
Un producto de la lista "evitar siempre" SHALL dar `DESCARTADA` con `EVITAR`, cualquiera que sea su descuento o su margen (RN-015 v1; S-16, S-21).

#### Scenario: B19 — Evitar siempre
- **GIVEN** un asiento para auto con 70% de descuento real y 60% de margen ajustado
- **WHEN** se evalúa la oferta
- **THEN** resultado **`DESCARTADA`**, motivo `EVITAR`

### Requirement: Usado sin valor de referencia
Un usado con menos de 3 comparables SHALL quedar sin valor de referencia ni descuento real, con la venta local por revisar y `SIN REFERENCIA DE USADOS`. Sin estimado de Jesús no se calcula margen; con estimado, margen neto y ajustado informativos. Si concurre una causa de cerrado del canal local, MUST prevalecer cerrado (RN-009 v2, RN-014 v1, RN-015 v1, RN-016 v1; S-12, S-31).

#### Scenario: B24 (a) — Usado con 2 comparables, sin estimado de Jesús
- **GIVEN** los datos de B18 (sin datos de Amazon), con solo 2 comparables ($120 y $130)
- **WHEN** se evalúa la oferta
- **THEN** 2 < 3 → sin valor de referencia ni descuento real (no se evalúan `MERCADO YA BARATO` ni `SOLO REFERENCIA`). Compra 70 + 9.50 = **$79.50**. Calidad del precio: **no aplica** (usado, EXT-031)
- **AND** Amazon **cerrado** (usado, S-12). Venta local **por revisar** (S-31): sin estimado de Jesús ni valor de referencia no hay precio local, así que no se calcula margen y `nivel_calculado` no está disponible
- **AND** precedencia (§3.2.4): no hay `SIN CANAL DISPONIBLE` (un canal por revisar) ni `MARGEN NEGATIVO` (no se calcula en un canal por revisar) → ningún motivo de DESCARTADA ni SOLO REFERENCIA
- **AND** motivos `SIN REFERENCIA DE USADOS`, `PARTICULAR` y `RIESGO DE PROCEDENCIA` (herramienta de particular) → resultado **`REVISION_MANUAL`**, motivo principal `SIN REFERENCIA DE USADOS` (va antes en §3.2.3)

#### Scenario: B24 (b) — Usado sin referencia con demanda local baja
- **GIVEN** los datos de B18 (sin datos de Amazon), con solo 2 comparables ($120 y $130), y Jesús calificó herramientas con demanda local **baja**
- **WHEN** se evalúa la oferta
- **THEN** la causa de cerrado prevalece (S-31) → local **cerrado**
- **AND** con Amazon cerrado → `SIN CANAL DISPONIBLE` → resultado **`DESCARTADA`**, motivo principal `SIN CANAL DISPONIBLE` (los motivos de revisión se guardan)

#### Scenario: B24 (c) — Usado sin referencia con estimado de Jesús
- **GIVEN** los datos de B18 (sin datos de Amazon), con solo 2 comparables ($120 y $130), y estimado local de Jesús $115
- **WHEN** se evalúa la oferta
- **THEN** techo $120 (menor de los 2 comparables) → pedido $115 → venta **$103.50**
- **AND** neto 103.50 − 79.50 − 9.50 = **$14.50 (18.2%)**; castigo 10% = $10.35 (sin mínimo de 60 días en Amazon); ajustado **$4.15 (5.2%)**, informativos
- **AND** `nivel_calculado` no disponible (sin descuento real); el canal sigue por revisar
- **AND** resultado **`REVISION_MANUAL`**, motivo principal `SIN REFERENCIA DE USADOS`

### Requirement: Reevaluación de oportunidades abiertas
Cuando una observación nueva cambia una referencia de precio de un producto, el sistema SHALL reevaluar la evaluación más reciente de cada publicación del producto que dio `NIVEL_ASIGNADO`, como evaluación nueva que conserva la anterior. Si la anterior tenía nivel con aviso y la nueva lo pierde, MUST salir como "ya no recomendado" en el siguiente resumen y en el tablero, sin aviso inmediato; una en Vigilar no se anuncia (RN-002 v2, RN-009 v2; S-33; DEC-204, DEC-224).

#### Scenario: B2 (b) — Vigilar que pierde el nivel
- **GIVEN** B2 abierta en Vigilar (sin aviso)
- **WHEN** llega una observación de la **ficha de Amazon**: botón de compra **$105**, y el mínimo de 60 días en Amazon baja a **$105**
- **THEN** cambian el precio de mercado hoy, el mínimo de 60 días y el precio de venta esperado en Amazon, así que B2 se reevalúa
- **AND** real sigue en **47.0%** (el habitual no incluye el día evaluado)
- **AND** Amazon: comisión 105 × 15% = **$15.75**, costo de venta $29.75; neto 105 − 85.12 − 29.75 = **−$9.87 (−11.6%)** → sin nivel
- **AND** local: venta **$116.10** (el estimado y el techo no cambian); neto **$21.48 (25.2%)**; castigo 50% × (116.10 − 105) = **$5.55** (antes $0); ajustado **$15.93 (18.7%)** → sin nivel (Vigilar exige 25%)
- **AND** no hay `MARGEN NEGATIVO` (el ajustado local es positivo) → resultado **`SIN_NIVEL`**
- **AND** como la evaluación anterior estaba en Vigilar, **no** aparece como "ya no recomendado" en el resumen: solo cambia en el tablero

#### Scenario: B9 (b) — Pierde el nivel
- **GIVEN** B1 abierta y avisada (Muy recomendable, Amazon); el precio habitual sigue en $119 y Target no tiene oferta
- **WHEN** llega una observación de la **ficha de Amazon**: botón de compra **$60**, y el mínimo de 60 días en Amazon baja a **$60**
- **THEN** la ficha no se evalúa como oferta (§3.1 punto 10), pero cambia tres referencias (precio de mercado hoy, mínimo de 60 días y precio de venta esperado en Amazon), así que B1 se reevalúa
- **AND** mercado hoy $60 (Amazon); competencia más barata: no (60 ≥ 60 × 85% = 51). Real sigue en 75.6%
- **AND** Amazon: comisión 60 × 15% = $9.00; costo de venta 9.00 + 14 + 2 = $25.00; neto 60 − 31.25 − 25.00 = **$3.75 (12.0%)**; devoluciones 60 × 7% × 50% = $2.10; castigo $0 (60 no pasa de 60); ajustado **$1.65 (5.3%)** < $10 → sin nivel
- **AND** local: 60 × 85% × 90% = **$45.90**; neto 45.90 − 31.25 − 9.50 = **$5.15 (16.5%)**; castigo $0 (45.90 < 60); ajustado **$5.15** < $10 → sin nivel
- **AND** resultado **`SIN_NIVEL`**. La evaluación anterior tenía aviso (Muy recomendable) → la oportunidad sale como **"ya no recomendado"** en el siguiente resumen (8:00 o 18:00) y en el tablero, **sin aviso inmediato**
