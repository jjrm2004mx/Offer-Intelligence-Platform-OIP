# Registro de decisiones — OIP

**Propósito:** que ninguna decisión dependa de una conversación. Aquí está **todo lo acordado**, con fecha, motivo y dónde aplica.
**Regla de mantenimiento:** este registro **solo se amplía**. Una decisión que cambia no se borra: se marca `REEMPLAZADA POR DEC-xxx` y se agrega la nueva.
**Versión:** 1.2 — 2026-11-11 (v1.0: sesión del 8-nov-2026 · v1.1: retroalimentación del experto, sesión 1 · v1.2: análisis de fuentes de mercado y casos reales)

**Estados:** `VIGENTE` · `PROVISIONAL` (valor por confirmar con el experto o con datos) · `PROPUESTA` (pendiente de aprobación de Jesús) · `REEMPLAZADA`

**Fuentes:**
- Arquitectura: `docs/arquitectura/arquitectura-tecnica.md` (archivo único vigente; versiones anteriores en su tabla "Archivo vigente")
- Reglas de negocio: `docs/negocio/reglas/`
- Flujos: `docs/proceso/flujo-general.md` y `docs/proceso/flujo-negocio-a-requerimiento.md`
- Requerimiento: issue #2 (REQ-2026-0001), inspección: issue #3

---

## 1. Producto y alcance

| ID | Decisión | Estado | Motivo | Dónde aplica |
|---|---|---|---|---|
| DEC-001 | OIP es una **herramienta interna, personal y privada** para detectar oportunidades de reventa | VIGENTE, **precisada por DEC-110** (también ofrece un servicio a clientes) | Definición del dueño del producto | Todo |
| DEC-002 | **Oportunidad comercial = margen de reventa** validado contra el precio de mercado, no contra el descuento anunciado (caso "lámpara") | VIGENTE | Un 90% anunciado puede ser falso | Arq. C-01, ADR-006; RN-003 |
| DEC-003 | Operación **todo el año**, con perfiles de temporada (Buen Fin, Black Friday, Navidad, regreso a clases, liquidaciones) | VIGENTE | La Navidad es solo un pico | Arq. §1, §3.1 |
| DEC-004 | Interés en descuentos de **40% a 90%**, siempre como descuento **real** | VIGENTE | Las ofertas raras y profundas son el objetivo | RN-009 |
| DEC-005 | Comercios: **Home Depot y Walmart** en el Inc. 1; **Target** en el Inc. 2; después, comercios reconocidos por categoría | VIGENTE, **precisada por DEC-132** (Target se adelanta al Inc. 1; entran Best Buy, GameStop y Nintendo Store) | Los más relevantes primero | Arq. §3.1, §12 |
| DEC-006 | Categorías: **herramientas (prioridad)**, hogar e iluminación, tecnología, juguetes, relojes, joyería, perfumes; abierto a "lo que la gente mueve" | VIGENTE, **precisada por DEC-138** | — | Arq. §3.1; RN-006 |
| DEC-007 | Compra **en línea** y en **tienda física** en la zona de San Diego; más lejos solo si la ganancia lo justifica | VIGENTE | Las liquidaciones más profundas suelen estar en tienda | Arq. C-03, §6; RN-007, RN-008 |
| DEC-008 | Venta en **Amazon FBM** (envío propio, no FBA) como referencia; **Facebook Marketplace** en una fase posterior | VIGENTE, **precisada por DEC-140** (canales por oportunidad: Amazon FBM y venta directa en el Inc. 1) | — | Arq. §3.1; RN-006 |
| DEC-009 | **Logística y costos transfronterizos de la venta fuera del modelo** (la venta puede ser en EE. UU. o en México) | VIGENTE | Decisión del dueño del producto | Arq. C-14, §6.4; RN-001 |
| DEC-010 | El **costo del viaje a comprar** (km, gasolina, cruce, tiempo) **sí** cuenta | VIGENTE | Es costo de adquisición | RN-008 |
| DEC-011 | Todos los cálculos en **USD** | VIGENTE | — | RN-001 |
| DEC-012 | Fuera de alcance por ahora: compra automática, publicación automática, CAPTCHA con servicios de terceros, sesiones con cuentas personales de las tiendas | VIGENTE | — | Arq. §3.2 |
| DEC-013 | **Cuenta de vendedor de Amazon:** no existe todavía; dejar todo preparado (adaptador SP-API desactivado) | VIGENTE | Se usará después | Arq. ADR-008 |

## 2. Arquitectura y stack

| ID | Decisión | Estado | Motivo | Dónde aplica |
|---|---|---|---|---|
| DEC-020 | Núcleo en **Python / FastAPI** (en lugar de Java / Spring Boot) | VIGENTE | Java no es requisito; un solo lenguaje para núcleo y crawling | Arq. C-04, ADR-001 |
| DEC-021 | **PostgreSQL + TimescaleDB** para las series de precio | VIGENTE | Historial de precios con alto volumen | Arq. ADR-013 |
| DEC-022 | **Scrapyd + cola de tareas en PostgreSQL**; RabbitMQ diferido hasta que haya varios nodos | VIGENTE | Volumen inicial bajo | Arq. C-09, ADR-010 |
| DEC-023 | **Keepa** como fuente de precio de mercado y demanda de Amazon (plan de entrada ~49 €/mes y 20 tokens/min, por confirmar) | VIGENTE como fuente futura, **diferida por DEC-123 y DEC-124** (no se contrata en la PoC; entra al final, conforme madure el producto); **precisada por DEC-156** (sin consulta directa a Amazon mientras tanto) | Historial de precio y BSR sin hacer scraping de Amazon | Arq. §4.3, ADR-007 |
| DEC-024 | Alertas por **Telegram** + tablero (**Metabase** en el Inc. 1, UI propia en el Inc. 2) | VIGENTE | Las ofertas fuertes duran horas | Arq. C-10, ADR-012, §9.1 |
| DEC-025 | Despliegue en **Rocky Linux + Podman rootless con Quadlets**; `podman-compose` solo para desarrollo | VIGENTE | Plataforma objetivo | Arq. C-11, ADR-014 |
| DEC-026 | OIP mantiene el **catálogo maestro**; producto ≠ publicación | VIGENTE | — | Arq. ADR-005 |
| DEC-027 | Identificación del producto: UPC/GTIN (preferente) → MPN + marca → búsqueda en Keepa → título (solo auxiliar) | VIGENTE | Evitar coincidencias incorrectas | Arq. §7.3 |
| DEC-028 | La arquitectura debe pasar a **v1.3** para alinearse con las RN (rendimiento mensual en vez de ROI anualizado; niveles por mínimo y no por rangos; precio de venta sin ajuste por competencia; MERCADO YA BARATO sin condición del 50%; viaje fuera del margen por unidad) | VIGENTE — **aplicada en la arquitectura v1.3** (C-25), en revisión de Jesús | En reglas de negocio prevalecen las RN | REQ #2 §9; Arq. v1.3 |

