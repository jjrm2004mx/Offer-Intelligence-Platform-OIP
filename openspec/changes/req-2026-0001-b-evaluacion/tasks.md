# Tasks

Tareas de la parte B del REQ-2026-0001 v2.9 (`req-2026-0001-b-evaluacion`). **1 tarea = 1 PR**, de 4 a 8 h (DEC-228). Cada tarea dice qué construye de `design.md` con sus identificadores (`CMP`, `TAB`, `CTR`, `PAR`, `RNF`). Las tareas de escenarios cubren escenarios completos de una sola capacidad; las de cimientos (T01 a T06) y la de operación (T23) no tienen escenarios y sus comportamientos salen de la estrategia de pruebas de `design.md` §12.

## Hitos y ruta crítica

| Hito | Resultado comprobable | Tareas |
|---|---|---|
| H1 Cimientos listos | El paquete instala, el dinero redondea solo la lista cerrada, la configuración de §5 carga con versión, el contrato y las capturas validan su forma, el motor devuelve un registro, las migraciones suben y bajan y el repositorio guarda y lee en memoria y en PostgreSQL | T01, T02, T03, T04, T05, T06 |
| H2 Entradas | Una observación inválida da `RECHAZADA_VALIDACION` con su motivo; un archivo JSON Lines o CSV carga, rechaza por registro y deja su reporte | T07, T08a, T08b |
| H3 Referencias de precio | Precio habitual con episodio de liquidación, descuento real, franja y calidad del precio, como B30, B6 y B7 | T09, T10 |
| H4 La parte evalúa una oferta de punta a punta | B1 completo: confianza, referencias, costo de compra, los dos canales, elección, nivel del aviso y resultado | T11 |
| H5 Canales, referencias y configuración completos | Todos los escenarios de `canales-y-margen`, B14, B32, B27 y B31 | T24, T25, T12, T13, T14, T15, T16, T17 |
| H6 Resultado completo | Descartadas, revisión manual, evitar, particular y usados | T18, T19, T20 |
| H7 Carga que evalúa, guarda, reevalúa y reproduce | B34 (a) de punta a punta, registro en PostgreSQL recalculable, ≤ 2 s, y reevaluación con "ya no recomendado" | T21, T22 |
| H8 Desplegado en Rocky | Migraciones probadas en Rocky (PoC de DEC-179) y carga de un archivo con Podman, con evidencia en el PR | T23 |

**Ruta crítica:** T01 → T02 → T04 → T09 → T10 → T11 → T20 → T21 → T22 → T23 (72 h). En paralelo: T03 (después de T01), T05 → T06 y T07 → T08a → T08b (después de T04), T24 y T25 (después de T11) y T12 a T19 (después de T11; T12 a T16 y T18 esperan además a T24, y T13, T16 y T18 a T25). Total: 26 tareas, 168 h. T08 se partió en T08a y T08b, y se agregaron T24 y T25, por las observaciones del issue #34 (DEC-273).

**Definition of Done común** (todas las tareas): comportamientos esperados con prueba en verde (los escenarios con `@pytest.mark.scenario("<ID de la matriz>")`); `ruff check .` y `ruff format --check .` limpios; `bash scripts/check-egress.sh src` en verde; sin secretos ni datos personales en código, logs, pruebas o commits; sin `float` en montos; gates de GitHub Actions en verde; commits con `Refs: #2` y `Change: req-2026-0001-b-evaluacion`; PR revisado y fusionado por Jesús (G4).

## 1. T01 — Estructura del paquete, catálogos cerrados y dinero (cimientos)

- **Objetivo:** dejar el paquete con su estructura, sus dependencias, los catálogos cerrados y el único módulo que redondea dinero.
- **Capacidad:** cimientos. **Escenarios:** ninguno propio; lo ejercitan B33 (redondeo) y todos los escenarios con montos.
- **Alcance:** subpaquetes `entradas/`, `evaluacion/`, `persistencia/`; dependencias de `design.md` §5 en `pyproject.toml`; marcador `integracion`; `dinero.py`; `catalogos.py`.
- **Fuera de alcance:** configuración, contrato, persistencia y cualquier fórmula de negocio.
- **Construye (design.md):** CMP-01, CMP-02, CMP-03, RNF-5, RNF-6, RNF-10
- **Comportamientos esperados** (design.md §8, §9, §12): `redondear` aplica `ROUND_HALF_UP` a centavos para cada `TipoMonto` (2.2475 → 2.25, 5.215 → 5.22, 2.5375 → 2.54, 76.614750 → 76.61, −9.125 → −9.13); un `float` levanta `TypeError`; `formatear_porcentaje` da 1 decimal sin alterar el valor usado para comparar; los enums tienen los valores y el orden de §9 (el orden de motivos es el de REQ §3.2.3).
- **Guía de implementación:** ningún otro módulo usa `quantize`; los catálogos guardan el código exacto del REQ (con espacios y acentos) y su "lleva a"; las dependencias nuevas se justifican en el PR y pasan `pip-audit`; ninguna es cliente HTTP.
- **Depende de:** —. **Estimación:** 6 h.
- **DoD:** común; `pip install -e ".[dev]"` funciona en Windows (`py -3`) y Linux.

- [x] 1.1 Crear la estructura de subpaquetes, agregar las dependencias y el marcador `integracion`, y verificar que `pytest` y `ruff` corren limpios
- [x] 1.2 Implementar `dinero.py` con la lista cerrada de `TipoMonto` y verificar las pruebas unitarias de redondeo, negativos, `float` y porcentajes
- [x] 1.3 Implementar `catalogos.py` (§9) y verificar con pruebas unitarias los valores y el orden de motivos, niveles y calidad

## 2. T02 — Configuración versionada (cimientos)

- **Objetivo:** cargar la configuración desde YAML con esquema estricto, huella y versión, sin valores por defecto en el código.
- **Capacidad:** cimientos. **Escenarios:** ninguno propio; la ejercitan todos, y B27 y B31 la prueban en T17.
- **Alcance:** esquema de las secciones PAR-01 a PAR-13; `configuracion.py`; `tests/fixtures/config/base.yaml` (REQ §5, con "—" como clave ausente); `config/oip-config.yaml` inicial de producción con la fuente de cada valor en comentarios (Pendiente 7).
- **Fuera de alcance:** guardar la versión en la base (T06) y la CLI (T08b); secciones de las partes A, C y D.
- **Construye (design.md):** CMP-04, PAR-01, PAR-02, PAR-03, PAR-04, PAR-05, PAR-06, PAR-07, PAR-08, PAR-09, PAR-10, PAR-11, PAR-12, PAR-13, RNF-2, RNF-6
- **Comportamientos esperados** (design.md §7, §12): un archivo válido da un objeto inmutable con `version`, `schemaVersion` y `sha256` estable; un parámetro faltante, un tipo inválido o una sección desconocida rechazan el archivo entero con el nombre del parámetro; los montos y porcentajes quedan como `Decimal`; los dos archivos del repo cargan.
- **Guía de implementación:** pydantic en modo estricto, `extra="forbid"`; comisiones con los tres tipos (`flat`, `total_threshold`, `tiers`) y el mínimo por unidad; la tasa de devolución asignada referencia otra categoría (S-27); el umbral de demanda se deriva del tamaño de la categoría (DEC-225); dominios de comercios solo en `config/` y en `tests/fixtures/` (gate de egress).
- **Depende de:** T01. **Estimación:** 7 h.
- **DoD:** común; Jesús revisa los valores de `config/oip-config.yaml` en el PR.

