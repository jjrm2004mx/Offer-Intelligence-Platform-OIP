# Insumo de arquitectura — Referencia del stack de tickets

**Tipo:** insumo externo (como la arquitectura de Gemini, `flujo-general.md` §12.1). **No reemplaza** la arquitectura v1.3: se compara punto por punto y solo lo que apruebe el dueño del producto pasa a DEC/ADR.
**Versión:** 1.0 — 2026-11-16 · **Estado:** BORRADOR para revisión
**Origen:** un ecosistema propio en operación (gestión de tickets por correo), con 9 repositorios, Podman rootless en Rocky Linux, IA opcional y unos 20 contenedores. Todo lo de este documento se tomó de sus specs, compose, runbooks y lecciones de operación.
**Convención de certeza** (la de OIP): **Verificado** = funciona así en el stack de referencia · **Propuesta** = recomendación para OIP · **PoC** = hay que probarlo en OIP antes de adoptarlo.

---

## Cómo usar este documento (para Claude)

1. **Cuándo leerlo:** en la **Etapa 3 (arranque técnico)** y cuando un REQ toque un ADR. **No** se carga con `@` en `CLAUDE.md`: lo adoptado pasa a DEC/ADR y de ahí al `CLAUDE.md`.
2. **Precedencia:** en reglas de negocio mandan las RN; en decisiones técnicas manda la arquitectura vigente de OIP. Si este documento choca con un ADR o una DEC **VIGENTE**, gana OIP, y el choque se anota en la Parte 2 como "No aplica" o "Adaptar".
3. **Estructura:** la **Parte 1** es genérica y sirve para cualquier proyecto. Cada punto trae *Regla*, *Porqué* y *Ejemplo*. La **Parte 2** es el encaje con OIP v1.3: tabla de veredictos, propuesta de dos repos y DEC propuestas.
4. **IDs propios** de este documento: `P-` principio, `I-` infraestructura, `C-` componente, `O-` OpenSpec, `T-` trampa. Son locales al insumo y no se mezclan con los DEC/ADR de OIP.

---

# Parte 1 — Arquitectura de referencia (genérica)

## 1. El stack de referencia en una tabla

| Componente | Responsabilidad única | Guarda lo suyo en |
|---|---|---|
| Ingesta | Leer cada buzón (un flujo por canal), sin modificarlo, y entregar cada mensaje nuevo a la bandeja del clasificador | Volumen propio: flujos, credenciales, cursores |
| Clasificación | Bandeja persistente, decidir qué es cada mensaje (reglas primero, IA opcional) y entregar a gestión con reintentos | BD propia, Redis propio (cola), almacén de objetos propio |
| Gestión (núcleo) | Sistema de registro: tickets, flujos, permisos, auditoría y **outbox de eventos** | BD propia, Redis (stream de eventos), almacén de objetos |
| Notificaciones | Consumir eventos y enviar avisos, con bitácora y proveedor por canal | BD propia (bitácora de envíos) |
| Agente RAG | Responder con la documentación, filtrada por rol y audiencia | Base vectorial propia |
| Text-to-SQL | Pregunta → SQL **validado**. Nunca toca una base | Nada (sin estado) |
| Consola de soporte | UI estática de plataforma, separada del negocio | Nada |
| Monitoreo | Métricas, logs, tableros y el **orquestador** del arranque | Volúmenes propios |

Flujo principal: `entrada → bandeja persistente → decisión → sistema de registro → evento → aviso`, con el monitoreo observando todo.

---

## 2. Principios

### P-01 · Un repositorio por responsabilidad

- **Regla:** cada componente con un ciclo de vida propio (despliegue, dependencias, ritmo de cambio) vive en su repo, con su `docker-compose.yml`, su `start.sh`, su `openspec/` y su `CLAUDE.md`. Si dos piezas siempre se cambian y despliegan juntas, van en un mismo repo.
- **Porqué:** un cambio en el clasificador no obliga a reconstruir el núcleo. Cada repo es reutilizable en otro proyecto: el servicio de notificaciones o el motor text-to-sql se pueden llevar tal cual. El contexto que lee Claude por repo también es más chico y preciso.
- **Costo (Verificado):** un cambio que cruza repos exige varios PRs, un orden de despliegue y un orden de archivado de OpenSpec. Con 9 repos, la coordinación pesa. **No dividir por capas** (frontend/backend), sino por responsabilidad.
- **Ejemplo:** el motor text-to-sql se separó del núcleo porque su pieza crítica (el validador de SQL) necesita su propia suite de casos negativos y su propio ritmo de cambio, y porque se diseñó para que otra aplicación lo adopte con un kit de adopción de 7 pasos.

### P-02 · Cada componente persiste y recupera lo suyo

- **Regla:** lo que un componente recibe queda **persistido en ese componente** antes de responder, y se puede **recuperar si se cae**. No hay base compartida: cada servicio tiene su BD, su usuario y sus migraciones. La deduplicación y los reintentos son del componente que **recibe** el dato, no del núcleo.
- **Porqué:** si el receptor no persiste, una caída pierde datos o el emisor tiene que reintentar sin saber qué pasó. Centralizar la cola en el núcleo lo vuelve un monolito por la puerta de atrás.
- **Ejemplo (Verificado):** se rechazó un diseño que movía la recepción y los reintentos de correos al núcleo. La bandeja quedó en el clasificador, y el núcleo solo ofrece **creación idempotente**.