## 3. Repositorios base Open Source (los 4) y apoyo

| ID | Decisión | Estado | Cuándo entra | Dónde aplica |
|---|---|---|---|---|
| DEC-030 | **Scrapy** (BSD-3): descubrimiento **y** seguimiento de ofertas | VIGENTE | Inc. 1, con REQ de descubrimiento (parte A) | Arq. §4.1, ADR-002 |
| DEC-031 | **scrapy-playwright** (BSD-3): renderizado de páginas dinámicas; stealth disponible por fuente | VIGENTE | Inc. 1, parte A | Arq. §4.1, ADR-003 |
| DEC-032 | **PriceStalker** (MIT): **fuera del núcleo**; candidato opcional detrás de `TrackingProvider`, fijado en v2.0.0; entra para un comercio solo si gana la **PoC-D** (50 URLs) | VIGENTE | Inc. 1 (prueba comparativa) | Arq. C-06, §4.2, ADR-004 |
| DEC-033 | **changedetection.io** (Apache-2.0): disparador de descubrimiento cuando cambian páginas de liquidación | VIGENTE (diferido) | Inc. 3 | Arq. C-09, ADR-011 |
| DEC-034 | **PriceGhost**: **descartado** (abandonado desde feb-2026, sin archivo LICENSE) | VIGENTE | — | Arq. C-05, ADR-015 |
| DEC-035 | OSS de apoyo: **Scrapyd**, **extruct** (JSON-LD/GTIN), **price-parser**; **Spidermon** en el Inc. 2. Licencias por confirmar en el commit fijado | VIGENTE | Inc. 1 y 2 | Arq. C-12, §4.1 |
| DEC-036 | Hallazgos verificados en el código de PriceStalker (8-nov-2026): usa `puppeteer-extra-plugin-stealth`, tiene webhooks (6 eventos de alerta), la única versión estable es v2.0.0, está pensado para Docker Compose | VIGENTE (dato) | — | Arq. §4.2 |

## 4. Acceso a comercios y protección de la IP

| ID | Decisión | Estado | Motivo | Dónde aplica |
|---|---|---|---|---|
| DEC-040 | Acceso **por fuente** con escalera `api_feed → http → browser → browser_stealth`. **Stealth apagado por defecto**; activarlo es una decisión manual de Jesús, registrada y medida (reemplaza "stealth como requisito", C-07) | VIGENTE | Riesgo legal y operativo por fuente, decidido con datos | Arq. §3.3, C-17, ADR-016 |
| DEC-041 | **La IP de casa nunca se usa para scraping.** Todo sale por `oip-egress` (WireGuard → VPS en el MVP; proxies residenciales cuando haya volumen), en una red interna sin salida a internet, fail-closed, con verificación de IP en cada job | VIGENTE (requisito duro), **precisada por DEC-120 y DEC-121** (topología Core/Worker y modo de red en la PoC) | Proteger la IP doméstica | Arq. §3.4, C-18, ADR-017 |
| DEC-042 | Las APIs legítimas (Keepa, Telegram, SP-API) salen directo, sin egress | VIGENTE | No hay riesgo | Arq. §3.4 |
| DEC-043 | **Puppeteer** como motor **alternativo** por fuente, detrás de `BrowserRenderer` (`browser_engine = playwright \| puppeteer`). Playwright es el valor por defecto; el servicio Node de Puppeteer se construye **solo si la PoC-A lo justifica** (matiza C-08) | VIGENTE | Un comercio puede detectar un motor y no el otro | Arq. §3.3.1, C-19, ADR-020, R-17 |
| DEC-044 | **PoC-A** (experimento de bloqueo) por escalón y por motor, siempre vía `oip-egress`, **antes** de escribir la parte A (descubrimiento) | VIGENTE | No especificar el acceso sin datos | Arq. §12 |
| DEC-045 | Volumen: el MVP con pocas consultas; se escala y se contratan terceros (proxies) solo si se demuestra que funciona | VIGENTE | Costo controlado | Conversación 8-nov |
| DEC-046 | Revisar la **API de afiliados de Walmart** como fuente de escalón 0 | PENDIENTE | Alternativa sin scraping | Arq. §14.8 |

## 5. Reglas de negocio (valores provisionales hasta la sesión con el experto)