- [x] 2.1 Definir el esquema de PAR-01 a PAR-13 y la carga con huella y verificar las pruebas unitarias de archivo válido, faltante, tipo inválido y sección desconocida
- [x] 2.2 Escribir `tests/fixtures/config/base.yaml` y `config/oip-config.yaml` y verificar que los dos cargan y que `check-egress.sh src` sigue en verde

## 3. T03 — Contrato de ingesta 3.1 y esquemas de capturas (cimientos)

- **Objetivo:** modelar la observación del contrato 3.1 y las 7 capturas con los nombres y tipos de `design.md` CTR-04.
- **Capacidad:** cimientos. **Escenarios:** ninguno propio; los ejercitan B20 (T07) y B34 (T08b, T21).
- **Alcance:** `entradas/contrato.py` (contrato 3.1 citado de la arquitectura §8, `schemaVersion` 3.1 / 3.0 / ausente, reglas del particular de DEC-227 b, `title` armado con `brand` + `model`, GTIN con dígito verificador) y `entradas/capturas.py` (7 esquemas, conversión MXN → USD sin redondear).
- **Fuera de alcance:** validación contra la configuración (dominios, ciudades: T07) y lectura de archivos (T08b).
- **Construye (design.md):** CMP-05, CMP-06, CTR-01, CTR-04, RNF-7, RNF-11
- **Comportamientos esperados** (design.md §6, §12): cada obligatorio faltante produce `CAMPO OBLIGATORIO FALTANTE (<campo>)` con el nombre del campo del archivo y en el orden de §6; campos desconocidos se descartan; `client_request` no tiene campo de notas; un GTIN con dígito verificador inválido no confirma la coincidencia; `price.current` con más de 2 decimales o ≤ 0 se marca para `PRECIO INVÁLIDO`.
- **Guía de implementación:** el contrato no se redefine: los nombres y obligatorios son los de la arquitectura §8; `recordType` no es parte del modelo (lo quita el cargador); el alias del cliente nunca se escribe en logs ni en mensajes de error.
- **Depende de:** T01. **Estimación:** 6 h.
- **DoD:** común.

- [x] 3.1 Implementar el modelo del contrato 3.1 con las reglas del particular y verificar las pruebas unitarias de obligatorios, `schemaVersion`, `title` y GTIN
- [x] 3.2 Implementar los 7 esquemas de capturas y verificar las pruebas unitarias de obligatorios, conversión de MXN y campos desconocidos descartados

## 4. T04 — Contexto, registro de evaluación y esqueleto del motor (cimientos)

- **Objetivo:** fijar los tipos de dominio que usa todo el motor, su serialización reproducible y la precedencia de §3.2.4.
- **Capacidad:** cimientos. **Escenarios:** ninguno propio; la precedencia la verifican B3 y B29 (T18) y todos los escenarios con resultado.
- **Alcance:** `evaluacion/contexto.py` (`ContextoEvaluacion`, `RegistroEvaluacion` con todos los campos de REQ §7 y de TAB-10/TAB-11, serialización CTR-06); `evaluacion/resultado.py` (reunir motivos y precedencia); `evaluacion/motor.py` con los pasos de §3 de `design.md` como funciones vacías que las tareas siguientes llenan.
- **Fuera de alcance:** las reglas de cada paso.
- **Construye (design.md):** CMP-09, CMP-16, CMP-17, CTR-06, RNF-3
- **Comportamientos esperados** (design.md §3, §9, §12): ida y vuelta de la serialización da un contexto igual y una salida byte a byte igual; la precedencia da DESCARTADA con cualquier motivo de descarte, luego SOLO_REFERENCIA, luego REVISION_MANUAL, luego NIVEL_ASIGNADO o SIN_NIVEL; el motivo principal es el primero en el orden de §3.2.3 y se guardan todos.
- **Guía de implementación:** `evaluacion/` no importa `persistencia/` ni usa el reloj; el `instante` es parte del contexto; la versión de configuración y las versiones de RN viajan en el contexto.
- **Depende de:** T02, T03. **Estimación:** 7 h.
- **DoD:** común.

- [x] 4.1 Implementar `ContextoEvaluacion` y `RegistroEvaluacion` con su serialización canónica y verificar la prueba de ida y vuelta
- [x] 4.2 Implementar la precedencia de §3.2.4 y el esqueleto del motor y verificar las pruebas unitarias de la tabla de precedencia

## 5. T05 — Modelo de datos y migraciones (cimientos)

- **Objetivo:** crear el esquema de PostgreSQL + TimescaleDB con migraciones versionadas.
- **Capacidad:** cimientos. **Escenarios:** ninguno propio; el registro lo ejercitan B34 (a) y B2 (b) / B9 (b) en T21 y T22.
- **Alcance:** `persistencia/tablas.py` (SQLAlchemy Core) y `migrations/` (Alembic): `0001_esquema` (TAB-01 a TAB-12) y `0002_hypertables` (TAB-05 a TAB-07).
- **Fuera de alcance:** repositorios (T06); compresión, agregados y retención (Pendiente 8); PoC en Rocky (T23).
- **Construye (design.md):** CMP-19, TAB-01, TAB-02, TAB-03, TAB-04, TAB-05, TAB-06, TAB-07, TAB-08, TAB-09, TAB-10, TAB-11, TAB-12, RNF-10
- **Comportamientos esperados** (design.md §4, §12): `alembic upgrade head` y `downgrade base` funcionan contra un contenedor TimescaleDB; las hypertables existen; los `CHECK` rechazan códigos fuera del catálogo; las claves únicas de idempotencia existen. Pruebas `@pytest.mark.integracion`, que se saltan sin `OIP_TEST_DATABASE_URL`.
- **Guía de implementación:** claves primarias con la columna de tiempo; montos `numeric(12,2)`, medianas y conversiones `numeric(14,4)`; ninguna tabla guarda el contenido de un renglón rechazado; la URL de pruebas sale del entorno, nunca del repo.
- **Depende de:** T04. **Estimación:** 7 h.
- **DoD:** común; evidencia en el PR de las pruebas de integración corridas en local.

- [x] 5.1 Definir las tablas de §4 en SQLAlchemy Core y la migración `0001_esquema` y verificar `upgrade` / `downgrade` en una prueba de integración
  - Evidencia de integración (T05): Jesús la corrió el 2026-11-19 en Rocky Linux 10.2 contra `docker.io/timescale/timescaledb:latest-pg16` (digest `sha256:62a5323a3c2e35f16b8e0a9fb8f15ac4bb7d95d57f5a95ab7767d4fcb51b9e8d`): 84 passed y 1 skipped (la esperada, `test_sin_timescaledb_la_0002_falla_y_no_deja_nada_a_medias`), 0 fallidas.
- [x] 5.2 Escribir `0002_hypertables` y verificar en integración que TAB-05 a TAB-07 son hypertables
  - Evidencia de integración (T05): Jesús la corrió el 2026-11-19 en Rocky Linux 10.2 contra `docker.io/timescale/timescaledb:latest-pg16` (digest `sha256:62a5323a3c2e35f16b8e0a9fb8f15ac4bb7d95d57f5a95ab7767d4fcb51b9e8d`): 84 passed y 1 skipped (la esperada, `test_sin_timescaledb_la_0002_falla_y_no_deja_nada_a_medias`), 0 fallidas.

## 6. T06 — Repositorios en memoria y PostgreSQL (cimientos)

