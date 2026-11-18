# Spec Delta

## Purpose

Evaluación por canal de venta (Amazon FBM y venta local) de la parte B: costo de compra, estado de cada canal, margen neto y ajustado, unidades, días, rendimiento y nivel, elección del canal y nivel del aviso, con el redondeo de la lista cerrada de REQ-2026-0001 §5.

## ADDED Requirements

### Requirement: Evaluación por canal y elección del canal
El sistema SHALL calcular por canal el costo de compra, el margen neto y el ajustado y, con descuento real ≥ 25% en un canal disponible, unidades, días, rendimiento y nivel, con el mínimo de margen ajustado mayor entre $10 y 10% del costo de compra. MUST elegir el canal por ganancia total del lote; con diferencia < 10% contra la mayor, desempata el rendimiento mensual (RN-001 v2, RN-004 v2, RN-005 v2, RN-006 v2, RN-009 v2, RN-016 v1, RN-017 v1, RN-018 v1; S-05, S-24).

#### Scenario: B1 — Sierra circular, situación base → Amazon, Muy recomendable
- **GIVEN** Home Depot Chula Vista, **liquidación**, herramientas, 4 kg, código confirmado, vendida por el comercio, $29.00 con tachado $129.00, "3 disponibles" hace 2 h; Home Depot sin historial suficiente propio; precio habitual $119 (8 observaciones en 6 días, 60 días de historial); hoy Amazon (botón de compra) $119 y Walmart $124 (hace 8 h); mínimo de 60 días en Amazon $109; ranking 6,000 (promedio de 7 días; hace 30 días 6,000), 5 vendedores, 200 comprados el mes pasado; sin estimado local de Jesús
- **WHEN** se evalúa
- **THEN** confianza **Alta** (cantidad exacta en liquidación, 2 h ≤ 3 h)
- **AND** anunciado 77.5%, real 75.6% (sigue). Marca `DESCUENTO ANUNCIADO NO COMPROBADO`
- **AND** mercado hoy $119; competencia más barata: no (119 ≥ 101.15). Calidad del precio **Buena oferta** (2 comercios; 60 días < 90)
- **AND** compra: impuesto $2.25 → **$31.25**. Demanda SUFICIENTE
- **AND** Amazon: comisión $17.85, envío $14, empaque $2 → costo de venta $33.85; neto **$53.90** (172.5%); devoluciones $4.17, castigo $5.00 → ajustado **$44.73 (143.1%)**; unidades mín(200 ÷ 6 = 33, 3 disponibles, tope 5) = **3**; días 7 + 30 = 37; rendimiento **116.1%**; nivel **Muy recomendable**; ganancia total **$134.19**
- **AND** local: 119 × 85% = $101.15 → × 0.90 = **$91.04**; neto $50.29 (160.9%); castigo $0; unidades 2; días 30; rendimiento 160.9%; Muy recomendable; total **$100.58**. Marca `SIN COMPARABLES LOCALES`
- **AND** diferencia (134.19 − 100.58) ÷ 134.19 = 25.0% → **Amazon**
- **AND** resultado `NIVEL_ASIGNADO` = **Muy recomendable, Amazon**

#### Scenario: B2 (base) — Taladro → venta local, Vigilar
- **GIVEN** Home Depot Chula Vista (no liquidación), herramientas, 2 kg, código confirmado, $79.00 con tachado $199.00, "4 disponibles" hace 2 h; precio típico de Home Depot en 60 días $149 (con historial suficiente); precio habitual $149 (8 observaciones en 6 días); hoy Amazon $149 y Walmart $152 (hace 6 h); mínimo de 60 días en Amazon $139; ranking 8,500 (hace 30 días 8,000), 9 vendedores, 300 comprados; estimado local de Jesús $129; comparables locales $135, $139 y $150
- **WHEN** se evalúa
- **THEN** anunciado 60.3%; no inflado (199 ≤ 1.5 × 149 = 223.50); real 47.0%. Calidad **Buena oferta**
- **AND** compra $85.12. Demanda SUFICIENTE (empeoró 6.25%, sin advertencia)
- **AND** Amazon: comisión $22.35, envío $12, empaque $2 → $36.35; neto **$27.53 (32.3%)**; devoluciones 149 × 7% × 50% = 5.215 → **$5.22**; castigo $5.00; ajustado **$17.31 (20.3%)**; 3 unidades; 37 días; rendimiento 16.5%; **sin nivel** (Vigilar exige 25%)
- **AND** local: techo $135 → pedido $129 → venta **$116.10**; entrega $9.50; neto **$21.48 (25.2%)**; castigo $0 (116.10 < 139); 2 unidades; 30 días; rendimiento 25.2%; mínimo mayor(10, 8.51) = $10 ✓ → **Vigilar**; total $42.96
- **AND** resultado `NIVEL_ASIGNADO` = **Vigilar, venta local** (solo tablero)

