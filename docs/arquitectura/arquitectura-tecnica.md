# Offer Intelligence Platform (OIP)

## Propuesta de alcance, auditoría de repositorios Open Source y arquitectura técnica

**Versión:** 1.4 — referencia de precio por etapas (Keepa diferido), dos repositorios Core y Worker, contratos versionados, IA opcional, operación endurecida, guía de estilo y alineación con las RN v2 (sobre v1.3, sin eliminar contenido: lo modificado se marca *(v1.4)* y conserva la redacción anterior)
> *(v1.4)* Redacción anterior: **Versión:** 1.3 — dos funcionalidades (búsqueda automatizada y búsqueda por artículo), topología Core/Worker, consulta responsable y alineación con las reglas de negocio (sobre v1.2, sin eliminar contenido: lo modificado se marca *(v1.3)* y conserva la redacción anterior)

**Fecha:** 16 de noviembre de 2026 (v1.4) · v1.3: 9 de noviembre de 2026 · v1.2: 8 de noviembre de 2026
**Fuentes de la v1.4:** DEC-123 a DEC-136 (fuentes de mercado), DEC-137 a DEC-172 y las RN v2 (RN-001 a RN-011 v2, RN-012 a RN-018 v1), DEC-173 a DEC-190 (insumo del stack de tickets y guía de estilo). **En reglas de negocio prevalecen las RN**: esta arquitectura las referencia y no copia sus fórmulas completas
**Estado:** Línea base aprobada para construcción por incrementos; decisiones marcadas "PoC" se cierran con datos
**Tipo de producto:** Herramienta interna, uso propio, operación todo el año
**Idioma:** Español