### P-03 · Contratos explícitos, versionados y autenticados entre componentes

- **Regla:** los componentes se hablan por pocos contratos escritos en la spec, y cada uno tiene versión:
  1. **API interna** con llave por servicio (`X-Service-Key`), en una red que no se publica.
  2. **Stream de eventos** (Redis Streams) que alimenta una **outbox** en la BD del emisor.
  3. **Webhook** con secreto (`X-Send-Secret`) para acciones de salida.
- **Idempotencia:** el receptor deduplica con una clave natural o con un `clientRequestId`.
- **Cambio incompatible:** sube la versión **MAYOR** y se lleva al consumidor en el mismo cambio.
- **Ejemplo (Verificado):** el catálogo del motor text-to-sql publica un `contract.json`. Si cambia algo que la base debe igualar, sube la versión mayor y obliga a regenerar el contrato y llevarlo a la aplicación en el mismo PR.

### P-04 · Falla cerrado

- **Regla:** ante configuración ausente, dato desconocido o verificación fallida, el sistema **no actúa** y avisa. Nunca hay un "camino por defecto" que haga algo potencialmente dañino.
- **Ejemplos (Verificado):**
  - Un aviso cuyo canal no tiene proveedor activo **no se envía**: queda en la bitácora como fallido, sin reintento.
  - El validador de SQL rechaza cualquier nodo, función o literal desconocido.
  - Un objeto del catálogo sin filtro obligatorio hace que el catálogo **no cargue**.

### P-05 · El código decide; la IA complementa (IA opcional)

- **Regla:**
  1. Toda función tiene un **camino determinístico que se sostiene solo**. El LLM solo resuelve lo ambiguo o corrige donde se midió que acierta más.
  2. La IA se enciende o apaga **por función** con interruptores en la configuración, con tres modos: `apagada | solo registra | aplica`.
  3. Toda propuesta de diseño describe **qué pasa con la IA encendida y qué pasa con la IA apagada**.
- **Porqué:** hay clientes o momentos sin IA (costo, privacidad, caída del proveedor). Si el sistema depende del LLM para funcionar, un cambio del proveedor lo tumba. Un caso Verificado: un modelo empezó a gastar sus tokens razonando y devolvió vacío, y los tiempos pasaron de 3–8 s a más de 20 s sin que cambiara nada del lado propio.
- **Cómo se adopta una regla con IA:**
  - Se mide contra un **banco etiquetado**: muestra estratificada más un control aparte, sin ajustar nada sobre el control.
  - Hay umbrales explícitos. En el stack de referencia: **≥ 95 % para que el código corrija al LLM** y **≥ 80 % para usarse sin IA**.
  - Cada decisión guarda su **fuente** (`regla | lector | ia`) para poder explicarla después.
- **Ejemplo (Verificado):** un "lector de correo" determinístico decide sin IA los correos del equipo a terceros. Con IA encendida corrige al modelo solo donde el banco mostró 99 % contra 68 %, y respalda cuando el modelo falla.

### P-06 · Lo automático aplica por defecto; el humano lo apaga

- **Regla:** lo que el sistema decide con reglas aprobadas **se aplica solo**. Una persona puede apagar, a demanda, la gestión automática o la IA. "Dejarlo como sugerencia por prudencia" no es el valor por defecto.
- **Matiz:** las decisiones de **riesgo** (las que el dueño marca como gate) sí exigen la acción explícita de una persona, y esa acción queda registrada.

### P-07 · Puertos y adaptadores para todo lo externo

- **Regla:** el dominio no conoce frameworks, la BD ni proveedores. Cada dependencia externa (correo, LLM, almacenamiento) entra por una interfaz (puerto) con uno o más adaptadores elegidos por configuración. Capas: `infrastructure → application → domain`, nunca al revés.
- **Ejemplo (Verificado):** el envío de correo es un `EmailPort` y el proveedor se elige con una variable. El gateway de LLM recibe `provider` por petición o por variable, con un cliente en caché por proveedor.

### P-08 · Mínimo privilegio en los datos

- **Regla:** quien solo lee usa un **rol de solo lectura** sobre **vistas** dedicadas, con **seguridad por fila** (RLS) cuando hay separación entre dueños de datos. Un servicio de IA nunca recibe una cadena de conexión.
- **Ejemplos (Verificado):**
  - El motor text-to-sql genera y valida el SQL, y la aplicación dueña lo ejecuta con su rol de solo lectura sobre las vistas `insights`.
  - El agente RAG filtra por **audiencia** y después por **rol** antes de recuperar fragmentos.

### P-09 · Logs y métricas sin contenido

- **Regla:** logs y métricas llevan **identificadores, conteos y tiempos**, nunca contenido: ni preguntas, ni SQL, ni cuerpos de mensajes, ni llaves o tokens. Las métricas se agrupan por aplicación o fuente, no por usuario.

### P-10 · La plataforma separada del negocio

- **Regla:** las herramientas de operación (diagnóstico, consola de soporte, alta de clientes) van **fuera** de la UI de negocio, solo en loopback o por túnel. "Soporte" significa infraestructura, nunca decisiones de negocio.
- **Ejemplo (Verificado):** la consola de soporte es HTML estático servido por Nginx. Nginx agrega la llave del agente al reenviar, y la llave nunca llega al navegador.

---

## 3. Infraestructura

### I-01 · Podman rootless, un compose por repo y un orquestador