### Requirement: Restricción en Amazon cierra el canal
Una categoría, marca o producto en la tabla de restricciones SHALL dejar Amazon cerrado con `NO VENDIBLE EN AMAZON (POR AHORA)` (sin cuenta de vendedor), y la oferta MUST evaluarse en venta local. `MATERIAL PELIGROSO` solo no cierra Amazon; el perfume se cierra por la categoría (RN-006 v2; S-07, S-09).

#### Scenario: B4 — Perfume restringido → venta local, Recomendable
- **GIVEN** Walmart en línea (envío al PO Box), perfumes y belleza, 0.3 kg, código confirmado, vendido por Walmart, $27.00; precio habitual $90; hoy Amazon $88 y Target $92; mínimo de 60 días en Amazon $80; estimado local de Jesús $55; comparables locales $59 y $65; "disponible confirmada"
- **WHEN** se evalúa
- **THEN** real **70.0%**. Calidad **Buena oferta** (27 ≤ 89.76)
- **AND** Amazon: categoría belleza restringida, sin cuenta → `NO VENDIBLE EN AMAZON (POR AHORA)` y `MATERIAL PELIGROSO` → canal cerrado
- **AND** compra: impuesto $2.09 → $29.09. Local: pedido $55 → venta **$49.50**; neto 49.50 − 29.09 − 9.50 = **$10.91 (37.5%)**; castigo $0; unidades mín(2, tope 3) = 2; rendimiento 37.5%; mínimo $10 ✓ → **Recomendable** (Muy recomendable exige 40%)
- **AND** resultado `NIVEL_ASIGNADO` = **Recomendable, venta local** (resumen)

### Requirement: Competencia más barata y nivel del aviso
Con competencia más barata (RN-002 §4.3; 15%, REQ §5), el sistema SHALL marcar `COMPETENCIA MÁS BARATA` y bajar un nivel en Amazon. El canal elegido da la ganancia; el nivel del aviso MUST ser el más alto entre los canales con nivel, aunque el canal elegido sea otro, y el registro muestra aparte el canal de mejor ganancia total y el de mejor nivel (RN-002 v2 §4.3, RN-009 v2, RN-018 v1; S-33; DEC-219, DEC-221).

#### Scenario: B9 (base) — Competencia más barata
- **GIVEN** los datos de B1, y Target la vende hoy a $99 (hace 10 h)
- **WHEN** se evalúa la oferta
- **THEN** mercado hoy $99; `COMPETENCIA MÁS BARATA` (99 < 101.15) → Amazon baja de Muy recomendable a **Recomendable**; tope 3; 3 unidades; total $134.19
- **AND** local: 99 × 85% = $84.15 → **$75.74**; neto $34.99 (112.0%); Muy recomendable; 2 unidades; total $69.98
- **AND** diferencia (134.19 − 69.98) ÷ 134.19 = 47.9% → **Amazon**
- **AND** resultado `NIVEL_ASIGNADO` = **Recomendable, Amazon**. Calidad sigue en Buena oferta (29 ≤ 100.98)
- **AND** aviso (pregunta 4, §3.3 punto 4): nivel más alto entre los canales = **Muy recomendable** (venta local) → **inmediato**. El cuerpo muestra por separado el canal con mejor ganancia total (**Amazon**, Recomendable, $134.19) y el canal con mejor nivel (**venta local**, Muy recomendable, $69.98)
- **AND** si B1 ya estaba abierta y avisada, la observación de Target cambia el precio de mercado hoy y B1 se reevalúa con este resultado (§3.2.5): el nivel del aviso sigue en Muy recomendable y no se repite (C5)

### Requirement: Ranking de Amazon y demanda desconocida
El ranking SHALL ser el promedio de 7 días; con 1 a 6 días de datos, el promedio de los días disponibles; con 0 días, `DEMANDA DESCONOCIDA` y Amazon por revisar. El mismo valor MUST usarse para el umbral de demanda, los días de venta y el tope de primera compra. Un canal por revisar y otro con nivel: se usa el canal con nivel y el otro se muestra "por revisar" (RN-004 v2, RN-009 v2, RN-018 v1; S-30; DEC-206).

