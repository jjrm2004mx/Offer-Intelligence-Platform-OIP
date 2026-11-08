# OIP — Reglas de negocio

**Offer Intelligence Platform (OIP)** es una herramienta personal que busca, todos los días, productos que se pueden comprar muy por debajo de su precio real de mercado y revender con ganancia. Por ejemplo: liquidaciones en Home Depot, Walmart o Target, para revender en Amazon.

Este sitio contiene **las reglas con las que la herramienta decide qué es una buena oportunidad**. Están escritas sin lenguaje técnico y con ejemplos numéricos, para que un experto de negocio pueda revisarlas y corregirlas antes de construir nada.

## Cómo leer este sitio

1. Cada **regla (RN)** explica qué se quiere lograr, cómo funciona, qué valores usa y trae ejemplos con números.
2. Los valores marcados **"Por confirmar"** son propuestas iniciales: ahí su opinión es la más valiosa.
3. Cada regla tiene una sección **"Preguntas para el experto"**.
4. Cada regla pasa por una **inspección de calidad**, con su dictamen y preguntas adicionales. Está en el menú "Inspecciones".

## Cómo encajan las reglas

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

## Estado de las reglas

| Regla | Tema | Estado | Inspección |
|---|---|---|---|
| [RN-001](reglas/RN-001-margen-neto.md) | Margen neto de reventa | Borrador | [Ver](inspecciones/RN-001.md) |
| [RN-002](reglas/RN-002-precio-de-mercado.md) | Precio de mercado y de venta | Borrador | [Ver](inspecciones/RN-002.md) |
| [RN-003](reglas/RN-003-descuentos-falsos.md) | Descuentos falsos | Borrador | [Ver](inspecciones/RN-003.md) |
| [RN-004](reglas/RN-004-demanda.md) | Demanda suficiente | Borrador | [Ver](inspecciones/RN-004.md) |
| [RN-005](reglas/RN-005-rentabilidad-ajustada-por-tiempo.md) | Rentabilidad ajustada | Borrador | [Ver](inspecciones/RN-005.md) |
| [RN-006](reglas/RN-006-comisiones-y-restricciones.md) | Comisiones y restricciones | Borrador | [Ver](inspecciones/RN-006.md) |
| [RN-007](reglas/RN-007-confianza-disponibilidad-tienda.md) | Disponibilidad en tienda | Borrador | [Ver](inspecciones/RN-007.md) |
| [RN-008](reglas/RN-008-costo-de-traslado.md) | Costo del viaje | Borrador | [Ver](inspecciones/RN-008.md) |
| [RN-009](reglas/RN-009-niveles-y-alertas.md) | Niveles y avisos | Borrador | [Ver](inspecciones/RN-009.md) |

## Decisiones generales ya tomadas

- La herramienta es de uso personal y funciona todo el año, con atención especial a temporadas (Buen Fin, Black Friday, Navidad, liquidaciones).
- Se compra en línea y en tiendas físicas de la zona de San Diego.
- Se vende en Amazon enviando uno mismo (FBM). Facebook Marketplace llegará después.
- Costos de importación o cruce **para la venta**: fuera del modelo.
- Todos los cálculos en dólares (USD).

## ¿Cómo dar sus comentarios?

Envíe sus respuestas o correcciones directamente a Jesús, citando la regla y el número de pregunta (por ejemplo, "RN-003, pregunta 1: yo usaría 25%"). Cada cambio queda registrado en la sección "Decisiones tomadas" de la regla.

Términos que pueden ser nuevos: ver el [Glosario](glosario.md).