> **Archivo vigente.** La arquitectura vive en un solo archivo; GitHub guarda el historial. Las versiones anteriores se consultan con estos enlaces permanentes (apuntan a un commit fijo y no cambian):
>
> | Versión | Fecha | Dónde |
> |---|---|---|
> | **v1.4** (vigente) | 2026-11-16 | Este archivo |
> | v1.3 | 2026-11-09 | [enlace permanente al archivo único](https://github.com/jjrm2004mx/Offer-Intelligence-Platform-OIP/blob/a00af3f0191d2f78390cd8c4f1c16316214521f9/docs/arquitectura/arquitectura-tecnica.md) · [enlace permanente original](https://github.com/jjrm2004mx/Offer-Intelligence-Platform-OIP/blob/a13c81801642f5ac49958fa92a9fd65e425b5948/docs/arquitectura/OIP_Arquitectura_Tecnica_Integrada_v1.3.md) |
> | v1.2 | 2026-11-08 | [enlace permanente](https://github.com/jjrm2004mx/Offer-Intelligence-Platform-OIP/blob/a13c81801642f5ac49958fa92a9fd65e425b5948/docs/arquitectura/OIP_Arquitectura_Tecnica_Integrada_v1.2.md) |
> | v1.1 y v1.0 | 2026-11-08 | Fuera del repo: documentos del proyecto en Claude y carpeta OIP del Drive (la v1.0 en `otros/`) |

> **Convención de certeza** (se conserva de v1.0): **Verificado** = observado en código/documentación;
> **Propuesta** = decisión arquitectónica recomendada; **PoC** = no se da por resuelto hasta probarlo.

---

## 0. Cambios respecto a v1.0

| # | Cambio | Motivo |
|---|---|---|
| C-01 | **Oportunidad comercial = margen de reventa**, validado contra precio de mercado, no contra el descuento anunciado. | Definición confirmada. Un 90% de descuento declarado puede ser falso o irrelevante. |
| C-02 | Se agrega todo el **lado de venta**: referencia de mercado (Amazon vía Keepa), match por UPC/GTIN, comisiones, restricciones, demanda. | v1.0 solo diseñaba la compra. |
| C-03 | Se agrega **tienda física** (radio San Diego) con inventario por sucursal y **costo de traslado** en el margen. | Muchas liquidaciones fuertes son solo en tienda. |
| C-04 | Núcleo en **Python (FastAPI)** en lugar de Java/Spring Boot. | Java no es requisito; un solo lenguaje para núcleo y crawling. |
| C-05 | **PriceGhost descartado.** | Sin commits desde 2-feb-2026, 2 autores, sin archivo LICENSE (solo "MIT" en README). |
| C-06 | **PriceStalker sale del núcleo**; queda como candidato opcional detrás de un adaptador, fijado en v2.0.0. | Joven (ene-2026), alta rotación (main en 2.2.0-beta), runtime Node adicional, doble extracción de precio. |
| C-07 | **Capacidad anti-bot (stealth) es requisito**; se elimina "no evadir controles" del fuera de alcance y se registra como riesgo aceptado. | Decisión del dueño del producto. |
| C-08 | **Un solo motor de navegador** (Playwright). | Elimina el segundo runtime (Puppeteer). |
| C-09 | **RabbitMQ y changedetection.io pasan a fase posterior.** Scrapyd + ingesta REST en el arranque. | Volumen inicial no lo justifica. |
| C-10 | Alertas por **Telegram** desde el primer incremento, además del dashboard. | Las ofertas fuertes duran horas. |
| C-11 | Despliegue en **Rocky Linux + Podman rootless con Quadlets** (systemd). | Plataforma objetivo. |
| C-12 | Se agregan OSS de apoyo: **extruct, price-parser, Spidermon, Scrapyd**. | Atacan directamente R-01, R-02, R-03 de v1.0. |
| C-13 | Correcciones editoriales: numeración duplicada en §20, formatos de tabla mixtos, inconsistencia changedetection "si se incorpora" vs ADR-010. | — |
| C-14 | Logística/costos transfronterizos de venta **fuera del modelo**. | Decisión del dueño del producto. |
| C-15 | *(v1.2)* **Rentabilidad ajustada por tiempo**: días de venta, ROI anualizado, riesgo de caída, devoluciones, unidades. | Rentabilidad real, no aparente. |
| C-16 | *(v1.2)* **Confianza del dato de tienda**, antigüedad, re-consulta previa al viaje, registro de visitas. | La disponibilidad no es inventario garantizado. |
| C-17 | *(v1.2)* **Acceso por fuente** con escalera; stealth apagado por defecto (reemplaza C-07). | Decisión por fuente con datos. |
| C-18 | *(v1.2)* **Egress obligatorio** (VPS → proxy), fail-closed; IP doméstica nunca expuesta. | Requisito duro del dueño del producto. |
| C-19 | *(v1.2)* **Puppeteer como motor alternativo por fuente** detrás de una interfaz de renderizado; se construye solo si la PoC-A lo justifica (matiza C-08). | Algunos comercios pueden detectar un motor y no el otro. |
| C-20 | *(v1.3)* **Dos funcionalidades** con un mismo motor de adquisición: **A. búsqueda automatizada** (reventa) y **B. búsqueda particular por artículo** (servicio a clientes; en el Inc. 1 la captura Jesús). | Retroalimentación del experto (DEC-110 a DEC-114). |
| C-21 | *(v1.3)* **Topología Core local + Scraper Worker remoto** (configurable; solo el worker remoto se construye). Precisa §3.4: la consulta nace en el VPS. | DEC-120. |
| C-22 | *(v1.3)* **Consulta responsable**: límites por dominio, pausas, concurrencia 1, caché, reintentos con espera creciente, timeouts y pausa por bloqueo (nueva §3.5). | DEC-115, RN-010. |
| C-23 | *(v1.3)* **Modo de red de la PoC** (`modo_red: estricto \| desarrollo`) con lista permitida y bloqueo de comercios desde casa por firewall (nueva §3.6). | DEC-121. |
| C-24 | *(v1.3)* **Infraestructura de referencia** del VPS y costos (por verificar); Rocky + Podman también en el VPS. | DEC-118, DEC-119. |
| C-25 | *(v1.3)* **Alineación con las RN** (prevalecen en reglas de negocio): rendimiento mensual en vez de ROI anualizado, niveles por mínimos, precio de venta conservador sin ajuste por competencia, `MARKET_ALREADY_CHEAP` sin condición del 50%, viaje fuera del margen por unidad. | DEC-028; RN-001 a RN-009. |
| C-26 | *(v1.3)* Sugerencias técnicas del experto **no adoptadas**: Java/Spring Boot y Ubuntu + Docker. | DEC-118. |
| C-27 | *(v1.4)* **Referencia de precio por etapas:** historial propio + comparación entre comercios → APIs oficiales → Keepa al final. **Keepa diferido**: no entra en el Inc. 1; cuando entre, solo para Amazon, complementario y contratado por meses. Cada fuente detrás de una interfaz intercambiable, guardando cuál se usó. | DEC-123, DEC-124, DEC-125. |
| C-28 | *(v1.4)* **Tres indicadores** (descuento, competitividad, demanda) y **cuatro referencias** (precio habitual, precio de mercado hoy, MSRP, precio tachado); el descuento real solo contra el precio habitual, con **historial suficiente** (mediana de 60 días, ≥ 5 observaciones en ≥ 3 días). | DEC-128, DEC-129, DEC-130, DEC-147; RN-002 v2. |
| C-29 | *(v1.4)* **Dos ejes de clasificación:** calidad del precio (RN-012) y oportunidad de reventa (RN-009); la búsqueda por artículo usa solo el primero. Niveles renombrados: Comprar ya · Muy recomendable · Recomendable · Vigilar. | DEC-131, DEC-164. |
| C-30 | *(v1.4)* **Comercios del Inc. 1:** Home Depot, Walmart, Target, Best Buy, GameStop, Nintendo Store y la ficha de Amazon; solo EE. UU., USD. | DEC-132. |
| C-31 | *(v1.4)* **APIs oficiales** como escalón `api_feed`; comparadores y sitios de seguimiento **solo como señal**, confirmando cada precio en la ficha del comercio. | DEC-133, DEC-154. |
| C-32 | *(v1.4)* **Datos de cada observación** ampliados (vendedor, estado del producto, estados de disponibilidad en línea, envío, MSRP con fuente y fecha, contenido) y **contrato de ingesta 2.0** (§8). | DEC-134, DEC-169; RN-013. |
| C-33 | *(v1.4)* **Evaluación por canal** (Amazon FBM y venta local) con elección del mejor canal; **3 orígenes × 2 canales**; origen y canal independientes. | DEC-140, DEC-146, DEC-151, DEC-170; RN-016 a RN-018. |
| C-34 | *(v1.4)* **Usados y particulares por captura manual**, con estado obligatorio y valor de usados comparables. | DEC-149, DEC-150; RN-014, RN-015. |
| C-35 | *(v1.4)* **Costos por etapa y VPS creciente** (2 vCPU / 4 GB para arrancar; 4 / 8 al medir > 75% de memoria). | DEC-126, DEC-127. |
| C-36 | *(v1.4)* **Dos repositorios, Core y Worker**; el Core no contiene spiders y un gate lo verifica. | DEC-173; precisa ADR-022. |
| C-37 | *(v1.4)* **Contratos Core ↔ Worker versionados** (N y N-1) y **bandeja de salida** en el Worker. | DEC-174, DEC-175. |
| C-38 | *(v1.4)* **Estados de tareas** con transiciones condicionales, **barrido de recuperación** y estado `HELD`. | DEC-176. |
| C-39 | *(v1.4)* **IA opcional:** el código decide y la IA complementa, con interruptor de tres modos (nueva §5.5). | DEC-177. |
| C-40 | *(v1.4)* **Operación endurecida:** puertos en `127.0.0.1`, migraciones versionadas, Metabase con rol de solo lectura, logs sin contenido, runbook con trampas conocidas. | DEC-178 a DEC-183. |
| C-41 | *(v1.4)* **Guía de estilo** y formato de los avisos de Telegram; los emoji ⚡ ✅ 👍 🛑 🧪 reemplazan 🔴🟠🟡⚪. | DEC-184 a DEC-190. |
| C-42 | *(v1.4)* **Alineación con las RN v2:** franjas del descuento real (20% / 25%), umbrales de niveles y mínimo por unidad, mínimo de 60 días (no 90), pago de Amazon a 30 días (no 14), demanda por percentil de la categoría, zonas desde la garita, confianza en tienda, consulta responsable escalonada. | DEC-155 a DEC-171; RN v2. |

---

## 1. Resumen ejecutivo

OIP es una herramienta interna que **detecta productos que se pueden comprar muy por debajo de su precio real de mercado y revender con margen**. Funciona todo el año, con picos de temporada (Buen Fin, Black Friday, Navidad, regreso a clases, liquidaciones de fin de temporada).

El flujo central:

> **Descubrir ofertas** (online y en tienda física) → **identificar el producto** (UPC/GTIN → ASIN) →
> **obtener su precio real de mercado y demanda** (Amazon/Keepa + otros comercios + historial propio) →
> **descartar descuentos inflados** → **calcular margen neto** (incluyendo comisiones y traslado) →
> **filtrar restricciones** → **alertar** las que superen el umbral.

*(v1.3)* OIP tiene **dos funcionalidades** que comparten el mismo motor de adquisición (API · HTTP · navegador) y los mismos controles de consulta responsable:

| | Funcionalidad | Disparo | Resultado | Reglas |
|---|---|---|---|---|
| **A** | Búsqueda automatizada de ofertas (reventa) | Periódica (scheduler) | Oportunidades con nivel y alertas | RN-001 a RN-009 |
| **B** | Búsqueda particular por artículo (servicio a clientes) | Bajo demanda: Jesús captura la solicitud del cliente | Alternativas ordenadas: la más económica entre las disponibles | RN-011 |

Ambas respetan RN-010 (consulta responsable). *(v1.3)* Topología: **OIP Core** en el servidor de Jesús y **Scraper Worker** en un VPS (§3.4, §9).

Stack: Python (FastAPI + Scrapy + Playwright), PostgreSQL/TimescaleDB, Keepa API, Telegram, desplegado con Podman Quadlets en Rocky Linux. Unos 5–6 contenedores en el primer incremento.

> *(v1.4)* **Flujo vigente:** descubrir ofertas (con filtro previo) → identificar el producto (código de barras o modelo + marca, RN-013) → **referencias de precio del historial propio y de la comparación entre comercios** (RN-002; Keepa diferido, DEC-124) → descuento real y calidad del precio (RN-003, RN-012) → **margen por canal** (Amazon FBM y venta local) → elegir canal (RN-018) → nivel o revisión manual (RN-009) → avisar. **Stack del Inc. 1 sin Keepa**: Python (FastAPI + Scrapy + Playwright), PostgreSQL/TimescaleDB, Telegram, Metabase; Rocky + Podman en el servidor de Jesús (Core) y en el VPS (Worker), en **dos repositorios** (§3.4.1).

---

## 2. Definición de oportunidad comercial

### 2.1 Las tres métricas

| Métrica | Fórmula | Uso |
|---|---|---|
| **Descuento declarado** | `1 − precio_oferta / precio_antes_comercio` | Solo para **descubrir candidatos**. No decide nada. |
| **Descuento real** | `1 − precio_oferta / precio_referencia_mercado` | Decide si de verdad está barato. |
| **Margen neto** | `precio_venta_esperado − costo_total_adquisición − costo_venta` | Decide si conviene comprarlo. |

Donde:

```
costo_total_adquisición = precio_oferta + impuesto_venta + costo_traslado (tienda física) + costo_envío_a_mí (online)
# (v1.3) Alineado con RN-001/RN-008: el costo_traslado NO entra en el margen por unidad;
#        se evalúa por viaje completo (RN-008). Por unidad: precio + impuesto + envío hacia mí.
costo_venta             = comisión_canal + envío_al_cliente (FBM) + empaque + otros_costos_venta (default 0)
margen_neto_%           = margen_neto / costo_total_adquisición
```

> *(v1.4, alineado con RN-001 v2, RN-003 v2 y DEC-128)* Son **tres indicadores que no se mezclan**: **descuento** (contra el precio habitual, RN-003), **competitividad** (contra el precio de mercado hoy, RN-012) y **demanda** (RN-004 y RN-017). El margen se calcula **por canal**: `costo de compra = precio + impuesto + envío hacia mí` (más la recogida en compras a particulares, RN-008); `costo de venta` = comisión + envío al cliente + empaque (Amazon, RN-006) o costo de entrega (venta local, RN-008). Margen % sobre lo invertido. Las compras en línea van a un **PO Box en San Diego** (impuesto de esa zona; dirección pendiente) y la cuota mensual de Amazon es un gasto fijo fuera del margen por unidad (DEC-156). Montos con `Decimal`, a centavos con el medio centavo hacia arriba; porcentajes sin redondear para calcular y comparar (DEC-060).

### 2.2 Precio de referencia de mercado

Se calcula con varias fuentes y se guarda cuál se usó:

1. **Amazon — precio habitual:** mediana de 90 días del precio Buy Box / nuevo (Keepa).
2. **Amazon — precio actual** (Keepa; SP-API cuando haya cuenta de vendedor).
3. **Otros comercios seguidos por OIP:** precio vigente del mismo producto en Walmart/Target/HD/etc.
4. **Historial propio del comercio que oferta:** mediana de los últimos 60 días en ese comercio.

`precio_referencia_mercado` = mínimo razonable entre (1) y (3) — el precio al que el comprador final puede conseguirlo hoy. `precio_venta_esperado` = (1) ajustado por competencia actual (número de vendedores, Buy Box).

> *(v1.3, alineado con RN-002)* `precio_referencia_mercado` = **el más bajo** entre (2) Amazon hoy, (1) mediana de 90 días y (3) otros comercios con dato ≤ 48 h. `precio_venta_esperado` = **el más bajo entre (2) y (1)**, sin ajuste por competencia (la competencia se evalúa en la demanda, RN-004). Sin oferta de Amazon hoy: se usa la mediana y la evaluación va a revisión manual (REQ-2026-0001 §3.3).

> *(v1.4, alineado con RN-002 v2, DEC-123, DEC-129, DEC-147 y DEC-157)* **Cuatro referencias separadas:** **precio habitual** (mediana de 60 días del historial propio, con historial suficiente, DEC-130) para el descuento real; **precio de mercado hoy** (el más bajo de hoy, dato ≤ 48 h, disponible, sin la oferta evaluada) para la competitividad; **MSRP** solo sin historial (la calidad no pasa de "Precio competitivo"); **precio tachado**, que nunca es referencia. **Precio de venta en Amazon** = botón de compra hoy; sin oferta hoy, precio habitual en Amazon marcado "sin oferta hoy" (ya **no** va a revisión manual). **Competencia más barata** (mercado hoy < venta en Amazon × 85%) baja un nivel en el canal Amazon. **Fuentes por etapas:** historial propio + comparación entre comercios → APIs oficiales → Keepa al final, detrás de una interfaz `PriceReferenceSource` que guarda la fuente usada.

### 2.3 Reglas anti-descuento inflado (Verificables con datos propios)

| Flag | Regla | Efecto |
|---|---|---|
| `INFLATED_WAS_PRICE` | `precio_antes_comercio` > 1.5 × mediana 60 días del propio comercio | Se ignora el descuento declarado |
| `MARKET_ALREADY_CHEAP` | descuento real < 20% aunque el declarado sea ≥ 50% · *(v1.3, RN-003: descuento real < 20%, **sin** condición sobre el declarado)* | Descartada (caso "lámpara") |
| `NO_MARKET_REFERENCE` | sin match en Amazon ni en otros comercios | A revisión manual, no alerta |
| `LOW_MATCH_CONFIDENCE` | match por título/similitud, sin UPC/GTIN | A revisión, no alerta automática |

**Ejemplo (lámpara):** Walmart anuncia antes $200, ahora $20 (90% declarado). Amazon la vende habitualmente en $22. Descuento real 9%, margen negativo tras comisión → `MARKET_ALREADY_CHEAP`, descartada.

> *(v1.4, alineado con RN-003 v2, RN-013 y DEC-158)* **Filtro previo** en el descubrimiento: descuento anunciado ≥ 40%, marca reconocida y categoría acordada (no califica la oferta). **Franjas del descuento real:** < 20% → `MERCADO YA BARATO` (descartada); 20% a < 25% → `SOLO REFERENCIA` (solo tablero); ≥ 25% → sigue. `PRECIO ANTES INFLADO`: tachado > 1.5 × mediana de 60 días de esa tienda (con historial suficiente). Sin precio habitual: `SIN HISTORIAL SUFICIENTE` → revisión manual. Identificación solo por nombre: `COINCIDENCIA NO CONFIRMADA` → revisión manual (equivalen a `NO_MARKET_REFERENCE` y `LOW_MATCH_CONFIDENCE`). Los nombres de las marcas en el código siguen las RN.

### 2.4 Niveles (configurables)

Aplicados sobre **descuento real**, con margen neto mínimo y demanda mínima:

| Nivel | Descuento real | Margen neto mínimo | Acción |
|---|---|---|---|
| 🔴 Excepcional | ≥ 80% | ≥ 50% y ≥ $X | Alerta inmediata Telegram |
| 🟠 Muy buena | 70–79% | ≥ 40% | Alerta inmediata |
| 🟡 Buena | 50–69% | ≥ 30% | Resumen periódico |
| ⚪ Interesante | 40–49% | ≥ 25% | Solo dashboard |

Valores iniciales; se calibran con datos reales. `$X` = margen absoluto mínimo para que valga el esfuerzo (traslado, tiempo).

> *(v1.3, alineado con RN-009)* Los niveles se definen por **mínimos** (no por rangos): se asigna **el nivel más alto cuyas dos condiciones se cumplan** (descuento real ≥ X y margen **ajustado** ≥ Y). Mínimo absoluto: **$10 por unidad**. Avisos: Excepcional y Muy buena inmediatos; Buena en resumen (8:00 y 18:00); Interesante solo en el tablero.

> *(v1.4, alineado con RN-009 v2, DEC-164 y DEC-189)* **Niveles por canal** (mínimos de descuento real y margen ajustado %): ⚡ **Comprar ya** ≥ 80% / ≥ 50% (inmediato) · ✅ **Muy recomendable** ≥ 70% / ≥ 40% (inmediato) · 👍 **Recomendable** ≥ 50% / ≥ 30% (resumen 8:00 y 18:00) · **Vigilar** ≥ 25% / ≥ 25% (solo tablero). **Mínimo por unidad:** el mayor entre $10 y 10% del costo de compra. **Precedencia:** DESCARTADA > SOLO REFERENCIA > REVISIÓN MANUAL > nivel (la revisión manual guarda su nivel calculado). Un aviso por cadena; no se repite en 24 h salvo que suba de nivel o el precio baje ≥ 5%. Los emoji 🔴🟠🟡⚪ de la tabla de arriba quedan **reemplazados** (el rojo se reserva para problemas operativos, 🛑); formato completo en la guía de estilo §10. **Dos ejes visibles a la vez** (DEC-131, DEC-186): nivel (RN-009) y calidad del precio (RN-012: Oferta excepcional · Buena oferta · Precio competitivo · Descuento cuestionable · Precio normal).

### 2.5 Demanda ("lo que la gente mueve")

- **Ranking de ventas Amazon (BSR)** actual y tendencia 30/90 días (Keepa).
- Número de ofertas/vendedores activos (saturación).
- Umbral de BSR por categoría (configurable). Un producto barato que nadie compra no es oportunidad.

> *(v1.4, alineado con RN-004 v2, RN-017 y DEC-159)* **Demanda en Amazon SUFICIENTE** = ranking en la categoría principal ≤ **0.5% del total de artículos** de la categoría (relojes y joyería: además primeros 100 de la subcategoría) **y** ≤ 20 vendedores de nuevo; promedios de 7 días; `DEMANDA A LA BAJA` si empeora > 50% contra hace 30 días (advertencia). Sin ranking o sin vendedores → `DEMANDA DESCONOCIDA` (canal Amazon "por revisar"). Demanda insuficiente **cierra el canal Amazon, no la oferta**: se evalúa la venta local. **Demanda local** (RN-017): alta 7 días por unidad, media 14 (valor inicial), baja → canal local no viable; se recalibra con 5 ventas reales. Sin Keepa, el ranking, los vendedores y "N+ comprados el mes pasado" salen de la **ficha de Amazon** consultada por el Worker.

### 2.5.1 Rentabilidad ajustada por tiempo

Un margen alto que tarda meses en venderse puede valer menos que uno moderado que se vende en días. Se agregan:

| Métrica | Cálculo | Uso |
|---|---|---|
| `dias_estimados_venta` | Función de BSR, número de vendedores y unidades a vender (Keepa) | Estimado, se calibra con `opportunity_outcome` |
| `roi_anualizado` | `margen_neto_% × (365 / dias_estimados_venta)` | **Ordena** las oportunidades |
| `riesgo_caida_precio` | Volatilidad del precio Amazon 90 días | Penaliza el margen esperado |
| `unidades_recomendadas` | Máximo vendible en N días según demanda | Evita sobrecomprar |
| `tasa_devolucion` | % configurable por categoría | Se descuenta del margen |

`margen_neto_ajustado = margen_neto − (precio_venta_esperado × tasa_devolucion) − (precio_venta_esperado × riesgo_caida_precio)`

Los niveles de §2.4 se evalúan sobre `margen_neto_ajustado`; el dashboard y las alertas se ordenan por `roi_anualizado`.

> *(v1.3, alineado con RN-005)* Se reemplaza `roi_anualizado` por **`rendimiento_mensual` = margen ajustado % × 30 ÷ días para recuperar** (días de venta según ranking 7/21/45 + 14 días de pago de Amazon). Fórmula vigente del margen ajustado: `margen_neto − (precio_venta_esperado × tasa_devolucion × pérdida_por_devolución) − (precio_venta_esperado − mínimo_90d) × 50%`; sin mínimo de 90 días, castigo = 10% del precio de venta esperado. Unidades recomendadas = ventas al mes ÷ (vendedores + 1), con tope.

> *(v1.4, alineado con RN-005 v2 y DEC-160)* Por canal: costo por devoluciones = venta × tasa × pérdida (Amazon; local 0%); castigo por baja = 50% × (venta − **mínimo de 60 días** en Amazon), sin mínimo 10% de la venta; **días para recuperar** = días de venta (Amazon por ranking 7 / 21 / 45; local según RN-017) + **días de pago** (Amazon **30** con cuenta nueva, 21 con historial; local 0). Unidades = el menor entre ventas al mes que le tocan a Jesús, disponibles, límite por cliente y **tope de primera compra** (3; 5 en casos muy buenos), que se levanta con resultados reales. Menos de 1 venta al mes → canal cerrado (`SIN ROTACIÓN`).

### 2.6 Restricciones de venta

Antes de alertar, marcar:

- Categorías/marcas que requieren aprobación en Amazon (joyería y relojes suelen requerirla — **confirmar en Seller Central**).
- Posible clasificación de materiales peligrosos/hazmat (perfumes, aerosoles, baterías) — **confirmar**.
- Productos restringidos por marca.

Sin cuenta de vendedor: tabla manual configurable. Con cuenta: adaptador SP-API (ya preparado, desactivado).

> *(v1.4, alineado con RN-006 v2, RN-015 y DEC-161)* Restricciones en **tres niveles** (categoría, marca, producto), material peligroso, caducidad (fuera de alcance), usados en categorías sensibles y juguetes en temporada. **Restringido en Amazon → se evalúa la venta local.** Lista de productos que se **evitan siempre** (→ DESCARTADA) y riesgo de procedencia (→ revisión manual). Envío FBM por peso y empaque por tabla, cotizando lo que pase de 6 kg.

### 2.7 *(v1.4)* Canales de venta y elección del mejor canal

Cada oportunidad se evalúa **por canal** y se elige uno (RN-018, DEC-140, DEC-151, DEC-170). Origen de compra y canal de venta son **independientes** (DEC-146).

| | Orígenes de compra (Inc. 1) | Canales de venta (Inc. 1) |
|---|---|---|
| 1 | Tienda en línea (envío al PO Box o recoger en tienda) | **Amazon FBM**: comisión, envío y restricciones estimados con tabla manual (sin cuenta de vendedor) |
| 2 | Tienda física | **Venta local** (OfferUp, Facebook Marketplace y venta personal): precio estimado de RN-016 (estimado de Jesús o 85% del mercado hoy, con techo de comparables y 10% de negociación) |
| 3 | Particulares, por captura manual (DEC-150) | — |

- **Estado de cada canal:** cerrado, por revisar o disponible (REQ-2026-0001 §3.2.1). Un canal cerrado no cierra la oferta.
- **Elección:** mayor ganancia total del lote (margen ajustado × unidades); si la diferencia contra la mayor es < 10%, desempata el rendimiento mensual.
- El tablero muestra **los dos canales** con sus números; el aviso usa el del canal elegido.
- **Compra por oportunidad** (DEC-141): se puede comprar por precio excepcional y conservar el producto hasta encontrar comprador; el riesgo de inventario se mide con los días para vender y el rendimiento mensual.

---

## 3. Alcance

### 3.1 Dentro del alcance

| Dimensión | Alcance |
|---|---|
| Operación | Todo el año; perfiles de temporada (frecuencia mayor en Buen Fin, Black Friday, Navidad, liquidaciones). |
| Comercios | Arranque: **Home Depot, Walmart, Target**. Después: otros comercios reconocidos por categoría. Cada comercio = conector configurable. |
| Categorías | Herramientas (prioridad), hogar/iluminación, tecnología, juguetes, relojes, joyería, perfumes. Abierto: cualquier categoría "que se mueva". |
| Canales de compra | **Online** y **tienda física** en radio configurable (inicial: zona San Diego). Más allá, solo si el margen absoluto lo justifica. |
| Canales de venta | **Amazon FBM** (referencia principal) y **Facebook Marketplace** (precio estimado, fase posterior). |
| Notificación | Telegram + dashboard. |
| *(v1.3)* Funcionalidades | **A.** Búsqueda automatizada de ofertas (reventa). **B.** Búsqueda particular por artículo, servicio a clientes: en el Inc. 1 el cliente pide a Jesús y Jesús captura en OIP; la solicitud directa del cliente (p. ej. WhatsApp) es futura. |
| *(v1.3)* Comercios para la búsqueda por artículo | Home Depot, Walmart y Amazon (precio de nuevo vía Keepa); ampliable. |
| *(v1.4)* Comercios del Inc. 1 | **Home Depot, Walmart, Target, Best Buy, GameStop, Nintendo Store** y la ficha de Amazon, para las dos funcionalidades; solo tiendas de EE. UU. y USD (DEC-132). Target se adelanta del Inc. 2 |
| *(v1.4)* Orígenes y canales | 3 orígenes (en línea, tienda física, particulares por captura manual) × 2 canales (Amazon FBM y venta local) (DEC-151, §2.7) |
| *(v1.4)* Estado del producto | Nuevo, caja abierta, reacondicionado, usado, para piezas; los no nuevos solo se evalúan en venta local en el Inc. 1 (DEC-149, RN-014) |
| *(v1.4)* Categorías | Las que más consume la gente, priorizadas por temporada (DEC-138, DEC-153), con operación todo el año |
| Seguimiento | Precio, disponibilidad (online y por tienda), historial. |
| Administración | Comercios, tiendas, categorías, frecuencias, umbrales, tabla de comisiones/restricciones. |

### 3.2 Fuera del alcance (por ahora)

- Compra automática / carrito / checkout.
- Publicación automática en Amazon o Facebook (fase futura; el adaptador de Amazon queda preparado).
- Resolver CAPTCHA mediante servicios de terceros (se registra el bloqueo y se reintenta más tarde).
- Sesiones con cuentas personales de las tiendas.

### 3.3 Acceso a comercios: decisión por fuente

La capacidad stealth existe en la capa de navegador, pero **está apagada por defecto en todas las fuentes**. Cada fuente tiene un `access_mode` y sube la escalera solo con datos:

| Escalón | `access_mode` | Cuándo |
|---|---|---|
| 0 | `api_feed` | Existe API/feed/sitemap utilizable (p. ej. API de afiliados de Walmart — confirmar acceso y datos) |
| 1 | `http` | Página entrega los datos sin JavaScript |
| 2 | `browser` | Requiere renderizado; navegador normal |
| 3 | `browser_stealth` | Solo si la tasa de bloqueo medida inutiliza la fuente **y** no hay alternativa en escalones 0–2 |

Reglas:

- Subir a `browser_stealth` es un **cambio manual de configuración** del dueño del producto, registrado con fecha y motivo; el sistema mide la tasa de bloqueo antes/después.
- Si el bloqueo supera el umbral incluso en el escalón 3, la fuente **se pausa sola** y avisa por Telegram.
- Frecuencias conservadoras por dominio y jitter; backoff automático.
- Métrica de **tasa de bloqueo por fuente y escalón** desde el día uno.
- Riesgo aceptado para fuentes en escalón 3: posible incumplimiento de términos de uso (ver R-09).

> *(v1.4, DEC-133 y DEC-154)* Las **APIs oficiales** de los comercios (Amazon, Walmart u otros) entran por el escalón **`api_feed`** cuando se autoricen. Un **comparador de precios** o un sitio de seguimiento puede **señalar** una oferta, pero nunca es dato de historial ni de precio: cada precio se confirma en la ficha del comercio. Activar stealth sigue siendo el gate **G5** de Jesús.

### 3.3.1 Motor de navegador por fuente

Los spiders no invocan un navegador concreto: piden el renderizado a una interfaz `BrowserRenderer`. El motor se elige por fuente con `browser_engine`:

- **`playwright`** (por defecto): integrado en los workers Scrapy vía scrapy-playwright.
- **`puppeteer`** (alternativa): servicio Node.js aparte (`oip-renderer-puppeteer`) que recibe la URL por HTTP y devuelve el HTML. Su tráfico también sale solo por `oip-egress`.

El servicio Puppeteer **no se construye en el arranque**; se construye solo si la PoC-A encuentra una fuente que pasa con Puppeteer y no con Playwright. La escalera de acceso (§3.3) aplica igual con cualquier motor.

### 3.4 Protección de la IP doméstica (requisito duro)

**La IP de la casa nunca debe usarse para scraping.** Esto se garantiza por topología de red, no por configuración:

- Los contenedores de crawling viven en una red Podman **interna sin salida a Internet**. Su única ruta es el contenedor `oip-egress`.
- `oip-egress` envía el tráfico por **WireGuard a un VPS** (MVP) o a un **proveedor de proxies** (volumen). Cambiar de uno a otro es configuración del egress, sin tocar spiders.
- **Fail-closed:** si el túnel/proxy cae, los spiders quedan sin conectividad. Nunca hay fallback a la conexión directa.
- **Verificación al arrancar cada job:** el spider consulta su IP pública; si coincide con la IP doméstica registrada (o falla la verificación), aborta el job y alerta.
- Tráfico a APIs legítimas (Keepa, Telegram, SP-API) sí sale directo desde `oip-api`.
- Navegador bloquea imágenes, fuentes y media para reducir consumo (relevante con proxies de pago por GB).
- **Etapas:** MVP con VPS barato (IPs de datacenter, más propensas a bloqueo — se mide); volumen con proxies residenciales de pago por GB por fuente según necesidad.
- El experimento de bloqueo (spike) corre por el egress desde su primera ejecución.

#### 3.4.1 *(v1.3)* Topología Core local + Scraper Worker remoto (DEC-120)

Precisa lo anterior: en lugar de correr el scraping en casa y redirigir su tráfico por un túnel, **el scraping corre en el VPS**. La casa nunca habla con los comercios.

| Pieza | Dónde | Contiene |
|---|---|---|
| **OIP Core** | Servidor de Jesús (Rocky + Podman) | `oip-api` (FastAPI, scheduler, motor de oportunidad, búsqueda por artículo, notificador), `oip-db`, `oip-dashboard`, `oip-backup` |
| **OIP Scraper Worker** | VPS (Rocky + Podman) | `oip-scrapyd` (Scrapy + scrapy-playwright + Chromium), verificador de IP, firewall de salida |
| **Canal** | WireGuard Core ↔ Worker | Core → Worker: `schedule.json` de Scrapyd (trabajos). Worker → Core: `POST /ingest` (resultados). Solo por el túnel; ningún puerto expuesto a Internet salvo WireGuard en el VPS |

Reglas:
- **El Worker verifica su IP pública antes de cada job** y aborta si no es la IP autorizada del VPS (fail-closed).
- El firewall del VPS permite salida HTTPS a los comercios y entrada **solo** por WireGuard. Scrapyd no escucha en la interfaz pública.
- Autenticación del canal: claves WireGuard + token por servicio en `schedule.json` e `/ingest` (secreto en `podman secret`).
- **Configurable:** el Core usa una sola interfaz (`ACQUISITION_WORKER_URL` + endpoint de ingesta), así que el Worker puede vivir en el VPS o en casa detrás de `oip-egress`. **Solo se construye y opera el modo worker remoto**; el modo túnel (lo descrito arriba en esta sección) queda **documentado y sin construir**.
- Escalamiento futuro: más Workers o un Worker detrás de proxies residenciales (DEC-117) sin tocar el Core.

> *(v1.4, DEC-173 y DEC-174)* **Dos repositorios:** `oip-core` (este repo: API, BD, tablero, respaldos, documentación de negocio y proceso, REQ, inspecciones y agentes) y `oip-worker` (spiders, scrapy-playwright, Chromium, `BrowserRenderer`, verificador de IP, firewall de salida, bandeja de salida, runbooks del VPS, con su propio `CLAUDE.md` y `openspec/`). Se separan en la Etapa 3, antes de la primera línea del Worker. **El repo del Core no contiene spiders ni clientes HTTP hacia comercios**, y un gate lo verifica. Los contratos `schedule` e `ingest` se escriben como spec en los dos repos (§8); en el Worker, los commits citan el REQ como `jjrm2004mx/<core>#N`.

### 3.5 *(v1.3)* Consulta responsable (DEC-115, RN-010)

| Control | Implementación (Scrapy / Core) | Valor inicial |
|---|---|---|
| Límite de consultas | `CONCURRENT_REQUESTS_PER_DOMAIN=1` + `DOWNLOAD_DELAY` y limitador por dominio en el Worker | ≤ 6 por minuto por comercio |
| Pausa (throttling) | `DOWNLOAD_DELAY=10` con `RANDOMIZE_DOWNLOAD_DELAY` ajustado al rango 10–15 s; AutoThrottle activado como techo adicional | 10–15 s |
| Concurrencia | 1 por comercio; comercios distintos en paralelo (`CONCURRENT_REQUESTS` global moderado) | 1 / comercio |
| Caché | En el Core, por publicación: 6 h (búsqueda automatizada), **1 h** (búsqueda por artículo); Keepa 6 h | 6 h / 1 h / 6 h |
| Reintentos | Cola de reintentos del Core con espera creciente; no se usa el reintento inmediato de Scrapy para errores de bloqueo | 3 intentos: 1, 5, 15 min |
| Timeout | `DOWNLOAD_TIMEOUT` (HTTP) y timeout de navegación (Playwright) | 30 s / 60 s |
| Pausa por bloqueo | Métrica por dominio en ventana de 1 h; si > 20% bloqueadas → `retailer_policy.estado = pausado` por 24 h y aviso | 20% / 24 h |
| robots.txt | `ROBOTSTXT_OBEY` configurable por comercio | **Pendiente** (pregunta RN-010 · P2) |

Postura (DEC-116): OIP no pretende ocultarse ni evadir restricciones; stealth deshabilitado por defecto (§3.3).

> *(v1.4, alineado con RN-010 v2 y DEC-165)* **robots.txt se respeta por defecto** (resuelve el pendiente de la tabla); términos de uso revisados comercio por comercio antes de activarlo. **Pausa por bloqueo** solo con ≥ 10 consultas en la hora y > 20% bloqueadas, **escalonada**: 24 h, luego 48 h (dentro de 7 días desde la reanudación) y la tercera hasta que Jesús lo autorice; cada pausa avisa (🛑). La **solicitud de un cliente** pasa antes que la búsqueda automatizada, con los mismos límites, y antes de salir a una tienda **siempre** se re-consulta sin caché.

### 3.6 *(v1.3)* Modo de red para la prueba de concepto (DEC-121)

- `modo_red: estricto | desarrollo`, **estricto por defecto**.
- **Estricto:** toda consulta a comercios va al Worker en el VPS. El Core no tiene ruta de scraping propia.
- **Desarrollo:** permite ejecutar spiders en casa **solo** contra una lista permitida (fixtures guardados, simulaciones, APIs que permiten automatización).
- **Límite duro, independiente de la aplicación:** el firewall del servidor de Jesús (nftables / firewalld) **rechaza la salida hacia los dominios de Home Depot, Walmart y Target** desde los contenedores. Ninguna opción de OIP lo desbloquea.
  - *(v1.3, precisión 2026-11-11 — DEC-122)* El límite duro se implementa como **lista de permitidos (salida denegada por defecto)**, no como lista de prohibidos: los firewalls filtran por IP, y los comercios usan CDN con IPs numerosas y cambiantes, por lo que una lista de prohibidos es frágil y no cubre comercios futuros.
    - Los contenedores del servidor de Jesús tienen **la salida a Internet denegada por defecto** (firewalld/nftables, zona propia para la red de Podman).
    - Solo se permite salida hacia **destinos aprobados**: Keepa, Telegram, el endpoint WireGuard del VPS, el registro de imágenes y los servicios de prueba del modo desarrollo. Se mantienen como conjunto (`set`) de nftables, con resolución DNS controlada para los que cambian de IP.
    - Cualquier otro destino, **incluidos Home Depot, Walmart, Target y cualquier comercio futuro**, queda bloqueado sin necesidad de conocer sus IPs.
    - Cada conexión rechazada se registra; un intento de salida hacia un comercio genera un aviso.
    - Ninguna opción de OIP modifica estas reglas; solo el administrador del servidor.
- Activar el modo desarrollo deja un registro (quién y cuándo) y muestra un aviso visible en el tablero y en Telegram.

---

## 4. Auditoría Open Source revisada

### 4.1 Tabla de decisión

| Proyecto | Licencia | Rol en OIP | Decisión |
|---|---|---|---|
| **Scrapy** | BSD-3-Clause | Descubrimiento y seguimiento | **Adoptar** (núcleo) |
| **scrapy-playwright** | BSD-3-Clause | Renderizado + stealth en páginas dinámicas | **Adoptar** selectivo |
| **Scrapyd** | BSD-3-Clause (verificar) | Ejecutar spiders por API HTTP | **Adoptar** en arranque |
| **extruct** | BSD (verificar) | Leer JSON-LD/microdata schema.org (GTIN, precio, disponibilidad) | **Adoptar** |
| **price-parser** | BSD (verificar) | Parsear precios en texto | **Adoptar** |
| **Spidermon** | BSD (verificar) | Monitoreo de calidad de extracción | Incremento 2 |
| **PriceStalker** | MIT | Seguimiento alternativo | **Opcional**, PoC comparativa |
| **PriceGhost** | Sin LICENSE (solo README) | — | **Descartado** |
| **changedetection.io** | Apache-2.0 | Disparador de discovery por cambio | Incremento 3 |
| **TimescaleDB** | Apache-2.0 (core) / TSL (algunas funciones) | Series de tiempo de precios | **Adoptar** (uso interno sin problema) |
| **Keepa API** | Comercial | Referencia de mercado y demanda Amazon | **Adoptar** |
| *(v1.4)* **Keepa API** | Comercial | Historial y Sales Rank de Amazon, **complementario** | **Diferido** (DEC-124): no entra en el Inc. 1; se contrata por meses ante una necesidad concreta; la integración puede desarrollarse con respuestas simuladas |
| **Amazon SP-API** | Comercial (requiere cuenta vendedor) | Comisiones exactas, restricciones | Adaptador preparado, desactivado |

### 4.2 PriceStalker — hallazgos verificados en código (8-nov-2026)

- Repo creado en enero 2026; 477 commits; **176 commits en últimos 90 días**.
- Mantenedores efectivos: ~3 (mikeknight85, stevene1919, clucraft como autor original).
- Única estable: **v2.0.0 (31-ago-2026)**; main en **v2.2.0-beta.2**. `version.json` dice `2.0.0-beta.1` (inconsistente con tags).
- Usa `puppeteer-extra-plugin-stealth` (`scraper/src/core/SessionManager.ts`).
- **Sí tiene webhooks**: proveedor de notificaciones con 6 eventos (baja de precio, precio objetivo, regreso a stock, no disponible, restaurado, anunciado). Son alertas, no cada observación; el historial completo requiere polling.
- Despliegue con Docker Compose; para Podman: `podman-compose` o `podman kube play` — PoC.
- La tabla de símbolos de moneda no incluye MXN (menor).

**Por qué sale del núcleo:** OIP ya necesita seguir precios con Scrapy (para el historial propio y la regla anti-inflado). Con PriceStalker el precio se extraería dos veces con dos motores, el historial quedaría duplicado en dos bases y se agrega Node + Puppeteer. Se conserva como **benchmark**: si en la PoC extrae precios notablemente mejor en algún comercio, se integra para ese comercio vía adaptador `TrackingProvider`.

### 4.3 Keepa

Servicio que registra desde hace años el historial de precio y ranking de ventas del catálogo de Amazon. Permite consulta por ASIN y por código (UPC/EAN).

- Plan de entrada reportado: **~49 €/mes, 20 tokens/min** (fuente de terceros; confirmar en keepa.com).
- 1 token por producto estándar, hasta 100 por llamada → ~28,000 consultas/día con el plan de entrada.
- Estrategia: **caché agresiva** en OIP (la referencia de mercado cambia lento); refrescar solo candidatos con descuento declarado relevante.

> *(v1.4, DEC-123, DEC-124 y DEC-125)* **Keepa queda diferido.** No se contrata en la PoC ni en el Inc. 1: las referencias salen del historial propio y de la comparación entre comercios (§2.2). Cuando entre, será solo para productos de Amazon, como fuente complementaria de historial y Sales Rank, contratada por meses y con resultados guardados y reutilizados. Su historial es de Amazon, no del mercado completo. Filosofía de contratación: gratis o local primero, pago por consumo después, suscripción solo con valor comprobado.

---

## 5. Arquitectura lógica

```mermaid
flowchart TB
    subgraph BUY["Lado compra"]
        HD["Home Depot"]
        WM["Walmart"]
        TG["Target"]
        OTH["Otros comercios"]
    end

    subgraph CRAWL["Crawling (Python)"]
        SCRAPYD["Scrapyd"]
        DISC["Spiders de descubrimiento<br/>(ofertas, liquidaciones, categorías)"]
        TRACK["Spider de seguimiento<br/>(URLs + tiendas físicas)"]
        PW["Playwright + stealth<br/>(selectivo)"]
        EXT["extruct / price-parser"]
    end

    subgraph CORE["OIP Core (FastAPI)"]
        INGEST["Ingesta idempotente"]
        CAT["Catálogo: producto ↔ publicaciones"]
        MATCH["Match UPC/GTIN → ASIN"]
        MKT["Referencia de mercado"]
        OPP["Motor de oportunidad<br/>(anti-inflado, margen, restricciones, demanda)"]
        SCHED["Scheduler + perfiles de temporada"]
        NOTIF["Notificador"]
        API["API + dashboard"]
    end

    subgraph SELL["Lado venta"]
        KEEPA["Keepa API"]
        SPAPI["Amazon SP-API<br/>(preparado, off)"]
        FB["FB Marketplace<br/>(estimado)"]
    end

    DB[("PostgreSQL + TimescaleDB")]
    TELEGRAM["Telegram"]

    SCHED -->|schedule.json| SCRAPYD
    SCRAPYD --> DISC & TRACK
    DISC & TRACK -.-> PW
    DISC & TRACK --> EXT
    HD & WM & TG & OTH --> DISC & TRACK
    EXT -->|POST /ingest| INGEST
    INGEST --> CAT --> MATCH
    MATCH --> KEEPA
    KEEPA --> MKT
    SPAPI -.-> MKT
    FB -.-> MKT
    MKT --> OPP
    CAT --> OPP
    OPP --> NOTIF --> TELEGRAM
    CORE --> DB
    API --> DB
```

### 5.1 Responsabilidades

| Componente | Hace | No hace |
|---|---|---|
| Spiders de descubrimiento | Recorrer ofertas/liquidaciones/categorías; emitir candidatos con evidencia | Decidir identidad ni oportunidad |
| Spider de seguimiento | Re-extraer precio/stock de publicaciones seleccionadas; por tienda cuando aplica | Descubrir |
| Scrapyd | Ejecutar jobs de spiders por API | Planificar (lo hace OIP) |
| Ingesta | Validar esquema, dominio, canonicalizar URL, deduplicar | Llamar a Keepa en línea |
| Match | Ligar producto a ASIN por UPC/GTIN; similitud solo como auxiliar | Fusionar sin evidencia |
| Referencia de mercado | Consultar/cachear Keepa, consolidar precios de otros comercios | — |
| Motor de oportunidad | Aplicar §2 completo y asignar nivel | Comprar o publicar |
| Notificador | Telegram con deduplicación (no repetir la misma oferta) | — |

### 5.2 Ejecución asíncrona

Arranque: **Scrapyd** para spiders + **cola de tareas sobre PostgreSQL** (p. ej. Procrastinate) para enriquecimiento Keepa y cálculo de oportunidad. Sin broker adicional.
Migrar a RabbitMQ solo si hay más de un nodo de crawling o la cola en Postgres se vuelve cuello de botella.

> *(v1.4, DEC-176)* **Estados de tareas en el Core** con transiciones condicionales (`UPDATE … WHERE estado = <anterior>`), de modo que dos procesos nunca toman el mismo paso; **barrido de recuperación** periódico que re-encola lo atascado o lo que ya debe reintentarse; estado **`HELD`** para lo que necesita a Jesús (por ejemplo, una evaluación en revisión manual o una fuente en pausa que pide autorización). La base es la fuente de verdad; la cola solo avisa. Nada depende de que un proceso siga vivo.

### 5.3 *(v1.3)* Despliegue físico: Core local + Scraper Worker remoto

```mermaid
flowchart LR
    subgraph HOME["Servidor de Jesús (Rocky + Podman) — OIP Core"]
        API["oip-api<br/>scheduler · motor de oportunidad<br/>búsqueda por artículo · notificador"]
        DB[("oip-db<br/>PostgreSQL + TimescaleDB")]
        DASH["oip-dashboard (Metabase)"]
        FW1["Firewall: comercios bloqueados<br/>(modo_red, §3.6)"]
    end
    subgraph VPS["VPS (Rocky + Podman) — Scraper Worker"]
        SCR["oip-scrapyd<br/>Scrapy + scrapy-playwright"]
        IPV["Verificador de IP<br/>(fail-closed)"]
        FW2["Firewall: entrada solo WireGuard"]
    end
    COM["Comercios<br/>(ven la IP del VPS)"]
    KEEPA["Keepa / Telegram<br/>(salida directa)"]

    API <-->|"WireGuard: schedule.json →<br/>← POST /ingest"| SCR
    SCR --> IPV --> COM
    API --> DB
    DASH --> DB
    API --> KEEPA
```

### 5.4 *(v1.3)* Flujos de las dos funcionalidades

**A. Búsqueda automatizada:** scheduler del Core → `schedule.json` (spider de descubrimiento/seguimiento) → Worker consulta comercios con los controles de §3.5 → `POST /ingest` → catálogo → match → Keepa → motor de oportunidad (RN-001 a RN-009) → alertas.

**B. Búsqueda por artículo:** Jesús captura la solicitud (`client_request`) en el Core → el Core busca primero en caché (≤ 1 h) → para lo que falte, `schedule.json` (spider de búsqueda por artículo, con prioridad sobre los trabajos periódicos pero con los mismos límites por comercio) + consulta a Keepa para Amazon → `POST /ingest` → ordenamiento de RN-011 (disponibles por precio total; el resto aparte) → resultado consultable y exportable para que Jesús responda al cliente.

> *(v1.4)* **Sin Keepa** (DEC-124): en los dos flujos, Amazon se consulta como un comercio más (**ficha de Amazon** por el Worker: botón de compra, vendedores, ranking, reseñas y "comprados el mes pasado"), y la evaluación usa el **historial propio** y la comparación entre comercios. El flujo A evalúa **por canal** y elige canal (§2.7) antes de asignar nivel. El flujo B usa datos de **1 hora o menos**, Zonas 1 y 2 y máximo 5 tiendas por comercio, y el viaje y la entrega se muestran aparte sin cambiar el orden (DEC-166, DEC-168). Las opciones de **vendedor externo** se marcan y no se recomiendan por defecto, y los canales especiales (Walmart Business) se marcan "puede requerir cuenta especial" (DEC-135). Las **sugerencias** de ofertas relacionadas (DEC-139) se agregan cuando RN-011 defina su criterio. Las **capturas manuales** de Jesús (particulares, comparables locales, precio local estimado, demanda local, MSRP) entran por el Core con el mismo contrato de observación.

### 5.5 *(v1.4)* IA opcional (DEC-177)

OIP no usa IA en el Inc. 1. Cuando entre, **el código decide y la IA complementa**:

| Regla | Detalle |
|---|---|
| Camino sin IA | Toda función con IA tiene un camino sin IA que se sostiene solo |
| Interruptor por función | `apagada \| solo registra \| aplica` |
| Banco etiquetado | Casos reales (`docs/negocio/casos/`) con umbrales escritos **antes** de encenderla |
| Fuente registrada | Cada decisión guarda si salió de `regla` o de `ia` |
| Pruebas | La suite corre sin llamadas al modelo |
| Adaptador | Un adaptador de modelo con timeout y caché, dentro del Core |

Candidatos (insumo del stack de tickets §9): identificación sin código (nunca confirma sola), extracción de precio sin JSON-LD como respaldo, búsqueda por necesidad (futura, DEC-152) y redacción del resumen de avisos.

---

## 6. Tienda física

### 6.1 Qué cambia

- Precio e inventario **por sucursal**, frecuentemente distintos del precio online.
- Los comercios exponen disponibilidad por tienda/código postal en su sitio; el spider de seguimiento debe consultar con la tienda seleccionada.
- Las liquidaciones más profundas a veces **no aparecen en línea** → cobertura parcial aceptada; se registra la fuente del dato.

### 6.2 Configuración de tiendas

Tabla `store` con: comercio, número de tienda, dirección, coordenadas, código postal, distancia y tiempo estimado desde el origen (Tijuana), activa/inactiva. Inicial: sucursales de HD, Walmart y Target en el área de San Diego (Chula Vista, National City, San Ysidro, San Diego, etc.).

### 6.3 Costo de traslado

```
costo_traslado = (km_ida_vuelta × costo_por_km)
               + (horas_totales × valor_hora)
               + costo_fijo_cruce
horas_totales  = tiempo_manejo + tiempo_cruce_frontera_estimado + tiempo_en_tienda
```

- Parámetros configurables: rendimiento, precio de gasolina, valor de tu hora, tiempo de cruce promedio.
- **Agrupación de viaje:** si hay varias oportunidades en la misma zona, el costo se prorratea → el dashboard muestra "ruta de compra" con margen total.
- Regla: tiendas fuera del radio solo alertan si `margen_neto_absoluto` ≥ umbral alto configurable.

> *(v1.4, alineado con RN-008 v2 y DEC-163)* **Zonas por km desde la garita** (San Ysidro u Otay Mesa): Zona 1 ≤ 20 km (mínimo $50 por viaje), Zona 2 ≤ 40 km ($75), Lejos ($150, y solo entonces se avisa); en una ruta manda la zona más lejana. `costo del viaje = km × $0.20 + horas × $15 + fijos`, con `horas = manejo + espera en garita + 0.5 h por tienda`; la ganancia del viaje usa el **canal elegido** (RN-018). Una oportunidad que sola no paga el viaje queda **en espera** 2 días (1 en liquidación). La misma tarifa da el **costo de entrega** de la venta local (DEC-142, DEC-148). Tienda nueva sin distancia registrada: no se recomienda hasta registrarla.

### 6.3.1 Confianza del dato de disponibilidad en tienda

La disponibilidad en tienda **no es inventario garantizado**. Cada observación registra:

- `consultado_en` y antigüedad visible en toda alerta ("consultado hace 3 h").
- `confianza`:
  - **Alta:** cantidad numérica, consulta < N horas.
  - **Media:** solo "en stock" / "pocas unidades", o cantidad de antigüedad media.
  - **Baja:** dato antiguo o el comercio reporta "limited stock".
- **Decaimiento:** la confianza baja con las horas según la velocidad de agotamiento de la categoría.
- **Re-consulta previa al viaje:** botón en la alerta de Telegram que vuelve a consultar la tienda justo antes de salir.
- **Registro de visita** (encontrado / no encontrado / precio distinto) en `opportunity_outcome`, para calibrar confianza por tienda y comercio.
- Oportunidades de tienda física con confianza **baja** no generan alerta inmediata.

> *(v1.4, alineado con RN-007 v2 y DEC-162)* La confianza sale de la **tabla de RN-007** (cantidad exacta, "en existencia", "pocas unidades", con tiempos a la mitad en liquidación); "pocas unidades" es Media hasta 2 h. Castigo por historial con ≥ 3 visitas y recuperación con 3 aciertos. **Llamar antes de salir** si la ganancia del viaje es ≥ $100 (≥ $50 con confianza Media); si la tienda confirma, Alta por 2 h. En línea: disponible confirmada · existencia limitada · no confirmada · agotado (DEC-134); recoger en tienda cuenta como en línea y suma el viaje.

### 6.4 Logística de venta

Fuera del alcance del modelo de margen por decisión del dueño del producto: no se modelan costos de importación ni de cruce para la venta. El parámetro `otros_costos_venta` queda disponible por canal (default 0) por si se requiere un ajuste manual.

---

## 7. Modelo de datos

### 7.1 Entidades

| Entidad | Propósito |
|---|---|
| `retailer`, `retailer_domain` | Comercio y dominios autorizados |
| `store` | Sucursal física con ubicación y costo de traslado calculado |
| `category`, `retailer_source` | Taxonomía y URLs de entrada (ofertas, liquidaciones, categorías) |
| `product` | Identidad canónica |
| `product_identifier` | UPC/GTIN/EAN, MPN, SKU comercio, **ASIN** |
| `listing` | Publicación de un producto en un comercio (online) |
| `price_observation` *(hypertable)* | Precio con fecha, moneda, tipo (oferta/regular/liquidación), `store_id` opcional |
| `availability_observation` *(hypertable)* | Stock online o por tienda, con `consultado_en`, `confianza` y fuente |
| `store_visit` | Resultado de cada visita a tienda (encontrado/no encontrado/precio distinto) |
| `market_reference` *(hypertable)* | Snapshot de referencia: fuente (keepa/otro comercio/historial), precio, BSR, vendedores, ventana |
| `fee_schedule` | Comisión por canal y categoría (manual; SP-API cuando exista) |
| `sale_restriction` | Categoría/marca restringida o hazmat por canal |
| `opportunity` | Resultado del motor: métricas (incl. `margen_neto_ajustado`, `roi_anualizado`, `dias_estimados_venta`, `unidades_recomendadas`), flags, nivel, estado (nueva/alertada/descartada/comprada/vendida) |
| `opportunity_outcome` | Resultado real: precio de compra, precio de venta, días para vender → **calibra el motor** |
| *(v1.3)* `client_request` | Solicitud de búsqueda por artículo: alias del cliente (sin datos personales), descripción, modelo/UPC, cantidad, notas, fecha, estado |
| *(v1.3)* `client_request_result` | Opciones encontradas por solicitud: comercio/sucursal, precio, envío, total, disponibilidad, confianza, consultado_en, enlace, grupo (disponible / otras), posición, recomendada |
| *(v1.3)* `fetch_log` | Registro por consulta a comercio: dominio, hora, resultado (ok / error / bloqueada), duración; alimenta los límites y la pausa por bloqueo (§3.5) |
| *(v1.3)* `network_mode_change` | Cambios de `modo_red` (quién, cuándo, motivo) (§3.6) |
| `crawl_job`, `extraction_evidence` | Trazabilidad |
| `retailer_policy` | Frecuencia, límites, perfil de temporada, `access_mode`, `browser_engine` (`playwright` \| `puppeteer`), egress asignado, estado de bloqueo |
| `access_mode_change` | Historial de cambios de escalón por fuente (fecha, motivo, tasa de bloqueo antes/después) |
| *(v1.4)* `price_observation` / `availability_observation` (ampliadas) | Agregan vendedor (`comercio · externo · particular · desconocido`), estado del producto, estado de disponibilidad en línea, modo de compra, envío, liquidación, MSRP con fuente y fecha, contenido (DEC-134, DEC-169) |
| *(v1.4)* `amazon_listing_observation` *(hypertable)* | Ficha de Amazon: botón de compra (o sin oferta hoy), vendedores de nuevo, ranking en categoría y subcategoría, reseñas, comprados el mes pasado |
| *(v1.4)* `price_reference` | Referencias calculadas (habitual, mercado hoy, MSRP, mínimo de 60 días) con la **fuente usada** (historial propio, comparación, API oficial, Keepa) (DEC-123) |
| *(v1.4)* `evaluation`, `evaluation_channel` | Registro de cada evaluación: valores por canal, estado del canal, calidad del precio, marcas, todos los motivos, motivo principal, `nivel_calculado`, canal elegido, resultado y versiones de RN y configuración (REQ-2026-0001 §7). Complementa a `opportunity`; la relación exacta la fija el `design.md` de la parte B (Propuesta) |
| *(v1.4)* `private_listing` | Publicación de particular capturada por Jesús, **sin datos personales del vendedor** (DEC-150) |
| *(v1.4)* `local_comparable`, `local_estimate`, `local_demand` | Comparables y estimados de venta local, y demanda local por categoría (RN-014, RN-016, RN-017) |
| *(v1.4)* `config_version` | Configuración versionada (umbrales de las RN, tablas de comisión, envío, viajes, avisos) (DEC-155) |
| *(v1.4)* `task` | Estados de tareas del Core con `next_attempt_at` y `HELD` (§5.2, DEC-176) |
| *(v1.4)* `ingest_receipt` | Claves de idempotencia recibidas del Worker, para deduplicar la bandeja de salida (DEC-175) |

`opportunity_outcome` es clave: con lo que realmente compres y vendas se ajustan umbrales y estimados.

### 7.2 Diagrama ER conceptual

```mermaid
erDiagram
    RETAILER ||--o{ STORE : has
    RETAILER ||--o{ LISTING : publishes
    PRODUCT ||--o{ LISTING : appears_as
    PRODUCT ||--o{ PRODUCT_IDENTIFIER : has
    PRODUCT ||--o{ MARKET_REFERENCE : priced_by
    LISTING ||--o{ PRICE_OBSERVATION : records
    LISTING ||--o{ AVAILABILITY_OBSERVATION : records
    STORE ||--o{ PRICE_OBSERVATION : at
    STORE ||--o{ AVAILABILITY_OBSERVATION : at
    LISTING ||--o{ OPPORTUNITY : generates
    OPPORTUNITY ||--o| OPPORTUNITY_OUTCOME : results_in
    CATEGORY ||--o{ FEE_SCHEDULE : priced_with
    CATEGORY ||--o{ SALE_RESTRICTION : restricted_by
```

### 7.3 Identidad y match

1. UPC/GTIN/EAN válido (dígito verificador) — preferente; extraído de JSON-LD con extruct.
2. MPN + marca.
3. Búsqueda Keepa por código.
4. Título + marca + atributos (solo auxiliar; marca `LOW_MATCH_CONFIDENCE`).

Corrección manual desde el dashboard con trazabilidad.

### 7.4 Volumen y retención

`price_observation` y `market_reference` como hypertables TimescaleDB con compresión a partir de 30 días y agregados continuos diarios. Retención de detalle: 1 año; agregados: indefinido.

> *(v1.4, DEC-179)* **Migraciones versionadas**: todo cambio de esquema va en una migración nueva; nunca un `ALTER` manual ni editar una migración aplicada. Respaldo antes de cada migración y etiqueta `:rollback-<fecha>` de la imagen antes de cada despliegue. Lista escrita de **volúmenes que nunca se borran** (el historial de precios es un activo de OIP, DEC-123). Las migraciones con hypertables o compresión de TimescaleDB pasan por una **PoC** antes de producción.

---

## 8. Contrato de ingesta (Scrapy → OIP)

```json
{
  "schemaVersion": "1.1",
  "crawlJobId": "uuid",
  "retailerCode": "homedepot",
  "storeCode": "hd-0123",
  "sourceType": "clearance",
  "sourceUrl": "https://...",
  "productUrl": "https://...",
  "title": "...",
  "brand": "...",
  "model": "...",
  "retailerSku": "...",
  "gtin": "0123456789012",
  "price": { "current": 19.97, "was": 199.00, "currency": "USD", "type": "clearance" },
  "availability": { "status": "in_stock", "quantity": 4, "scope": "store" },
  "extractedAt": "2026-11-08T18:00:00Z",
  "extractionMethod": "playwright_jsonld",
  "blocked": false,
  "evidence": { "jsonld": true, "priceSelector": "..." }
}
```

Idempotencia: `retailer + canonical_url + store_code + extractedAt (truncado a ventana)`. `blocked: true` alimenta la métrica de bloqueo sin generar observación.

> *(v1.4, DEC-134, DEC-169, DEC-174 y DEC-175)* **Contrato de ingesta 2.0** (cambio incompatible: sube la versión mayor). El esquema 1.1 de arriba se conserva como referencia histórica. Durante la transición el Core acepta **N y N-1**.

```json
{
  "schemaVersion": "2.0",
  "crawlJobId": "uuid",
  "idempotencyKey": "homedepot|https://.../p/123|hd-0123|2026-11-16T18:00",
  "retailerCode": "homedepot",
  "storeCode": "hd-0123",
  "sourceType": "clearance",
  "productUrl": "https://...",
  "title": "...",
  "brand": "...",
  "model": "...",
  "gtin": "0123456789012",
  "content": "tool only",
  "category": "tools",
  "weightKg": 4.0,
  "dimsCm": null,
  "price": { "current": "29.00", "was": "129.00", "currency": "USD" },
  "seller": "comercio",
  "condition": "nuevo",
  "availability": { "state": "in_stock_confirmed", "text": "3 disponibles", "quantity": 3, "scope": "store", "addToCart": true },
  "isClearance": true,
  "purchaseMode": "tienda",
  "shipping": { "toMeCost": "0.00", "days": null, "mode": "pickup" },
  "msrp": { "value": "149.00", "source": "fabricante", "date": "2026-11-10" },
  "amazonListing": null,
  "extractedAt": "2026-11-16T18:00:00Z",
  "extractionMethod": "playwright_jsonld",
  "blocked": false,
  "evidence": { "jsonld": true, "priceSelector": "..." }
}
```

- **Montos como texto decimal** (`"29.00"`), para leerlos con `Decimal` sin pasar por `float` (DEC-060).
- `seller`: `comercio · externo · particular · desconocido`. `availability.state` en línea: disponible confirmada · existencia limitada · no confirmada · agotado (RN-007). `purchaseMode`: `envio · recoleccion · tienda · particular`.
- `amazonListing` (solo en la ficha de Amazon): `buyBoxPrice` o `null` (sin oferta hoy), `sellersNew`, `rankMain`, `rankSub`, `reviews`, `boughtLastMonth`.
- Las **capturas manuales** de Jesús usan el mismo esquema con `retailerCode: "particular"` o `"manual"`, sin datos personales.
- **Bandeja de salida en el Worker:** cada resultado se guarda `PENDIENTE → ENTREGADO`, se reintenta con espera creciente si el Core o el túnel no responden, y tiene retención corta. El Core deduplica con `idempotencyKey` (`ingest_receipt`).
- **Autenticación:** token por servicio en `schedule` e `ingest` (`podman secret`), solo por WireGuard. Los contratos `schedule` e `ingest` son spec en **los dos** repos, con el mismo `Change: <id>` cuando cambian.

---

## 9. Despliegue (Rocky Linux + Podman rootless)

### 9.1 Contenedores del incremento 1

| Contenedor | Imagen base |
|---|---|
| `oip-api` | Python 3.12 + FastAPI + workers de tareas |
| `oip-scrapyd` | Python 3.12 + Scrapy + scrapy-playwright + Chromium |
| `oip-db` | PostgreSQL + TimescaleDB |
| `oip-dashboard` | Metabase (lectura sobre la BD) en incremento 1; UI propia en incremento 2 |
| `oip-backup` | Job de respaldo (`pg_dump` programado) |
| `oip-egress` | Cliente WireGuard hacia VPS (MVP) o proxy (volumen); única salida de `oip-scrapyd` (y de `oip-renderer-puppeteer` si existe) |
| `oip-renderer-puppeteer` | *Condicional.* Servicio Node.js que recibe "renderiza esta URL" por HTTP y devuelve HTML; solo se despliega si la PoC-A lo justifica. Vive en `oip-internal` |

Redes Podman: `oip-internal` (sin salida; `oip-scrapyd`, `oip-egress`, `oip-api`, `oip-db`) y `oip-public` (`oip-api`, `oip-egress`, dashboard). `oip-scrapyd` **no** está en `oip-public`. Detalle en §3.4.

> *(v1.3, DEC-120)* **Topología vigente: worker remoto.** Los contenedores se reparten en dos hosts:
>
> | Host | Contenedores |
> |---|---|
> | **Servidor de Jesús (Core)** | `oip-api`, `oip-db`, `oip-dashboard`, `oip-backup`, endpoint WireGuard |
> | **VPS (Worker)** | `oip-scrapyd` (Scrapy + scrapy-playwright + Chromium), verificador de IP, endpoint WireGuard; firewall de salida |
>
> `oip-egress` y la red `oip-internal` descritas arriba corresponden al **modo túnel** (worker en casa), que queda **documentado y sin construir**. En el modo worker remoto, la salida a los comercios es la IP pública del VPS, y la casa no tiene ninguna ruta de scraping.
>
> **Infraestructura de referencia del VPS (DEC-119, precios por verificar antes de contratar):** proveedor tipo Hetzner, DigitalOcean o Vultr; referencia del experto: ~USD 6.49/mes (2 vCPU / 4 GB) + ~USD 0.60/mes de IPv4. **Recomendado para navegadores: 4 vCPU / 8 GB.** Sistema: **Rocky Linux + Podman** (DEC-118), no Ubuntu + Docker. Monitoreo de disponibilidad del Worker desde el Core (heartbeat por WireGuard).

> *(v1.4, DEC-126, DEC-127, DEC-173 y DEC-180)*
> - **VPS creciente:** arrancar con **2 vCPU / 4 GB** (40–50 GB de disco, IPv4 pública, WireGuard), suficiente con 1 consulta a la vez por comercio; **subir a 4 vCPU / 8 GB** al medir memoria > 75% sostenida o al correr varios navegadores en paralelo (precisa la recomendación anterior).
> - **Costos por etapa:** PoC con datos guardados USD 0; PoC con consultas reales ~USD 5–15/mes de VPS (por verificar), sin proxies; proxies por GB solo con volumen; Keepa según DEC-124.
> - **Repositorios:** los contenedores del Core salen de `oip-core` y los del Worker de `oip-worker` (§3.4.1), cada uno con sus Quadlets.
> - **Metabase** lee con un **rol de solo lectura** sobre vistas de reporte, nunca con el dueño de la base.

### 9.2 Operación

- **Quadlets** (`.container`, `.network`, `.volume`) gestionados por `systemd --user`, con `loginctl enable-linger`.
- Red Podman privada; solo el dashboard/API expuestos detrás de reverse proxy con TLS (o solo VPN/Tailscale, por ser herramienta interna).
- Secretos con `podman secret` (Keepa key, token Telegram, credenciales BD).
- Desarrollo local: `podman-compose`.
- PriceStalker (si se prueba): `podman kube play` sobre su compose convertido, en red separada — PoC.

> *(v1.4, DEC-178, DEC-179 y DEC-183)*
> - **Todos los puertos en `127.0.0.1`**; la única puerta a la red (o ninguna) se decide en la Etapa 3; lo demás, por túnel SSH o WireGuard. En el VPS, Scrapyd solo escucha en la interfaz WireGuard. El firewall solo no basta: hacen falta las dos capas.
> - La **API de solo lectura y el tablero** solo se alcanzan por la VPN, con autenticación (REQ-2026-0001 §10).
> - **Migraciones** como contenedor de una sola ejecución antes del servicio (§7.4).
> - **Runbook de operación** con la tabla maestra de los dos hosts (contenedores, puertos, redes, quién habla con quién) y las trampas conocidas T-01 a T-15 del insumo del stack de tickets.

---

## 10. Seguridad y operación

Se conservan de v1.0: validación de URL y protección SSRF (solo http/https, dominio del comercio, bloqueo de rangos privados y metadata, revalidar redirecciones), secretos fuera de código, logs sin tokens, BD sin exposición.

> *(v1.4, DEC-150, DEC-177 y DEC-181)* **Logs y métricas sin contenido:** sin tokens (Telegram, credenciales, Keepa cuando exista), sin datos de clientes ni de particulares y sin HTML de los comercios; solo identificadores, conteos y tiempos. De los particulares solo se guarda la publicación (plataforma, enlace, ciudad, precio, estado), nunca nombre ni teléfono. Los accesos denegados a la API y al tablero se registran. Las funciones con IA registran la fuente de cada decisión (§5.5).

### 10.1 Observabilidad mínima

- Tasa de éxito y **tasa de bloqueo por comercio**.
- Candidatos/día por comercio y fuente; % con GTIN; % con match a ASIN.
- Consumo de tokens Keepa vs presupuesto.
- Oportunidades por nivel; % descartadas por `INFLATED_WAS_PRICE` / `MARKET_ALREADY_CHEAP`.
- Antigüedad de la última observación por publicación.
- **Precisión del motor**: de las oportunidades que compraste, % que se vendieron con el margen estimado (desde `opportunity_outcome`).

Herramienta: logs estructurados + métricas en Postgres visibles en Metabase; Prometheus/Grafana solo si se requiere después.

---

## 11. Riesgos

| ID | Riesgo | Impacto | Mitigación |
|---|---|---|---|
| R-01 | Bloqueos anti-bot (HD/Walmart/Target usan protecciones comerciales agresivas) | Crítico | Stealth, frecuencia conservadora, métrica de bloqueo, pausa automática, proxies si se justifica |
| R-02 | Descuento inflado tomado como oportunidad | Alto | Reglas §2.3 + historial propio |
| R-03 | Match incorrecto producto ↔ ASIN | Alto | GTIN preferente; baja confianza no alerta |
| R-04 | Precio en tienda distinto al online / liquidación no visible | Alto | Seguimiento por tienda; fuente registrada; cobertura parcial aceptada |
| R-05 | Restricciones de venta no detectadas | Alto | Tabla de restricciones; SP-API cuando haya cuenta |
| R-07 | Cambios de HTML rompen spiders | Alto | JSON-LD primero, Spidermon, pruebas por comercio |
| R-08 | Costo Keepa crece | Medio | Caché, refresco solo de candidatos, presupuesto de tokens |
| R-09 | Términos de uso de los sitios | Medio/alto (aceptado) | Uso interno, frecuencia baja, sin datos personales |
| R-10 | Fugas de memoria del navegador | Medio | Límites de contextos, reciclaje, métricas |
| R-17 | Un comercio detecta el motor de navegador en uso | Alto | Interfaz de renderizado con motor por fuente; PoC-A compara Playwright vs Puppeteer |
| R-18 | *(v1.3)* El VPS (Worker) no está disponible | Alto | Sin respaldo desde casa (fail-closed); heartbeat y aviso; trabajos en cola hasta que vuelva |
| R-19 | *(v1.3)* Canal Core ↔ Worker expuesto o comprometido | Crítico | Solo WireGuard; Scrapyd sin interfaz pública; token por servicio; firewall de entrada |
| R-20 | *(v1.3)* Datos de clientes (búsqueda por artículo) | Medio | Solo alias, sin datos personales; respaldo cifrado |
| R-21 | *(v1.3)* Pocas o ninguna opción disponible para un cliente | Medio | Mostrar "otras opciones" y aviso de repetir la búsqueda (RN-011) |
| R-22 | *(v1.4)* Contratos Core ↔ Worker desalineados entre los dos repos | Alto | Contratos como spec en los dos repos, versión mayor ante cambio incompatible, Core acepta N y N-1, mismo `Change: <id>` (DEC-174) |
| R-23 | *(v1.4)* Resultados perdidos si el túnel o el Core caen | Medio | Bandeja de salida en el Worker con reintentos y deduplicación en el Core (DEC-175) |
| R-24 | *(v1.4)* Sin Keepa, poco historial propio al inicio | Medio | `SIN HISTORIAL SUFICIENTE` → revisión manual; comparación entre comercios y MSRP con calidad máxima "Precio competitivo"; Keepa por meses ante una necesidad concreta (DEC-124, DEC-130) |
| R-25 | *(v1.4)* Una función con IA decide mal o el proveedor cambia | Medio | Camino sin IA, interruptor de tres modos, banco etiquetado y pruebas sin modelo (DEC-177) |
| R-26 | *(v1.4)* Migración que daña el historial de precios | Alto | Migraciones versionadas, respaldo previo, etiqueta de rollback y PoC para TimescaleDB (DEC-179) |
| R-11 | SSRF desde URLs descubiertas | Crítico | §10 |
| R-12 | Alertas repetidas/ruido | Medio | Deduplicación por oportunidad y ventana |
| R-13 | **IP doméstica marcada o bloqueada** | Crítico | Egress obligatorio, red interna sin salida, fail-closed, verificación de IP por job (§3.4) |
| R-14 | IP del VPS (datacenter) bloqueada | Alto | Medir; cambiar egress de esa fuente a proxy residencial |
| R-15 | Rentabilidad aparente (margen alto, rotación lenta) | Alto | Margen ajustado y ROI anualizado (§2.5.1) |
| R-15 *(v1.4)* | Rentabilidad aparente | Alto | Margen ajustado y **rendimiento mensual** por canal, con pago a 30 días y tope de primera compra (RN-005 v2) |
| R-16 | Viaje a tienda sin producto | Medio | Confianza del dato, re-consulta previa, registro de visitas (§6.3.1) |

---

## 12. Plan por incrementos

### Incremento 1 — "Primera oportunidad real"

- Conectores: **Home Depot** (ofertas + liquidaciones, online + tiendas San Diego) y **Walmart** (ofertas online).
- Extracción JSON-LD + Playwright stealth selectivo.
- Match GTIN → ASIN vía Keepa; referencia de mercado y BSR.
- Motor de oportunidad completo (§2) con tabla de comisiones manual.
- Alertas Telegram + Metabase.
- *(v1.3)* **Búsqueda por artículo** (funcionalidad B, RN-011): captura por Jesús, búsqueda en Home Depot, Walmart y Amazon, resultado ordenado.
- *(v1.3)* **Consulta responsable** (RN-010) y **topología Core local + Worker en VPS**.
- Despliegue con Quadlets en Rocky.

> *(v1.4)* **Ajustes al Inc. 1:** sin Keepa (DEC-124): match por código o modelo + marca y referencias del historial propio y de la comparación entre comercios; comercios **Home Depot, Walmart, Target, Best Buy, GameStop, Nintendo Store** y la ficha de Amazon (DEC-132); evaluación **por canal** con venta local y capturas manuales de particulares (DEC-151); avisos con el formato de la guía de estilo §10 (DEC-189); **dos repos** Core y Worker (DEC-173). Orden de construcción del REQ-2026-0001 (DEC-082): **B** evaluación → **C** viajes y avisos → **A** adquisición (después de la PoC-A) → **D** búsqueda por artículo.


**Criterio de salida:** al menos una oportunidad real validada a mano por semana con margen ≥ umbral; tasa de bloqueo medida por comercio.

### Incremento 2 — "Cobertura"

- **Target** y comercios adicionales por categoría (perfumes, relojes, joyería, juguetes).
- Costo de traslado y rutas de compra agrupadas.
- Restricciones de venta; `opportunity_outcome` y calibración de umbrales.
- Spidermon; UI propia del dashboard (FastAPI + HTMX o React).
- *(v1.4)* La UI propia sigue la **guía de estilo** (`docs/diseno/guia-de-estilo.md`, DEC-184 a DEC-190): monocromo con color solo para estado, dos ejes visibles, Inter servida localmente, tablas que se vuelven tarjetas en el teléfono y **modo oscuro** (DEC-188). Target ya no se agrega aquí: pasó al Inc. 1 (DEC-132).
- Perfiles de temporada.

### Incremento 3 — "Venta"

- Facebook Marketplace (precio estimado y luego observado).
- Activar SP-API (cuando exista cuenta de vendedor): comisiones exactas, restricciones, y base para publicación.
- changedetection.io como disparador sobre páginas de liquidación.
- RabbitMQ si hay multi-nodo; proxies si la tasa de bloqueo lo exige.

### PoCs (antes/durante incremento 1)

| PoC | Pregunta | Criterio |
|---|---|---|
| PoC-A | ¿Qué escalón de acceso y qué motor (Playwright vs Puppeteer, script Node desechable) necesitan HD y Walmart, siempre vía `oip-egress`? | Tasa de bloqueo por escalón y motor medida 7 días; IP doméstica nunca aparece |
| PoC-B | ¿Qué % de candidatos trae GTIN y hace match con ASIN en Keepa? | ≥ 60% en herramientas |
| PoC-C | ¿El inventario por tienda de HD es consultable de forma confiable? | Datos por tienda coinciden con visita/llamada |
| PoC-D | Spider de seguimiento vs PriceStalker v2.0.0 sobre las mismas 50 URLs | Decide si PriceStalker entra (por comercio) |

> *(v1.3)* La PoC-A se ejecuta desde el **Worker en el VPS** (DEC-120/121). En casa solo se prueba en `modo_red: desarrollo` contra la lista permitida.

> *(v1.4)* La **PoC-B** pasa a medir el % de candidatos identificados por código o por modelo + marca y el % con historial suficiente a los 7 días, sin Keepa. La PoC-A puede vivir como script desechable antes de crear `oip-worker` (insumo §8.4).

---

## 13. Decisiones arquitectónicas (ADR)

| ID | Decisión | Estado |
|---|---|---|
| ADR-001 | Núcleo en Python/FastAPI | Aprobada (reemplaza Spring Boot) |
| ADR-002 | Scrapy para descubrimiento **y** seguimiento | Aprobada |
| ADR-003 | Playwright como motor por defecto; stealth disponible, apagado por defecto | Aprobada |
| ADR-020 | Interfaz de renderizado (`BrowserRenderer`) con motor por fuente; Puppeteer como servicio Node aparte, construido solo si la PoC-A muestra una fuente que pasa con Puppeteer y no con Playwright | Aprobada (implementación condicional) |
| ADR-021 | *(v1.3)* Dos funcionalidades (búsqueda automatizada y búsqueda por artículo) sobre un mismo motor de adquisición | Aprobada |
| ADR-022 | *(v1.3)* Topología Core local + Scraper Worker remoto en VPS, con interfaz configurable; solo el worker remoto se construye | Aprobada |
| ADR-023 | *(v1.3)* Consulta responsable: límites por dominio, pausas, concurrencia 1, caché, reintentos 1/5/15 min, timeouts y pausa por bloqueo | Aprobada (valores provisionales) |
| ADR-024 | *(v1.3)* `modo_red` estricto/desarrollo con bloqueo de comercios desde casa por firewall | Aprobada |
| ADR-025 | *(v1.3)* Rocky + Podman también en el VPS; no se adoptan Java/Spring Boot ni Ubuntu + Docker | Aprobada |
| ADR-026 | *(v1.4)* **IA opcional:** el código decide y la IA complementa; camino sin IA, interruptor `apagada \| solo registra \| aplica`, banco etiquetado, fuente registrada y pruebas sin modelo (§5.5) | Aprobada (DEC-177); se aplica cuando entre la primera función con IA |
| ADR-027 | *(v1.4)* **Contratos Core ↔ Worker versionados** (versión mayor ante cambio incompatible, N y N-1) y **bandeja de salida** en el Worker con deduplicación por clave de idempotencia en el Core (§8) | Aprobada (DEC-174, DEC-175) |
| ADR-028 | *(v1.4)* **Migraciones versionadas** y nunca manuales, con respaldo previo, etiqueta de rollback y PoC para TimescaleDB (§7.4) | Aprobada (DEC-179) |
| ADR-004 | PriceStalker opcional detrás de `TrackingProvider`, fijado v2.0.0 | PoC-D |
| ADR-005 | OIP mantiene catálogo maestro; producto ≠ publicación | Aprobada |
| ADR-006 | Oportunidad = margen neto sobre referencia de mercado; descuento declarado solo descubre | Aprobada |
| ADR-007 | Keepa como fuente de referencia y demanda de Amazon | Aprobada (confirmar plan) |
| ADR-007 *(v1.4)* | Referencia de precio **por etapas** detrás de una interfaz intercambiable: historial propio + comparación → APIs oficiales → **Keepa al final**, complementario y solo para Amazon | **Modificada** por DEC-123 y DEC-124 (Keepa diferido) |
| ADR-008 | SP-API: adaptador preparado, desactivado | Aprobada |
| ADR-009 | Tienda física con inventario por sucursal y costo de traslado | Aprobada |
| ADR-010 | Scrapyd + cola en Postgres; RabbitMQ diferido | Aprobada |
| ADR-011 | changedetection.io diferido a incremento 3 | Aprobada |
| ADR-012 | Telegram + dashboard como canales | Aprobada |
| ADR-012 *(v1.4)* | Telegram + dashboard, con el formato de avisos de la guía de estilo §10 | Aprobada · precisada por DEC-189 |
| ADR-013 | PostgreSQL + TimescaleDB para series de precio | Aprobada |
| ADR-014 | Podman rootless + Quadlets en Rocky Linux | Aprobada |
| ADR-015 | PriceGhost descartado | Aprobada |
| ADR-016 | Acceso por fuente con escalera `api_feed → http → browser → browser_stealth`; stealth solo por decisión manual con datos | Aprobada (reemplaza "stealth como requisito") |
| ADR-017 | Todo el scraping sale por `oip-egress` (VPS → proxy), fail-closed; IP doméstica nunca expuesta | Aprobada · *(v1.3) precisada por ADR-022: el scraping corre en el VPS* |
| ADR-022 *(v1.4)* | Topología Core + Worker en **dos repositorios** (`oip-core` sin spiders, verificado por un gate; `oip-worker` con su `CLAUDE.md` y `openspec/`) | Aprobada · precisada por DEC-173 |
| ADR-016 *(v1.4)* | Escalera de acceso: las APIs oficiales entran como `api_feed`; comparadores y sitios de seguimiento solo como señal | Aprobada · precisada por DEC-133 y DEC-154 |
| ADR-018 | Oportunidades se evalúan con margen ajustado y se ordenan por ROI anualizado | Aprobada · *(v1.3) modificada: se ordenan por rendimiento mensual (RN-005)* |
| ADR-018 *(v1.4)* | Oportunidades se evalúan **por canal** (Amazon FBM y venta local) con margen ajustado, se elige canal por ganancia total del lote (RN-018) y se ordenan por rendimiento mensual | Aprobada · precisada por DEC-140, DEC-151 y DEC-170 |
| ADR-019 | Disponibilidad en tienda con confianza, antigüedad y re-consulta previa al viaje | Aprobada |

---

## 14. Pendientes y preguntas abiertas

1. **Presupuesto mensual** para Keepa y, en su caso, proxies.
2. **Margen absoluto mínimo** ($X) por nivel.
3. **Parámetros de traslado:** valor de tu hora, rendimiento del vehículo, tiempo de cruce promedio.
4. Lista inicial de **sucursales** en San Diego por comercio.
5. Tabla inicial de **comisiones y restricciones** por categoría (validar en Seller Central).
6. Confirmar licencias de Scrapyd, extruct, price-parser y Spidermon en el commit fijado.
7. **Proveedor de VPS** para el egress del MVP (región EE. UU. recomendada) y, a futuro, proveedor de proxies residenciales.
8. Acceso a la **API de afiliados de Walmart** (requisitos y datos disponibles).
9. Tasas de devolución y valores iniciales de decaimiento de confianza por categoría.
10. Estado de mantenimiento actual de `puppeteer-extra-plugin-stealth` y alternativas stealth para Playwright.
11. *(v1.3)* Verificar precios y tamaño del VPS (DEC-119) y contratarlo.
12. *(v1.3)* Decidir si se respeta robots.txt por comercio (RN-010 · P2).
13. *(v1.3)* Preguntas de la búsqueda por artículo: impuesto en el total, ¿Jesús compra y entrega o solo comparte el enlace?, reacondicionados, cobro del servicio, comercios adicionales (RN-011 · P1–P6).
14. *(v1.4)* **Resueltos o cambiados desde la v1.3:** Keepa diferido (1, DEC-124); robots.txt se respeta por defecto (12, DEC-165); búsqueda por artículo resuelta en RN-011 v2 (13, DEC-166, DEC-168); tamaño del VPS para arrancar (7 y 11, DEC-127, falta contratar).
15. *(v1.4)* Dirección del **PO Box** y **empaques** (RN-001 · P3, P4, P6), pendientes del experto (sesión 3).
16. *(v1.4)* Validar en la sesión 3 las propuestas aceptadas por Jesús (DEC-159 a DEC-167) y los umbrales de RN-012 a RN-017.
17. *(v1.4)* Decidir en la Etapa 3 la única puerta a la red del Core, o ninguna (DEC-178).
18. *(v1.4)* Nombre definitivo de los repos (`oip-core` puede ser este repo renombrado o tal cual) y fecha de la separación (DEC-173).

---

## 15. Fuentes

- Scrapy — <https://github.com/scrapy/scrapy> · <https://docs.scrapy.org/>
- scrapy-playwright — <https://github.com/scrapy-plugins/scrapy-playwright>
- Scrapyd — <https://github.com/scrapy/scrapyd>
- extruct — <https://github.com/scrapinghub/extruct>
- price-parser — <https://github.com/scrapinghub/price-parser>
- Spidermon — <https://github.com/scrapinghub/spidermon>
- PriceStalker — <https://github.com/mikeknight85/PriceStalker> (clonado y revisado 8-nov-2026)
- PriceGhost — <https://github.com/clucraft/PriceGhost> (clonado y revisado 8-nov-2026)
- changedetection.io — <https://github.com/dgtlmoon/changedetection.io>
- Keepa API — <https://keepa.com/api-docs/> · <https://keepa.com/api-docs/plans-tokens.html>
- Precios Keepa (terceros) — <https://revenuegeeks.com/software/keepa/api>
- TimescaleDB — <https://github.com/timescale/timescaledb>
- Podman Quadlet — <https://docs.podman.io/en/latest/markdown/podman-systemd.unit.5.html>
- *(v1.4)* Registro de decisiones — `docs/proceso/registro-de-decisiones.md` (DEC-123 a DEC-190)
- *(v1.4)* Reglas de negocio v2 — `docs/negocio/reglas/` (RN-001 a RN-011 v2, RN-012 a RN-018 v1)
- *(v1.4)* Insumo del stack de tickets — `docs/arquitectura/insumos/referencia-stack-tickets.md`
- *(v1.4)* Guía de estilo — `docs/diseno/guia-de-estilo.md`

---

**Fin del documento.**