- **Regla:**
  - Cada repo trae un `docker-compose.yml` y un `start.sh` idempotente: crea el `.env` desde `.env.example` si falta, crea las redes externas **solo si faltan** y levanta.
  - Un **orquestador** (`startup.sh` con los comandos `up | down | restart | status | build | deploy`) arranca los repos **en un orden fijo**, espera la salud de cada uno y se detiene ante un fallo fatal.
- **Ejemplo (Verificado):** el orden de arranque es núcleo → clasificación → notificaciones → ingesta → motor opcional → monitoreo. Un repo opcional que no está clonado se salta con un aviso.

### I-02 · Redes: una interna por stack y una compartida mínima

- **Regla:**
  - Cada stack tiene su **red interna**, que crea su compose.
  - Hay una **red compartida** (bus) donde solo están los servicios que de verdad se hablan entre stacks.
  - **Las bases de datos y los servicios auxiliares nunca están en la red compartida.**
  - Las redes se crean **sin `--subnet` fija** y **nunca** se borran contenedores ni redes desde un script de arranque.
- **Porqué (Verificado):** con Podman rootless (netavark), las subredes automáticas salen de `10.89.0.0/16`, así que una subred fija choca con ellas. Un `ensure_networks` que "arreglaba" el choque borrando contenedores llegó a ser un riesgo real.

### I-03 · Todo en loopback salvo una puerta

- **Regla:** todos los `ports:` se publican como `127.0.0.1:<puerto>`. **Un solo** puerto queda abierto a la LAN (el portal) y todo lo demás se usa por **túnel SSH**.
- **Por qué no basta el firewall (Verificado):** abrir un puerto en el firewall no expone un servicio publicado en `127.0.0.1`. Hacen falta las dos capas.

```yaml
services:
  api:
    ports: ["127.0.0.1:8080:8080"]   # solo loopback
  portal:
    ports: ["8090:80"]               # la única puerta a la LAN
```

### I-04 · Configuración y secretos

- **Regla:**
  - `.env.example` está versionado con **todas** las variables y su explicación. `.env` está en `.gitignore`.
  - Hay una llave **por servicio y por dirección**. Ninguna llave va en el frontend.
  - Un interruptor `REGISTRY_BASE` alterna entre las imágenes locales (`localhost`) y un registro remoto.
- **Para Rocky:** usar `podman secret` para las llaves en producción; en el stack de referencia siguen en `.env` (Known Gap).

### I-05 · Migraciones versionadas y nunca manuales

- **Regla:**
  - Todo cambio de esquema va en una migración nueva (`V{N}__descripcion.sql`). Nunca un `ALTER TABLE` a mano y nunca editar una migración ya aplicada.
  - `clean-disabled=true` y `out-of-order=false`.
  - Nomenclatura en inglés, `snake_case` plural, `id` como PK y `{tabla}_id` como FK, `created_at` y `updated_at`, booleanos `is_*`.
- **Ejemplo (Verificado):** Flyway corre como **contenedor de una sola ejecución** (`*-flyway`) antes del servicio, también en los repos Python, sin JVM.

### I-06 · Volúmenes, respaldos y vuelta atrás

- **Regla:**
  - Los volúmenes llevan nombre, y una **lista de volúmenes que nunca se borran** queda escrita en el runbook.
  - Antes de cada migración se hace un **respaldo** (`pg_dump -Fc` con fecha y migración en el nombre).
  - Antes de cada despliegue, la imagen vigente se etiqueta `:rollback-<fecha>`.
  - Los volúmenes regenerables (caché) se documentan como seguros de borrar, con el comando exacto (`podman unshare rm -rf …`).

### I-07 · Despliegue reproducible

- **Pasos (Verificado):**
  1. `git pull`.
  2. Etiquetar la imagen de rollback.
  3. `build`.
  4. Correr la migración.
  5. `up -d --force-recreate --no-deps <servicio>`.
  6. Revisar la salud.
  7. `podman image prune -f`.
- Cada paso está en un script (`deploy_<repo>.sh`), no en la memoria de quien despliega.

### I-08 · Healthchecks y observabilidad

- **Healthchecks:** cada servicio expone `/health` y `/metrics` (Prometheus). Las imágenes Python suelen **no traer `curl`**, así que el healthcheck usa `python3 -c "import urllib.request; …"`.
- **Monitoreo (Verificado):** Prometheus, Grafana, Loki y Promtail (lee **journald** del host, con etiquetas `container` y `service`) más Node Exporter.
- **Diagnóstico:** `diagnostico-stack.sh` revisa salud, puertos, redes y **disco**, y avisa al 80 % y al 90 %.
- **Regla:** agregar un servicio al monitoreo actualiza `prometheus.yml` **y** el `CLAUDE.md` de ese repo.

### I-09 · SELinux en Rocky

- **Regla:** todo bind mount lleva `:Z` (o `:z` si se comparte). Promtail necesita el journal persistente, el grupo `systemd-journal` y `label=disable`. La configuración del compose se valida en el servidor con `podman-compose config`.

---

## 4. Componentes como patrones reutilizables

### C-01 · Adaptador de entrada "tonto", un flujo por fuente

- **Patrón:** cada fuente (buzón, comercio, feed) tiene su **flujo propio**, una copia de una plantilla de solo lectura. El adaptador lee, normaliza al contrato y **entrega**, sin tomar decisiones de negocio. Guarda su **cursor** (hasta dónde leyó) y su credencial.
- **Contrato (Verificado):** `POST /inbox/<canal>` con la llave del canal y un payload versionado. El receptor responde rápido y procesa después.
- **Lección:** el adaptador **no marca como leído** ni modifica la fuente; el cursor se mueve solo después de una entrega confirmada.