- **Objetivo:** dar al cargador y al ensamblador una interfaz de datos con dos implementaciones equivalentes.
- **Capacidad:** cimientos. **Escenarios:** ninguno propio; lo ejercitan B34 (T08b, T21) y la reevaluación (T22).
- **Alcance:** `persistencia/repositorios.py`: Protocol `Repositorio`, `RepositorioMemoria`, `RepositorioPostgres`; guardar y leer observaciones (con TAB-08), capturas, versiones de configuración, cargas y evaluaciones; lecturas "a un instante" de §5 de `design.md`; conexión con la contraseña del `podman secret`.
- **Fuera de alcance:** armar el contexto (T21).
- **Construye (design.md):** CMP-20, RNF-8
- **Comportamientos esperados** (design.md §5, §12): la misma batería de contrato pasa con memoria y con PostgreSQL (integración); un duplicado por clave de idempotencia no se guarda dos veces; ninguna lectura devuelve datos posteriores al instante; la URL de conexión no aparece en logs ni en excepciones.
- **Guía de implementación:** una transacción por registro y por evaluación; `Decimal` de ida y vuelta sin `float`; la contraseña se lee del archivo del secreto si existe.
- **Depende de:** T05. **Estimación:** 8 h.
- **DoD:** común; evidencia de la batería contra PostgreSQL en local.

- [x] 6.1 Implementar `Repositorio` y `RepositorioMemoria` y verificar la batería de contrato en CI
- [x] 6.2 Implementar `RepositorioPostgres` con la conexión por secreto y verificar la misma batería en integración
  - Implementado en el PR de T06 (con la migración `0003_registro_de_rechazo`, DEC-250).
  - Evidencia de integración (T06): Jesús la corrió el 2026-11-21 en Rocky Linux 10.2 contra `docker.io/timescale/timescaledb:latest-pg16` (digest `sha256:2f190aac33a7ee3913e104082e7ec953d3183b3e228331a11de359b00e413843`) sobre 0bb6da4: integración 159 passed y 1 skipped (la esperada, `test_sin_timescaledb_la_0002_falla_y_no_deja_nada_a_medias`), 0 fallidas; suite completa 3890 passed, 1 skipped.

## 7. T07 — Validación de cada observación (B20)

- **Objetivo:** paso 1 de REQ §3.2 con `RECHAZADA_VALIDACION` y su motivo.
- **Capacidad:** `carga-y-validacion`. **Escenarios:** B20 (a), B20 (b), B20 (c), B20 (d), B20 (e), B20 (f), B20 (g), B20 (h).
- **Alcance:** `entradas/validacion.py` (precio, dominio autorizado, enlace `https` de plataforma permitida, obligatorios del contrato y del particular, ciudad); el paso 1 del motor y el registro de rechazo.
- **Fuera de alcance:** lectura de archivos (T08b).
- **Construye (design.md):** CMP-07, CMP-17, RNF-7, RNF-4
- **Comportamientos esperados:** los 8 escenarios de B20; además, el orden de comprobaciones de `design.md` §6 cuando fallan dos a la vez (prueba unitaria); la publicación de un particular con `availability.state` distinto de `listed` se rechaza (REQ §6 punto 1; DEC-242).
- **Guía de implementación:** validación sintáctica de la URL (host igual o subdominio de un dominio autorizado; prefijo de ruta de la plataforma si lo configura PAR-09); nunca se abre una URL; el rechazo no guarda la observación en el historial; T07 valida `availability.state = listed` en la publicación de un particular (REQ §6 punto 1; DEC-242), que T03 no comprueba.
- **Depende de:** T02, T03, T04. **Estimación:** 6 h.
- **DoD:** común.

- [x] 7.1 Implementar la validación del paso 1 y verificar los 8 escenarios de B20 marcados con `@pytest.mark.scenario`

## 8. T08a — Validación y persistencia previas al cargador (cimientos)

- **Objetivo:** dejar listos los esquemas de entrada, la migración y el repositorio que usa el cargador, con las decisiones del issue #34 de validación y persistencia (DEC-273).
- **Capacidad:** `carga-y-validacion`. **Escenarios:** ninguno propio; los ejercitan B20 (T07) y B34 (T08b, T21).
- **Alcance:**
  - Montos con más de 2 decimales rechazados al leer en `entradas/contrato.py` y rangos de las capturas en `entradas/capturas.py`, con sus motivos (DEC-257; decisiones 2 y 2b).
  - Migración `0004`: `local_comparable.price_usd` a `numeric` sin escala, y se quita la excepción `_DERIVADAS` de T06 (DEC-258; decisión 3).
  - Repositorio, en memoria y en PostgreSQL: `buscar_publicacion` rechaza con `ValueError` una tienda vacía o solo espacios, y sin tienda se pasa `None` (decisión 16). Las lecturas por id (`version_configuracion`, `leer_producto`, `leer_observacion`, `leer_carga`, `leer_evaluacion`, `terminar_carga`, `observacion_por_clave`) verifican el tipo exacto (`int` sin `bool`, `UUID`, `str`) y dan `TypeError` (decisión 17).
  - `conexion.py`: `url_de_conexion` rechaza con `ErrorDeConexion`, sin la URL en el mensaje, las claves `password` y `passfile` en la query, sin distinguir mayúsculas (decisión 18).
  - `_checks.py` y `_columnas.py`: `NotImplementedError` al importar ante casts distintos de `::text[]`, identificadores que no son columnas de la tabla (y `TRUE`/`FALSE`) y `SmallInteger` (16 bits o `NotImplementedError`); en `_patron_are`, ante `[:`, `[.`, `[=`, `(?`, `***` y escapes alfabéticos, con los patrones validados al importar (decisión 19).
  - `entradas/contrato.py`: en la observación de un comercio, `pickupLocation` se descarta al leer; ni se valida ni se guarda (decisión 37).
- **Fuera de alcance:** el cargador, la clave de idempotencia y la URL canónica (T08b).
- **Construye (design.md):** CMP-05, CMP-06, CMP-19, CMP-20, CTR-01, CTR-04, TAB-09, RNF-5, RNF-4
- **Comportamientos esperados:** una prueba por regla: cada monto con más de 2 decimales y cada rango de CTR-04 con su motivo (`PRECIO INVÁLIDO` o `CAMPO OBLIGATORIO FALTANTE (<campo>)`); `0004` sube y baja en integración y `price_usd` guarda el mismo valor en memoria y en PostgreSQL; la batería de contrato con la tienda vacía y los tipos de id; `password` en la query rechazado; los `NotImplementedError` al importar; un comercio con una ciudad que no existe se acepta sin `pickup_location`.
- **Guía de implementación:** el rechazo del repositorio queda como última barrera de los decimales; los motivos solo llevan el código y el campo, nunca el valor (R-20).
- **Depende de:** T06, T07. **Estimación:** 6 h.
- **DoD:** común; evidencia de las pruebas de integración de `0004` (Jesús en Rocky o el job de CI de DEC-251).

- [x] 8.1 Implementar los decimales y rangos de entrada y el descarte de `pickupLocation` en un comercio, y verificar sus pruebas unitarias
- [ ] 8.2 Escribir `0004`, endurecer el repositorio, la conexión y los `CHECK` de memoria, y verificar la batería de contrato en memoria y en integración

## 8b. T08b — Cargador de archivos JSON Lines y CSV con reporte (B34 b y c)

- **Objetivo:** un solo cargador que valida por `recordType`, rechaza por registro sin detener la carga y deja el reporte.
- **Capacidad:** `carga-y-validacion`. **Escenarios:** B34 (b), B34 (c).
- **Alcance:**
  - `entradas/cargador.py` (CTR-02, CTR-03, CTR-05); guardar en el repositorio; `oip config cargar` y `oip cargar` en la CLI (sin evaluar todavía: la evaluación la conecta T21).
  - Clave de idempotencia de una observación sin `idempotencyKey`, con `extractedAt` en UTC truncado al minuto y `storeCode` ausente como texto vacío (DEC-255; decisión 1).
  - URL canónica, y prefijo de ruta de PAR-09 comparado sobre la ruta normalizada en `entradas/validacion.py`, con una prueba de `..` y `%2e%2e` (DEC-256; decisiones 1b y 1b-bis).
  - El cargador pone `captured_at` = instante de la carga (reloj o `--instante`), con una prueba de reproducción (DEC-271; decisión 31).
  - Una prueba de que todo rechazo de una carga lleva su carga y su renglón (decisión 33).
