# Pendientes de consolidación (ejercicios de comprobación, 2026-11-11)

```yaml
fecha: 2026-11-11
estado: ABIERTO (se decide todo junto en la consolidación)
fuentes: [CASO-001 a CASO-006, ANL-001, registro de decisiones §9.1 y §10]
```

> **Para qué sirve:** reunir en un solo lugar todo lo que salió de los ejercicios y **todavía no está decidido**, con la propuesta de Claude cuando la hay. Ninguna propuesta está aprobada. Las decisiones ya tomadas están en el registro (DEC-123 a DEC-142) y no se repiten aquí.

## 1. Preguntas de alcance para Jesús

| # | Pregunta | Propuesta de Claude | Origen |
|---|---|---|---|
| P-01 | ¿RN-002 separa **precio de mercado hoy** (competitividad) y **precio habitual** (descuento)? | Sí. Ejemplo: taladro habitual $200, hoy $150 en otro comercio; con la regla actual no se vería el 25% de descuento real | DEC-128, DEC-129 |
| P-02 | ¿Se confirma el costo de entrega con las tarifas de RN-008? | Sí ($0.20/km, $15/hora) | DEC-142 |
| P-03 | ¿Los **productos usados** entran al alcance? | Sí, con estado obligatorio y valor de usados comparables | CASO-006, ANL-001 |
| P-04 | ¿**F3** (particulares) arranca con **captura manual** de publicaciones? | Sí; automatizar después de revisar condiciones de uso | CASO-006, ANL-001 |
| P-05 | ¿El Inc. 1 se limita a 3 orígenes × 2 canales? | Orígenes: tienda en línea, tienda física, particulares por captura manual. Canales: Amazon FBM calculado y **venta local** (OfferUp, Marketplace y venta personal juntas, con precio estimado) | ANL-001 §7 |
| P-06 | ¿Búsqueda **por necesidad** (el cliente describe lo que necesita)? | Inc. 1: Jesús traduce la necesidad en 1 a 3 modelos al capturar; automática, después | CASO-002 |
| P-07 | Lista priorizada de categorías por temporada | Por proponer con el experto | DEC-138 |
| P-08 | ¿Sitios de seguimiento de precios como fuente temporal de historial? | Solo como señal, igual que comparadores; revisar condiciones de uso | CASO-004 |

## 2. Propuestas para las reglas (se aplican al reescribirlas)

### Identidad y datos
- **Producto exacto:** solo se compara el mismo modelo, versión, generación y contenido. Sin certeza, la comparación queda "no confirmada". Se repitió en 4 casos (edición, kit, generación, contenido). (CASO-001, 002, 003, 006)
- **Estado del producto:** nuevo, caja abierta, reacondicionado, usado, para piezas. (CASO-006)
- **Disponible confirmada en línea:** la ficha dice "en existencia" **y** permite agregar al carrito. (CASO-003)
- **Para comparar** solo cuentan publicaciones del mismo producto, vendidas por el comercio y disponibles; las demás se muestran aparte. (CASO-003)
- **Mínimo de comercios** para calificar un precio; uno solo no basta. (CASO-005)
- **Confirmación por segundo comercio:** un precio bajo en dos comercios independientes es más creíble. (CASO-004)

### Calidad del precio (RN-012)
- **Umbrales iniciales:** "Buena oferta" = 15% o más bajo el habitual y entre los más baratos del mercado; "Oferta excepcional" = además, por debajo del mínimo de 12 meses. Calibrar con CASO-004 (20.32% / 27.28% = Buena oferta). (CASO-003, 004)
- **Cercanía al mínimo histórico** como criterio aparte del descuento contra la mediana. (CASO-003)
- **Marca "descuento anunciado no comprobado"**, separada de la clasificación del precio. (CASO-003)
- **Promedio contra mediana:** OIP usa mediana; los sitios externos suelen usar promedio. (CASO-004)
- **Renombrar** los niveles de RN-009 o las clases de RN-012, porque comparten "Excepcional" y "Buena". (CASO-005)

### Descubrimiento (F1)
- **Filtro previo:** el descuento anunciado decide **qué investigar** (por ejemplo, 40% o más, marca reconocida, categoría acordada), no califica la oferta. Necesario por el límite de RN-010. (CASO-003)
- **Descuento general contra aislado:** la oportunidad de reventa nace cuando un comercio está muy por debajo de los demás, sobre todo de Amazon; las ofertas nacionales que Amazon iguala no dejan margen. Pasó en los 4 primeros casos. (CASO-003, 004)

### Demanda
- **Reseñas** como señal complementaria fuera de Amazon, nunca suficiente sola; vale más su **variación** entre consultas. (CASO-002)

### Costo total de compra (F2)
- Precio + envío ordenan las opciones. **Impuestos:** se muestran, no ordenan (dependen del código postal de entrega). **Membresías:** marcar "requiere membresía"; no es el precio normal. **Cupones:** solo los que aparecen en la ficha. **Devolución y garantía:** se muestran como información. (CASO-003)
- **Desempate** con precio igual: envío, disponibilidad confirmada, devolución. (CASO-004)
- **Sugerencias** (DEC-139): la otra generación o una oferta relacionada. (CASO-003)
- **Particulares en F2:** marcados y no recomendados por defecto, como el vendedor externo. (ANL-001)

### Venta y riesgo
- **Techo del precio de venta local:** no supera el menor precio pedido comparable **en la zona**. (CASO-005)
- **Precio máximo de compra y vigilancia:** si no es viable, calcular a qué precio lo sería y avisar si baja. Ejemplo: $75.50 para las baterías Milwaukee. (CASO-005)
- **Doble traslado** al comprar y vender con particulares. (CASO-006)
- **Inspección física obligatoria** antes de comprar a un particular. (CASO-006)
- **Riesgo de procedencia** (falsificación, robo) para baterías, herramientas, perfumes y relojes. (CASO-005, 006)
- **Amazon con usados:** requisitos por categoría, por confirmar en RN-006. (ANL-001)

## 3. Reorganización de las reglas

> **Aprobada** el 2026-11-11 con la agrupación de ANL-002 §2.1 (DEC-143 a DEC-146). La tabla siguiente se conserva como la propuesta original.

| Grupo | Reglas |
|---|---|
| Comunes | RN-003, RN-007, RN-008, RN-010, RN-011, RN-012 (nueva); identidad, estado, riesgo y costo de adquisición |
| Amazon FBM | RN-006 y la parte de Amazon de RN-001, RN-002 y RN-004 |
| Venta local | Nueva regla: precio estimado, techo local, entrega, demanda local, tiempo de venta |
| Resultado | RN-005 (rendimiento mensual = oportunidad de inversión) y RN-009 (niveles) |

## 4. Después de decidir

1. Reescribir RN-001 a RN-011 (v2) y crear RN-012 y la regla de venta local.
2. Revisión de consistencia (`oip-revisor-rn`) de cada una.
3. Anotar la arquitectura (§2.2, §4.3, §6, §7, §9, §12, ADR-007).
4. Sesión 2 con el experto.
5. Reestructurar REQ-2026-0001 (#2) y reinspeccionar.
