# Revisión externa — OIP, noviembre de 2026

| | |
|---|---|
| Fecha | 2026-11-17 |
| Tipo | Revisión externa e independiente, de solo lectura. El revisor no participó en la redacción de nada de lo revisado |
| Base | `main` en `a822fcd`. REQ-2026-0001 **v2.5** (#2), inspección **v7** (#3) |
| Alcance | `docs/negocio/` (RN-001 a RN-018, revisiones, casos, glosario y plantilla), `docs/proceso/` (flujos y registro, DEC-001 a DEC-191), `docs/arquitectura/` (v2.0 e insumo), `docs/diseno/guia-de-estilo.md`, `.claude/agents/` (los 5 agentes de DEC-172), issues #2 y #3 |
| Método | Lectura cruzada de los documentos. Cuentas rehechas con `Decimal` y `ROUND_HALF_UP` (`py -3`) y simulación minuto a minuto de los avisos (S-29 y S-32) |
| Fuera del reporte | Los defectos D-001 a D-038 de la inspección, que ya están cerrados y no se repiten aquí |

Los ID `EXT-NNN` son permanentes. EXT-042 se agregó al final de la revisión (casos) y se muestra junto a los de su severidad.

## 1. Resumen ejecutivo

1. **Las cuentas cuadran.** Rehíce 54 comprobaciones de las RN, el REQ y los casos, y simulé los avisos de C7 y C15 (las cuatro variantes); no encontré ninguna diferencia en el REQ.
2. Los problemas no son de aritmética: son **huecos de definición, documentos desactualizados y un proceso que hoy no se puede ejecutar**. Hay **42 hallazgos**: 3 ALTA, 24 MEDIA y 15 BAJA.
3. **ALTA:**
   - Falta la **Etapa 3** (arranque técnico), y sin ella `oip-analista` se bloquea en su propia revisión previa.
   - El REQ no dice qué pasa con un producto **sin precio de venta en Amazon**. Es un caso frecuente, y en él RN-002 y RN-004 se contradicen.
   - La regla de la **IP de casa** no cubre a los agentes que corren en el equipo de Jesús.
4. **MEDIA, las que más pesan en la parte B:**
   - el margen ajustado sin descuento real (decide si aplica `MARGEN NEGATIVO`);
   - cómo se arma la mediana del precio habitual;
   - qué es `nivel_calculado`;
   - qué observaciones disparan la evaluación;
   - el contrato de observación, que no coincide entre el REQ y la arquitectura;
   - los datos de entrada de B, que viven en la parte A;
   - los casos, que no se actualizaron a las RN v2 y que, según DEC-136, se van a convertir en pruebas.
5. **Veredicto: todavía no se puede pasar a construir la parte B.** Antes hay que hacer tres cosas:
   - la **Etapa 3 mínima**;
   - una **REQ v2.6**, con una reinspección corta, que resuelva EXT-002, 004, 007 a 010 y 013;
   - la **regla de los agentes** (EXT-003).

## 2. Hallazgos

Categorías:
- **A** contradicción entre documentos;
- **B** números que no cuadran (no hubo hallazgos de esta categoría);
- **C** hueco que bloquea la parte B;
- **D** seguridad o IP de casa;
- **E** referencia rota o desactualizada;
- **F** proceso y agentes;
- **G** claridad.

### ALTA

| ID | Cat. | Dónde | Hallazgo | Evidencia | Corrección mínima |
|---|---|---|---|---|---|
| EXT-001 | F | [flujo-general.md](../flujo-general.md) §3 y §10; [oip-analista.md](../../../.claude/agents/oip-analista.md), revisión previa | La Etapa 3 no existe. El siguiente paso declarado ("análisis de la parte B") falla en el control del propio analista. | El repo no tiene `openspec/`, `CLAUDE.md`, `src/`, `tests/` ni `.github/workflows/`. Con eso: el analista da `ANALYSIS READINESS: FAIL`, el tester da `TEST INFRASTRUCTURE: MISSING` y el developer no puede cumplir su Definition of Done (ruff, pytest, gates). La Etapa 3 no tiene agente ni lista de salida. | Hacer antes una Etapa 3 mínima: `openspec init` (fijando la versión y comprobando que existen los comandos `/opsx:*` que citan los agentes), `CLAUDE.md`, `pyproject` con pytest y ruff, el hook y un workflow. En §10, poner "Siguiente: Etapa 3". |
| EXT-002 | C/A | REQ §3.2.1 y §3.2.3; [RN-002](../../negocio/reglas/RN-002-precio-de-mercado.md) §11 frente a [RN-004](../../negocio/reglas/RN-004-demanda.md) §11 | Un canal Amazon sin precio de venta no tiene estado. Pasa con un producto que no está en Amazon, o que no tiene oferta hoy ni historial suficiente en Amazon (S-02). | Al pie de la letra cae en `DEMANDA DESCONOCIDA` (sin ranking), así que queda "por revisar" y se le piden margen y `nivel_calculado` sin precio; si la venta local no tiene nivel, termina en `REVISION_MANUAL`. RN-002 §11 dice lo contrario: "se evalúa solo la venta local". El resultado cambia entre REVISION_MANUAL, SIN_NIVEL y DESCARTADA. Es frecuente: [CASO-002](../../negocio/casos/CASO-002-dewalt-atomic-dck225d2.md) §4.4 ya señala los modelos exclusivos de un comercio, y al arrancar no hay historial de Amazon. | Agregar una fila a §3.2.1: Amazon cerrado, `SIN PRECIO DE VENTA EN AMAZON` (o por revisar, si Jesús lo prefiere). Agregar el escenario B28 con dos casos: (a) no está en Amazon; (b) sin oferta hoy y sin historial. |
| EXT-003 | D | [oip-developer.md](../../../.claude/agents/oip-developer.md), "Reglas de OIP que no se negocian"; oip-tester; oip-analista; DEC-122 | La regla de la IP de casa solo habla del código del Core. Los agentes tienen Bash y pueden consultar páginas de comercios desde el equipo de Jesús, que el firewall de DEC-122 no protege (ese firewall es el de los contenedores del servidor). | La parte B se construye antes de la PoC-A, así que no hay datos guardados del VPS, y es tentador armar fixtures "realistas" con la página real. No existe `.claude/settings.json` con reglas `deny`. | Agregar a los tres agentes y a `CLAUDE.md`: "Nunca consultes dominios de comercios (DEC-132) desde este equipo, ni con curl, ni con WebFetch, ni con un navegador; los fixtures son sintéticos o vienen del VPS". Reforzarlo con reglas `deny` en `.claude/settings.json`. |

### MEDIA

| ID | Cat. | Dónde | Hallazgo | Evidencia | Corrección mínima |
|---|---|---|---|---|---|
| EXT-004 | A | REQ §3.2.1 ("Disponible: todo") y párrafo final de §3.2, frente a B3 y B7 ("no se calcula RN-005") | No está definido si en un canal disponible se calcula el margen ajustado cuando no hay descuento real (por ejemplo, `SIN HISTORIAL SUFICIENTE`). | De eso depende si aplica `MARGEN NEGATIVO`: el resultado sería DESCARTADA o REVISION_MANUAL. Es el caso más común al arrancar (R-24 de la arquitectura). | Una frase en §3.2 y un escenario: sin historial y con margen negativo en todos los canales disponibles. |
| EXT-005 | A | REQ §6 frente a [arquitectura §8](../../arquitectura/arquitectura-tecnica.md) | El contrato de observación no coincide entre los dos documentos. | REQ: `shippingToMe`, `taxLocation` y la observación de Amazon aparte. Arquitectura: `shipping.toMeCost`, sin `taxLocation`, con `amazonListing` anidado. Los códigos mezclan idiomas (`in_stock_confirmed` frente a "disponible confirmada", `tools` frente a "herramientas") y no hay una lista cerrada. | Un solo contrato (el de la arquitectura §8), citado desde el REQ, con `taxLocation` y la tabla de códigos de `availability.state`, `category` y `condition`. |
| EXT-006 | A/D | REQ §3.1 punto 8, §3.3 punto 6, §7 ("API de solo lectura") y §10; DEC-180 | No hay canal de escritura para las capturas de Jesús (particulares, comparables, estimado, demanda local, visitas, resultados, solicitudes de clientes), ni autenticación para él. | La API es de solo lectura y Metabase también (DEC-180). | Definir el canal (formulario mínimo, CLI o API de escritura con token por la VPN) y asignarlo a una parte. |
| EXT-007 | C | REQ §3.2 paso 3; RN-002 §4.1; RN-003 (precio típico); RN-012 (mínimo registrado) | No está definido cómo se arma la mediana del precio habitual. | No dice si entran la observación evaluada y los días de la misma liquidación: con el seguimiento diario, una liquidación de 2 semanas baja su propio habitual y su descuento real. Con el "mínimo registrado", una oferta nunca puede ser menor que sí misma. Ningún escenario da observaciones crudas: todos dan el habitual ya calculado. | Fijar una observación por publicación y día y excluir la publicación evaluada a su precio actual. Agregar un escenario con observaciones crudas (por ejemplo, las 8 de RN-002 A). |
| EXT-008 | C | REQ §3.2.2, B11, B21 y §7; RN-009 §4.1 y §4.2 | `nivel_calculado` no tiene definición. | B11 lo calcula ignorando la demanda (Amazon por revisar) y B21 ignorando la confianza Baja. No dice si aplican el mínimo por unidad ni la baja por competencia más barata. | Una línea en §3.2.2: "nivel de RN-009 §4.3 con el mínimo por unidad y la baja por competencia, sin los requisitos de canal de §4.2 (demanda, vendible, confianza)". |
| EXT-009 | C | REQ §3.1 punto 10 ("Cada observación nueva dispara la parte B") | No dice qué observaciones se evalúan ni qué se reevalúa. | ¿Una observación de la ficha de Amazon es una oferta para comprar? [CASO-004](../../negocio/casos/CASO-004-ninja-bn701.md) evalúa una compra en Amazon para revender. ¿Una observación de seguimiento sin descuento genera un registro? Si Target baja a $99 (B9), ¿se reevalúa la oportunidad vigente de B1? Afecta el volumen, los avisos y "ya no recomendado". | Una regla de disparo (qué tipos de observación se evalúan) y otra de reevaluación cuando cambia una referencia. |
| EXT-010 | C/F | REQ §1 (B se construye 1.º y A 3.º), §3.1 puntos 8 y 9, §6; [oip-analista.md](../../../.claude/agents/oip-analista.md) ("sin ampliarlo"); oip-tester, regla 5 | B se construye primero, pero sus entradas pertenecen a la parte A o a ninguna parte. | La carga JSON Lines (§3.1 punto 9) y las capturas (punto 8) son de la parte A; la configuración versionada (§6) no tiene parte. El analista no puede incluirlas sin ampliar el alcance, y el tester usa la carga JSON Lines como fuente de datos. | Mover a la parte B la carga JSON Lines, el modelo de las capturas y la carga de la configuración versionada, y decirlo en §1. |
| EXT-011 | C | REQ §5 y §6 (categorías); RN-004 §4 ("Por cargar"); RN-005 (días de venta solo para herramientas); arquitectura §14.8 | La configuración inicial está incompleta. | Sin el tamaño de categoría de belleza, hogar y cocina, juguetes y electrónica, todo producto de esas categorías queda con Amazon por revisar y va a revisión manual si la venta local no tiene nivel. Es justo la temporada de noviembre (DEC-153). Faltan días de venta y tasas para otras categorías, y la "tabla pública" mensual no tiene fuente con nombre. | No bloquea construir. Antes de operar: cargar la tabla con su fuente y fecha, y decir qué días de venta usan las demás categorías. |
| EXT-012 | C | RN-004 §4 ("promedios de 7 días"); arquitectura §2.5; REQ §3.1 punto 2 (una consulta cada 24 h) | "Promedio de 7 días" no está definido cuando hay menos de 7 días de datos, que es el caso de todo producto al arrancar. | Tampoco dice qué ranking usan la tabla de días y el tope: B1 y B13 dan el mismo valor para el ranking de hoy y para el promedio. | Fijar un mínimo de datos y un respaldo (el último ranking observado), y decir que el mismo valor sirve para el umbral, los días y el tope. |
| EXT-013 | C | DEC-060; REQ §5 (redondeo); RN-005 §4 | "Cada monto a centavos en cada paso" no dice qué es un paso. | Devoluciones con una venta de $149.50: $5.24 si se redondea después de "venta × tasa", $5.23 si se redondea una sola vez. Venta local con $10.03: $7.68 frente a $7.67. Los escenarios actuales no lo distinguen, pero las pruebas comparan centavos exactos. | Una lista cerrada de los montos que se redondean, y redondear una sola vez cada fórmula de varios factores. |
| EXT-014 | F | [oip-analista.md](../../../.claude/agents/oip-analista.md), revisión previa, fila 2; traza `OIP_TRACE` del inspector | El analista debe comprobar que la versión inspeccionada es la actual, y con REST no puede hacerlo. | La traza solo guarda `inspection_version`. El historial de ediciones del cuerpo del issue solo está en GraphQL, que no está disponible. Hoy se deduce del texto libre de #3. | Agregar `requirement_version: v2.5` a la traza del inspector y que el analista la compare con la "Versión" del cuerpo. |
| EXT-015 | F | Inspección #3 (R-02, R-04, R-09, R-10); comentario de #3; registro §10 | Llevar los supuestos a las RN (S-28 a RN-012; S-31 a RN-016 y RN-014; S-29 y S-32 a RN-009) no tiene dueño ni fecha. | Cuando se haga, sube la versión de las RN, y §9 del REQ obliga a reinspeccionar a media construcción. R-04 ("congelar versiones") no quedó como decisión. | Una DEC nueva: versiones de RN congeladas hasta el merge de la parte B, y cambios en bloque después de la sesión 3, con dueño. |
| EXT-016 | F/D | REQ §10 y §12; [oip-tester.md](../../../.claude/agents/oip-tester.md), regla 5 ("sin red") | A6 y C13 son pruebas de infraestructura (firewall en casa, VPS caído, VPN y credenciales). No se pueden hacer con pytest ni en GitHub Actions, y nadie es dueño de ellas. | El gate de egress en Actions solo puede ser estático. DEC-182 dice que las tareas incluyen la prueba en Rocky, pero no quién la hace. | Separar las pruebas de host, con dueño (Jesús y el runbook) y evidencia en el PR, y decir en §12 qué parte del gate es estática. |
| EXT-017 | D | [Guía de estilo §10.2](../../diseno/guia-de-estilo.md) (botones); REQ §10; arquitectura §10; tester S1 a S8 | El bot de Telegram recibe acciones (re-consultar tienda, registrar visita) y nada exige que solo acepte el chat de Jesús. Tampoco dice si usa webhook, que choca con DEC-178, o sondeo. | Una re-consulta pone a trabajar al Worker y una visita cambia la confianza de la tienda. | Solo el `chat_id` de Jesús, sondeo largo y cada acción registrada. Agregarlo a la lista de seguridad del tester. |
| EXT-018 | D | REQ §6 ("descripción") frente a §10; paso 1 de §3.2 ("salvo particulares") | La descripción libre de un particular suele traer su nombre o teléfono. Además, el enlace de particulares no se valida. | §10 no incluye la descripción entre los datos permitidos de particulares. No se exige esquema ni plataforma para el enlace. | Quitar la descripción o limpiarla al capturar. Exigir https y una lista de plataformas permitidas (OfferUp, Facebook). |
| EXT-019 | A/G | [Arquitectura](../../arquitectura/arquitectura-tecnica.md) §1 y §5.4; DEC-110, 134, 135, 137 y 139; glosario | "A" y "B" significan funcionalidades en un lado (B = búsqueda por artículo) y partes del REQ en el otro (B = evaluación, D = búsqueda por artículo). | Un agente que busque "parte B" en la arquitectura llega a RN-011. | Renombrar las funcionalidades (F1 reventa y F2 servicio a clientes) y registrarlo en una DEC. |
| EXT-020 | A | [glosario.md](../../negocio/glosario.md) | El glosario que ve el experto contradice RN-003 v2 y está incompleto. | Dice que el descuento real es "contra el precio de mercado" (es contra el precio habitual, DEC-129) y que la inspección es "de cada regla" (es del REQ, DEC-076). Le faltan precio habitual, mercado hoy, canal, venta local, por revisar, los niveles nuevos y la calidad del precio. Ya está registrado como RN-002 D-011 y sigue sin corregir. | Actualizar el glosario con los términos de las RN v2. |
| EXT-021 | A | [registro-de-decisiones.md](../registro-de-decisiones.md): DEC-051, 083, 027, 131 y 167 | Hay decisiones vigentes, sin marcar, que contradicen lo vigente. | DEC-051 (90 días; venta igual al mínimo) frente a RN-002 v2 y DEC-157. DEC-083 (crear `oip-negocio` y `oip-seguridad`) frente a DEC-172. DEC-027 (búsqueda en Keepa) frente a DEC-124 y DEC-169. DEC-131 (4 clases) frente a RN-012 (5). DEC-167 ("desempate de 10 puntos") frente a DEC-170 y RN-018 (10% relativo a la ganancia mayor). El analista está obligado a leer el registro. | Marcarlas REEMPLAZADA o PRECISADA, con la DEC que manda. |
| EXT-022 | A | [Guía de estilo §10.3](../../diseno/guia-de-estilo.md) frente a S-29, C7 y C15 | La guía describe el aviso agrupado de otra forma que S-29 (parte C). | La guía: "⚡ 12 oportunidades en la última hora". Con S-29 el agrupado lleva solo los acumulados (2 en C7 y C15) y sale cuando la cuenta baja de 10. Además, ⚡ es el emoji de "Comprar ya" y el grupo puede traer "Muy recomendable". | Encabezado "N oportunidades acumuladas", con el emoji del nivel más alto del grupo y la cita de S-29. |
| EXT-023 | E | REQ §4 ("arquitectura v1.3") y §9; inspección R-05 | El REQ manda tratar la arquitectura como desactualizada. | La vigente es la v2.0 y ya refleja las RN v2 (C-42) y DEC-173 a DEC-190. Un analista puede ignorar la §8 (contrato) o la §7 (modelo de datos). | Cambiar a v2.0, quitar la lista de diferencias de §9 y actualizar R-05. |
| EXT-024 | E | [flujo-general.md](../flujo-general.md) §5 y §7 | Cita REQ que ya no existen. | `oip-arquitecto` aparece "previsto: REQ-2026-0003". El plan de §7 sigue con REQ-0002, 0003 y 0004, y con REQ-0001 como "lógica + Keepa". Todo eso quedó absorbido por DEC-081 y D-018. | Rehacer §7 con las partes A a D y decir que `oip-arquitecto` se crea cuando una parte toque un ADR. |
| EXT-025 | E | Registro: encabezado, DEC-081 y §10 | El registro tiene cosas viejas marcadas como vigentes o pendientes. | Dice "Versión 1.3" aunque ya tiene §9.4. DEC-081 sigue "pendiente de aplicar" y con tres partes. §10 lista como abiertas tareas ya hechas (aplicar la parte D, aplicar A/B/C, leer el REQ v2, crear el Project, separar las referencias de RN-002) y dice "la vigente es la v1.4". | Subir la versión, dejar DEC-081 VIGENTE con las partes A a D y tachar lo hecho en §10. |
| EXT-026 | E | `docs/negocio/revisiones/` (las 18 revisiones) | Las revisiones tienen defectos abiertos que ya se corrigieron. | Unos 12 defectos "documento técnico…" los cerró la arquitectura v2.0: RN-001 D-008, RN-002 D-003, RN-003 D-004, RN-004 D-006, RN-005 D-006, RN-006 D-008, RN-007 D-005, RN-008 D-009, RN-009 D-012, RN-010 D-009, RN-011 D-010 y RN-018 D-007. RN-002 D-012 ya está corregido en el texto de la RN (mínimo de $109). `oip-revisor-rn` solo corre cuando cambia una RN, así que nadie los cierra. | Una pasada de `oip-revisor-rn` que cierre lo resuelto, y un disparador nuevo: "cambió la arquitectura". |
| EXT-042 | A/E | [docs/negocio/casos/](../../negocio/casos/); DEC-136 | Los casos no se actualizaron a las RN v2, y según DEC-136 cada caso se va a volver una prueba automática. | CASO-001 está marcado "ESCENARIO DE PRUEBA … reglas vigentes", pero usa la clase "Sin clasificación de oferta" (no existe en RN-012) y datos de un comparador (DEC-154: solo son señal). CASO-004 espera DESCARTADA, pero su descuento real de 20.3% da SOLO_REFERENCIA con RN-003 v2. CASO-006 calcula el margen % sobre $70; con RN-001 v2 y S-14 la base es $79.50, así que da 39.0%, no 44.3%. CASO-002 a 006 siguen "EN ANÁLISIS" aunque sus decisiones se tomaron (DEC-145 a DEC-171), y CASO-004 cita "90 días para Amazon". | Actualizar el estado y el resultado esperado de cada caso con las RN v2, o marcarlos "antecedente, no es prueba" hasta hacerlo. |

### BAJA

| ID | Cat. | Dónde | Hallazgo | Evidencia | Corrección mínima |
|---|---|---|---|---|---|
| EXT-027 | E | REQ §9 ("RN-001 · P3, P4, P6") frente a §13 ("P1, P2"); RN-001 §4 frente a §12; arquitectura §14.2 | La cita "RN-00X · P#" (DEC-093) cambia de significado entre versiones de la RN. | En RN-001 v2, "P1" y "P2" del cuerpo son "otros costos" y "margen %", y las preguntas abiertas de §12 también se numeran 1 y 2. | Citar con la versión ("RN-001 v1 · P3") o no renumerar §12. |
| EXT-028 | A | Guía §7.2 y DEC-131 frente a RN-012 | Falta la apariencia de la clase "Precio normal" (RN-012 D-006 sigue abierto). | — | Agregar la fila. |
| EXT-029 | A | Guía §10.2 | Hay dos detalles del aviso que no encajan con el REQ. | La marca "⚠️ No confirmada" no puede salir en un aviso: esa oferta va a revisión manual sin aviso (RN-009 §4.1, REQ §3.2.3). "Registrar visita" no tiene la opción "confirmado por llamada" (REQ §3.3 punto 6). | Quitar la marca y agregar la opción. |
| EXT-030 | A | [Arquitectura §3.1](../../arquitectura/arquitectura-tecnica.md) | "Los no nuevos solo se evalúan en venta local" está escrito como hecho. | Es el supuesto S-12 del REQ, todavía por validar. Ni DEC-149 ni RN-014 lo dicen ("por confirmar con la cuenta de vendedor"). | Citarlo como supuesto. |
| EXT-031 | C | B18 y B24; RN-012 | B18 y B24 dependen de datos que no dan, y la calidad de un usado no está definida. | El castigo de 10% supone que no hay mínimo de 60 días en Amazon, pero el "Dado" no lo dice; con un mínimo, el castigo local sería 0 (S-05). Ninguno de los dos da la calidad del precio, y RN-012 no la define para usados (el mercado hoy es de nuevos). | Agregar "sin datos de Amazon" al "Dado" y definir la calidad para usados, o decir que no aplica. |
| EXT-032 | C | RN-002 §4.1; RN-012 ("2 comercios además del evaluado"); D1 | No está claro si otra sucursal, o la tienda en línea de la misma cadena, cuenta como "otro comercio". | D1 cuenta Walmart en línea como mercado hoy de Walmart Chula Vista sin que haya liquidación; RN-002 da a entender que solo cuenta en liquidación. | Definir "comercio = cadena", y si su precio en línea cuenta siempre. |
| EXT-033 | C | RN-006 §4.1 | Las comisiones con umbral usan las mismas palabras con sentidos distintos. | "8% hasta $10; 15% si el precio es mayor" se aplica al precio completo; "16% hasta $1,500; 3% sobre el excedente" se aplica por tramos. | Redactar sin ambigüedad: "si el precio total es de $10 o menos, 8% del total". |
| EXT-034 | F | `oip-inspector` y `oip-revisor-rn` ("rehaz con python3") | En el equipo de Jesús, `python3` abre la Microsoft Store; funciona `py -3`. | Un agente que no lo note puede saltarse las cuentas. | Decir "`py -3` en Windows o `python3`", o fijarlo en `CLAUDE.md`. |
| EXT-035 | F | `oip-tester`, control 1; `oip-developer` | `IMPLEMENTATION READY` no tiene soporte. | No dice si es una etiqueta, el cuerpo del PR o la traza del REQ, ni quién lo cambia al corregir. | Una etiqueta de PR que pone el developer y quita el tester. |
| EXT-036 | F | DEC-071; hook de commits (flujo-general §3); historial de git | Los commits de documentación no llevan `Refs:` ni `Change:`; el hook los bloquearía. | Los cambios de docs o de RN no tienen `change-id`. | Definir la excepción (por ejemplo, `Change: docs`) antes de instalar el hook. |
| EXT-037 | F | Gates G1 a G5; comentarios de #2 y #3 | Las aprobaciones de Jesús no se distinguen de un texto del agente. | Todos los comentarios, incluida la "Decisión de Jesús" en #3 y los vistos buenos G2, salen de la cuenta de Jesús con el pie "Generated by Claude Code". | G3 y G4 como aprobación del PR en GitHub. G2 con una etiqueta que pone Jesús, o un comentario suyo sin el pie. |
| EXT-038 | E | [flujo-general.md](../flujo-general.md) §4 y §10; [flujo-negocio-a-requerimiento.md](../flujo-negocio-a-requerimiento.md) §7 y §8; PR #10 | Varios datos de proceso no coinciden entre sí. | flujo-general §4 dice "Closes #2" y una rama `feat/<N>-<id>`; `oip-developer` dice que solo la última tarea lleva `Closes` y que la rama incluye la tarea. flujo-general §10 pone #2 y #3 en "Análisis", pero la inspección v7 vio el último movimiento a "Inspección". flujo-negocio-a-requerimiento sigue con el estado del 2026-11-08. El PR #10 sigue abierto aunque lo reemplazó el #12. | Alinear los textos con `oip-developer`, confirmar la columna del Project y cerrar el PR #10. |
| EXT-039 | E | [oip-revisor-rn.md](../../../.claude/agents/oip-revisor-rn.md), Salida | El agente manda actualizar "14. Estado de inspección". | En la plantilla y en las 18 RN la sección se llama "14. Revisión de consistencia". | Corregir el nombre en el agente. |
| EXT-040 | D | DEC-091 (sitio en Vercel sin contraseña) | El sitio público describe la postura de acceso. | RN-010 §4.5 explica el VPS y el bloqueo desde la casa, con las tiendas y la zona de la garita. Tiene `noindex`, pero no está registrado como riesgo aceptado. | Registrar el riesgo, o escribir de forma genérica las secciones operativas. |
| EXT-041 | G | REQ §7 (API) y §3.2 paso 3 (MSRP) | Dos piezas no tienen un papel claro. | La API de solo lectura no tiene parte asignada (C13 la prueba en la parte C). El MSRP no entra en ningún cálculo de B: B6 lo da y no influye. | Asignar la API a la parte C y decir que en B el MSRP solo se muestra. |

## 3. Cuentas rehechas

Con `Decimal` y `ROUND_HALF_UP`: montos a centavos y porcentajes sin redondear para comparar (DEC-060). **Todas cuadran.**

- **B1:**
  - Compra: impuesto 2.25, costo de compra 31.25.
  - Amazon: comisión 17.85, costo de venta 33.85; neto 53.90 (172.5%); devoluciones 4.17, castigo 5.00; ajustado 44.73 (143.1%); 3 unidades, 37 días, rendimiento 116.1%, total 134.19.
  - Venta local: venta 91.04, neto 50.29 (160.9%), 2 unidades, total 100.58.
  - Diferencia 25.0%: gana Amazon.
- **B2:**
  - Compra: 85.12.
  - Amazon: neto 27.53 (32.3%); ajustado 17.31 (20.3%); rendimiento 16.5%; sin nivel.
  - Venta local: venta 116.10; neto 21.48 (25.235% sin redondear, así que alcanza Vigilar); total 42.96.
- **B3:** −11.85 en Amazon y −14.22 en venta local.
- **B4:** compra 29.09; venta local 49.50; neto 10.91 (37.5%); Recomendable.
- **B9:**
  - Amazon baja a Recomendable, con tope 3 y total 134.19.
  - Venta local: venta 75.74, neto 34.99 (112.0%).
  - Diferencia 47.9%.
- **B12:** total 89.46; diferencia 11.1%; gana la venta local.
- **B13:** 51 días; rendimiento 84.2%.
- **B14:**
  - Amazon: neto 59.00; ajustado 46.62 (149.2%); rendimiento 121.0%; total 139.86.
  - Venta local: total 108.22.
  - Diferencia 22.6%.
- **B15:** ajustado 7.41 en Amazon y 9.87 (11.6%) en venta local.
- **B16:** ajustado 15.31 (18.0%).
- **B18:** valor de referencia 110.50; descuento real 36.7%; ajustado 0.50.
- **B23:** −9.12.
- **B24 (c):** neto 14.50 (18.2%); ajustado 4.15 (5.2%).
- **B25:** 0 ventas al mes para Jesús.
- **B26 (b):**
  - Amazon: ajustado 36.73 (117.5%); total 110.19; rendimiento 95.3%.
  - Diferencia 8.7%: desempata el rendimiento y gana la venta local.
- **B27:** comisión 27.20; devoluciones 18.70.
- **C1 a C5:**
  - Viaje típico 55; ganancias del viaje 79.19, 122.15, 45.58 y −12.04.
  - Viaje a Los Ángeles 200, que deja 180 o 100.
  - Baja de precio de 6.9%.
- **C10:** mediana de 10 días.
- **C7, C15 (a, b, c, d) y la variante de C7 en la que el agrupado no cuenta:** coinciden con el REQ.
  - C7: agrupados a las 11:02 y a las 11:06.
  - C15 (b): agrupados a las 10:17 y a las 11:02.
  - C15 (c): agrupado a las 11:02.
  - C15 (d): agrupados a las 10:17 y a las 10:32.
- **D1:** ahorro 30.00; costos aparte 64.50; límites 335.58 y 304.98.
- **D5:** ahorro de 11.7%.
- **A1:** 50 y 62.5 min.
- **A2:** 26.7% y 16.7%.
- **Ejemplos de las RN:** RN-016 B 113.99; RN-008 C 67.50 y 26.50; RN-006 E 52.50; RN-012 A 20.3%.
- **Casos:**
  - CASO-004: descuento real 20.3%.
  - CASO-005: compra máxima 75.50.
  - CASO-006: margen 31.00, que es 44.3% sobre $70 y 39.0% sobre $79.50 (EXT-042).
- **Redondeo (EXT-013):** con una venta de $149.50, las devoluciones dan 5.24 o 5.23 según dónde se redondee; con $10.03, la venta local da 7.68 o 7.67.

## 4. Preguntas que solo Jesús o el experto pueden responder

**Jesús**
1. Producto sin precio de venta en Amazon (EXT-002): ¿Amazon queda cerrado y se evalúa solo la venta local, o queda por revisar y la oferta va a revisión manual?
2. Sin historial suficiente y con margen negativo en todos los canales (EXT-004): ¿la oferta se descarta o va a revisión manual?
3. ¿Una oferta en Amazon puede ser origen de compra, es decir, comprar en Amazon y vender en local? Y si cambia una referencia de precio, ¿se reevalúan las oportunidades vigentes? (EXT-009)
4. En B9 gana el canal de menor nivel: Amazon Recomendable contra venta local Muy recomendable. El aviso pasa de inmediato a resumen. ¿Es lo que se quiere, o el aviso debe usar el nivel más alto?
5. ¿Cómo se capturan los datos en el Inc. 1: formulario, Telegram o un archivo que se carga? (EXT-006)
6. ¿Se congelan las versiones de las RN mientras se construye la parte B? (EXT-015)
7. Impuesto: en las tablas del estado (CDTFA), Chula Vista y National City aparecen con más de 7.75% (alrededor de 8.75%; hay que verificarlo). ¿Se carga la tasa por tienda desde ya? Con 8.75%, la compra de B1 pasa de $31.25 a $31.54.

**Experto**
8. Precio "habitual": ¿cuentan los días en que el producto ya estaba en esa misma liquidación?
9. Además del costo por paquete del PO Box, ¿cuánto cuesta ir a recoger a San Diego? Hoy el modelo lo pone en $0, y en B4 el margen ($10.91) apenas pasa el mínimo de $10.
10. ¿Contra qué se dice que un usado es "buena oferta"?
11. ¿Basta el ranking de Amazon del día, o hay que esperar a tener 7 días de datos?
12. ¿De qué tabla pública sale el tamaño de cada categoría de Amazon, y quién la actualiza cada mes?

## 5. Siguiente paso sugerido

1. **Etapa 3 mínima** (EXT-001), que ya incluya la regla de los agentes y las reglas `deny` (EXT-003).
2. **REQ v2.6:**
   - con las respuestas a las preguntas 1 a 4;
   - con EXT-004, 005, 007 a 010 y 013;
   - con las referencias a la arquitectura v2.0 (EXT-023).
3. **Reinspección v8**, solo de los puntos que cambian.
4. **Análisis de la parte B** con `oip-analista`. Los MEDIA que no se resuelvan en la v2.6 pasan a "Preguntas" de la propuesta.
5. **Limpieza de documentos**, en un PR aparte y sin bloquear la parte B: EXT-019 a 026, EXT-042 y los BAJA.