- **Fuera de alcance:** disparar evaluaciones (T21); el origen de un rechazo del Worker (parte A).
- **Construye (design.md):** CMP-08, CMP-22, CTR-02, CTR-03, CTR-05, CTR-07, RNF-5, RNF-4
- **Comportamientos esperados:** B34 (b) y B34 (c), con los motivos de `design.md` §6 (`CAMPO OBLIGATORIO FALTANTE (condition)` en B34 b); más las pruebas unitarias de §12 (archivo vacío, renglón que no es JSON, CSV sin tipo en el nombre, listas con `|`, duplicados contados en `duplicates`).
- **Guía de implementación:** JSON con `parse_float=Decimal`; `recordType` se quita antes de validar la observación; una transacción por registro; el reporte no guarda contenido; `citiesToRegister` con las ciudades de `CIUDAD NO CONFIGURADA`. Los esquemas de T03 tienen enteros y booleanos estrictos (DEC-238): el cargador convierte el texto de CSV (`"true"`/`"false"`, `"3"`) al tipo del campo antes de validar; un texto que no se convierte llega como está y el esquema lo rechaza. El cargador pasa a `leer_captura` la zona de `general.timezone` (DEC-240), siempre la zona ya validada de la configuración: una zona inválida es un error de configuración, no del registro (DEC-247).
- **Depende de:** T08a. **Estimación:** 7 h.
- **DoD:** común.

- [ ] 8b.1 Implementar la lectura de JSON Lines y CSV con el despacho por `recordType`, la clave de idempotencia y la URL canónica, y verificar las pruebas unitarias de formato, de la clave y de la URL
- [ ] 8b.2 Implementar el reporte de carga, `captured_at` y los comandos de la CLI, y verificar B34 (b) y B34 (c) con `RepositorioMemoria`

## 9. T09 — Precio habitual y episodio de liquidación (B30)

- **Objetivo:** el precio habitual con una observación por publicación y día y el episodio de liquidación de DEC-201, DEC-224 y DEC-226.
- **Capacidad:** `referencias-de-precio`. **Escenarios:** B30 (base), B30 (b), B30 (c), B30 (d), B30 (e).
- **Alcance:** en `evaluacion/referencias.py`: observación diaria, mediana sin el día evaluado (par = promedio, sin redondear), historial suficiente, baja, episodio (inicio, valor congelado, fin, límite); descuento real contra el valor que aplique (lo mínimo de `descuento.py` para la franja).
- **Fuera de alcance:** mercado hoy, Amazon y calidad (T10, T16).
- **Construye (design.md):** CMP-11, CMP-12, PAR-08, RNF-4
- **Comportamientos esperados:** los 5 escenarios de B30, leyendo `SOLO_REFERENCIA` y `MERCADO YA BARATO` como la franja (motivo) según `design.md` §12 (Pregunta 5); prueba unitaria de mediana par.
- **Guía de implementación:** el episodio se recalcula desde el historial de la publicación (design.md §10 punto 2); el registro guarda la referencia usada, su fuente (`historial_propio`) y, si hay episodio, su inicio y el valor congelado.
- **Depende de:** T04. **Estimación:** 8 h.
- **DoD:** común.

- [x] 9.1 Implementar la observación diaria, la mediana y el historial suficiente y verificar B30 (base) y la prueba de mediana par
- [x] 9.2 Implementar el episodio con su límite y su fin y verificar B30 (b) a B30 (e)

## 10. T10 — Descuento, franja, mercado hoy y calidad del precio (B6, B7)

- **Objetivo:** descuento anunciado y real con sus marcas, precio de mercado hoy y calidad del precio.
- **Capacidad:** `referencias-de-precio`. **Escenarios:** B6, B7.
- **Alcance:** `descuento.py` (CMP-12: franjas, `PRECIO ANTES INFLADO`, `DESCUENTO ANUNCIADO NO COMPROBADO`, calidad RN-012 con S-22 y S-28, y el uso del precio típico y del MSRP, este solo para mostrar) y, en `referencias.py` (CMP-11), el precio típico de la tienda, el MSRP y el precio de mercado hoy básico (48 h, disponible, sin la oferta evaluada). Corregido por la decisión 29 del issue #34: el precio típico y el MSRP están en `referencias.py`, como dice CMP-11.
- **Fuera de alcance:** comercio = cadena y su excepción (T16); Amazon sin oferta hoy (T16).
- **Construye (design.md):** CMP-11, CMP-12, PAR-10, RNF-4
- **Comportamientos esperados:** B6 y B7 (con el "Dado" completado como dice `design.md` §12).
- **Guía de implementación:** comparar porcentajes sin redondear; sin historial, la calidad no pasa de Precio competitivo; "comercios" para el mínimo de RN-012 = cadenas distintas de la evaluada.
- **Depende de:** T09. **Estimación:** 7 h.
- **DoD:** común.

- [x] 10.1 Implementar el descuento con sus marcas y el precio de mercado hoy y verificar B7
- [x] 10.2 Implementar la calidad del precio y verificar B6

## 11. T11 — Evaluación por canal de punta a punta (B1)

- **Objetivo:** la primera evaluación completa: confianza, costo de compra, canal Amazon, venta local, rentabilidad, nivel, elección y nivel del aviso.
- **Capacidad:** `canales-y-margen`. **Escenarios:** B1.
- **Alcance:** confianza RN-007 en `identificacion.py`; `canales.py` (costo de compra con impuesto, estado del canal, Amazon: ranking, demanda, comisión, envío, empaque; local: precio RN-016, demanda RN-017, entrega); `rentabilidad.py` (márgenes, devoluciones, castigo, nivel, `nivel_calculado`, tope, unidades, días, rendimiento); `eleccion.py` (RN-018 y S-33).
- **Fuera de alcance:** las variantes de los demás escenarios de canales (T12 a T15).
- **Construye (design.md):** CMP-10, CMP-13, CMP-14, CMP-15, PAR-06, PAR-07, PAR-11, PAR-12, PAR-13, RNF-9, RNF-4
- **Comportamientos esperados:** B1; prueba unitaria de que todo cálculo de Amazon lleva `MARGEN ESTIMADO` y `EMPAQUE POR CONFIRMAR` (RNF-9); concurrencia cerrado / por revisar (S-31).
- **Guía de implementación:** nivel antes que unidades (el tope depende del nivel); cada monto de la lista cerrada se redondea una vez con `dinero.redondear`; los montos combinados usan los ya redondeados (`design.md` §8).
- **Depende de:** T10. **Estimación:** 8 h.
- **DoD:** común.

- [x] 11.1 Implementar la confianza, el costo de compra y el canal Amazon y verificar las cuentas de Amazon de B1 en pruebas unitarias
- [x] 11.2 Implementar la venta local, la rentabilidad, la elección y el nivel del aviso y verificar B1 completo y RNF-9

## 12. T12 — Venta local con estimado y techo, castigo, peso y comisión (B2 base, B15, B16, B17)

