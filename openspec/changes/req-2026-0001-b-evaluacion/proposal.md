# Proposal

- **Issue:** #2
- **Requerimiento:** REQ-2026-0001 v2.9 (inspección v11, `APROBADO` → `CONTINUAR`, #3)
- **Parte:** B — Evaluación de oportunidades
- **Título:** Detectar, evaluar y avisar oportunidades de reventa y buscar artículos para clientes — parte B

## Why

Sin la evaluación (parte B), las ofertas no tienen juicio (REQ §1). La parte B decide si una observación de un origen de compra es una oportunidad real de reventa y en qué canal conviene venderla: carga sus entradas (archivo, capturas de Jesús y configuración versionada, §3.2.6), calcula referencias, descuento, calidad del precio, margen y nivel **por canal**, elige el canal y da el resultado. Es la **primera** parte que se construye (DEC-082) porque no consulta comercios.

## What Changes

- **Entradas de la parte B** (§3.2.6; DEC-200, DEC-205, DEC-223, DEC-227): un solo cargador por archivo (JSON Lines para observaciones guardadas; JSON Lines o CSV para las capturas de Jesús), validación por `recordType`, rechazo por registro sin detener la carga y reporte de carga; modelo de datos de las dos familias de capturas (§6); carga de la configuración versionada (§6).
- **Validación** de cada observación, también la publicación de un particular (§3.2 paso 1): `RECHAZADA_VALIDACION` con su motivo.
- **Referencias de precio** (RN-002): precio habitual con una observación por publicación y día, episodio de liquidación con valor congelado, precio de mercado hoy con comercio = cadena, mínimo de 60 días, precio de venta esperado en Amazon; descuento real y franjas (RN-003); calidad del precio (RN-012); valor de referencia de usados (RN-014). MSRP solo se muestra (DEC-218).
- **Canales y margen**: costo de compra con impuesto por ubicación (DEC-220), estado de cada canal (cerrado, por revisar, disponible; §3.2.1), margen neto y ajustado, unidades, días, rendimiento y nivel por canal (RN-001, RN-004 a RN-009, RN-016, RN-017), elección del canal (RN-018) y nivel del aviso (el más alto entre los canales, S-33). Redondeo de la lista cerrada de §5, una sola vez por fórmula (DEC-207, DEC-222).
- **Resultado y reevaluación**: todos los motivos, motivo principal y resultado con la precedencia de §3.2.4; `nivel_calculado` (DEC-202, DEC-224); registro de evaluación (§7); reevaluación de oportunidades abiertas cuando cambia una referencia de precio, con "ya no recomendado" (§3.2.5; DEC-204, DEC-224).

### Alcance

Copiado del REQ §2, sin ampliarlo.

**Incluye**
- **Orígenes de compra** (DEC-151): tienda en línea (envío al PO Box o recoger en tienda), tienda física y **particulares por captura manual** (DEC-150).
- **Canales de venta** (DEC-151): **Amazon FBM** y **venta local** (OfferUp, Facebook Marketplace y venta personal, con precio estimado). Origen y canal son independientes (DEC-146).
- **B:** todo lo de §3.2: sus entradas (§3.2.6) y la evaluación de cada observación nueva de un origen de compra, con la reevaluación de §3.2.5.
- Parámetros configurables sin cambiar código (§6). Todos los valores numéricos son **iniciales** (DEC-155).

**No incluye**
- Las partes **A**, **C** y **D** del REQ: son otros cambios (DEC-081, DEC-082).
- **Keepa** y APIs de pago: diferidos (DEC-123, DEC-124). Las referencias salen del **historial propio** y de la comparación entre comercios.
- Cuenta de vendedor de Amazon y SP-API (DEC-013): comisiones, envíos y restricciones son **estimados** con tabla manual.
- Búsqueda automática en sitios de particulares (DEC-150) y Facebook Marketplace con datos observados (DEC-140).
- **Amazon como origen de compra** en la parte B: ahí Amazon solo es referencia de precio (EXT-009, DEC-203).
- **Capturas por Telegram:** en el Inc. 1 las capturas de Jesús entran por archivo; por Telegram, después de asegurar el bot (§10; EXT-006, DEC-200).
- Compra o publicación automáticas, CAPTCHA con terceros, sesiones con cuentas personales (DEC-012).
- Logística y costos transfronterizos de la venta, incluida la franquicia aduanal (DEC-009, C-14).
- Productos con caducidad (RN-006 §4.3).

### Reglas de negocio que aplican

Versiones congeladas hasta el merge de la parte B (DEC-209). Ninguna `REEMPLAZADA`.

| RN | Versión | Uso en la parte B (REQ §4) |
|---|---|---|
| RN-001 Margen neto, por canal | v2 | Costo de compra, costo de venta y margen neto por canal |
| RN-002 Referencias de precio y precio de venta en Amazon | v2 | Precio habitual, de mercado hoy, MSRP, venta en Amazon, competencia más barata |
| RN-003 Descuento real y descuentos falsos | v2 | Descuento, franjas y marcas |
| RN-004 Demanda en Amazon | v2 | Demanda y advertencia |
| RN-005 Rentabilidad ajustada, por canal | v2 | Margen ajustado, unidades, días, rendimiento |
| RN-006 Comisiones, envío y restricciones en Amazon | v2 | Comisión, envío, restricción |
| RN-007 Confianza de la disponibilidad | v2 | Estados en línea y confianza en tienda |
| RN-008 Costo de traslado | v2 | Entrega local y recogida con particulares |
| RN-009 Niveles de oportunidad y avisos | v2 | Precedencia y niveles |
| RN-012 Calidad del precio | v1 | Eje 1 |
| RN-013 Identificación y datos de la observación | v1 | Coincidencia y datos de cada observación |
| RN-014 Condición y valor de usados | v1 | Estado, valor de usados, compra a particulares |
| RN-015 Riesgo de compra y de venta | v1 | Vendedor externo, particular, procedencia, evitar siempre |
| RN-016 Precio de venta local | v1 | Precio local estimado y techo |
| RN-017 Demanda local | v1 | Demanda local, días por unidad |
| RN-018 Selección del mejor canal | v1 | Elección del canal |

Cada requisito de las specs cita las RN del comportamiento que define. La lista completa de RN de cada criterio (todo el recorrido de la evaluación) está en su cabecera del REQ §5 y la recoge la matriz de cobertura de `oip-disenador`.

**Prevalencia** (REQ §4): donde una RN deja un punto abierto, manda el supuesto del REQ. Excepción declarada: **S-33** prevalece sobre RN-018 §4 y RN-009 §3 hasta el cambio en bloque.

### Supuestos del REQ que usa la parte B (§13)

S-01, S-02, S-03, S-05, S-06, S-07, S-08, S-09, S-10, S-11, S-12, S-13, S-14, S-16, S-18, S-21, S-22, S-23, S-24, S-25, S-27, S-28, S-30, S-31 y S-33. De ellos cambian la lógica (R-03): S-03, S-05, S-07, S-08, S-09, S-11, S-12, S-27, S-28, S-30, S-31 y S-33.

## Capabilities

Las cinco capacidades de la parte B las fija **DEC-228** (confirmado por DEC-229). En total, **54 escenarios**: los 34 criterios B1–B34 con sus variantes, uno por escenario.

### New Capabilities

- `carga-y-validacion`: carga por archivo (JSON Lines y CSV) con validación por `recordType`, reporte de carga y validación de cada observación con `RECHAZADA_VALIDACION` (B20 a–h, B34 a–c; 11 escenarios).
- `configuracion`: configuración versionada de la evaluación; impuesto por ubicación de la tienda y valores por código de `category` (B27, B31; 2 escenarios).
- `referencias-de-precio`: precio habitual y episodio de liquidación, precio de mercado hoy con comercio = cadena, precio de venta esperado en Amazon, descuento real y su franja, calidad del precio (B6, B7, B14, B30 base y b–e, B32; 9 escenarios).
- `canales-y-margen`: costo de compra, estado de cada canal, márgenes, RN-005, nivel por canal, elección del canal, nivel del aviso y redondeo (B1, B2 base, B4, B9 base, B10 a y b, B12, B13, B15, B16, B17, B21, B25, B26 a y b, B28 a y b, B33; 18 escenarios).
- `resultado-y-reevaluacion`: motivos, motivo principal, precedencia, resultado, `nivel_calculado`, registro de evaluación y reevaluación con "ya no recomendado" (B2 b, B3, B5, B8, B9 b, B11, B18, B19, B22, B23, B24 a–c, B29; 14 escenarios).

### Modified Capabilities

Ninguna: `openspec/specs/` está vacío.

## Impact

- Repo del Core sin código todavía: este cambio crea los primeros paquetes (los fija `design.md`).
- Entradas: archivos JSON Lines y CSV (§3.2.6) y la configuración versionada (§6). Contrato de ingesta 3.1 de la arquitectura v2.2 §8 (DEC-199, DEC-223, DEC-227).
- Salidas: registro de evaluación y reporte de carga (§7), que usa la parte C.
- No consulta comercios (DEC-082, DEC-173, DEC-194): los fixtures son sintéticos o de datos guardados en el VPS.

## Requisitos no funcionales

Los de la parte B (REQ §10 y §12). Los que no tienen escenario los resuelve `oip-disenador` en `design.md`.

| # | Requisito | Sección del REQ | Escenario |
|---|---|---|---|
| RNF-1 | Evaluación de una observación (parte B) en **≤ 2 segundos** | §12 | Sin escenario |
| RNF-2 | Todos los parámetros de §6 configurables **sin desplegar código nuevo**, con versión de la configuración. Cada evaluación guarda la versión que usó | §12; §3.2.6 punto 4; §7 | Sin escenario (B27 y B31 usan valores de la configuración, no prueban el cambio sin despliegue) |
| RNF-3 | **Reproducibilidad:** cada evaluación se recalcula desde su registro (observaciones + configuración + versión de RN) con el mismo resultado | §12 | Sin escenario |
| RNF-4 | Pruebas automatizadas para **todos** los escenarios B1–B34 (la parte B no tiene pruebas de host) | §12 | Todos los de la parte B |
| RNF-5 | Todo en **USD**; redondeo según DEC-060 y la lista cerrada de §5 (una sola vez por fórmula; porcentajes sin redondear; DEC-207) | §10; §5 | B33 (redondeo); B34 (a) (comparable en `MXN` sin tipo de cambio) |
| RNF-6 | **La IP de casa nunca consulta comercios** (DEC-041); el gate automático es estático: `scripts/check-egress.sh` comprueba que el Core no tiene clientes HTTP hacia comercios (DEC-173) | §10 | Sin escenario (gate estático) |
| RNF-7 | **Particulares:** solo la publicación (plataforma, enlace, ciudad, precio, estado), sin descripción libre, nombre ni teléfono; el enlace debe ser `https` y de una plataforma de la lista permitida (EXT-018, DEC-212) | §10; §6 | B20 (d) y (e) (enlace); la ausencia de datos personales, sin escenario |
| RNF-8 | Secretos como `podman secret`; nunca en el código, los logs ni los registros | §10 | Sin escenario |
| RNF-9 | Sin cuenta de vendedor: comisión, envío y restricciones de Amazon son **estimados** y así se marcan (`MARGEN ESTIMADO`, `EMPAQUE POR CONFIRMAR`, §3.2.3) | §10; §3.2.3 | Sin escenario propio (el REQ no repite esas marcas en los escenarios) |
| RNF-10 | Stack sin cambios: Python/FastAPI, PostgreSQL + TimescaleDB, Rocky Linux + Podman (DEC-020, DEC-021, DEC-025, DEC-118) | §10 | Sin escenario |

El REQ no fija volúmenes ni reintentos para la parte B (los reintentos de §12 son de los avisos, parte C).

## Dependencias y riesgos

**Dependencias** (REQ §9):
- RN de §4 en las versiones indicadas, **congeladas hasta el merge de la parte B** (DEC-209). El cambio en bloque posterior sube sus versiones y el REQ se reinspecciona.
- Sesión 3 con el experto: valida los supuestos de §13 y las propuestas DEC-159 a DEC-167. **No bloquea construir B.**
- Arquitectura **v2.2**: manda su contrato de ingesta 3.1 (§8), redondea como DEC-207 (§2.1, DEC-222) y el aviso usa el nivel más alto entre los canales (§2.7, DEC-221).
- Tasas de impuesto: Jesús confirma la de Chula Vista y National City (8.75%) en la CDTFA antes de cargarlas (DEC-220).
- Dirección del PO Box y empaques: pendientes del experto (RN-001 · P3, P4, P6); mientras, valores provisionales.

**Riesgos de la inspección v11 (#3) que tocan la parte B:**
- **R-01:** el mínimo "10% del costo de compra" de RN-009 nunca decide (RN-009 D-007 abierto); solo decide el $10.
- **R-02:** S-28 resuelve RN-012 D-009 en el REQ; el texto de RN-012 dice otra cosa hasta el cambio en bloque.
- **R-03:** 12 de los supuestos que usa B cambian la lógica; diseñarlos como estrategias configurables (§13).
- **R-04:** RN congeladas hasta el merge de B; reinspección obligatoria después.
- **R-05:** la arquitectura v2.2 no recoge DEC-197, DEC-198, DEC-201, DEC-204, DEC-206, DEC-226 ni DEC-227 (b). El `design.md` debe citar DEC-226 y DEC-227 y validar la publicación de un particular con el REQ §3.2 paso 1, no solo con el contrato.
- **R-06:** empaque y PO Box provisionales (`EMPAQUE POR CONFIRMAR`).
- **R-08:** el REQ es grande; se analiza y construye por parte (DEC-081).
- **R-09:** S-31 se aparta de RN-016 §11 y, con B24 (b), de RN-014 §4; va al cambio en bloque.
- **R-11:** valores provisionales: límite de 30 días del episodio (DEC-201) y 8.75% de Chula Vista y National City (DEC-220); si cambian, cambian B30 (b) y B31.

## Preguntas

1. **Ubicación de los escenarios en las capacidades.** DEC-228 fija las cinco capacidades, pero no qué escenario va en cada una. Los asigné por lo que verifica cada escenario (su título y su resultado esperado). Los casos dudosos, para que Jesús los confirme en G3:
   - **B27** (tasa asignada y "—" por columna) y **B31** (impuesto por ubicación) en `configuracion`, porque prueban cómo se leen las tablas de categorías e impuestos; podrían ir en `canales-y-margen`.
   - **B33** (redondeo una sola vez por fórmula) en `canales-y-margen`, porque prueba el precio de venta local; el redondeo es transversal (DEC-207, DEC-222).
   - **B28** (sin precio de venta en Amazon) en `canales-y-margen` y no en `referencias-de-precio`, porque lo que verifica es el cierre del canal y la venta local.
   - **B3, B11, B18 y B24** en `resultado-y-reevaluacion`, porque su conclusión es el motivo principal y el resultado, aunque recorren referencias y canales.
2. **B27 no da el resultado de la evaluación ni la categoría de su segundo caso.** Dice "Una categoría de la tabla sin tasa propia ni asignada → Amazon cerrado, `TASA DE DEVOLUCIÓN DESCONOCIDA`" sin nombrar la categoría (en la tabla de §5 no tienen tasa `watches`, `jewelry` y `toys`), y no dice el resultado final. La spec copia B27 tal cual; la categoría del dato de prueba la elige quien escriba la prueba, de la tabla de §5. ¿Basta así, o el REQ debe fijarla?
3. **RNF sin escenario** (RNF-1, RNF-2, RNF-3, RNF-6, RNF-8 a RNF-10): quedan en esta propuesta, sin escenarios inventados, para que `oip-disenador` los resuelva en `design.md`.