### C-02 · Bandeja persistente con estados y cola durable

- **Estados:** `RECEIVED → CLASSIFYING → READY → DELIVERED`, más `HELD` (necesita una persona).
- **La BD es la fuente de verdad:** cada transición es un `UPDATE … WHERE estado = <anterior>` condicional, así que dos workers nunca toman el mismo paso.
- **La cola solo avisa:** la cola (Redis Stream con grupo de consumidores, AOF) **solo lleva el id**.
- **Barrido de recuperación:** corre cada minuto y re-encola lo atascado más de 10 min o lo que ya debe reintentarse (`next_attempt_at`). Así **nada depende de que Redis o un proceso sigan vivos**.
- **Entrega con reserva:** la entrega reserva el mensaje 10 min (`next_delivery_at`); si el proceso cae, se reintenta al vencer.
- **Retención:** los cuerpos se purgan a los N días de entregados; los metadatos se conservan.
- **Detalle que costó caro (Verificado):** el timeout de lectura del socket de Redis debe ser **mayor** que el `BLOCK` de la lectura bloqueante. redis-py 8 trae 5 s por defecto, igual al `BLOCK 5000`, y eso producía errores falsos.

### C-03 · Eventos con outbox

- **Patrón:**
  - El emisor escribe el evento en una tabla `event_outbox` **en la misma transacción** que el cambio.
  - Un publicador lo pasa al stream.
  - Un fallo del stream **no bloquea** la operación (try/catch).
  - Hay un **catálogo cerrado** de tipos de evento en la spec.
  - Los campos del stream son siempre `String` y se convierten explícitamente al leer.
- **Consumidor pasivo:** nadie depende de él. Si se cae, retoma desde su posición en el grupo.

### C-04 · Servicio de avisos

- **Patrón:**
  - Consume eventos, resuelve `evento → plantilla + asunto` y envía por un proveedor elegido **por canal**.
  - Registra **cada intento** en una bitácora (`notification_logs`) para auditar y reintentar.
  - **Un aviso por evento**, sin repetir. Si no hay proveedor activo, **no envía** (P-04).
- **Desacople de la salida:** el envío físico puede delegarse a un webhook del adaptador de salida, así el servicio de avisos no conoce las credenciales del proveedor.

### C-05 · Gateway de LLM

- **Patrón:**
  - Un solo servicio habla con los modelos: `POST /ask {prompt, system?, provider?}`.
  - El proveedor se elige por variable o por petición, con un cliente en caché por proveedor y una caché de respuestas en Redis.
  - Lleva `request_id` y métricas.
- **Known Gaps aprendidos:**
  - Falta un **timeout** en la llamada al modelo.
  - La clave de caché **debe incluir el modelo**.
  - Un fallo de la caché no debe tumbar la petición.
  - El gateway **no** debe publicarse en el host.
- **Parámetros del proveedor:** se exponen como variables (`*_REASONING_EFFORT`, `*_MAX_TOKENS`).

### C-06 · Agente RAG por rol y audiencia

- **Patrón:**
  - Ingesta de documentos con etiquetas de **rol**, **audiencia** y, si aplica, **tenant**, y una sola consulta filtrada por esas etiquetas.
  - Búsqueda híbrida opcional (vectorial + BM25) y expansión del fragmento padre.
  - **Re-ingesta** con un script después de cambiar la documentación.
- **Restricción (Verificado):** el modelo de embeddings es **de por vida del índice**; cambiarlo obliga a re-ingestar todo.
- **Respuestas:** el agente responde **desde los documentos** y no inventa comandos. La calidad depende más de la recuperación que del modelo.

### C-07 · Preguntas sobre los datos (text-to-SQL)

- **Patrón:**
  - El motor recibe una pregunta y un **catálogo** (vistas, columnas, reglas, ejemplos) y devuelve una de tres cosas: SQL, una aclaración o "fuera de alcance".
  - El SQL final se **genera desde el árbol validado**, nunca desde el texto del modelo.
  - Un **filtro obligatorio** (por dueño de los datos) se inyecta siempre.
  - La aplicación ejecuta el SQL con un rol de solo lectura y devuelve las filas al motor para que redacte la respuesta.
- **Reglas:**
  - El motor no tiene base ni red hacia una base.
  - Todo cambio del validador lleva su **caso negativo** en las pruebas.
  - La suite corre **sin modelo**; las corridas con el modelo real son aparte y con permiso.

### C-08 · Consola de soporte estática

- **Patrón:** un solo `index.html` sin frameworks ni CDN, servido por Nginx, que reenvía solo `health` y `query` al agente agregando la llave. Escucha solo en loopback (P-10).

### C-09 · Orquestador y diagnóstico

- **Patrón:** el repo de monitoreo es también dueño del **ciclo de vida del ecosistema**: `startup.sh`, `diagnostico-stack.sh`, `sync-repos.sh` y la tabla maestra de **puertos, redes y bases**, con la pertenencia de cada contenedor a cada red. Esa tabla es la referencia que se revisa antes de agregar un servicio.

---

## 5. OpenSpec: lecciones de uso

### O-01 · Las specs describen lo que hace el código

