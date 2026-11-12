# CASO-001 — Nintendo Switch 2, edición Zelda 40 aniversario

```yaml
id: CASO-001
tipo: búsqueda por artículo (funcionalidad B)
fecha_del_ejercicio: 2026-11-11
moneda: USD
comercios: solo EE. UU.
reglas_que_prueba: [RN-011, RN-012 (propuesta)]
estado: ESCENARIO DE PRUEBA (resultado esperado acordado con las reglas vigentes)
```

> **Para qué sirve este caso.** Es un ejercicio real que se usó para comprobar las reglas antes de construir. Cuando OIP exista, con estos mismos datos debe dar **exactamente** el resultado esperado de la sección 3. Los precios vienen del ejercicio y **no se verificaron** contra los comercios.

## 1. La solicitud

Un cliente quiere el **Nintendo Switch 2 – Zelda 40th Anniversary Edition** (consola nueva, edición especial). Pide dónde está más económico y disponible.

## 2. Datos encontrados

| Comercio | Vendedor | Precio | Disponibilidad en línea |
|---|---|---|---|
| Walmart | **Vendedor externo** (marketplace) | $459.99 | No confirmada |
| Amazon | Sin dato | $499.99 | No confirmada |
| GameStop | El comercio | $499.99 | No confirmada |
| Walmart Business | El comercio (canal para empresas) | $519.00 | Existencia limitada |
| Best Buy | El comercio | $519.99 | Agotado |
| Target | El comercio | $519.99 | Agotado |
| Nintendo Store | Fabricante | $519.99 | Agotado |

**Precio oficial del fabricante (MSRP):** $519.99.
**Historial propio de OIP:** ninguno (producto nunca monitoreado).
**Fuente de los datos:** un comparador de precios (Deal.ai). No se confirmó cada precio en la ficha del comercio.

## 3. Resultado esperado

### 3.1 Búsqueda por artículo (RN-011)

- **Opción recomendada: ninguna.** No hay una sola opción con disponibilidad confirmada.
- **Mensaje:** *"No hay opción disponible confirmada; repetir la búsqueda más tarde."*
- Todas las opciones aparecen en **"Otras opciones"**, ordenadas por total:
  1. Walmart $459.99, marcada **vendedor externo · disponibilidad no confirmada**.
  2. Amazon $499.99, **disponibilidad no confirmada**.
  3. GameStop $499.99, **disponibilidad no confirmada**.
  4. Walmart Business $519.00, **existencia limitada · puede requerir cuenta de empresa**.
  5. Best Buy, Target y Nintendo Store, $519.99, **agotado**.

### 3.2 Calidad del precio (RN-012, propuesta)

Sin historial propio, la única referencia es el MSRP, y con ella el máximo posible es **"Precio competitivo"**.

| Opción | Diferencia contra el MSRP | Clasificación | Por qué |
|---|---|---|---|
| Amazon / GameStop $499.99 | $20.00 menos (3.85%) | Precio competitivo | Mejor precio del comercio mismo, sin historial que pruebe un descuento |

> **Precisión (2026-11-11, RN-012 v1):** para Amazon, "Precio competitivo" supone que Jesús confirma en su captura que vende Amazon (DEC-160). Si el vendedor queda sin confirmar, el resultado es "sin clasificación" hasta confirmarlo.
| Walmart $459.99 | $60.00 menos (11.54%) | Descuento cuestionable | Vendedor externo y disponibilidad no confirmada |
| Walmart Business $519.00 | $0.99 menos (0.19%) | Sin clasificación de oferta | Prácticamente el MSRP |

**Conclusión esperada:** hay precios por debajo del oficial, pero **no hay evidencia suficiente de una oferta confirmada**. Coincide con la conclusión del ejercicio.

## 4. Huecos que descubrió en las reglas (adoptados el 2026-11-11)

| # | Hueco | Cambio adoptado | Regla afectada |
|---|---|---|---|
| 1 | No se distingue si vende **el comercio** o un **vendedor externo** | Registrar siempre el vendedor; las opciones de vendedor externo se muestran marcadas y **no se recomiendan por defecto** | RN-011 v2, RN-012 |
| 2 | No existe el **precio oficial del fabricante (MSRP)** como referencia | Agregarlo como referencia solo cuando no hay historial; nunca se calcula un descuento contra él | RN-012 |
| 3 | No están definidos los **estados de disponibilidad en línea** | Estados: disponible confirmada · existencia limitada · no confirmada · agotado | RN-011 v2 (mismo defecto D-002 de su revisión) |
| 4 | **Canales especiales** (Walmart Business) | Canal aparte, marcado "puede requerir cuenta especial" | RN-011 v2 |
| 5 | **Comercios y fuentes nuevas** | GameStop y Nintendo Store entran como comercios. Un comparador puede ser fuente, pero cada precio se confirma contra la ficha del comercio | RN-011 v2, DEC-132, DEC-133 |

Decisiones relacionadas: DEC-129 a DEC-136 en `docs/proceso/registro-de-decisiones.md`.

## 5. Cómo se verifica

Cuando exista el motor, este caso se convierte en una prueba automática: se cargan los datos de la sección 2 y se compara la salida contra la sección 3. Las cuentas de la sección 3.2 se verificaron con un script (redondeo a 2 decimales).