#### Scenario: B10 (a) — Sin ranking: Amazon por revisar, nivel en venta local
- **GIVEN** los datos de B1, sin ranking (0 días de datos)
- **WHEN** se evalúa la oferta
- **THEN** Amazon **por revisar** (`DEMANDA DESCONOCIDA`, no es motivo porque el otro canal tiene nivel)
- **AND** local: tope 3 → 2 unidades, $50.29 por unidad, total **$100.58**, Muy recomendable
- **AND** resultado `NIVEL_ASIGNADO` = **Muy recomendable, venta local**; Amazon se muestra "por revisar". (El viaje lo resuelve C3.)

#### Scenario: B10 (b) — Ranking con solo 3 días de datos
- **GIVEN** los datos de B1, con solo **3 días** de ranking: 9,000, 12,000 y 15,000 (sin dato de hace 30 días)
- **WHEN** se evalúa la oferta
- **THEN** 1 a 6 días → promedio de los disponibles (DEC-206): (9,000 + 12,000 + 15,000) ÷ 3 = **12,000**
- **AND** el mismo valor sirve para las tres cosas: umbral (12,000 ≤ 168,440 → SUFICIENTE; sin dato de hace 30 días no se evalúa `DEMANDA A LA BAJA`), días de venta (10,000 a 50,000 → 21; 21 + 30 = 51) y tope (12,000 no es < 10,000 → tope 3)
- **AND** Amazon: ajustado $44.73 (143.1%); unidades mín(33, 3, 3) = **3**; rendimiento 143.1% × 30 ÷ 51 = **84.2%**; Muy recomendable; total **$134.19**
- **AND** local como B1 ($100.58). Diferencia 25.0% → resultado `NIVEL_ASIGNADO` = **Muy recomendable, Amazon**

### Requirement: Unidades y demanda a la baja en Amazon
Las unidades en Amazon SHALL calcularse con RN-005 y el tope de primera compra (3; 5 si ranking < 10,000 y el nivel en el canal es Comprar ya o Muy recomendable, REQ §5); sin dato de comprados el mes pasado, MUST ser máximo 2 unidades con `ESTIMADO (unidades)`. `DEMANDA A LA BAJA` es una marca informativa: no cambia el resultado (REQ §3.2.3) (RN-004 v2, RN-005 v2, RN-018 v1).

#### Scenario: B12 — Sin ventas al mes: cambia el canal
- **GIVEN** los datos de B1, sin dato de comprados el mes pasado
- **WHEN** se evalúa la oferta
- **THEN** Amazon: unidades mín(2, 3, 5) = **2**, marca `ESTIMADO (unidades)`, días 7 + 30, rendimiento 116.1%, total $89.46
- **AND** local total $100.58; diferencia (100.58 − 89.46) ÷ 100.58 = 11.1% → **venta local**
- **AND** resultado `NIVEL_ASIGNADO` = **Muy recomendable, venta local**

#### Scenario: B13 — Demanda a la baja
- **GIVEN** los datos de B1, salvo: promedio de 7 días hoy 30,000, hace 30 días 18,000, y 10 vendedores
- **WHEN** se evalúa la oferta
- **THEN** SUFICIENTE con `DEMANDA A LA BAJA` (66.7%)
- **AND** unidades mín(200 ÷ 11 = 18, 3, tope 3) = 3; días 21 + 30 = 51; rendimiento **84.2%**
- **AND** resultado `NIVEL_ASIGNADO` = **Muy recomendable, Amazon** (134.19 contra 100.58)

### Requirement: Sin rotación cierra el canal
Si la venta al mes que le toca a Jesús es menor que 1, el sistema SHALL cerrar ese canal con `SIN ROTACIÓN` y evaluar el otro (RN-004 v2, RN-005 v2, RN-018 v1; S-08).

#### Scenario: B25 — Sin rotación en Amazon
- **GIVEN** los datos de B1, con 15 vendedores y 10 comprados el mes pasado
- **WHEN** se evalúa la oferta
- **THEN** 10 ÷ (15 + 1) = 0.625 → 0 → Amazon cerrado (`SIN ROTACIÓN`, §13 S-08)
- **AND** local como B1 ($100.58) → resultado `NIVEL_ASIGNADO` = **Muy recomendable, venta local**