| ID | Decisión | Estado | Dónde aplica |
|---|---|---|---|
| DEC-050 | Margen neto = venta esperada − (compra + impuesto + envío hacia mí) − (comisión + envío al cliente + empaque + otros) | VIGENTE | RN-001 |
| DEC-051 | Precio de mercado = el más bajo entre Amazon hoy, la mediana de 90 días y otros comercios (≤ 48 h); precio de venta esperado = el más bajo entre Amazon hoy y la mediana de 90 días | PROVISIONAL | RN-002 |
| DEC-052 | Descuento real mínimo 20%; "precio antes" inflado si es > 1.5 × la mediana de 60 días (≥ 5 consultas) | PROVISIONAL | RN-003 |
| DEC-053 | Demanda suficiente: ranking ≤ 150,000 y ≤ 20 vendedores; advertencia si empeora > 50% en 30 días | PROVISIONAL | RN-004 |
| DEC-054 | Margen ajustado: devoluciones (tasa × pérdida 50%), castigo por baja 50% de (precio esperado − mínimo de 90 días), días según ranking (7 / 21 / 45) + 14 días de pago; **rendimiento mensual** para ordenar; unidades = ventas ÷ (vendedores + 1) con tope | PROVISIONAL | RN-005 |
| DEC-055 | Comisiones, envío por peso y restricciones en una **tabla manual** mientras no exista SP-API | PROVISIONAL | RN-006 |
| DEC-056 | Confianza del dato de tienda: Alta / Media / Baja con ventanas de 6 / 12 / 24 h; baja un nivel con 2 "no encontrado" en 5 visitas; re-consulta antes del viaje; solo Alta y Media generan alerta | PROVISIONAL | RN-007 |
| DEC-057 | Viaje: $0.20/km, hora a $15, 1.5 h de cruce, 0.5 h por tienda; ganancia mínima por viaje $50 en San Diego y $150 fuera; rutas que juntan tiendas | PROVISIONAL | RN-008 |
| DEC-058 | Niveles por **mínimos** (se asigna el más alto que se cumpla): Excepcional ≥ 80% / ≥ 50% · Muy buena ≥ 70% / ≥ 40% · Buena ≥ 50% / ≥ 30% · Interesante ≥ 40% / ≥ 25%; mínimo $10 por unidad | PROVISIONAL | RN-009 |
| DEC-059 | Avisos: inmediatos (Excepcional y Muy buena), resumen a las 8:00 y 18:00 (Buena), solo tablero (Interesante); no repetir en 24 h salvo que suba de nivel o el precio baje ≥ 5% | PROVISIONAL | RN-009 |
| DEC-060 | Redondeo: cada monto a centavos con el medio centavo hacia arriba; porcentajes sin redondear para comparar y calcular, con 1 decimal al mostrar | VIGENTE | REQ #2 §10 |

## 6. Proceso de trabajo

