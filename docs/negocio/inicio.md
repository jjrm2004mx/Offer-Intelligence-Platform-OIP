# OIP — Reglas de negocio

**Offer Intelligence Platform (OIP)** es una herramienta que busca productos en distintos comercios y tiene **dos funcionalidades principales**, que comparten el mismo motor de búsqueda:

| | Funcionalidad | Qué hace | Reglas |
|---|---|---|---|
| **A** | **Búsqueda automatizada de ofertas** | Trabaja de forma periódica y autónoma: identifica productos en oferta, compara precios entre tiendas, detecta cambios de precio y encuentra los que se pueden comprar muy por debajo de su precio real de mercado para **revender con ganancia**. Por ejemplo: liquidaciones en Home Depot o Walmart, para revender en Amazon | RN-001 a RN-009 |
| **B** | **Búsqueda particular por artículo** (servicio a clientes) | Un cliente pide un producto concreto (por ejemplo, un Nintendo Switch) y OIP lo busca, compara precios, revisa la disponibilidad publicada y presenta alternativas con enlaces: **primero la más económica, que además esté disponible** | RN-011 |

Las dos funcionan bajo una **consulta responsable** (RN-010): OIP consulta los comercios sin generar tráfico excesivo, sin ocultarse y sin evadir restricciones.

Este sitio contiene **las reglas con las que la herramienta decide**. Están escritas sin lenguaje técnico y con ejemplos numéricos, para que un experto de negocio pueda revisarlas y corregirlas antes de construir nada.

## Cómo leer este sitio

1. Cada **regla (RN)** explica qué se quiere lograr, cómo funciona, qué valores usa y trae ejemplos con números.
2. Los valores marcados **"Por confirmar"** son propuestas iniciales: ahí su opinión es la más valiosa.
3. Cada regla tiene una sección **"Preguntas para el experto"**.
4. Cada regla pasa por una **revisión de consistencia** (cuentas, contradicciones, ambigüedades), con su dictamen y preguntas adicionales. Está en el menú "Revisión de consistencia".

## Cómo encajan las reglas

**Funcionalidad A — búsqueda automatizada (reventa)**

```
Oferta encontrada en una tienda
   │
   ├─ RN-002  ¿Cuánto vale de verdad en el mercado? ¿A cuánto la vendo?
   ├─ RN-003  ¿El descuento es real o inflado?
   ├─ RN-004  ¿La gente compra este producto?
   ├─ RN-006  ¿Cuánto cobra Amazon? ¿Se puede vender?
   ├─ RN-001  ¿Cuánto gano por unidad?
   ├─ RN-005  ¿Cuánto gano de verdad, contando tiempo, devoluciones y riesgo?
   ├─ RN-007  Si es en tienda: ¿qué tan seguro es que esté ahí?
   ├─ RN-009  ¿Qué nivel de oportunidad es? ¿Aviso de inmediato?
   └─ RN-008  Si es en tienda: ¿vale la pena el viaje?
```

**Funcionalidad B — búsqueda por artículo (servicio a clientes)**

```
Un cliente pide un artículo a Jesús → Jesús lo captura en OIP
   │
   ├─ RN-011  ¿Dónde está más económico? ¿Está disponible?
   └─ RN-007  Si es en tienda: ¿qué tan seguro es que esté ahí?
```

**Para las dos:** RN-010, consulta responsable (cuántas consultas, a qué velocidad y desde dónde).

## Estado de las reglas

| Regla | Tema | Estado | Revisión |
|---|---|---|---|
| [RN-001](reglas/RN-001-margen-neto.md) | Margen neto de reventa | Borrador | [Ver](revisiones/RN-001.md) |
| [RN-002](reglas/RN-002-precio-de-mercado.md) | Precio de mercado y de venta | Borrador | [Ver](revisiones/RN-002.md) |
| [RN-003](reglas/RN-003-descuentos-falsos.md) | Descuentos falsos | Borrador | [Ver](revisiones/RN-003.md) |
| [RN-004](reglas/RN-004-demanda.md) | Demanda suficiente | Borrador | [Ver](revisiones/RN-004.md) |
| [RN-005](reglas/RN-005-rentabilidad-ajustada-por-tiempo.md) | Rentabilidad ajustada | Borrador | [Ver](revisiones/RN-005.md) |
| [RN-006](reglas/RN-006-comisiones-y-restricciones.md) | Comisiones y restricciones | Borrador | [Ver](revisiones/RN-006.md) |
| [RN-007](reglas/RN-007-confianza-disponibilidad-tienda.md) | Disponibilidad en tienda | Borrador | [Ver](revisiones/RN-007.md) |
| [RN-008](reglas/RN-008-costo-de-traslado.md) | Costo del viaje | Borrador | [Ver](revisiones/RN-008.md) |
| [RN-009](reglas/RN-009-niveles-y-alertas.md) | Niveles y avisos | Borrador | [Ver](revisiones/RN-009.md) |
| [RN-010](reglas/RN-010-consulta-responsable.md) | Consulta responsable a los comercios | Borrador | [Ver](revisiones/RN-010.md) |
| [RN-011](reglas/RN-011-busqueda-por-articulo.md) | Búsqueda por artículo (servicio a clientes) | Borrador | [Ver](revisiones/RN-011.md) |

## Decisiones generales ya tomadas

- La herramienta es de uso personal y funciona todo el año, con atención especial a temporadas (Buen Fin, Black Friday, Navidad, liquidaciones).
- Además, ofrece un **servicio de búsqueda por artículo a clientes**. Por ahora el cliente le pide a Jesús; más adelante podrá pedirlo directamente (por ejemplo, por WhatsApp). Entra en el primer incremento.
- OIP **no pretende ocultarse ni evadir restricciones**; las consultas a los comercios salen desde un servidor en la nube, nunca desde la casa de Jesús.
- Se compra en línea y en tiendas físicas de la zona de San Diego.
- Se vende en Amazon enviando uno mismo (FBM). Facebook Marketplace llegará después.
- Costos de importación o cruce **para la venta**: fuera del modelo.
- Todos los cálculos en dólares (USD).

## ¿Cómo dar sus comentarios?

Envíe sus respuestas o correcciones directamente a Jesús, citando la regla y el número de pregunta (por ejemplo, "RN-003, pregunta 1: yo usaría 25%"). Cada cambio queda registrado en la sección "Decisiones tomadas" de la regla.

Términos que pueden ser nuevos: ver el [Glosario](glosario.md).