- La spec principal (`openspec/specs/<capacidad>/spec.md`) es la **fuente de verdad verificada contra el código**: cita los archivos fuente y lleva una sección **Known Gaps / Risks** con lo que el código **no** garantiza.
- El `CLAUDE.md` **no** repite comportamiento: apunta a las specs.

### O-02 · Ningún ajuste queda solo en el código

Antes del PR:

1. Un detalle dentro de un requisito que el cambio modifica se agrega al delta (regla + escenario).
2. Una corrección fuera de los requisitos del delta entra como `MODIFIED` del requisito **completo**, copiado de la spec principal con todos sus escenarios.
3. Si un cambio posterior reescribe ese requisito, la regla se copia también en ese delta, o el archivado la revierte.
4. Lo detectado y no corregido va a **Known Gaps**.
5. Si el código difiere de la spec sin razón, se alinea el **código** a la spec.

### O-03 · Simular el archivado antes del PR

- Correr `openspec validate --specs --strict`.
- Sobre una **copia** en una carpeta temporal, archivar en orden todos los cambios abiertos (`openspec archive <c> --yes`), validar en modo estricto y hacer `grep` de que las reglas nuevas sobreviven.
- Con varios cambios abiertos sobre la misma capacidad, el **orden de archivado** se escribe en el §0 de cada `tasks.md`.

### O-04 · Inventario inicial

- Al adoptar OpenSpec sobre código existente, primero se hace un **inventario de cobertura** (qué capacidades existen y qué archivos las implementan) y una revisión de armonía entre repos.
- Después se hace un cambio por mejora.

### O-05 · Las tareas incluyen despliegue y verificación

- `tasks.md` incluye las tareas de **despliegue y prueba** (rollout), no solo de código. El cambio no se archiva hasta que se probó en el servidor.

---

## 6. Trampas conocidas

| ID | Trampa | Síntoma | Remedio |
|---|---|---|---|
| T-01 | Bind mount sin `:Z` bajo SELinux Enforcing | El contenedor no lee su configuración o sus datos ("permission denied") | `:Z` en todo bind mount. No traer overrides de otro entorno (WSL) por git |
| T-02 | `podman-compose up -d` no recrea con una imagen nueva | Se despliega y sigue corriendo la versión anterior | `up -d --force-recreate --no-deps <servicio>` |
| T-03 | Imágenes colgadas llenan `/home` | `podman ps` devuelve 125 ("unable to open database file"); Postgres en PANIC | `podman image prune -f` en cada despliegue; diagnóstico de disco al 80/90 %. **Nunca** borrar volúmenes para liberar espacio |
| T-04 | Subred fija en una red Podman | `subnet already used` y scripts que "arreglan" borrando contenedores | Redes sin `--subnet`; los scripts nunca borran |
| T-05 | Resolver DNS fijo en Nginx (`resolver 10.89.0.1`) | El portal deja de resolver si cambia la red | Tomar el resolver del `resolv.conf` (`NGINX_ENTRYPOINT_LOCAL_RESOLVERS`) |
| T-06 | Timeout del socket de Redis ≤ `BLOCK` | Errores de lectura con la cola vacía | Timeout del socket mayor que el `BLOCK`; fijar la versión mayor del cliente |
| T-07 | El proveedor de LLM cambia su comportamiento | Respuestas vacías o lentas sin cambio propio | Exponer los parámetros del modelo como variables; medir los tokens de salida primero; timeouts por cliente |
| T-08 | Timeouts encadenados mal alineados | El backend corta a 30 s y el agente tarda 27 s | Timeout de lectura propio por cliente lento; el proxy con un margen mayor |
| T-09 | Llamadas de pago en iteraciones | Se gastan miles de llamadas en evaluar | Iterar con las fallas y una muestra pequeña; la corrida completa solo al final; lo determinista se mide sin llamadas |
| T-10 | Healthcheck con `curl` en una imagen Python o MinIO | El contenedor queda "unhealthy" para siempre | `python3 -c urllib…` / `mc ready` |
| T-11 | Scripts editados en Windows | Fallan en Linux por CRLF | `.gitattributes` con `*.sh text eol=lf`; para copiar al servidor, `git -c core.autocrlf=false archive` |
| T-12 | Ramas del servidor distintas a las del equipo | Se despliega `main` creyendo que es `develop` | El servidor sigue **una** rama conocida; `status` del orquestador la muestra |
| T-13 | Migrar datos de prueba con cuidado de producción | Backfills complejos para datos que se pueden borrar | Mientras solo haya datos de prueba, **reiniciar** en vez de migrar. Revisar el supuesto cuando entren datos reales |
| T-14 | Cuerpos purgados por la retención | El banco de evaluación pierde sus datos | Correr las mediciones antes de la purga; no copiar datos sensibles fuera del servidor |
| T-15 | `python` en Windows | Abre el alias de la Microsoft Store | Usar `py` |

---

# Parte 2 — Encaje con OIP v1.3

## 7. Tabla de encaje

Veredictos: **Adoptar** (entra tal cual) · **Adaptar** (entra con cambios) · **Ya cubierto** (OIP ya lo decidió) · **No aplica**.