- **Objetivo:** variantes sobre B2: estimado de Jesús con techo de comparables, castigo sin mínimo, peso desconocido y categoría sin comisión.
- **Capacidad:** `canales-y-margen`. **Escenarios:** B2 (base), B15, B16, B17.
- **Alcance:** techo con comparables locales; castigo del 10% sin mínimo de 60 días (S-05); envío y empaque sin peso con `ESTIMADO (peso)` (S-06); `COMISIÓN DESCONOCIDA`.
- **Fuera de alcance:** más de 6 kg (T14).
- **Construye (design.md):** CMP-13, CMP-14, PAR-06, PAR-12, RNF-4
- **Comportamientos esperados:** B2 (base), B15, B16, B17.
- **Guía de implementación:** los comparables cuentan solo del mismo producto y estado y de la zona de venta local (PAR-09).
- **Depende de:** T11, T24. **Estimación:** 6 h.
- **DoD:** común.

- [ ] 12.1 Implementar el techo local, el castigo sin mínimo, el envío sin peso y la comisión desconocida y verificar B2 (base), B15, B16 y B17

## 13. T13 — Restricción, competencia más barata, confianza baja y sin rotación (B4, B9 base, B21, B25)

- **Objetivo:** causas de cierre de Amazon, la baja de nivel por competencia y el nivel del aviso cuando gana otro canal.
- **Capacidad:** `canales-y-margen`. **Escenarios:** B4, B9 (base), B21, B25.
- **Alcance:** restricción por categoría, marca y producto (S-09), `MATERIAL PELIGROSO` (S-07), temporada de juguetes (S-10); `COMPETENCIA MÁS BARATA`; confianza Baja sin nivel con `nivel_calculado`; `SIN ROTACIÓN` (S-08).
- **Fuera de alcance:** el disparo de la reevaluación (T22). El último punto de B9 (base) se verifica como la evaluación de la oferta de B1 con Target a $99 y nivel del aviso Muy recomendable; "no se repite" es de la parte C (C5).
- **Construye (design.md):** CMP-13, CMP-14, CMP-15, PAR-05, PAR-13, RNF-4
- **Comportamientos esperados:** B4, B9 (base), B21, B25; prueba unitaria del empate de nivel del aviso (`design.md` §10 punto 6).
- **Guía de implementación:** la baja por competencia aplica solo en Amazon; `nivel_calculado` solo en canales disponibles o por revisar (DEC-224 a).
- **Depende de:** T11, T24, T25. **Estimación:** 6 h.
- **DoD:** común.

- [ ] 13.1 Implementar restricciones, competencia más barata, confianza baja y sin rotación y verificar B4, B9 (base), B21 y B25

## 14. T14 — Ranking, demanda, unidades y más de 6 kg (B10 a y b, B12, B13, B26 a y b)

- **Objetivo:** el ranking de DEC-206, la demanda desconocida con Amazon por revisar, las unidades sin ventas al mes, la demanda a la baja y el envío de más de 6 kg.
- **Capacidad:** `canales-y-margen`. **Escenarios:** B10 (a), B10 (b), B12, B13, B26 (a), B26 (b).
- **Alcance:** promedio de 1 a 7 días; canal por revisar con margen y `nivel_calculado` informativo (S-30); máximo 2 unidades con `ESTIMADO (unidades)`; `DEMANDA A LA BAJA`; cotización capturada y `ENVÍO POR COTIZAR`; desempate por rendimiento.
- **Fuera de alcance:** el motivo `DEMANDA DESCONOCIDA` sin otro canal con nivel (B11, T19).
- **Construye (design.md):** CMP-13, CMP-14, CMP-15, PAR-06, PAR-11, RNF-4
- **Comportamientos esperados:** B10 (a), B10 (b), B12, B13, B26 (a), B26 (b).
- **Guía de implementación:** el mismo ranking sirve para umbral, días y tope; ventana del ranking según `design.md` §10 punto 3.
- **Depende de:** T11, T24. **Estimación:** 7 h.
- **DoD:** común.

- [ ] 14.1 Implementar el ranking y la demanda desconocida y verificar B10 (a) y B10 (b)
- [ ] 14.2 Implementar unidades sin ventas, demanda a la baja y más de 6 kg y verificar B12, B13, B26 (a) y B26 (b)

## 15. T15 — Sin precio de venta en Amazon y redondeo una vez por fórmula (B28 a y b, B33)

- **Objetivo:** cerrar Amazon sin precio de venta (DEC-197) y probar el redondeo de DEC-207 y DEC-222 en la venta local.
- **Capacidad:** `canales-y-margen`. **Escenarios:** B28 (a), B28 (b), B33.
- **Alcance:** `SIN PRECIO DE VENTA EN AMAZON` con prevalencia sobre `DEMANDA DESCONOCIDA`; sin margen de Amazon; precio local redondeado una sola vez.
- **Fuera de alcance:** Amazon sin oferta hoy con precio habitual (T16).
- **Construye (design.md):** CMP-13, CMP-02, RNF-5, RNF-4
- **Comportamientos esperados:** B28 (a), B28 (b), B33.
- **Guía de implementación:** sin precio de venta no hay margen de Amazon, ni informativo; la venta local se calcula con la fórmula completa y un solo `redondear`.
- **Depende de:** T11, T24. **Estimación:** 5 h.
- **DoD:** común.

- [ ] 15.1 Implementar el cierre sin precio de venta en Amazon y verificar B28 (a), B28 (b) y B33

## 16. T16 — Amazon sin oferta hoy y comercio = cadena (B14, B32)

- **Objetivo:** el precio de venta esperado con el habitual de Amazon (S-02) y la regla de comercio = cadena con su excepción (DEC-216).
- **Capacidad:** `referencias-de-precio`. **Escenarios:** B14, B32.
- **Alcance:** en `referencias.py`: oferta nueva hoy (`design.md` §10 punto 3), `SIN OFERTA HOY`, precio habitual de Amazon; exclusión de la misma cadena y su excepción en liquidación en sucursal, para el mercado hoy y para el mínimo de 2 comercios de RN-012.
- **Fuera de alcance:** —.
- **Construye (design.md):** CMP-11, CMP-12, PAR-02, PAR-08, RNF-4
- **Comportamientos esperados:** B14, B32.
- **Guía de implementación:** la cadena sale de PAR-02; S-28 en la calidad de B14.
- **Depende de:** T11, T24, T25. **Estimación:** 5 h.
- **DoD:** común.

- [ ] 16.1 Implementar el precio de venta sin oferta hoy y la regla de cadena y verificar B14 y B32

## 17. T17 — Impuesto por ubicación y valores por categoría (B27, B31)

- **Objetivo:** probar la lectura de las tablas de impuestos y de categorías de la configuración en la evaluación.
- **Capacidad:** `configuracion`. **Escenarios:** B27, B31.
- **Alcance:** impuesto por `taxLocation` con respaldo de 7.75% (DEC-220); comisión con umbral y por tramos (DEC-217); tasa asignada con `ESTIMADO (devolución)` (S-27), `TASA DE DEVOLUCIÓN DESCONOCIDA`; sin umbral de demanda → por revisar (DEC-225).
- **Fuera de alcance:** —.
- **Construye (design.md):** CMP-13, PAR-04, PAR-07, RNF-4
- **Comportamientos esperados:** B27 (la categoría sin tasa la elige el fixture de la tabla de §5, pregunta 2 de `proposal.md`), B31; prueba unitaria de comisiones `total_threshold` y `tiers` con los ejemplos de REQ §5.
- **Guía de implementación:** la tasa de respaldo y las tasas por ubicación salen solo de PAR-07.
- **Depende de:** T11. **Estimación:** 5 h.
- **DoD:** común.

- [ ] 17.1 Completar impuestos y valores por categoría y verificar B27, B31 y las pruebas de comisiones

## 18. T18 — Descartadas: mercado ya barato, sin canal y margen negativo (B3, B22, B23, B29)

