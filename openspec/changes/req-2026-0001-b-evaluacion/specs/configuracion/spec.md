# Spec Delta

## Purpose

Configuración versionada de la evaluación de la parte B: las tablas y parámetros de REQ-2026-0001 §6 (impuestos por ubicación, valores por código de `category` y demás umbrales), editables sin cambiar código, de modo que cada evaluación use y registre la versión con que se calculó.

## ADDED Requirements

### Requirement: Impuesto por ubicación de la tienda
El sistema SHALL calcular el impuesto de compra con la tasa de la ubicación de la tienda (`taxLocation`) cargada en la tabla de impuestos de la configuración versionada, con fuente (CDTFA) y fecha de vigencia. Si la tienda no tiene ubicación cargada, MUST usar la tasa de respaldo 7.75%. Con envío al PO Box, la ubicación es la del PO Box (San Diego, 7.75%). Particulares sin impuesto (RN-001 v2; S-14; REQ §3.2 paso 6, §5, §6; DEC-220).

#### Scenario: B31 — Tienda de Chula Vista a 8.75%
- **GIVEN** los datos de B1, con la tasa de la ubicación de Home Depot Chula Vista cargada en la tabla de impuestos: **8.75%** (fuente CDTFA, con fecha de vigencia)
- **WHEN** se evalúa la oferta
- **THEN** compra: impuesto 29 × 8.75% = 2.5375 → **$2.54** → **$31.54** (con 7.75% era $31.25)
- **AND** Amazon: costo de venta $33.85; neto 119 − 31.54 − 33.85 = **$53.61 (170.0%)**; devoluciones $4.17, castigo $5.00 → ajustado **$44.44 (140.9%)**; 3 unidades; 37 días; rendimiento **114.2%**; Muy recomendable; total **$133.32**
- **AND** local: venta $91.04; neto 91.04 − 31.54 − 9.50 = **$50.00 (158.5%)**; castigo $0; 2 unidades; 30 días; rendimiento 158.5%; Muy recomendable; total **$100.00**
- **AND** diferencia (133.32 − 100.00) ÷ 133.32 = 25.0% → **Amazon**; resultado `NIVEL_ASIGNADO` = **Muy recomendable, Amazon**
- **AND** si la tienda no tuviera ubicación cargada, se usaría la tasa de respaldo 7.75% (los números de B1)

### Requirement: Valores por código de category
El sistema SHALL tomar de la configuración, por código cerrado de `category`, la comisión, la tasa de devolución (propia o asignada) y la pérdida por devolución, y el umbral de demanda. Consolas y videojuegos MUST usar la tasa de tecnología (11%) con `ESTIMADO (devolución)`. Un "—" en comisión o tasa de devolución cierra Amazon; en el umbral de demanda lo deja por revisar con `DEMANDA DESCONOCIDA` (RN-004 v2, RN-005 v2, RN-006 v2; S-27; REQ §5; DEC-225).

#### Scenario: B27 — Consola sin tasa propia
- **GIVEN** una consola de videojuegos con venta esperada en Amazon de $339.99
- **WHEN** se evalúa la oferta
- **THEN** comisión 339.99 × 8% = $27.20
- **AND** devoluciones con la tasa de tecnología: 339.99 × 11% × 50% = **$18.70**, marca `ESTIMADO (devolución)`
- **AND** una categoría de la tabla sin tasa propia ni asignada → Amazon cerrado, `TASA DE DEVOLUCIÓN DESCONOCIDA`
- **AND** `video_game_consoles` no tiene umbral de demanda en la configuración base (§5): Amazon **no** se cierra por eso; queda **por revisar** con `DEMANDA DESCONOCIDA` (§3.2.1; RN-004 §11; DEC-225)