| ID | Punto | OIP hoy | Veredicto | Acción propuesta |
|---|---|---|---|---|
| P-01 | Un repo por responsabilidad | Un solo repo; frontera natural Core / Worker (ADR-022) | **Adaptar** | Dos repos, Core y Worker (§8). No dividir más en el Inc. 1 |
| P-02 | Cada componente persiste lo suyo | El Worker no persiste: entrega a `/ingest` | **Adaptar** | El Worker guarda una **bandeja de salida** mínima (resultado + estado de entrega) para reintentar si el Core o el túnel no están; el Core deduplica (§8.3) |
| P-03 | Contratos versionados y autenticados | `schemaVersion 1.1`, token por servicio, WireGuard (§3.4.1, §8) | **Ya cubierto** + Adaptar | Escribir los dos contratos (`schedule` e `ingest`) como spec en **ambos** repos, con regla de versión mayor |
| P-04 | Falla cerrado | IP doméstica fail-closed, `modo_red` estricto, pausa por bloqueo (§3.4–§3.6) | **Ya cubierto** | Extender a los avisos: sin destino de Telegram configurado no se envía y se registra |
| P-05 | El código decide; IA opcional | Motor determinístico con RN; sin IA | **Adoptar** (como principio para lo que viene) | DEC propuesta; ver §9 |
| P-06 | Lo automático aplica por defecto | Avisos automáticos por nivel; gate G5 para stealth | **Ya cubierto** | Sin cambio: G5 es el "matiz de riesgo" de P-06 |
| P-07 | Puertos y adaptadores | `BrowserRenderer`, `TrackingProvider`, fuentes intercambiables (DEC-123), SP-API preparado | **Ya cubierto** | Hacerlo regla general en el `CLAUDE.md`: todo externo entra por interfaz |
| P-08 | Mínimo privilegio en datos | Metabase lee la BD | **Adaptar** | Metabase con **rol de solo lectura sobre vistas** (`reporting.*`), no con el dueño de la BD |
| P-09 | Logs sin contenido | Logs sin tokens (§10) | **Adoptar** | Sin tokens de Keepa ni de Telegram, sin datos del cliente (`client_request` solo con alias) |
| P-10 | Plataforma separada | Herramienta personal; Metabase como tablero | **No aplica** por ahora | Revisar si llega una UI propia (Inc. 2) |
| I-01 | Compose por repo + orquestador | **Quadlets + systemd** en producción, `podman-compose` en desarrollo (DEC-025) | **Adaptar** | Producción: el orden y las dependencias los da **systemd** (`After=`, `Requires=`), no un `startup.sh`. Desarrollo: `start.sh` por repo. Ver T-02, que Quadlets evita |
| I-02 | Red interna + compartida mínima | `oip-internal` / `oip-public` (modo túnel, sin construir); Core y Worker en hosts distintos | **Adaptar** | Core: red interna con `oip-db` **sin** salida a internet; solo `oip-api` en la red con salida (allowlist DEC-122). Sin `--subnet` |
| I-03 | Todo en loopback salvo una puerta | "Detrás de reverse proxy con TLS o solo VPN" (§9.2) | **Adoptar** | Todo en `127.0.0.1`; la única puerta es Metabase (o ninguna y todo por túnel). En el VPS, Scrapyd solo en la interfaz WireGuard |
| I-04 | `.env.example` y secretos | `podman secret` (§9.2) | **Ya cubierto** + Adoptar | `.env.example` documentado para lo que no es secreto; secretos solo en `podman secret` |
| I-05 | Migraciones nunca manuales | No definido | **Adoptar** | Herramienta de migraciones versionadas (Alembic o Flyway en contenedor). Cuidado con las hypertables y la compresión de TimescaleDB dentro de las migraciones (**PoC**) |
| I-06 | Volúmenes, respaldos, rollback | `oip-backup` con `pg_dump` (§9.1) | **Adoptar** | Lista de volúmenes que nunca se borran; respaldo antes de cada migración; tag `:rollback-<fecha>` |
| I-07 | Despliegue reproducible | No definido | **Adoptar** | Script de despliegue por repo; con Quadlets: `podman auto-update` o `systemctl --user restart` tras el pull |
| I-08 | Healthchecks y observabilidad | Métricas en Postgres + Metabase; Prometheus "si se requiere" (§10.1) | **Adaptar** | Inc. 1: `/health` y `/metrics` en `oip-api` y en el Worker, y el **heartbeat** Core ↔ Worker. El stack Prometheus/Grafana/Loki solo si se justifica (DEC-125) |
| I-09 | SELinux `:Z` | Rocky en los dos hosts | **Adoptar** | Regla en el `CLAUDE.md` y en los Quadlets (`Volume=…:Z`) |
| C-01 | Adaptador "tonto" por fuente | Spiders por comercio; el motor decide en el Core (§5.1) | **Ya cubierto** | Confirma la separación: el spider no decide identidad ni oportunidad |
| C-02 | Bandeja persistente con estados | Ingesta idempotente; cola de tareas en Postgres (DEC-022) | **Adoptar** | En el Core: estados de cada lote ingerido y de cada tarea (Keepa, motor, aviso) con transiciones condicionales y **barrido de recuperación**. Procrastinate da parte; el barrido y `HELD` se diseñan |
| C-03 | Outbox de eventos | El notificador está dentro de `oip-api` | **Adaptar** | Una tabla `outbox` para los avisos (oportunidad alertada → aviso), sin Redis: la cola en Postgres basta (DEC-022) |
| C-04 | Servicio de avisos con bitácora | Telegram con deduplicación (§5.1, R-12) | **Adaptar** | **Módulo** dentro de `oip-api`, no un repo: bitácora de envíos, un aviso por evento, falla cerrado |
| C-05 | Gateway de LLM | — | **No aplica** hoy | Si llega la IA, entra como **adaptador** dentro del Core, con timeout y caché por modelo (§9) |
| C-06 | Agente RAG | — | **No aplica** | — |
| C-07 | Text-to-SQL | Metabase | **No aplica** hoy | Futuro: se podría **adoptar el motor del stack de referencia** con su kit de adopción, porque está hecho para eso |
| C-08 | Consola de soporte | — | **No aplica** | — |
| C-09 | Tabla maestra de puertos, redes y bases | No existe | **Adoptar** | Un runbook con los dos hosts: contenedores, puertos, redes y quién habla con quién |
| O-01 | Specs verificadas + Known Gaps | OpenSpec en la Etapa 3 (DEC-072) | **Adoptar** | Toda spec principal con "Known Gaps / Risks" y los archivos fuente |
| O-02 | Ningún ajuste solo en el código | — | **Adoptar** | Al `oip-developer` y al `oip-tester` (DEC-172) |
| O-03 | Simular el archivado | — | **Adoptar** | Paso del cierre (Etapa 5) antes de `/opsx:archive` |
| O-04 | Inventario inicial | Repo nuevo, sin código | **No aplica** | — |
| O-05 | Tareas con despliegue y prueba | "Modo completo / ligero" (DEC-084) | **Adoptar** | Las tareas de despliegue y verificación en `tasks.md`; no se archiva sin la prueba en Rocky |
| — | Ramas `feature/` y Conventional Commits | `feat/<N>-<id>` y trailers `Refs:` / `Change:` (DEC-071) | **No aplica** | Manda la convención de OIP |
| — | Multitenant | Herramienta personal | **No aplica** | — |
| T-01…T-15 | Trampas | — | **Adoptar** | Como sección "Trampas conocidas" del runbook de operación de OIP. **Especialmente** T-03: Chromium y TimescaleDB son pesados y el VPS tiene 40–50 GB |