### Requirement: Castigo sin mínimo de 60 días
El castigo por baja SHALL calcularse en Amazon y en venta local contra el mínimo de 60 días en Amazon; sin ese mínimo, MUST ser el 10% del precio de venta del canal (RN-005 v2, RN-009 v2; S-01, S-05).

#### Scenario: B15 — Sin mínimo de 60 días → sin nivel
- **GIVEN** los datos de B2, sin mínimo de 60 días en Amazon
- **WHEN** se evalúa la oferta
- **THEN** Amazon: castigo 10% × 149 = $14.90, ajustado **$7.41**
- **AND** local: castigo 10% × 116.10 = $11.61, ajustado **$9.87 (11.6%)**
- **AND** los dos < $10 → resultado **`SIN_NIVEL`**

### Requirement: Envío y empaque según el peso
El envío FBM y el empaque SHALL salir de la tabla por peso (hasta 6 kg). Sin peso, MUST usarse envío $14 y empaque $2 con `ESTIMADO (peso)`. Con más de 6 kg se usa la cotización capturada; sin ella, Amazon queda cerrado con `ENVÍO POR COTIZAR` (RN-001 v2, RN-005 v2, RN-006 v2, RN-018 v1; S-06).

#### Scenario: B16 — Peso desconocido
- **GIVEN** los datos de B2, sin peso ni medidas
- **WHEN** se evalúa la oferta
- **THEN** envío $14 y empaque $2 (`ESTIMADO (peso)`, §13 S-06); costo de venta $38.35; neto $25.53; ajustado $15.31 (18.0%) → Amazon sin nivel
- **AND** local igual que B2 → resultado `NIVEL_ASIGNADO` = **Vigilar, venta local**

#### Scenario: B26 (a) — Más de 6 kg sin cotización
- **GIVEN** los datos de B1, con peso de 8 kg, sin cotización
- **WHEN** se evalúa la oferta
- **THEN** Amazon cerrado (`ENVÍO POR COTIZAR`) → `NIVEL_ASIGNADO` = **Muy recomendable, venta local**

#### Scenario: B26 (b) — Más de 6 kg con cotización capturada
- **GIVEN** los datos de B1, con peso de 8 kg, con cotización capturada de $22
- **WHEN** se evalúa la oferta
- **THEN** costo de venta 17.85 + 22 + 2 = $41.85; neto $45.90; ajustado **$36.73 (117.5%)**; 3 unidades, total **$110.19**, rendimiento 95.3%
- **AND** local $100.58, rendimiento 160.9%
- **AND** diferencia (110.19 − 100.58) ÷ 110.19 = 8.7% < 10% → desempata el rendimiento → **venta local, Muy recomendable**

### Requirement: Comisión desconocida cierra Amazon
Una categoría sin comisión en la tabla SHALL dejar Amazon cerrado con `COMISIÓN DESCONOCIDA`, y la oferta MUST evaluarse en venta local (RN-006 v2, RN-018 v1; REQ §5).

#### Scenario: B17 — Comisión desconocida
- **GIVEN** los datos de B2, en una categoría sin comisión en la tabla
- **WHEN** se evalúa la oferta
- **THEN** Amazon cerrado (`COMISIÓN DESCONOCIDA`)
- **AND** local igual que B2 → resultado `NIVEL_ASIGNADO` = **Vigilar, venta local**

### Requirement: Confianza en tienda física para el nivel
En tienda física, el nivel de un canal disponible SHALL exigir confianza Alta o Media al evaluar; con confianza Baja, MUST marcarse `CONFIANZA BAJA` y el canal queda sin nivel, con su `nivel_calculado`. En recoger en tienda, "disponible confirmada" cuenta como Alta (RN-007 v2, RN-009 v2 §4.2; S-25; DEC-202).

#### Scenario: B21 — Confianza baja en tienda
- **GIVEN** los datos de B2, pero "existencia limitada" hace 3 h
- **WHEN** se evalúa la oferta
- **THEN** confianza **Baja** (`CONFIANZA BAJA`)
- **AND** `nivel_calculado` = Vigilar (local)
- **AND** resultado **`SIN_NIVEL`**

### Requirement: Sin precio de venta en Amazon
Si el producto no está en Amazon, o no tiene oferta nueva hoy ni precio habitual en Amazon, el sistema SHALL cerrar Amazon con `SIN PRECIO DE VENTA EN AMAZON`, sin calcular ningún margen de Amazon, y evaluar solo la venta local. Esta causa de cerrado MUST prevalecer sobre `DEMANDA DESCONOCIDA` (RN-002 v2 §11, RN-005 v2, RN-009 v2, RN-016 v1, RN-018 v1; S-05; DEC-197).