- **Objetivo:** los caminos a `DESCARTADA` con el margen ajustado calculado aunque no haya descuento real (DEC-198).
- **Capacidad:** `resultado-y-reevaluacion`. **Escenarios:** B3, B22, B23, B29.
- **Alcance:** motivos `MERCADO YA BARATO`, `SIN CANAL DISPONIBLE`, `MARGEN NEGATIVO`; demanda local baja cierra el canal local; todos los motivos guardados. Con `SIN CANAL DISPONIBLE`, las cuatro invariantes del registro por estado del canal (decisión 14 del issue #34; REQ §3.2.1, §3.2.2 y DEC-224 a): un canal cerrado sin `nivel` ni `nivel_calculado`; `NIVEL_ASIGNADO` con al menos un canal disponible con nivel; `SIN_NIVEL` con al menos un canal disponible.
- **Fuera de alcance:** usados y particulares (T20).
- **Construye (design.md):** CMP-16, CMP-14, RNF-4
- **Comportamientos esperados:** B3, B22, B23, B29.
- **Guía de implementación:** `MARGEN NEGATIVO` solo mira canales disponibles y exige que no haya canal por revisar; un canal por revisar no entra.
- **Depende de:** T11, T24, T25. **Estimación:** 6 h.
- **DoD:** común.

- [ ] 18.1 Implementar los motivos de descarte y verificar B3, B22, B23 y B29

## 19. T19 — Revisión manual y evitar siempre (B5, B8, B11, B19)

- **Objetivo:** motivos de revisión manual con `nivel_calculado` y el descarte por la lista "evitar siempre".
- **Capacidad:** `resultado-y-reevaluacion`. **Escenarios:** B5, B8, B11, B19.
- **Alcance:** en `identificacion.py`: coincidencia no confirmada (RN-013), vendedor externo o desconocido, riesgo de procedencia por categoría o marca (PAR-05, S-21), evitar siempre; `DEMANDA DESCONOCIDA` sin otro canal con nivel.
- **Fuera de alcance:** particular y usados (T20).
- **Construye (design.md):** CMP-10, CMP-16, PAR-05, RNF-4
- **Comportamientos esperados:** B5, B8, B11, B19.
- **Guía de implementación:** la coincidencia sale de la evidencia de la observación evaluada (`design.md` §10 punto 7); B8: vendedor externo sin confirmar da calidad Descuento cuestionable.
- **Depende de:** T11. **Estimación:** 6 h.
- **DoD:** común.

- [ ] 19.1 Implementar los motivos de revisión manual y evitar siempre y verificar B5, B8, B11 y B19

## 20. T20 — Compra a particular y usados (B18, B24 a, b y c)

- **Objetivo:** el particular con inspección y el usado con o sin valor de referencia (RN-014, S-31).
- **Capacidad:** `resultado-y-reevaluacion`. **Escenarios:** B18, B24 (a), B24 (b), B24 (c).
- **Alcance:** valor de referencia de usados (3 comparables, 85% de pedidos o mediana de ventas); recogida por ciudad (PAR-09) sin impuesto (S-14); Amazon cerrado por producto no nuevo (S-12); venta local por revisar sin valor de referencia y su prevalencia de cerrado; calidad "no aplica"; motivos `PARTICULAR`, `RIESGO DE PROCEDENCIA`, `SIN REFERENCIA DE USADOS`.
- **Fuera de alcance:** la carga del archivo de B34 (a) (T21).
- **Construye (design.md):** CMP-10, CMP-11, CMP-12, CMP-13, PAR-09, PAR-12, RNF-4
- **Comportamientos esperados:** B18, B24 (a), B24 (b), B24 (c).
- **Guía de implementación:** el usado usa el valor de referencia en lugar del precio habitual; con estimado de Jesús, margen informativo con el techo de los comparables que haya. En un usado, `references.precio_habitual` y su fuente quedan vacíos, con su prueba (DEC-263).
- **Depende de:** T11. **Estimación:** 8 h.
- **DoD:** común.

- [ ] 20.1 Implementar el valor de referencia de usados y el canal local por revisar y verificar B24 (a), B24 (b) y B24 (c)
- [ ] 20.2 Implementar la compra a particular con recogida y verificar B18

## 21. T21 — Carga que dispara la evaluación, registro guardado y reproducible (B34 a)

- **Objetivo:** cerrar el flujo de `design.md` §2: la carga evalúa cada observación nueva de un origen de compra, guarda el registro y lo puede recalcular.
- **Capacidad:** `carga-y-validacion`. **Escenarios:** B34 (a).
- **Alcance:** `persistencia/ensamblador.py` (contexto "a un instante", guardar TAB-10/TAB-11 con `config_version_id` y versiones de RN); conexión cargador → ensamblador; `oip evaluacion recalcular`; prueba de tiempo de RNF-1.
- **Fuera de alcance:** reevaluación (T22).
- **Construye (design.md):** CMP-21, CMP-08, CMP-22, RNF-1, RNF-2, RNF-3, RNF-4
- **Comportamientos esperados:** B34 (a) (con `CAMPO OBLIGATORIO FALTANTE (exchangeRate)` y la observación evaluada con el resultado de B18); recalcular cada evaluación guardada da el mismo registro (RNF-3); cambiar un parámetro y cargar la configuración cambia el resultado de una evaluación nueva y la anterior conserva su versión (RNF-2); evaluar con el historial sintético de `design.md` §11 tarda < 2 s (RNF-1), en memoria y en integración.
- **Guía de implementación:** las evaluaciones van después de cargar todo el archivo, en orden; la ficha de Amazon no se evalúa como oferta; `observations_used` lista cada observación del contexto con su fecha. Prueba del borde de los 90 días del contexto: una cadena de episodios que empezó antes no se ve y el recálculo da el mismo registro (DEC-264). El contexto toma las capturas con `captured_at` ≤ instante (DEC-271).
- **Depende de:** T08b, T20. **Estimación:** 8 h.
- **DoD:** común; evidencia de las pruebas de integración en local.

- [ ] 21.1 Implementar el ensamblador y guardar el registro y verificar B34 (a) con `RepositorioMemoria`
- [ ] 21.2 Implementar `oip evaluacion recalcular` y las pruebas de RNF-1, RNF-2 y RNF-3 y verificarlas en CI y en integración

## 22. T22 — Reevaluación de oportunidades abiertas (B2 b, B9 b)

- **Objetivo:** reevaluar las oportunidades abiertas cuando cambia una referencia de precio y marcar "ya no recomendado" (§3.2.5).
- **Capacidad:** `resultado-y-reevaluacion`. **Escenarios:** B2 (b), B9 (b).
- **Alcance:** `evaluacion/reevaluacion.py` (referencias cambiadas, oportunidades a reevaluar, `no_longer_recommended`); su uso desde el ensamblador; vista `open_opportunity`.
- **Fuera de alcance:** el resumen y el tablero (parte C).
- **Construye (design.md):** CMP-18, CMP-21, TAB-12, RNF-4
- **Comportamientos esperados:** B2 (b), B9 (b); prueba unitaria de que una observación del mismo día no cambia el habitual (excluye el día evaluado).
- **Guía de implementación:** `design.md` §10 punto 5 y Pendiente 6; la reevaluación guarda la evaluación anterior y las referencias que cambiaron. La oferta se toma exacta del `input_snapshot` de la evaluación anterior, con una prueba de que una marca restringida reevaluada da el mismo resultado (DEC-265); el mercado hoy usa el orden del filtro de DEC-261 (T25).
- **Depende de:** T21, T12, T13. **Estimación:** 7 h.
- **DoD:** común.

- [ ] 22.1 Implementar la detección de referencias cambiadas y la reevaluación y verificar B2 (b) y B9 (b)

## 23. T23 — Despliegue en Rocky y PoC de las migraciones (operación)

- **Objetivo:** dejar la parte B corriendo en Rocky con Podman y probar las migraciones de TimescaleDB antes de producción (DEC-179, DEC-182).
- **Capacidad:** operación. **Escenarios:** ninguno; prueba de host (la hace Jesús con el runbook).
- **Alcance:** `deploy/`: `Containerfile` del Core, Quadlets de `oip-db` y del contenedor de migraciones, `podman secret` de la contraseña, volumen de `config/` montado, sección del runbook (DEC-183) con la tabla de contenedores y puertos en `127.0.0.1` (DEC-178).
- **Fuera de alcance:** servicio HTTP, Metabase y Telegram (parte C).
- **Construye (design.md):** CMP-23, RNF-8, RNF-10
- **Comportamientos esperados** (design.md Migration Plan): respaldo, `upgrade` de `0001` y `0002`, `downgrade` y `upgrade` otra vez; `oip config cargar` y `oip cargar` de un archivo sintético en el contenedor; las pruebas de integración pasan contra la base de Rocky; ningún secreto en la imagen ni en los logs.
- **Guía de implementación:** contenedor de migraciones de una sola ejecución antes del servicio; etiqueta `:rollback-<fecha>`; ningún puerto fuera de `127.0.0.1`. Notas del runbook (decisión 32 del issue #34): no subir `psycopg` a DEBUG en producción; no bajar `0003` con rechazos guardados; esperar a la base con `pg_isready -h 127.0.0.1`. Código: `0003` se niega a bajar con rechazos guardados, como `0002` (se edita por DEC-272, antes de aplicarla en una base que no sea desechable), con prueba de integración en Rocky; el arranque fija el logger `psycopg` en WARNING de forma explícita.
- **Depende de:** T21, T22. **Estimación:** 6 h.
- **DoD:** común; evidencia de Jesús en el PR (salidas de los comandos en Rocky). No se archiva el cambio sin esta prueba (DEC-182).

- [ ] 23.1 Escribir el `Containerfile`, los Quadlets y la sección del runbook y verificar que la imagen construye sin secretos
- [ ] 23.2 Correr en Rocky el respaldo, las migraciones y una carga, y verificar la evidencia en el PR

## 24. T24 — Endurecimiento de los tipos de T04 (cimientos)

- **Objetivo:** cerrar las observaciones del issue #34 sobre los tipos del dominio, la configuración y los fixtures antes de las variantes de canales (DEC-273).
- **Capacidad:** cimientos. **Escenarios:** ninguno propio; lo ejercitan T12 a T22.
- **Alcance** (decisiones del issue #34):
  - 12: `RegistroEvaluacion` y `Referencias` rechazan con `ValueError` texto vacío o solo espacios en `motivo_rechazo`, `marcas` y `fuente_precio_habitual`.
  - 13: un `RegistroEvaluacion` con entrada exige `id`, `evaluado_en`, versiones de RN, evaluación anterior, referencias cambiadas y carga iguales a los de la entrada.
  - 15: `EvaluacionCanal` y `RegistroEvaluacion` validan cada marca contra el catálogo, con el catálogo cerrado nuevo del dato de `ESTIMADO (<dato>)` (DEC-266).
  - 20: `_ENTERO_DECIMAL` y `_ZONA_IANA` de `configuracion.py` usan `fullmatch`, con una prueba de un entero con salto de línea final rechazado.
  - 23: `EvaluacionCanal` rechaza con `ValueError` causas fuera del orden del catálogo (DEC-269).
  - 24: el docstring de `CanalEvaluado` dice que en venta local `costo_venta` = entrega + otros (sin prueba nueva).
  - 28: sucursales sintéticas por cadena (`tp-cv` y una de una segunda cadena sintética) en `tests/config_tienda_prueba.py`, para usar desde T12; los fixtures viejos no se reescriben.
  - 34: al construir, las tuplas dentro de un valor `Any` (`evidence`) se convierten en listas, con una prueba de ida y vuelta del `input_snapshot`.
  - 36: renombrar `test_el_particular_conserva_content_mientras_se_resuelve_rn_013` y `test_dec236_content_del_particular_se_conserva_pendiente_de_jesus` (sin "pendiente") y citar DEC-245 en sus docstrings; las aserciones no cambian.
- **Fuera de alcance:** las invariantes por estado del canal (T18); emitir marcas nuevas.
- **Construye (design.md):** CMP-04, CMP-09, CMP-17, CTR-06, RNF-3
- **Comportamientos esperados:** una prueba por punto (salvo el 24); la suite completa sigue en verde.
- **Guía de implementación:** si choca con T08a en los fixtures o en `configuracion.py`, la sesión de orquestación simula el merge y da el orden (DEC-253).
- **Depende de:** T11. **Estimación:** 6 h.
- **DoD:** común.

- [ ] 24.1 Implementar las validaciones de los tipos del dominio (12, 13, 15, 23, 34) y verificar sus pruebas unitarias
- [ ] 24.2 Aplicar `fullmatch`, las sucursales sintéticas, el docstring y los nombres de las pruebas (20, 24, 28, 36) y verificar la suite completa

## 25. T25 — Mercado hoy y calidad sin datos: ajustes (decisiones 6 y 10)

- **Objetivo:** fijar el orden del filtro del mercado hoy y la calidad con precio antes inflado sin datos, antes de las tareas que los usan.
- **Capacidad:** `referencias-de-precio`. **Escenarios:** ninguno nuevo; los ejercitan B6, B7, B9, B14, B32 y B3.
- **Alcance:** en `referencias.py`, de cada publicación primero la observación más reciente dentro de las 48 h y después el filtro de nueva, vendida por el comercio y disponible (DEC-261), para el mercado hoy, la competencia más barata y la reevaluación, con el ajuste de la prueba del developer de T10; en `descuento.py`, la marca `PRECIO ANTES INFLADO` se revisa antes de la salida "sin datos" y da Descuento cuestionable (RN-012 §3, "sin importar los números"; decisión 10 del issue #34).
- **Fuera de alcance:** comercio = cadena y su excepción (T16).
- **Construye (design.md):** CMP-11, CMP-12, RNF-4
- **Comportamientos esperados:** un agotado reciente saca a la publicación del mercado hoy; `PRECIO ANTES INFLADO` sin habitual ni mercado hoy da Descuento cuestionable; B6 y B7 siguen en verde.
- **Guía de implementación:** `design.md` §10 punto 4.
- **Depende de:** T11. **Estimación:** 4 h.
- **DoD:** común.

- [ ] 25.1 Implementar el orden del filtro del mercado hoy y la calidad con precio antes inflado sin datos, y verificar sus pruebas unitarias

## Matriz de cobertura

Una fila por escenario y variante de la parte B (54). La columna RN es la del encabezado del criterio en el REQ; donde el criterio no cita RN, la del requisito de la spec.

| Escenario del REQ | Capacidad | Requisito (spec) | Tarea | RN |
|---|---|---|---|---|
| B1 | `canales-y-margen` | Evaluación por canal y elección del canal | T11 | RN-001, RN-002, RN-003, RN-004, RN-005, RN-006, RN-007, RN-009, RN-012, RN-013, RN-016, RN-017, RN-018 |
| B2 (base) | `canales-y-margen` | Evaluación por canal y elección del canal | T12 | RN-001, RN-002, RN-003, RN-004, RN-005, RN-006, RN-009, RN-012, RN-016, RN-017, RN-018 |
| B2 (b) | `resultado-y-reevaluacion` | Reevaluación de oportunidades abiertas | T22 | RN-001, RN-002, RN-003, RN-004, RN-005, RN-006, RN-009, RN-012, RN-016, RN-017, RN-018 |
| B3 | `resultado-y-reevaluacion` | Precedencia, motivo principal y todos los motivos | T18 | RN-001, RN-002, RN-003, RN-004, RN-005, RN-012, RN-016 |
| B4 | `canales-y-margen` | Restricción en Amazon cierra el canal | T13 | RN-001, RN-003, RN-005, RN-006, RN-009, RN-012, RN-016, RN-017, RN-018 |
| B5 | `resultado-y-reevaluacion` | Revisión manual con nivel calculado | T19 | RN-009, RN-013 |
| B6 | `referencias-de-precio` | Sin historial suficiente no hay descuento real | T10 | RN-002, RN-003, RN-012 |
| B7 | `referencias-de-precio` | Franja del descuento real | T10 | RN-003 |
| B8 | `resultado-y-reevaluacion` | Vendedor externo y riesgo de procedencia | T19 | RN-009, RN-012, RN-015 |
| B9 (base) | `canales-y-margen` | Competencia más barata y nivel del aviso | T13 | RN-002, RN-005, RN-009, RN-016, RN-018 |
| B9 (b) | `resultado-y-reevaluacion` | Reevaluación de oportunidades abiertas | T22 | RN-002, RN-005, RN-009, RN-016, RN-018 |
| B10 (a) | `canales-y-margen` | Ranking de Amazon y demanda desconocida | T14 | RN-004, RN-009, RN-018 |
| B10 (b) | `canales-y-margen` | Ranking de Amazon y demanda desconocida | T14 | RN-004, RN-009, RN-018 |
| B11 | `resultado-y-reevaluacion` | Demanda desconocida sin otro canal con nivel | T19 | RN-004, RN-009 |
| B12 | `canales-y-margen` | Unidades y demanda a la baja en Amazon | T14 | RN-005, RN-018 |
| B13 | `canales-y-margen` | Unidades y demanda a la baja en Amazon | T14 | RN-004, RN-005 |
| B14 | `referencias-de-precio` | Precio de venta esperado en Amazon sin oferta hoy | T16 | RN-002, RN-005 |
| B15 | `canales-y-margen` | Castigo sin mínimo de 60 días | T12 | RN-005, RN-009 |
| B16 | `canales-y-margen` | Envío y empaque según el peso | T12 | RN-001, RN-006 |
| B17 | `canales-y-margen` | Comisión desconocida cierra Amazon | T12 | RN-006, RN-018 |
| B18 | `resultado-y-reevaluacion` | Compra a particular con inspección | T20 | RN-001, RN-008, RN-014, RN-015, RN-016 |
| B19 | `resultado-y-reevaluacion` | Evitar siempre descarta | T19 | RN-015 |
| B20 (a) | `carga-y-validacion` | Validación de cada observación | T07 | RN-013, RN-014 (del requisito; el criterio del REQ no cita RN) |
| B20 (b) | `carga-y-validacion` | Validación de cada observación | T07 | RN-013, RN-014 (del requisito; el criterio del REQ no cita RN) |
| B20 (c) | `carga-y-validacion` | Validación de cada observación | T07 | RN-013, RN-014 (del requisito; el criterio del REQ no cita RN) |
| B20 (d) | `carga-y-validacion` | Validación de cada observación | T07 | RN-013, RN-014 (del requisito; el criterio del REQ no cita RN) |
| B20 (e) | `carga-y-validacion` | Validación de cada observación | T07 | RN-013, RN-014 (del requisito; el criterio del REQ no cita RN) |
| B20 (f) | `carga-y-validacion` | Validación de cada observación | T07 | RN-013, RN-014 (del requisito; el criterio del REQ no cita RN) |
| B20 (g) | `carga-y-validacion` | Validación de cada observación | T07 | RN-013, RN-014 (del requisito; el criterio del REQ no cita RN) |
| B20 (h) | `carga-y-validacion` | Validación de cada observación | T07 | RN-013, RN-014 (del requisito; el criterio del REQ no cita RN) |
| B21 | `canales-y-margen` | Confianza en tienda física para el nivel | T13 | RN-007, RN-009 |
| B22 | `resultado-y-reevaluacion` | Sin canal disponible descarta | T18 | RN-004, RN-009, RN-017, RN-018 |
| B23 | `resultado-y-reevaluacion` | Margen negativo descarta | T18 | RN-001, RN-004, RN-005, RN-009, RN-016 |
| B24 (a) | `resultado-y-reevaluacion` | Usado sin valor de referencia | T20 | RN-009, RN-014, RN-015, RN-016 |
| B24 (b) | `resultado-y-reevaluacion` | Usado sin valor de referencia | T20 | RN-009, RN-014, RN-015, RN-016 |
| B24 (c) | `resultado-y-reevaluacion` | Usado sin valor de referencia | T20 | RN-009, RN-014, RN-015, RN-016 |
| B25 | `canales-y-margen` | Sin rotación cierra el canal | T13 | RN-004, RN-005, RN-018 |
| B26 (a) | `canales-y-margen` | Envío y empaque según el peso | T14 | RN-005, RN-006, RN-018 |
| B26 (b) | `canales-y-margen` | Envío y empaque según el peso | T14 | RN-005, RN-006, RN-018 |
| B27 | `configuracion` | Valores por código de category | T17 | RN-005, RN-006 |
| B28 (a) | `canales-y-margen` | Sin precio de venta en Amazon | T15 | RN-002, RN-005, RN-009, RN-016, RN-018 |
| B28 (b) | `canales-y-margen` | Sin precio de venta en Amazon | T15 | RN-002, RN-005, RN-009, RN-016, RN-018 |
| B29 | `resultado-y-reevaluacion` | Precedencia, motivo principal y todos los motivos | T18 | RN-001, RN-003, RN-005, RN-009, RN-012, RN-016 |
| B30 (base) | `referencias-de-precio` | Precio habitual con observaciones diarias y episodio de liquidación | T09 | RN-002, RN-003 |
| B30 (b) | `referencias-de-precio` | Precio habitual con observaciones diarias y episodio de liquidación | T09 | RN-002, RN-003 |
| B30 (c) | `referencias-de-precio` | Precio habitual con observaciones diarias y episodio de liquidación | T09 | RN-002, RN-003 |
| B30 (d) | `referencias-de-precio` | Precio habitual con observaciones diarias y episodio de liquidación | T09 | RN-002, RN-003 |
| B30 (e) | `referencias-de-precio` | Precio habitual con observaciones diarias y episodio de liquidación | T09 | RN-002, RN-003 |
| B31 | `configuracion` | Impuesto por ubicación de la tienda | T17 | RN-001, RN-005, RN-009, RN-018 |
| B32 | `referencias-de-precio` | Comercio = cadena | T16 | RN-002, RN-012, RN-016, RN-018 |
| B33 | `canales-y-margen` | Redondeo una sola vez por fórmula | T15 | RN-001, RN-005, RN-016 |
| B34 (a) | `carga-y-validacion` | Carga de un archivo JSON Lines con registros de varios tipos | T21 | RN-014, RN-016, RN-017 (del requisito; el criterio del REQ no cita RN) |
| B34 (b) | `carga-y-validacion` | Carga de un archivo CSV de un solo tipo | T08b | RN-014, RN-016 (del requisito; el criterio del REQ no cita RN) |
| B34 (c) | `carga-y-validacion` | recordType obligatorio en cada renglón JSON Lines | T08b | RN-013 (del requisito; el criterio del REQ no cita RN) |