### 7.1 Matices propios de OIP

- **T-13 (reiniciar en vez de migrar) tiene fecha de caducidad corta en OIP.** El **historial propio de precios** es un activo (DEC-123, DEC-130). En cuanto empiece la recolección real, `price_observation` y `market_reference` **no** son datos de prueba: toda migración que las toque lleva respaldo y plan.
- **T-09 (llamadas de pago) aplica a Keepa:** tokens que expiran y una suscripción por meses (DEC-124). Integrar con respuestas simuladas y medir con una muestra.
- **Quadlets cambia el arranque.** Lo que en el stack de referencia hace `startup.sh` (orden, espera de salud), en OIP lo hacen las unidades de systemd. El orquestador de I-01 queda **solo para desarrollo**.

---

## 8. Propuesta: dos repositorios, Core y Worker

**Estado:** Propuesta. **Toca ADR-022**, así que según DEC-172 la revisa `oip-arquitecto` cuando se cree.

### 8.1 Qué va en cada uno

| `oip-core` (el repo actual, renombrado o tal cual) | `oip-worker` (nuevo) |
|---|---|
| `oip-api`: scheduler, ingesta, catálogo, match, referencia de mercado, motor de oportunidad, búsqueda por artículo, notificador | `oip-scrapyd`: spiders, scrapy-playwright, Chromium, `BrowserRenderer` |
| `oip-db` (PostgreSQL + TimescaleDB), `oip-dashboard`, `oip-backup` | Verificador de IP (fail-closed), firewall de salida, bandeja de salida mínima |
| `docs/negocio/` (RN, casos, Vercel), `docs/proceso/`, `docs/arquitectura/`, el registro de decisiones | `docs/` técnico propio (runbooks del VPS) |
| Issues de REQ e inspección, agentes `.claude/agents/` | `CLAUDE.md` propio, `openspec/` propio |
| Quadlets del servidor del dueño | Quadlets del VPS |

### 8.2 Por qué conviene

1. **Se despliegan en hosts distintos**, con ritmos y riesgos distintos: el Worker cambia cada vez que un comercio cambia su HTML (R-07).
2. **La regla de la IP de casa queda en el código, no solo en la configuración:** el repo del Core **no contiene spiders**, y una prueba (gate) lo verifica. Esto fortalece DEC-041 y DEC-121.
3. **Dependencias separadas:** Chromium y Playwright no entran a la imagen del Core.
4. **El `CLAUDE.md` y las specs del Worker se enfocan** en consulta responsable (RN-010) y acceso por fuente (ADR-016).

### 8.3 Qué cuesta y cómo se mitiga

| Costo | Mitigación |
|---|---|
| La trazabilidad usa `Refs: #N` sobre issues de **un** repo | Los REQ siguen en el Core. En el Worker, los commits usan `Refs: jjrm2004mx/<core>#N` (referencia entre repos de GitHub) y el hook lo acepta |
| Un cambio que toca los dos contratos exige dos PRs | Los contratos `schedule` e `ingest` se escriben como spec **en los dos** repos, con versión; el Core acepta la versión N y la N-1 durante la transición |
| Dos `openspec/` que se pueden desalinear | El cambio que toca el contrato se crea en los dos repos con el **mismo id** (`Change: <id>`), y el orden de archivado se escribe en su §0 |
| Pérdida de resultados si el túnel cae | Bandeja de salida en el Worker (estados `PENDIENTE → ENTREGADO`), barrido que reintenta con espera creciente y retención corta. El Core deduplica con la clave de idempotencia de §8 de la arquitectura |
| Agentes duplicados | Los agentes viven en el Core; el Worker solo trae su `CLAUDE.md` |