| ID | Decisión | Estado | Dónde aplica |
|---|---|---|---|
| DEC-070 | Repositorio **GitHub privado** `jjrm2004mx/Offer-Intelligence-Platform-OIP`, **sin licencia** (todos los derechos reservados) | VIGENTE | Repo |
| DEC-071 | Trabajo en **ramas con PR** hacia `main`; commits con los trailers `Refs: #N` y `Change: <id>` | VIGENTE | Repo |
| DEC-072 | **OpenSpec** como columna vertebral técnica, desde la etapa de análisis (`/opsx:propose`, `/opsx:apply`, `/opsx:archive`) con Claude Code | VIGENTE | Etapa 4 |
| DEC-073 | **Squad** no se usa por ahora (alfa, orientado a Copilot); se puede probar en un cambio aislado del Inc. 2 | VIGENTE | — |
| DEC-074 | **Dos capas:** regla de negocio (RN, lenguaje llano, la ve el experto) y requerimiento formal (REQ, issue, no lo ve el experto) | VIGENTE | Etapas 1–2 |
| DEC-075 | El **requerimiento para el experto es indispensable**; la información del experto llega por las RN | VIGENTE | Etapa 1 |
| DEC-076 | `oip-inspector` inspecciona el **REQ** (14 criterios, tipo Fagan); las RN pasan por la **revisión de consistencia** (`oip-revisor-rn`) | VIGENTE | Etapas 1–2 |
| DEC-077 | **Gates humanos:** G1 lo acordado con el experto · G2 *"lo leo yo primero"* antes de inspeccionar · G3 la propuesta de OpenSpec · G4 el PR · G5 activar stealth | VIGENTE | Todas |
| DEC-078 | **Nada se duplica:** el mismo issue de REQ y el mismo issue de inspección se versionan (v1, v2…) con historial por columnas | VIGENTE | Etapa 2 |
| DEC-079 | Traza **`OIP_TRACE` schema 1** como comentario en los issues (se corrigió el campo `parent_issue` duplicado del original) | VIGENTE | Etapas 2–5 |
| DEC-080 | Formato de ID **`REQ-AAAA-NNNN`**; etiquetas `Requerimiento`, `Inspeccion` y `Regla de negocio`; milestone "Incremento 1" | VIGENTE | GitHub |
| DEC-081 | **Un solo requerimiento del usuario** (el flujo de punta a punta de la arquitectura §1 y el Inc. 1 de §12, **scraping incluido**), dividido en **partes A / B / C** para construir e inspeccionar: A descubrimiento, B evaluación (#2), C avisos y tablero | ACORDADA, pendiente de aplicar | Issues |
| DEC-082 | **Orden de construcción:** el motor (parte B) primero, porque no hace scraping; la PoC-A antes de la parte A | VIGENTE | Inc. 1 |
| DEC-083 | Agentes **reescritos desde cero**, inspirados en los SWD-TELCO, **sin texto ni referencias corporativas**; **sin COSMIC**; agentes nuevos: `oip-negocio` y `oip-seguridad` | VIGENTE | `.claude/agents/` |
| DEC-084 | Dos modos de trabajo: **completo** (REQ nuevo) y **ligero** (ajustes: developer → tester → seguridad) | VIGENTE | Etapa 4 |
| DEC-085 | Gates automáticos previstos: pytest y cobertura, ruff, gitleaks, pip-audit, bandit, regla de egress, trazabilidad; hook de commits | VIGENTE (se implementa en la Etapa 3) | Etapa 3 |
| DEC-086 | GitHub Action **"Requiere reinspección"** cuando cambia la versión de una RN | PROPUESTA | Etapa 2 |
| DEC-087 | **GitHub Project "OIP"** (tablero de etapas) para aprender la herramienta; el inspector conserva el control de "proyecto asociado" | VIGENTE (Jesús lo crea) | GitHub |
| DEC-088 | Trazabilidad de punta a punta: Requerimiento → Análisis → Diseño → Tareas → Rama/PR → Código → Documentación | VIGENTE | Todas |

## 7. Publicación para el experto

| ID | Decisión | Estado | Dónde aplica |
|---|---|---|---|
| DEC-090 | Las RN se publican en **Vercel** (`oip-negocio.vercel.app`) a partir de `docs/negocio/`; se actualizan solas al hacer merge a `main` | VIGENTE | Vercel |
| DEC-091 | Sitio **docsify** sin build, con la librería incluida en el repo (MIT); `noindex` (meta, cabecera y `robots.txt`); sin contraseña porque el plan Hobby no la ofrece | VIGENTE | `docs/negocio/` |
| DEC-092 | Vercel no publica archivos `README.md`: la portada es `inicio.md` | VIGENTE (dato) | `docs/negocio/` |
| DEC-093 | El experto responde citando **`RN-00X · P#`**; cada respuesta queda en "Decisiones tomadas" de la RN | VIGENTE | RN |

## 8. Preferencias de trabajo

| ID | Decisión | Estado |
|---|---|---|
| DEC-100 | Aprender haciendo; propuestas acotadas, que Jesús reduce o corrige | VIGENTE |
| DEC-101 | **No perder decisiones ni contenido**: los cambios solo agregan o reemplazan por versiones que lo contienen todo; nunca se borra sin acuerdo explícito | VIGENTE |
| DEC-102 | Una sola fuente de verdad para la arquitectura: **el repo**. La copia del Drive se sincroniza desde el repo | VIGENTE |
| DEC-103 | La arquitectura vive en **un solo archivo vigente** (`docs/arquitectura/arquitectura-tecnica.md`), sin versión en el nombre; el historial lo guarda GitHub y las versiones anteriores se consultan con enlaces permanentes a commit, desde la tabla "Archivo vigente" del propio documento | VIGENTE (2026-11-11) |

## 9. Retroalimentación del experto de negocio — sesión 1 (2026-11-09)

Fuente: resumen de la sesión que compartió Jesús. Las sugerencias técnicas del experto se registran también cuando **no** se adoptan, para que quede claro qué se consideró.

| ID | Decisión | Estado | Motivo | Dónde aplica |
|---|---|---|---|---|
| DEC-110 | OIP tiene **dos funcionalidades**: **A. Búsqueda automatizada de ofertas** (periódica y autónoma, para reventa) y **B. Búsqueda particular por artículo**, que se ofrece como **servicio a clientes** (por ejemplo, un cliente busca un Nintendo Switch) | VIGENTE | Propuesta del experto, confirmada por Jesús como necesaria | RN-011; Arq. v1.3 §1; REQ (parte D) |
| DEC-111 | La búsqueda por artículo **entra en el Incremento 1** | VIGENTE | Decisión de Jesús | Plan de incrementos |
| DEC-112 | En el Inc. 1, el cliente le pide el artículo **a Jesús** y Jesús lo **captura en OIP**. Que el cliente pida directamente (por ejemplo por WhatsApp) es **funcionalidad futura** | VIGENTE | Decisión de Jesús | RN-011 |
| DEC-113 | Regla de la búsqueda por artículo: **primero, dónde está más económico; segundo, que esté disponible** | VIGENTE (con preguntas de detalle en RN-011) | Decisión de Jesús | RN-011 |
| DEC-114 | Las dos funcionalidades **comparten el mismo motor de adquisición** (API · HTTP · navegador) y los mismos controles | VIGENTE | Propuesta del experto | Arq. v1.3 |
| DEC-115 | **Consulta responsable:** limitar cuántas consultas se hacen (rate limiting), regular la velocidad (throttling), reutilizar información (caché), esperar de forma creciente ante errores (backoff exponencial), controlar la concurrencia, reintentos y tiempos de espera (timeout), con valores por comercio | VIGENTE (valores provisionales) | Propuesta del experto | RN-010; Arq. v1.3 |
| DEC-116 | Postura de OIP: automatizar no implica infringir reglas; **OIP no pretende ocultarse ni evadir restricciones**; stealth es opcional y queda **deshabilitado por defecto** (confirma DEC-040) | VIGENTE | Acordado con el experto | RN-010; DEC-040 |
| DEC-117 | **Proxies residenciales:** el experto recomienda descartarlos. **Jesús decide no descartarlos**: no entran al MVP y quedan como opción para cuando haya volumen (sin cambio respecto a DEC-041) | VIGENTE | Decisión de Jesús | DEC-041 |
| DEC-118 | **Tecnologías sin cambio:** Python/FastAPI (DEC-020) y Rocky Linux + Podman (DEC-025), **también en el VPS**. **No se adoptan** las sugerencias técnicas del experto (Java/Spring Boot, Ubuntu + Docker). Las decisiones técnicas son del equipo técnico; el experto aporta en su ramo | VIGENTE | Decisión de Jesús | Arquitectura |
| DEC-119 | Infraestructura sugerida por el experto, como **referencia por verificar**: VPS (Hetzner, DigitalOcean o Vultr), del orden de USD 6.49/mes para 2 vCPU / 4 GB + USD 0.60 de IPv4. El experto recomienda 4 vCPU / 8 GB para correr navegadores | PROVISIONAL (precios sin verificar), **precisada por DEC-127** | Dato del experto | Arq. v1.3 §9 |
| DEC-120 | **Topología configurable:** el Core habla con el worker de adquisición por una interfaz única, así que el worker puede vivir en un **VPS (worker remoto)** o en casa detrás de un túnel. **Solo se construye y opera el worker remoto**: el Core (reglas, BD, tablero, alertas) en el servidor de Jesús y el Scraper Worker en el VPS, con comunicación cifrada y autenticada (WireGuard). El modo túnel queda documentado y sin construir | VIGENTE | Propuesta del experto; la consulta nace en el VPS y la casa nunca habla con los comercios | Arq. v1.3 §3.4, §5, §9 |
| DEC-121 | **Modo de red configurable para la PoC** (`modo_red: estricto \| desarrollo`), con **límite duro**: estricto por defecto; en desarrollo, desde casa solo se consulta una **lista permitida** (datos guardados, simulaciones, APIs); **Home Depot, Walmart y Target bloqueados desde casa por el firewall del servidor**, sin opción que los desbloquee; aviso visible y registro de quién lo activó y cuándo | VIGENTE, **precisada por DEC-122** | Flexibilidad para probar sin exponer la IP | RN-010; Arq. v1.3 §3.4 |
| DEC-122 | El límite duro de DEC-121 se implementa como **lista de permitidos con salida denegada por defecto** en el firewall del servidor de Jesús (no como lista de prohibidos): solo salen Keepa, Telegram, WireGuard al VPS, el registro de imágenes y los servicios de prueba; todo lo demás, incluidos todos los comercios, queda bloqueado | VIGENTE (2026-11-11) | Los comercios usan CDN con IPs cambiantes; una lista de prohibidos es frágil y no cubre comercios futuros | Arq. §3.6 |

## 9.1 Análisis de fuentes de mercado y casos reales (2026-11-11)

Fuente: análisis con ejemplos que compartió Jesús (comparación entre comercios, descuentos inflados, uso de Keepa, costos) y el caso real `docs/negocio/casos/CASO-001-switch2-zelda.md`. Las reglas de negocio afectadas se reescriben **al terminar los ejercicios de comprobación**; mientras tanto llevan un aviso "por actualizar".

| ID | Decisión | Estado | Motivo | Dónde aplica |
|---|---|---|---|---|
| DEC-123 | **Fuente del precio de referencia, por etapas, conforme madure el producto:** (1) **historial propio de OIP** (local), reforzado con los precios de hoy de otros comercios; si todavía no hay historial propio, **solo la comparación entre comercios**; (2) **APIs oficiales** de los comercios que las tengan (Amazon, Walmart u otros), cuando el producto madure; (3) **Keepa al final**. Cada fuente se conecta por una interfaz intercambiable y se guarda cuál se usó | VIGENTE (decisión de Jesús) | No depender de un servicio de pago para lo que OIP puede construir; el historial es propiedad de OIP | RN-002, RN-003, RN-012; Arq. §2.2, §4.3, §12 |
| DEC-124 | **Keepa diferido:** no se contrata en la PoC. Cuando se use, es **solo para productos de Amazon**, como fuente **complementaria** de historial de precio y de Sales Rank; se contrata **por meses** ante una necesidad concreta (por ejemplo, un producto que un cliente pide y que OIP nunca monitoreó), y sus resultados se guardan y reutilizan. La integración puede desarrollarse antes con **respuestas simuladas**. El historial de Keepa es de Amazon, no del mercado completo | VIGENTE | Su API cobra suscripción con tokens que expiran a los 60 min; no se paga por consulta | Arq. §4.3, ADR-007 (por anotar) |
| DEC-125 | **Filosofía de contratación:** (1) servicios gratuitos o locales primero; (2) pago por consumo cuando sea posible (proxies, almacenamiento); (3) suscripciones solo cuando aporten **valor comprobado** | VIGENTE | Propuesta del experto, aceptada | Toda contratación |
| DEC-126 | **Costos por etapa de operación:** PoC inicial (datos guardados y simulaciones) **USD 0**; PoC con consultas reales: VPS **~USD 5–15/mes** (precio por verificar), WireGuard USD 0, sin proxies; evolución: proxies residenciales **por GB** solo con volumen (DEC-117), APIs oficiales según autorización y condiciones, Keepa según DEC-124. No incluye otros servicios futuros (almacenamiento externo, notificaciones) | PROVISIONAL (precios sin verificar) | Costo operativo inicial prácticamente nulo | Arq. §9, §12 |
| DEC-127 | **Tamaño del VPS, creciente:** arrancar con **2 vCPU / 4 GB** (Rocky Linux + Podman, DEC-118; 40–50 GB de disco; IPv4 pública; WireGuard). Alcanza porque RN-010 limita a **1 consulta a la vez por comercio** y un navegador ocupa del orden de 1–1.5 GB. **Subir a 4 vCPU / 8 GB** cuando se mida memoria > 75% sostenida, o al correr varios navegadores en paralelo (más comercios o más frecuencia) | PROPUESTA (recomendación pedida por Jesús) | Pagar solo lo que se usa; el crecimiento se decide con datos medidos | Arq. §9; DEC-119 |
| DEC-128 | **Tres indicadores distintos que no se mezclan:** **descuento** (cuánto bajó contra el precio habitual), **competitividad** (qué tan barato está contra otros comercios hoy) y **demanda** (qué tan solicitado es). El **Sales Rank es un indicador de popularidad**, no de unidades vendidas | VIGENTE | Un producto puede tener excelente precio y poca demanda, o al revés | RN-003, RN-004, RN-012; glosario |
| DEC-129 | **Cuatro referencias de precio separadas:** **MSRP** (precio oficial del fabricante), **precio tachado** del comercio ("antes / was"), **precio de mercado hoy** (comparación horizontal) y **precio habitual** (comparación histórica, del historial propio). **El descuento real solo se calcula contra el precio habitual.** El MSRP solo se usa cuando no hay historial y, con él, el máximo es "Precio competitivo". El precio tachado nunca es referencia: solo se compara contra el habitual para detectar descuentos inflados | VIGENTE | Nunca confundir un precio sugerido o anunciado con el precio al que realmente se vende | RN-002, RN-003, RN-012 |
| DEC-130 | **Historial suficiente:** el precio habitual es la **mediana de las observaciones de los últimos 60 días**, con **al menos 5 observaciones en al menos 3 días distintos**. Con menos datos, el producto queda "sin historial suficiente" | PROVISIONAL (aceptado por Jesús; validar con el experto) | Durante los primeros días no hay base para afirmar que un descuento es excepcional | RN-012; RN-002 |
| DEC-131 | **Clasificación en dos ejes:** (1) **calidad del precio**, nueva **RN-012**: Oferta excepcional · Buena oferta · Precio competitivo · Descuento cuestionable; (2) **oportunidad de reventa**, RN-009 (niveles). Aplica a las dos funcionalidades; B usa solo el eje 1 | VIGENTE (umbrales por definir en RN-012) | Evita anunciar como gran oferta algo que solo tiene precio normal | RN-012 (por crear), RN-009 |
| DEC-132 | **Comercios:** **Best Buy y Target** en el Inc. 1 (Target se adelanta del Inc. 2); se agregan **GameStop y Nintendo Store**. **Solo tiendas de EE. UU., precios en USD** | VIGENTE | Los comercios del caso real; mismo mercado que el resto | DEC-005; Arq. §3.1, §12 |
| DEC-133 | **Fuentes futuras:** las **APIs oficiales** (Amazon, Walmart u otros que las tengan) entran como el escalón `api_feed`, el primero de la escalera de acceso. Un **comparador de precios** (por ejemplo Deal.ai) puede ser fuente, pero **cada precio se confirma contra la ficha del comercio** antes de recomendarse | VIGENTE (sin fecha) | Datos legítimos y más baratos de obtener; un comparador puede estar desactualizado | Arq. §3.3; RN-011 |
| DEC-134 | **Datos a capturar en cada observación:** (1) identificación exacta, que distinga **ediciones especiales** (GTIN; sin GTIN la comparación queda "no confirmada"); (2) precio; (3) **vendedor**: el comercio o un vendedor externo; (4) disponibilidad con **estados en línea**: disponible confirmada · existencia limitada · no confirmada · agotado; (5) **envío**: costo, plazo, envío o recoger en tienda, **también en la búsqueda de ofertas (A)**; (6) **MSRP** con fuente y fecha; (7) fecha y hora; (8) historial. El **precio tachado** se guarda y se usa según DEC-129 | VIGENTE | Sin estos datos no se puede afirmar que existe una oportunidad | Arq. §6, §7 (por anotar); RN-011 |
| DEC-135 | **Vendedor externo y canales especiales en la búsqueda por artículo (B):** las opciones de vendedor externo se muestran **marcadas y no se recomiendan por defecto**; los canales especiales (Walmart Business) se marcan "puede requerir cuenta especial" | VIGENTE | Cambian la confianza, la garantía y el riesgo de fraude | RN-011 v2 |
| DEC-136 | **Casos reales** como escenarios de prueba en `docs/negocio/casos/` (CASO-001 en adelante), en lenguaje llano y **en USD**; cuando exista el motor, cada caso se vuelve una prueba automática | VIGENTE | Comprobar las reglas antes de construir y revisarlas con el experto | `docs/negocio/casos/` |
| DEC-137 | **Vendedor externo en la búsqueda de ofertas (A):** la oportunidad **no se descarta ni se avisa automáticamente**; va a **revisión manual**, marcada "vendedor externo" | VIGENTE (decisión de Jesús, 2026-11-11) | Puede ser una oportunidad real, pero con más riesgo de fraude, garantía y devolución | RN-009 v2; precedencia DESCARTADA > REVISION_MANUAL > nivel (REQ-2026-0001) |
| DEC-138 | **Categorías:** las que **más consume la gente**, por **temporadas** (por ejemplo, la temporada navideña), pero con operación **todo el año**. Confirma y precisa DEC-006 (herramientas como prioridad, hogar e iluminación, tecnología, juguetes, relojes, joyería, perfumes, abierto a "lo que la gente mueve") y DEC-003 (perfiles de temporada); la lista priorizada por temporada se define al terminar los ejercicios | VIGENTE (lista priorizada por definir) | Los casos de videojuegos (CASO-001) y audio (CASO-003) caben en tecnología y juguetes | DEC-003, DEC-006; Arq. §3.1 |
| DEC-139 | **Sugerencias en la búsqueda por artículo (B):** según el tipo de artículo que busca el cliente, OIP puede **sugerir** ofertas o alternativas relacionadas (por ejemplo, la otra generación de un modelo, o una oferta de audífonos cuando busca audífonos). No es una funcionalidad aparte | VIGENTE (alcance por detallar en RN-011 v2) | Aprovechar las ofertas detectadas para el consumidor sin crear una tercera funcionalidad | RN-011 v2 |
| DEC-140 | **Canales de venta en el Inc. 1:** cada oportunidad se evalúa **por canal** y se elige el de mayor rentabilidad con posibilidad razonable de venta. Entran: **Amazon FBM**, calculado automáticamente, y **venta directa** (contactos, grupos locales, clientes), con **precio de venta estimado que captura Jesús** o un porcentaje del precio de mercado, siempre marcado "estimado". **Facebook Marketplace con datos observados** queda para después: no tiene API, exige sesión y solo muestra precios pedidos | VIGENTE (decisión de Jesús, 2026-11-11) | No descartar oportunidades por exigirles el canal más costoso | RN-001, RN-002, RN-004, RN-005, RN-006 v2; precisa DEC-008 |
| DEC-141 | **Compra por oportunidad en el Inc. 1:** comprar porque el precio es excepcional y conservar el producto hasta encontrar comprador. El riesgo de inventario se mide con los días para vender y el rendimiento mensual (RN-005) | VIGENTE (decisión de Jesús, 2026-11-11) | Algunas oportunidades valen aunque no haya comprador inmediato | RN-005, RN-009 v2 |
| DEC-142 | **El costo de entrega en venta directa usa las tarifas de RN-008** (USD 0.20/km y USD 15/hora del tiempo de Jesús), igual que el viaje a tienda. Ejemplo: 30 min y 10 km = USD 9.50 | VIGENTE, **confirmada por DEC-148** | Comparar canales con las mismas tarifas | RN-001 v2, RN-008 |
| DEC-143 | **Las reglas se amplían con el canal como parámetro, no se duplican:** cada RN que cambie pasa a **v2** con el canal de venta como parámetro (una sola fórmula de margen, de rentabilidad por tiempo, de niveles y de precio de venta, con costos de Amazon o costos locales). La **v1 no se borra**: queda en el historial de git, con su enlace permanente, y en este registro | VIGENTE (decisión de Jesús, 2026-11-11; camino "b" de ANL-002) | Dos copias de la misma fórmula tienden a separarse con el tiempo | RN-001, RN-002, RN-005, RN-009 v2; ANL-002 |
| DEC-144 | **Una sola numeración RN-xxx.** No se usan los prefijos RC ni RP; cada regla lleva un campo `grupo: común \| amazon \| local \| resultado`. Las reglas nuevas siguen desde RN-012 | VIGENTE (decisión de Jesús, 2026-11-11) | Issues, revisiones y decisiones ya citan RN-xxx; conserva la trazabilidad | Todas las RN; plantilla-rn.md |
| DEC-145 | **Agrupación de las reglas** según ANL-002 §2.1: de 38 entradas a **18 reglas**, las 11 actuales (algunas ampliadas) y 7 nuevas. Numeración provisional de las nuevas: **RN-012** calidad del precio · **RN-013** identificación del producto · **RN-014** condición y valor de usados · **RN-015** riesgo de compra y de venta · **RN-016** precio de venta local · **RN-017** demanda local · **RN-018** selección del mejor canal. RN-002 v2 conserva las referencias de precio (común) y el precio de venta en Amazon | VIGENTE (agrupación aprobada por Jesús; números provisionales) | Evitar reglas duplicadas o que solo cambian parámetros | ANL-002; RN v2 |
| DEC-146 | **Principio de diseño: el origen de compra y el canal de venta son independientes.** Ninguna regla obliga a vender en la plataforma donde se compró (RC-013 de ANL-002, que es principio y no regla) | VIGENTE | Encontrar la mejor combinación de compra y venta | ANL-001 §3; RN-018 |
| DEC-147 | **RN-002 separa dos referencias:** **precio de mercado hoy** (competitividad, comparación entre comercios) y **precio habitual** (descuento, historial). El descuento real se mide contra el habitual; la competitividad, contra el de hoy (P-01) | VIGENTE (2026-11-11) | Con un solo número "el más bajo de los dos", un descuento real puede quedar oculto (ejemplo: habitual $200, hoy $150 en otro comercio) | RN-002 v2, RN-003 v2, RN-012 |
| DEC-148 | **Confirma DEC-142:** el costo de entrega en venta local usa las tarifas de RN-008 (USD 0.20/km, USD 15/hora) (P-02) | VIGENTE (2026-11-11) | Mismas tarifas para todos los traslados | RN-008 v2, RN-001 v2 |
| DEC-149 | **Productos usados en el alcance**, con **estado obligatorio** (nuevo, caja abierta, reacondicionado, usado, para piezas) y valor de referencia de **usados comparables**, de preferencia ventas concretadas (P-03) | VIGENTE (2026-11-11) | Habilita la compra a particulares (CASO-006) | RN-014 |
| DEC-150 | **Particulares (F3) con captura manual** en el Inc. 1: Jesús captura las publicaciones de OfferUp, Marketplace u otras y OIP las evalúa; la búsqueda automática se considera después de revisar condiciones de uso, datos personales y protección de la IP (P-04) | VIGENTE (2026-11-11) | Mismo patrón que la captura de solicitudes de clientes (DEC-112) | RN-013, RN-015; Arq. |
| DEC-151 | **Alcance del Inc. 1: 3 orígenes × 2 canales.** Orígenes: tienda en línea, tienda física, particulares por captura manual. Canales: **Amazon FBM** (calculado) y **venta local** (OfferUp, Facebook Marketplace y venta personal juntas, con precio estimado) (P-05). Precisa DEC-140 | VIGENTE (2026-11-11) | Lo que se puede sostener con datos; se amplía con datos reales | Todas las RN v2; REQ-2026-0001 |
| DEC-152 | **Búsqueda por necesidad:** en el Inc. 1, Jesús traduce la necesidad del cliente en **1 a 3 modelos** al capturar la solicitud; la búsqueda por necesidad automática queda como funcionalidad futura (P-06) | VIGENTE (2026-11-11) | La automática exige criterios de equivalencia y amplía mucho el alcance | RN-011 v2 |
| DEC-153 | **Categorías priorizadas por temporada** (propuesta de Claude, por ajustar con el experto) (P-07). **Todo el año:** herramientas (prioridad), hogar y cocina, tecnología. **Enero:** liquidaciones posteriores a Navidad (tecnología, juguetes) y artículos de ejercicio. **Febrero:** perfumes, joyería, relojes (San Valentín). **Mayo:** perfumes, joyería, cocina (Día de las Madres en EE. UU.); herramientas y jardín (Memorial Day). **Junio:** herramientas, relojes, asadores (Día del Padre). **Julio:** tecnología y hogar (Prime Day y 4 de julio). **Julio y agosto:** tecnología y útiles (regreso a clases). **Septiembre:** herramientas y electrodomésticos (Labor Day); liquidación de verano (jardín y exterior). **Noviembre y diciembre:** juguetes, videojuegos, tecnología, perfumes, joyería y herramientas para regalo (Black Friday, Cyber Monday, Navidad) | PROVISIONAL (validar con el experto) | Precisa DEC-003 y DEC-138 con fechas de comercios de EE. UU. | Arq. §3.1 (perfiles de temporada) |
| DEC-154 | **Sitios de seguimiento de precios** (y comparadores y artículos editoriales) se usan **solo como señal**, nunca como dato de historial ni de precio; cada precio se confirma en la ficha del comercio (P-08). Precisa DEC-133 | VIGENTE (2026-11-11) | Pueden estar desactualizados y no son fuentes propias | RN-002 v2, RN-012 |
| DEC-155 | **Inventario de fuentes antes de desarrollar conectores:** una fila por comercio o plataforma con su tipo (1 API oficial · 2 páginas públicas · 3 páginas dinámicas · 4 marketplace con terceros · 5 requiere sesión o restringe la automatización), escalón inicial, condiciones de uso y `robots.txt` revisados, si requiere sesión y qué datos ofrece (precio, disponibilidad por tienda, vendedor, GTIN). La clasificación es una **hipótesis que se confirma en PoC-A**. El tipo 5 **nunca se automatiza con la cuenta personal de Jesús**: se queda en captura manual (DEC-150). Verificar si Best Buy, Walmart y Amazon tienen API vigente (candidatas al tipo 1) | VIGENTE (2026-11-11) | Modelo híbrido: no depender solo del scraping | Etapa 3; Arq. §3.3; RN-010 |
| DEC-156 | **Amazon no se consulta directamente.** En la etapa 1, OIP **no** consulta la página de Amazon; el precio, el historial y la demanda de Amazon llegan solo con una **API oficial** (etapa 2, si es accesible) o con **Keepa** (etapa 3) (P-09). Confirma el motivo de DEC-023. **Consecuencia:** el canal Amazon FBM de DEC-140 y DEC-151 se activa cuando exista esa fuente; mientras tanto, la reventa se evalúa en venta local | VIGENTE (decisión de Jesús, 2026-11-11) | No consultar Amazon directamente | RN-002, RN-004, RN-006 v2; DEC-140, DEC-151 |
| DEC-157 | **Productos de folletos y páginas de campaña sin precio tachado:** se investigan si son de una **categoría prioritaria de la temporada** (DEC-153) o si están **por debajo del último precio que OIP observó** (P-10) | VIGENTE (2026-11-11) | El filtro por descuento anunciado los dejaba fuera (CASO-007) | RN-003 v2 |
| DEC-158 | **Filtro previo:** descuento anunciado de **40%** en general y **30%** para marcas reconocidas de la lista prioritaria (P-11). Precisa DEC-004 | VIGENTE (2026-11-11; valores por confirmar con el experto) | La bocina Milwaukee (33.56%) quedaba fuera (CASO-007) | RN-003 v2 |
| DEC-159 | **Productos voluminosos o pesados** (refrigeradores, lavadoras y similares) **excluidos en el Inc. 1**, hasta tener una regla de flete (P-12) | VIGENTE (2026-11-11) | No son prácticos ni para Amazon FBM ni para entrega local | RN-006 v2, RN-016 |

## 10. Pendientes abiertos

| Pendiente | Dueño | Bloquea |
|---|---|---|
| Sesión con el experto (51 preguntas `RN-00X · P#`). **Sesión 1 hecha** (alcance e infraestructura, §9); quedan pendientes las preguntas de RN-001 a RN-009 | Jesús | RN v2 → REQ → reinspección v2 |
| Confirmar precios de VPS (DEC-119) y contratar | Jesús | PoC-A |
| Aplicar la parte D (búsqueda por artículo) en el requerimiento | Claude | — |
| Leer el REQ #2 v2 (G2) | Jesús | Reinspección |
| Aplicar la estructura A / B / C del requerimiento (DEC-081) | Claude | — |
| Crear el GitHub Project "OIP" y asociar el #2 | Jesús | D-002 de la inspección |
| ~~Contratar Keepa (confirmar plan)~~ **Diferido por DEC-124**: se contrata por meses solo ante una necesidad concreta | Jesús | — |
| VPS en EE. UU. para `oip-egress` | Jesús | PoC-A |
| Arquitectura v1.3 (DEC-028): **redactada**, pendiente de tu revisión (PR) | Jesús | — |
| Etapa 3, arranque técnico (OpenSpec, `CLAUDE.md`, agentes restantes, gates) | Claude | Etapa 4 |
| Decidir sobre la Action "Requiere reinspección" (DEC-086) | Jesús | — |
| **RN-002: separar "precio de mercado hoy" (competitividad) de "precio habitual" (descuento)** (DEC-128, DEC-129). Hoy la fórmula toma el más bajo entre el precio de hoy y la mediana de 90 días; falta que Jesús confirme el cambio | Jesús | RN-002 v2 |
| ~~Vendedor externo en la búsqueda de ofertas (A)~~ **Resuelto por DEC-137** (revisión manual) | — | — |
| Reescribir RN-002, RN-003, RN-004, RN-009 y RN-011 (v2) y crear RN-012 **al terminar los ejercicios de comprobación**; luego pasarlas por `oip-revisor-rn` | Claude | Sesión 2 con el experto |
| Anotar en la arquitectura (§2.2, §4.3, §6, §7, §9, §12, ADR-007) las decisiones DEC-123 a DEC-136 | Claude | — |
| **Canales de venta (análisis del 2026-11-11):** el modelo actual (RN-001 a RN-009) está orientado a Amazon FBM. Propuesta del análisis: evaluar cada oportunidad **por canal** (marketplace: Amazon, Facebook Marketplace u otros; **venta directa**: contactos, grupos locales, clientes; **compra por oportunidad**: comprar y conservar hasta encontrar comprador, con riesgo de inventario) y elegir el de mayor rentabilidad con posibilidad razonable de venta. Ejemplo: compra $79; Amazon a $119 con comisión $17.85 (15%), envío $12 y empaque $2 → margen **$8.15**; venta directa a $109 con entrega $5 y otros $1 → margen **$24.00**. Afecta RN-001, RN-002, RN-004, RN-005, RN-006 y RN-008 (tiempo de entrega). **Decidido** en DEC-140 y DEC-141; queda la propuesta DEC-142 | Claude | RN-001 a RN-009 v2 |
| **Consolidación de los ejercicios:** todas las preguntas y propuestas abiertas de CASO-001 a CASO-006 y ANL-001 están en `docs/negocio/analisis/pendientes-de-consolidacion.md` | Jesús | RN v2 |