#### Scenario: B28 (a) — El producto no está en Amazon
- **GIVEN** los datos de B1, salvo que el producto **no está en Amazon** (sin ficha: sin botón de compra, ranking, vendedores ni mínimo de 60 días; precio habitual $119 de las observaciones de Walmart)
- **WHEN** se evalúa la oferta
- **THEN** Amazon **cerrado**, `SIN PRECIO DE VENTA EN AMAZON`; no se calcula ningún margen de Amazon
- **AND** también falta el ranking: la causa de cerrado prevalece sobre `DEMANDA DESCONOCIDA` (§3.2.1), así que no hay revisión manual
- **AND** mercado hoy **$124** (Walmart, 1 comercio). Real **75.6%** (contra $119)
- **AND** compra **$31.25**. Local: 124 × 85% × 90% = **$94.86**; neto 94.86 − 31.25 − 9.50 = **$54.11 (173.2%)**; sin mínimo de 60 días → castigo 10% × 94.86 = **$9.49**; ajustado **$44.62 (142.8%)**; unidades 2; días 30; rendimiento 142.8%; mínimo $10 ✓ → **Muy recomendable**; total **$89.24**. Marca `SIN COMPARABLES LOCALES`
- **AND** resultado `NIVEL_ASIGNADO` = **Muy recomendable, venta local**

#### Scenario: B28 (b) — En Amazon sin oferta hoy ni observaciones en 60 días
- **GIVEN** los datos de B1, salvo que el producto está en Amazon (ranking 6,000, 5 vendedores, 200 comprados el mes pasado), pero **sin oferta nueva hoy** y **sin observaciones de oferta en 60 días** (sin precio habitual ni mínimo de 60 días en Amazon)
- **WHEN** se evalúa la oferta
- **THEN** Amazon **cerrado**, `SIN PRECIO DE VENTA EN AMAZON`; no se calcula ningún margen de Amazon
- **AND** mercado hoy **$124** (Walmart, 1 comercio). Real **75.6%** (contra $119)
- **AND** compra **$31.25**. Local: 124 × 85% × 90% = **$94.86**; neto 94.86 − 31.25 − 9.50 = **$54.11 (173.2%)**; sin mínimo de 60 días → castigo 10% × 94.86 = **$9.49**; ajustado **$44.62 (142.8%)**; unidades 2; días 30; rendimiento 142.8%; mínimo $10 ✓ → **Muy recomendable**; total **$89.24**. Marca `SIN COMPARABLES LOCALES`
- **AND** resultado `NIVEL_ASIGNADO` = **Muy recomendable, venta local**

### Requirement: Redondeo una sola vez por fórmula
El sistema SHALL redondear a centavos, con el medio centavo hacia arriba, solo los montos de la lista cerrada de REQ §5, y cada fórmula de varios factores MUST redondearse una sola vez, al final. Los porcentajes no se redondean para calcular ni para comparar; se muestran con 1 decimal (RN-001 v2, RN-005 v2, RN-016 v1; DEC-060, DEC-207, DEC-222).

#### Scenario: B33 — Redondeo una sola vez por fórmula
- **GIVEN** los datos de B28 (a) (el producto no está en Amazon), pero Walmart lo vende hoy a **$100.15**; el precio habitual sigue en $119
- **WHEN** se evalúa la oferta
- **THEN** mercado hoy $100.15; real **75.6%** (contra $119). Compra **$31.25**
- **AND** local: 100.15 × 85% × 90% = 76.614750 → **$76.61**, redondeado una sola vez al final. Si se redondeara en cada paso (100.15 × 85% = 85.1275 → $85.13 → × 90% = 76.617 → $76.62), el resultado sería distinto, y ese camino no es válido
- **AND** neto 76.61 − 31.25 − 9.50 = **$35.86 (114.8%)**; sin mínimo de 60 días → castigo 10% × 76.61 = 7.661 → **$7.66**; ajustado **$28.20 (90.2%)**; unidades 2; días 30; rendimiento 90.2%; mínimo $10 ✓ → **Muy recomendable**; total **$56.40**. Marca `SIN COMPARABLES LOCALES`
- **AND** resultado `NIVEL_ASIGNADO` = **Muy recomendable, venta local**