### 8.4 Cuándo hacerlo

**En la Etapa 3**, antes de la primera línea del Worker. La PoC-A puede vivir como script desechable sin que importe el repo. Separar después cuesta más: historial mezclado y referencias que hay que mover.

---

## 9. IA en OIP, más adelante

OIP no usa IA hoy. Estos son los puntos donde podría entrar, cada uno con su camino sin IA:

| Dónde | Sin IA (decide el código) | Con IA (complementa) | Riesgo |
|---|---|---|---|
| Identificación sin GTIN (`LOW_MATCH_CONFIDENCE`, RN-013) | Marca + modelo; si no, "no confirmada" y revisión manual | El LLM propone una equivalencia; **nunca** confirma solo y va a revisión | Una coincidencia falsa da un margen falso (R-03) |
| Extracción de precio sin JSON-LD | Selectores por comercio + price-parser | El LLM extrae del HTML **como respaldo**; el valor se valida contra rangos y contra la ficha | Precio inventado |
| Búsqueda por necesidad (DEC-152, futura) | El dueño traduce la necesidad a 1–3 modelos | El LLM sugiere modelos; el dueño confirma | Sugerencias fuera de lo que pidió el cliente |
| Resumen de avisos | Plantilla fija | Redacción del resumen de las 8:00 y las 18:00 | Bajo |
| Preguntas sobre los datos | Metabase | Motor text-to-sql del stack de referencia (C-07), con su kit | Bajo si se respeta P-08 |

Reglas para cuando llegue la IA:

1. Interruptor por función: `apagada | solo registra | aplica`.
2. Banco etiquetado con los casos reales (CASO-xxx) y umbrales escritos **antes** de encenderla.
3. Fuente guardada en cada decisión (`regla | ia`).
4. La suite corre sin llamadas al modelo.
5. Un adaptador de modelo con timeout y caché por modelo (C-05), dentro del Core.

---

## 10. DEC propuestas

Numeración provisional, después de DEC-172. Todas en estado **PROPUESTA**, pendientes del visto bueno del dueño.

| ID | Decisión propuesta | Fuente en este insumo |
|---|---|---|
| DEC-173 | Separar OIP en dos repos, **Core** y **Worker**, en la Etapa 3; los REQ y los agentes viven en el Core | §8 |
| DEC-174 | Los contratos Core ↔ Worker (`schedule`, `ingest`) son spec en ambos repos, con versión mayor ante un cambio incompatible y aceptación N / N-1 en la transición | P-03, §8.3 |
| DEC-175 | El Worker guarda una bandeja de salida mínima con reintento y espera creciente; el Core deduplica | P-02, C-02 |
| DEC-176 | En el Core, estados de tareas con transiciones condicionales y **barrido de recuperación**; un estado `HELD` para lo que necesita al dueño | C-02 |
| DEC-177 | Principio "el código decide, la IA complementa": toda función con IA tiene un camino sin IA, un interruptor de tres modos, un banco con umbrales y la fuente registrada | P-05, §9 |
| DEC-178 | Todos los puertos en `127.0.0.1`; la única puerta (o ninguna) se decide en la Etapa 3; todo lo demás por túnel o WireGuard | I-03 |
| DEC-179 | Migraciones versionadas (nunca un `ALTER` manual ni editar una aplicada), respaldo antes de migrar y tag `:rollback-<fecha>` antes de desplegar | I-05, I-06 |
| DEC-180 | Metabase lee con un rol de solo lectura sobre vistas de reporte | P-08 |
| DEC-181 | Logs y métricas sin contenido: sin tokens, sin datos del cliente, sin HTML de comercios | P-09 |
| DEC-182 | Prácticas de OpenSpec: specs con Known Gaps, ningún ajuste solo en el código, simulación del archivado y tareas de despliegue y prueba | O-01, O-02, O-03, O-05 |
| DEC-183 | Runbook de operación con la tabla maestra de los dos hosts y la sección de trampas conocidas (T-01…T-15) | C-09, §6 |

---

## 11. Lista para la Etapa 3

- [ ] Decidir DEC-173 a DEC-183, y anotar en la arquitectura (v1.4) las aprobadas.
- [ ] Si se aprueba DEC-173: crear `oip-worker` y ajustar el hook de commits para las referencias entre repos.
- [ ] `CLAUDE.md` de cada repo (con las secciones que siguen) y `.gitattributes` con `*.sh text eol=lf`.
  - Precedencia: RN > arquitectura > este insumo.
  - Puertos y adaptadores (P-07).
  - Falla cerrado (P-04).
  - Logs sin contenido (P-09).
  - `:Z` en los volúmenes (I-09).
  - Migraciones (I-05).
  - Specs como fuente de verdad (O-01).
- [ ] `.env.example` documentado; secretos en `podman secret`.
- [ ] Quadlets: redes sin `--subnet`, `127.0.0.1` en todos los puertos, `Volume=…:Z`, healthchecks sin `curl`.
- [ ] `oip-backup` y la lista de volúmenes que nunca se borran.
- [ ] Script de despliegue por repo con rollback y `podman image prune -f`.
- [ ] `/health` y `/metrics` en `oip-api` y en el Worker; heartbeat Core ↔ Worker; aviso de disco al 80/90 %.
- [ ] Runbook con la tabla maestra (C-09) y las trampas conocidas (§6).
- [ ] `openspec init` con la arquitectura **y** las DEC aprobadas de este insumo como contexto.
