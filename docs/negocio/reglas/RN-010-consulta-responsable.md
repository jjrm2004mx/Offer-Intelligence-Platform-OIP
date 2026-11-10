# RN-010 — Consulta responsable a los comercios

```yaml
id: RN-010
titulo: Consulta responsable a los comercios
estado: BORRADOR
version: 1
fecha: 2026-11-09
responsable: Jesús
revisor_negocio: Experto en negocios internacionales
depende_de: []
origen: Sesión 1 con el experto (2026-11-09) — DEC-115, DEC-116, DEC-121
```

## 1. ¿Qué queremos lograr?
Que OIP consulte los comercios **sin generar tráfico excesivo, sin ocultarse y sin evadir restricciones**, y que nunca use la conexión de la casa de Jesús para consultar Home Depot, Walmart o Target. Automatizar búsquedas no significa infringir reglas.

## 2. ¿Qué incluye y qué no?
**Incluye:**
- Cuántas consultas se hacen y a qué velocidad, por comercio.
- Reutilización de información ya obtenida (caché).
- Qué hacer ante errores, lentitud o bloqueos.
- Desde dónde salen las consultas, tanto en la prueba de concepto como en operación.
- La postura sobre técnicas para "pasar desapercibido".

**No incluye:**
- Qué se busca y cómo se decide una oportunidad (RN-001 a RN-009 y RN-011).
- Detalles técnicos de servidores y redes (documento de arquitectura).

## 3. ¿Cómo funciona, en palabras?
OIP se comporta como un visitante tranquilo: hace pocas consultas, con pausas entre una y otra, de una en una por comercio. Si una información ya la tiene y es reciente, no la vuelve a pedir. Si algo falla, espera cada vez más antes de reintentar, y si un comercio empieza a bloquear, se detiene con ese comercio y avisa. Las consultas a los comercios siempre salen desde un servidor contratado en la nube, nunca desde la casa.

## 4. La regla

**4.1 Límites por comercio**

| Control | Qué significa | Valor inicial | ¿Confirmado? |
|---|---|---|---|
| Límite de consultas | Máximo de consultas por minuto a un mismo comercio | 6 por minuto | Por confirmar |
| Pausa entre consultas | Espera aleatoria entre una consulta y la siguiente al mismo comercio | Entre 10 y 15 segundos | Por confirmar |
| Consultas simultáneas | Cuántas consultas al mismo tiempo a un mismo comercio | 1 (comercios distintos sí en paralelo) | Por confirmar |
| Tiempo de espera de respuesta | Página normal / página que requiere navegador | 30 s / 60 s | Por confirmar |

**4.2 Reutilizar información (caché)**

| Información | Se reutiliza durante | ¿Confirmado? |
|---|---|---|
| Precio y disponibilidad de una publicación, búsqueda automatizada | 6 horas | Por confirmar |
| Precio y disponibilidad, **búsqueda por artículo para un cliente** (RN-011) | 1 hora: el cliente necesita datos frescos | Por confirmar |
| Datos de Amazon (Keepa) | 6 horas | Por confirmar |

**4.3 Errores y reintentos**
- Ante un error temporal (el comercio no responde o tarda de más) se reintenta **hasta 3 veces**, esperando **1, 5 y 15 minutos** (espera creciente). Si sigue fallando, se registra y se pasa a lo siguiente.
- **Pausa automática por bloqueo:** si en la última hora **más del 20%** de las consultas a un comercio fueron bloqueadas (por ejemplo, una página de verificación de "no soy un robot"), OIP **deja de consultar ese comercio durante 24 horas** y avisa a Jesús.

**4.4 Postura**
- OIP **no pretende ocultarse ni evadir restricciones**.
- Las técnicas de navegación "invisible" (stealth) existen como opción, pero están **deshabilitadas por defecto**. Solo Jesús puede activarlas, comercio por comercio, y queda registrado cuándo y por qué (decisión G5).
- No se resuelven pruebas de "no soy un robot" con servicios de terceros.

**4.5 Desde dónde salen las consultas**
- **Operación y prueba de concepto:** toda consulta a un comercio sale desde el **servidor en la nube (VPS)**. Los comercios ven la dirección del servidor, no la de la casa.
- **Modo desarrollo** (opcional, para probar en casa): desde la casa **solo** se consultan datos guardados, simulaciones o servicios que permiten la automatización (APIs). Home Depot, Walmart y Target **quedan bloqueados desde la casa** y ninguna opción los desbloquea.
- El servidor en la nube **verifica su dirección antes de cada trabajo**. Si no es la autorizada, no consulta nada.

## 5. ¿Cómo sabremos que funciona? — Ejemplos con números

