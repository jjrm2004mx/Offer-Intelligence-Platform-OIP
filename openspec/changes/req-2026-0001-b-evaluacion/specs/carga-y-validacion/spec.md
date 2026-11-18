# Spec Delta

## Purpose

Carga por archivo de las entradas de la parte B (observaciones guardadas y capturas de Jesús) con validación por tipo de registro y reporte de carga, y validación de cada observación antes de evaluarla (REQ-2026-0001 §3.2 paso 1, §3.2.6 y §6).

## ADDED Requirements

### Requirement: Validación de cada observación
El sistema SHALL validar cada observación antes de evaluarla, también la publicación de un particular: precio > 0; dominio autorizado del comercio o, en particulares, enlace `https` de una plataforma de la lista permitida; campos obligatorios del contrato 3.1 y, en la publicación de un particular, también `pickupLocation`, `brand` y `model`. Si falla, el resultado MUST ser `RECHAZADA_VALIDACION` con su motivo, y la evaluación termina (RN-013 v1, RN-014 v1; REQ §3.2 paso 1, §6; DEC-212, DEC-227).

#### Scenario: B20 (a) — Precio $0.00
- **GIVEN** una observación con precio $0.00
- **WHEN** se evalúa la oferta
- **THEN** el resultado es **`RECHAZADA_VALIDACION`**, motivo `PRECIO INVÁLIDO`

#### Scenario: B20 (b) — URL de otro dominio para Home Depot
- **GIVEN** una observación de Home Depot con URL de `ejemplo.com`
- **WHEN** se evalúa la oferta
- **THEN** el resultado es **`RECHAZADA_VALIDACION`**, motivo `DOMINIO NO AUTORIZADO`

#### Scenario: B20 (c) — Sin category
- **GIVEN** una observación sin `category`
- **WHEN** se evalúa la oferta
- **THEN** el resultado es **`RECHAZADA_VALIDACION`**, motivo `CAMPO OBLIGATORIO FALTANTE (category)`

#### Scenario: B20 (d) — Particular con enlace http
- **GIVEN** la publicación de particular de B18 con enlace `http://` de OfferUp
- **WHEN** se evalúa la oferta
- **THEN** el resultado es **`RECHAZADA_VALIDACION`**, motivo `DOMINIO NO AUTORIZADO` (DEC-212)

#### Scenario: B20 (e) — Particular de una plataforma fuera de la lista
- **GIVEN** la publicación de particular de B18 con enlace `https://` de una plataforma que no está en la lista permitida
- **WHEN** se evalúa la oferta
- **THEN** el resultado es **`RECHAZADA_VALIDACION`**, motivo `DOMINIO NO AUTORIZADO` (DEC-212)

#### Scenario: B20 (f) — Particular sin pickupLocation
- **GIVEN** la publicación de B18 **sin** `pickupLocation`
- **WHEN** se evalúa la oferta
- **THEN** el resultado es **`RECHAZADA_VALIDACION`**, motivo `CAMPO OBLIGATORIO FALTANTE (pickupLocation)` (DEC-227)

#### Scenario: B20 (g) — Particular con ciudad fuera de la lista
- **GIVEN** la publicación de B18 con un código de ciudad que **no está** en la lista de §6
- **WHEN** se evalúa la oferta
- **THEN** el resultado es **`RECHAZADA_VALIDACION`**, motivo `CIUDAD NO CONFIGURADA` (DEC-227)

#### Scenario: B20 (h) — Particular sin model
- **GIVEN** la publicación de B18 **sin** `model`
- **WHEN** se evalúa la oferta
- **THEN** el resultado es **`RECHAZADA_VALIDACION`**, motivo `CAMPO OBLIGATORIO FALTANTE (model)` (DEC-227)

### Requirement: Carga de un archivo JSON Lines con registros de varios tipos
El sistema SHALL cargar un archivo JSON Lines que mezcle registros de cualquier tipo, validando cada uno según su `recordType`: una observación con el contrato 3.1 y el paso 1, y las demás capturas con los obligatorios de su tipo (§6). Un registro inválido MUST rechazarse con su motivo sin detener la carga, y al terminar MUST quedar un reporte de carga con los cargados y los rechazados por motivo (RN-014 v1, RN-016 v1, RN-017 v1; REQ §3.2.6, §6; S-23; DEC-200, DEC-205, DEC-223).

#### Scenario: B34 (a) — Archivo JSON Lines con 4 registros
- **GIVEN** que los comparables de B18 ya están cargados
- **WHEN** Jesús carga un archivo JSON Lines con 4 registros: (1) la publicación de B18 como observación (`recordType: observation`, `seller: particular`, `availability.state: listed`, `pickupLocation: san_diego`, enlace `https` de OfferUp); (2) un `local_comparable` en `MXN` **sin tipo de cambio**; (3) un `local_demand` de `beauty`, media; (4) un registro con `recordType: coupon`
- **THEN** se cargan (1) y (3)
- **AND** (2) se rechaza con `CAMPO OBLIGATORIO FALTANTE (tipo de cambio)` y (4) con `TIPO DE REGISTRO DESCONOCIDO`; los rechazos no detienen la carga (el nombre del campo en el motivo lo fija el `design.md`)
- **AND** la observación (1) dispara su evaluación, con el resultado de B18 (`REVISION_MANUAL`, motivo principal `PARTICULAR`)
- **AND** el reporte de carga dice 2 cargados y 2 rechazados, uno por cada motivo

### Requirement: Carga de un archivo CSV de un solo tipo
El sistema SHALL cargar un archivo CSV por tipo de registro, tomando el tipo del encabezado o del nombre del archivo, según lo fije el `design.md`, y validando cada renglón con los obligatorios de ese tipo (§6). Un renglón inválido MUST rechazarse con su motivo sin detener la carga y quedar en el reporte de carga (RN-014 v1, RN-016 v1; REQ §3.2.6, §6; DEC-223, DEC-227).

#### Scenario: B34 (b) — CSV de local_comparable con un renglón sin estado
- **GIVEN** que los comparables de B18 ya están cargados
- **WHEN** Jesús carga un archivo CSV de `local_comparable` con 4 renglones de otro producto, en USD: 3 completos y un cuarto **sin estado**
- **THEN** se cargan 3 y se rechaza 1 con `CAMPO OBLIGATORIO FALTANTE (estado)`
- **AND** el reporte de carga dice 3 cargados y 1 rechazado

### Requirement: recordType obligatorio en cada renglón JSON Lines
En JSON Lines, el sistema SHALL leer `recordType` de cada renglón, fuera del contrato 3.1, y quitarlo antes de validar la observación. Un renglón **sin** `recordType` MUST rechazarse con `TIPO DE REGISTRO DESCONOCIDO`. Las observaciones guardadas del VPS se exportan con `recordType: observation` (RN-013 v1; REQ §3.2.6 punto 1; DEC-227).

#### Scenario: B34 (c) — Observaciones guardadas del VPS con un renglón sin recordType
- **GIVEN** un archivo JSON Lines de observaciones guardadas del VPS con 2 renglones: uno con `recordType: observation` y otro **sin** `recordType` (DEC-227)
- **WHEN** Jesús carga el archivo
- **THEN** se carga 1 y se rechaza 1 con `TIPO DE REGISTRO DESCONOCIDO`
- **AND** el reporte de carga dice 1 cargado y 1 rechazado
