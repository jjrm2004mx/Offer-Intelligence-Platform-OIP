# Decisiones de Jesús sobre la revisión externa 2026-11

| | |
|---|---|
| Fecha | 2026-11-17 |
| Fuente | [revision-externa-2026-11.md](revision-externa-2026-11.md) (PR #21) |
| Estado | **Los 42 hallazgos están decididos.** Etapa 3 mínima hecha (PR #22, DEC-192 a DEC-196). Pendiente: REQ-2026-0001 v2.6 con sus DEC, reinspección v8 y PR de limpieza |

Este documento es la **entrada** de la REQ v2.6 y del PR de limpieza. Cada decisión se registra como DEC al aplicarse.

## 1. Preguntas de Jesús (sección 4 del reporte)

| Pregunta | Hallazgo | Decisión |
|---|---|---|
| 1 | EXT-002 | Producto sin precio de venta en Amazon: canal Amazon **cerrado** (`SIN PRECIO DE VENTA EN AMAZON`); se evalúa solo la venta local. Fila nueva en §3.2.1 y escenario B28: (a) no está en Amazon; (b) sin oferta hoy y sin historial. |
| 2 | EXT-004 | El margen ajustado **se calcula siempre** en un canal disponible, haya o no descuento real. Si es negativo en todos los canales disponibles: DESCARTADA (`MARGEN NEGATIVO`). Agregar el escenario. |
| 3a | EXT-009 | En la parte B, Amazon **no es origen de compra**, solo referencia de precio. CASO-004 pasa a "antecedente, no es prueba". |
| 3b | EXT-009 | Cuando cambia una referencia de un producto, **se reevalúan** sus oportunidades abiertas. La que deja de ser recomendable aparece como "ya no recomendado" en el resumen, sin aviso inmediato. |
| 4 | B9 | El aviso usa el **nivel más alto** entre los canales. El cuerpo muestra por separado el canal con mejor ganancia total y el canal con mejor nivel. |
| 5 | EXT-006 | Capturas de Jesús en el Inc. 1: **archivo** (CSV o JSON Lines) cargado con el mismo cargador de la parte B. Telegram, después de asegurar el bot. |
| 6 | EXT-015 | **Versiones de las RN congeladas** hasta el merge de la parte B. Después, un solo cambio en bloque con `oip-revisor-rn` (S-28, S-29, S-31, S-32), con Jesús como dueño. |
| 7 | Impuesto | **Tasa de impuesto por ubicación** de la tienda (`taxLocation`), en una tabla de la configuración versionada con fuente CDTFA y fecha de vigencia; **7.75% de respaldo** si la tienda no tiene ubicación cargada. Chula Vista y National City: 8.75% (confirmar en el buscador oficial de la CDTFA antes de cargar). Los escenarios actuales conservan sus números declarando una tienda a 7.75%; se agrega un escenario con una tienda de Chula Vista a 8.75% (en B1 la compra pasaría de $31.25 a $31.54). |

## 2. Categoría C (huecos que bloquean la parte B)

| Hallazgo | Decisión |
|---|---|
| EXT-007 | Precio habitual: (1) una observación por publicación y día (la última); (2) **episodio**: cuando el precio de una publicación baja de su habitual, el habitual se congela en el valor del día anterior a la baja, y todo el episodio se evalúa contra ese valor; termina cuando el precio vuelve al habitual o más; (3) límite del episodio de **30 días** en la configuración versionada; al día 31 el precio bajo entra a la mediana; (4) escenario con observaciones crudas que incluya una liquidación escalonada. El experto confirma los 30 días (sustituye a su pregunta 8). |
| EXT-008 | §3.2.2: `nivel_calculado` = nivel de RN-009 §4.3 con el mínimo por unidad y la baja por competencia más barata, sin los requisitos de canal de §4.2 (demanda, vendible, confianza). |
| EXT-010 | Pasan a la parte B (y se dice en §1): la carga JSON Lines, el modelo de datos de las capturas manuales y la carga de la configuración versionada. |
| EXT-011 | No entra en la v2.6. Tarea previa a operar: cargar los tamaños de categoría, los días de venta y las tasas, con fuente y fecha (pregunta 12 del experto). |
| EXT-012 | Ranking de Amazon: con 1 a 6 días se promedia lo disponible; con 0 días, demanda desconocida. El mismo valor se usa para el umbral, los días de venta y el tope. |
| EXT-013 | Lista cerrada en §5 de los montos que se redondean a centavos (impuesto, costo de compra, comisión, envío, devoluciones, castigo, neto, ajustado, total). Cada fórmula de varios factores se redondea una sola vez, al final. Los porcentajes no se redondean para comparar (DEC-060). |
| EXT-031 | B18 y B24: agregar "sin datos de Amazon" al "Dado". En la parte B, la calidad del precio de un usado es "no aplica" hasta que el experto responda la pregunta 10. |
| EXT-032 | **Comercio = cadena**: las sucursales y la tienda en línea de la misma cadena son el mismo comercio y no cuentan como "otro comercio". Corregir D1. |
| EXT-033 | Reescribir las comisiones de RN-006 §4.1 sin ambigüedad ("si el precio total es de $10 o menos, 8% del total"; "3% sobre el excedente" por tramos). Por EXT-015 (RN congeladas), se aplica en el cambio en bloque después del merge de B; mientras tanto, el REQ v2.6 lo aclara. |

## 3. Categoría A (contradicciones)

| Hallazgo | Decisión |
|---|---|
| EXT-005 | Manda el contrato de la arquitectura §8; el REQ solo lo cita. Se agrega `taxLocation`. Códigos en inglés y snake_case con tabla cerrada para `availability.state`, `category` y `condition`; etiquetas en español solo en avisos y Metabase. |
| EXT-006 | Ver pregunta 5. |
| EXT-019 | Las funcionalidades de la arquitectura se renombran a **F1** (reventa) y **F2** (servicio a clientes). "Parte A a D" queda reservado para el REQ. Se registra en una DEC. |
| EXT-020 | Actualizar el glosario a las RN v2 (descuento real contra el precio habitual; inspección del REQ; términos nuevos). |
| EXT-021 | Marcar DEC-051, 083, 027, 131 y 167 como REEMPLAZADA o PRECISADA, con la DEC que manda. |
| EXT-022 | Aviso agrupado en la guía: "N oportunidades acumuladas", con el emoji del nivel más alto del grupo, citando S-29. |
| EXT-028 | Agregar la apariencia de la clase "Precio normal" a la guía. |
| EXT-029 | Quitar la marca "⚠️ No confirmada" de los avisos y agregar "confirmado por llamada" a "Registrar visita". |
| EXT-030 | Citar en la arquitectura §3.1 "los no nuevos solo en venta local" como supuesto S-12. |
| EXT-042 | CASO-004: antecedente (ver 3a). Los demás casos se actualizan a las RN v2 en el PR de limpieza. No bloquean el análisis de B. |

## 4. Categoría D (seguridad)

| Hallazgo | Decisión |
|---|---|
| EXT-003 | Hecho en el PR #22 (DEC-194). |
| EXT-017 | Bot de Telegram: solo el `chat_id` de Jesús (los demás se ignoran y se registran), sondeo largo sin webhook, cada acción registrada. Se agrega a la lista de seguridad del tester. |
| EXT-018 | Se quita el campo de descripción libre de particulares. Enlace https y de una lista permitida (OfferUp, Facebook Marketplace), configurable. |
| EXT-040 | Reescribir de forma genérica las secciones operativas del sitio público (RN-010 §4.5). El detalle queda solo en el repo. |

## 5. Categoría F (proceso y agentes)

| Hallazgo | Decisión |
|---|---|
| EXT-001 | Hecho en el PR #22. OpenSpec 2.1.0 usa skills en lugar de `/opsx:*` (DEC-192). |
| EXT-014 | `requirement_version` en la traza `OIP_TRACE` del inspector; el analista la compara con la versión del cuerpo del issue. |
| EXT-015 | Ver pregunta 6. |
| EXT-016 | A6 y C13 son pruebas de host: las hace Jesús con el runbook y deja la evidencia en el PR. §12 dice qué parte del gate es estática. |
| EXT-034, 035, 036, 037 | Hechos en el PR #22 (DEC-193, DEC-195, DEC-196). |

## 6. Categorías E y G

| Hallazgo | Decisión |
|---|---|
| EXT-023 | El REQ cita la arquitectura v2.0; se quita la lista de diferencias de §9 y se actualiza R-05. |
| EXT-024 | Rehacer flujo-general §7 con las partes A a D; `oip-arquitecto` se crea cuando una parte toque un ADR. |
| EXT-025 | Registro: subir la versión, DEC-081 VIGENTE con las partes A a D, tachar lo hecho en §10. |
| EXT-026 | Pasada de `oip-revisor-rn` que cierre los 12 defectos resueltos por la arquitectura v2.0, más un disparador nuevo: "cambió la arquitectura". |
| EXT-027 | Citar siempre con versión ("RN-001 v1 · P3"). |
| EXT-038 | Alinear flujo-general con `oip-developer` (`Closes` y rama), confirmar la columna del Project y cerrar el PR #10. |
| EXT-039 | En `oip-revisor-rn`, "14. Revisión de consistencia". |
| EXT-041 | La API de solo lectura pasa a la parte C. En la parte B el MSRP solo se muestra. |

## 7. Dónde va cada uno

| Entrega | Hallazgos | Estado |
|---|---|---|
| Etapa 3 mínima | 001, 003, 034, 035, 036, 037 | **Hecho** (PR #22) |
| REQ v2.6 (+ DEC nuevas) | 002, 004, 005, 006, 007, 008, 009, 010, 012, 013, 014, 015, 016, 017, 018, 019, 023, 031, 032, 033 (aclaración), 041, pregunta 4 (aviso) y pregunta 7 (impuesto) | Pendiente |
| Reinspección v8 | Solo lo que cambia en la v2.6 | Pendiente |
| PR de limpieza (no bloquea B) | 020, 021, 022, 024, 025, 026, 027, 028, 029, 030, 038, 039, 040, 042 | Pendiente |
| Antes de operar | 011 | — |
| Después del merge de B | Cambio en bloque de las RN (EXT-015), incluido 033 en RN-006 | — |

## 8. Pendiente del experto

- Confirmar o ajustar los 30 días del episodio de liquidación (EXT-007).
- Costo de ir a recoger a San Diego (pregunta 9).
- Contra qué se mide un usado (pregunta 10, EXT-031).
- Fuente de la tabla de tamaños de categoría (pregunta 12, EXT-011).