**Ejemplo A — Recorrido de 300 productos en Home Depot**
- Con el límite de 6 por minuto, 300 consultas tardan **al menos 50 minutos** (300 ÷ 6).
- Con pausas de 10 a 15 segundos (12.5 s en promedio), tardan unos **62.5 minutos** (300 × 12.5 ÷ 60).
- Con la pausa mínima de 10 s, nunca se pasa de 6 por minuto (60 ÷ 10): pausa y límite coinciden.

**Ejemplo B — Se activa la pausa por bloqueo**
- En la última hora hubo 30 consultas a Walmart y **8** fueron bloqueadas: 8 ÷ 30 = **26.7%**, que es más de 20%.
- OIP deja de consultar Walmart por 24 horas y avisa a Jesús.

**Ejemplo C — No se activa**
- 30 consultas y **5** bloqueadas: 5 ÷ 30 = **16.7%**, que es menos de 20%. OIP sigue, con sus límites normales.

**Ejemplo D — Caché**
- El precio de un taladro se consultó a las 10:00 para la búsqueda automatizada. A las 13:00 se necesita otra vez: tiene 3 horas (menos de 6) y **se reutiliza**, sin consultar al comercio.
- A las 13:00 un cliente pide ese mismo taladro (RN-011): el dato tiene 3 horas (más de 1) y **se consulta de nuevo**.

**Ejemplo E — Desde la casa**
- En modo desarrollo, una prueba intenta consultar homedepot.com desde la casa: **la consulta se bloquea** y queda registrada. La misma prueba contra datos guardados sí funciona.

## 6. ¿Qué información necesitamos?
- Lista de comercios con sus límites (si alguno necesita valores distintos).
- Registro de cada consulta: hora, comercio, resultado (correcta / error / bloqueada).
- Dirección autorizada del servidor en la nube.

## 7. ¿Qué obtenemos?
- Consultas espaciadas y controladas por comercio.
- Avisos de pausa por bloqueo.
- Registro de bloqueos por comercio, que sirve para decidir el método de acceso a cada comercio.

## 8. ¿Quién participa?
- OIP aplica los límites.
- Jesús ajusta valores, activa técnicas opcionales (G5) y recibe avisos.
- El experto valida que la postura sea la adecuada para el negocio.

## 9. ¿De qué depende?
- Del servidor en la nube contratado (sin él no se puede consultar ningún comercio).
- Del documento de arquitectura v1.3 (cómo se implementa).

## 10. Limitaciones
- Con estos límites el volumen diario es moderado. Por ejemplo, un solo comercio no pasa de unas 8,640 consultas al día (6 × 60 × 24), y en la práctica serán muchas menos. Si se necesita más volumen, se revisa esta regla y sus costos (por ejemplo, proxies residenciales, que no se descartan: DEC-117).
- La dirección de un servidor en la nube puede ser bloqueada más fácilmente que una doméstica. Se mide con la pausa automática.

## 11. ¿Qué pasa si…?
| Situación | Qué hace OIP |
|---|---|
| El servidor en la nube no está disponible | No consulta comercios; avisa. **Nunca** consulta desde la casa como respaldo |
| La verificación de dirección falla | No consulta; avisa |
| Un comercio está en pausa y llega una búsqueda por artículo | Ese comercio se marca "no consultado (en pausa)" en el resultado; se consultan los demás |
| Se necesita un dato urgente con el caché vigente | Se usa el caché, salvo en la búsqueda por artículo, que exige datos de 1 hora o menos |

## 12. Preguntas para el experto
1. ¿Le parecen razonables 6 consultas por minuto por comercio, con pausas de 10 a 15 segundos?
2. ¿Conviene **respetar las indicaciones que cada sitio publica para los programas automáticos** (el archivo "robots.txt"), aunque eso deje fuera algunas páginas de ofertas?
3. ¿Qué tan "fresco" debe ser el dato para un cliente: 1 hora está bien, o lo quiere más reciente?
4. Ante una pausa por bloqueo, ¿24 horas es razonable o lo dejaría más tiempo?

## 13. Decisiones tomadas
| Fecha | Decisión | Quién |
|---|---|---|
| 2026-11-09 | Consulta responsable con límites, caché, reintentos y tiempos de espera | Jesús y experto |
| 2026-11-09 | OIP no pretende ocultarse; stealth deshabilitado por defecto | Jesús y experto |
| 2026-11-09 | Las consultas a comercios salen del servidor en la nube, también en la prueba de concepto; modo desarrollo con lista permitida | Jesús |
| 2026-11-09 | Proxies residenciales: no en el MVP, pero no se descartan | Jesús |

## 14. Revisión de consistencia
- Última revisión: pendiente
- Detalle: `revisiones/RN-010.md`
