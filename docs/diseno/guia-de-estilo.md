# Guía de estilo — OIP

**Qué es:** la guía de estilo que pide `flujo-general.md` §12.1. La citan `oip-analista` en cada propuesta con interfaz, `oip-developer` al construir y `oip-tester` al verificar.
**Versión:** 1.0 — 2026-11-16 · **Estado:** BORRADOR para revisión
**Origen:** el sistema visual de `prometheus-automation-shopper`. OIP es de la **misma familia**: misma base monocroma, misma tipografía y mismos componentes. Se tomó del **código** (`tailwind.config.js`, `src/index.css`, `src/components/ui.tsx`, `src/lib/theme.ts`), no de sus `.md`, que tienen errores.
**Alcance por incremento:**

- **Inc. 1:** solo aplica el **§10, avisos de Telegram**, porque el tablero es Metabase.
- **Inc. 2:** con interfaz propia, aplica todo.

**Tecnología:** la guía es **agnóstica**. Los tokens son variables CSS y sirven igual con FastAPI + HTMX que con React (arquitectura §12, Inc. 2). Tailwind aparece solo como ejemplo.
**Convención de certeza:** **Verificado** = así está en el código del shopper · **Propuesta** = nuevo para OIP · **PoC** = probar antes de fijar.

---

## 1. Principios

| # | Principio | Porqué |
|---|---|---|
| E-1 | **Monocromo por defecto; el color solo comunica estado** | Es la identidad del shopper (Verificado). En un tablero, si todo tiene color nada destaca: el color se reserva para lo que exige atención |
| E-2 | **Ningún color literal en el código**: todo pasa por tokens | Regla del shopper (Verificado: no hay ni un `#hex` ni un `red-500` en `src/`). El modo oscuro y los ajustes de la paleta cambian en un solo lugar |
| E-3 | **El estado nunca se comunica solo con color**: siempre lleva texto y, si ayuda, un ícono | Daltonismo, pantallas al sol en la tienda física y capturas en blanco y negro |
| E-4 | **Cifras tabulares y alineadas a la derecha** | OIP es un producto de números. El shopper ya usa `tabular-nums` en todas sus cifras (Verificado) |
| E-5 | **Accesibilidad no negociable**: contraste AA (≥ 4.5:1 en texto), foco visible, zoom nunca bloqueado, respeto a `prefers-reduced-motion` | Verificado en el shopper, salvo el contraste del gris terciario, que se corrige aquí (§2.1) |
| E-6 | **Primero el teléfono** en todo lo que se usa fuera de casa: avisos, oportunidad, visita a tienda y búsqueda por artículo | El dueño decide en la tienda, en la garita o en el auto |

---

## 2. Tokens

### 2.1 Base (heredados del shopper)

Formato HSL **sin** `hsl()`, para poder usar transparencia (`hsl(var(--border) / 0.4)`).

| Token | Claro (shopper) | Claro (OIP) | Oscuro (OIP, Propuesta) | Uso |
|---|---|---|---|---|
| `--background` | `0 0% 98%` | igual | `0 0% 7%` | Fondo de la página |
| `--foreground` | `0 0% 12%` | igual | `0 0% 92%` | Texto principal |
| `--surface` | `0 0% 96%` | igual | `0 0% 11%` | Tarjetas, filas alternas |
| `--border` | `0 0% 90%` | igual | `0 0% 20%` | Bordes y divisores |
| `--accent` | `0 0% 94%` | igual | `0 0% 15%` | Fondo de ilustraciones y hover suave |
| `--primary` | `0 0% 9%` | igual | `0 0% 96%` | Botón principal, chip activo |
| `--primary-foreground` | `0 0% 100%` | igual | `0 0% 9%` | Texto sobre `primary` |
| `--text-secondary` | `0 0% 40%` | igual | `0 0% 68%` | Texto de apoyo (5.50:1 en claro) |
| `--text-tertiary` | `0 0% 60%` | **`0 0% 44%`** | `0 0% 55%` | Etiquetas, ayudas, marcas de tiempo |
| `--radius` | `1rem` | igual | igual | Radio base |

> **Corrección (Verificado con cálculo WCAG):** el `--text-tertiary` del shopper (60 %) da **2.73:1** sobre el fondo y **no** pasa AA. Ese gris se usa en textos que hay que leer (eyebrows, ayudas, "consultado hace 3 h"), así que en OIP baja a **44 %**: 4.73:1 sobre el fondo y 4.52:1 sobre `surface`. Conviene llevar la misma corrección al shopper.

### 2.2 Estado (Propuesta, nuevos para OIP)

Cada estado tiene un color **fuerte**, para texto, ícono y borde, y uno **suave**, para el fondo de la insignia. Todos pasan AA, tanto sobre el fondo como sobre su versión suave:

| Token | Claro | Oscuro | Contraste claro (fondo / suave) | Contraste oscuro (fondo / suave) | Significado |
|---|---|---|---|---|---|
| `--success` / `--success-soft` | `142 64% 28%` / `142 50% 94%` | `142 55% 55%` / `142 40% 14%` | 5.50 / 5.20 | 9.09 / 6.75 | Confirmado, confianza Alta, buena calidad del precio |
| `--warning` / `--warning-soft` | `28 85% 34%` / `40 90% 93%` | `36 90% 60%` / `36 60% 13%` | 5.42 / 5.12 | 9.64 / 7.58 | Requiere atención: revisión manual, confianza Media, existencia limitada, cuestionable |
| `--danger` / `--danger-soft` | `0 70% 42%` / `0 80% 96%` | `0 80% 68%` / `0 50% 15%` | 6.24 / 5.74 | 6.28 / 5.49 | Bloqueo o pérdida: fuente bloqueada o pausada, agotado, confianza Baja, descartada |
| `--info` / `--info-soft` | `214 70% 40%` / `214 80% 95%` | `214 85% 68%` / `214 50% 15%` | 6.26 / 5.73 | 7.33 / 6.14 | Dato informativo: estimado, simulado, modo desarrollo |

Regla: el color de estado **solo** aparece en insignias, íconos, bordes de 2px y barras de aviso. **Nunca** en fondos de sección ni en botones principales.

### 2.3 Implementación (agnóstica)

```css
:root {
  --background: 0 0% 98%;  --foreground: 0 0% 12%;  --surface: 0 0% 96%;
  --border: 0 0% 90%;      --accent: 0 0% 94%;
  --primary: 0 0% 9%;      --primary-foreground: 0 0% 100%;
  --text-secondary: 0 0% 40%;  --text-tertiary: 0 0% 44%;
  --success: 142 64% 28%;  --success-soft: 142 50% 94%;
  --warning: 28 85% 34%;   --warning-soft: 40 90% 93%;
  --danger: 0 70% 42%;     --danger-soft: 0 80% 96%;
  --info: 214 70% 40%;     --info-soft: 214 80% 95%;
  --radius: 1rem;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) { /* valores oscuros de §2.1 y §2.2 */ }
}
:root[data-theme="dark"] { /* los mismos valores oscuros */ }
body { background: hsl(var(--background)); color: hsl(var(--foreground)); }
```

- **Con Tailwind:** se mapea igual que en el shopper, `success: 'hsl(var(--success) / <alpha-value>)'`, y se suman los cuatro colores de estado a los nueve heredados.
- **Sin Tailwind (HTMX):** se usan las variables directamente en un `.css` propio.
- **Un solo punto de escritura:** como `applyTheme()` en el shopper, solo el selector de tema cambia `data-theme`, y la preferencia se guarda en el navegador.

---

## 3. Tipografía

**Familia (Verificado):** Inter, con la pila de respaldo `-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif`. El shopper la carga desde `rsms.me`; OIP debe **servirla desde su propio servidor**, porque es una herramienta interna y no debe depender de terceros.

### 3.1 Escalas heredadas (Verificado)

| Clase | Tamaño (móvil → `sm`) | Peso · interletrado · interlínea | En OIP se usa para |
|---|---|---|---|
| `.display` | 36 → 60 px | 600 · −0.03em · 1.05 | No se usa en el tablero |
| `.headline-lg` | 30 → 48 px | 600 · −0.025em · 1.1 | Título de la pantalla de una oportunidad |
| `.headline-md` | 24 → 36 px | 600 · −0.02em · 1.15 | Título de página |
| `.headline-sm` | 20 → 24 px | 600 · −0.015em | Cifra principal (margen, ganancia del viaje), título de tarjeta |
| `.eyebrow` | 12 px | 600 · mayúsculas · +0.18em · `text-tertiary` | Etiqueta sobre un grupo ("SUCURSALES", "CANAL") |
| `.body-lg` | 18 px | 1.625 · `text-secondary` | Introducciones (poco en el tablero) |
| `.body-sm` | 14 px | 1.625 · `text-secondary` | Descripciones y ayudas |

### 3.2 Escala densa para el tablero (Propuesta)

| Clase | Tamaño | Uso |
|---|---|---|
| `.data` | 14 px · 500 · `tabular-nums` · interlínea 1.4 | Celdas de tabla y cifras en listas |
| `.data-strong` | 14 px · 600 · `tabular-nums` | Total, margen y nivel dentro de la tabla |
| `.data-xs` | 12 px · 500 · `tabular-nums` · `text-tertiary` | "hace 3 h", código del comercio, SKU |
| `.th` | 12 px · 600 · mayúsculas · +0.08em · `text-tertiary` | Encabezados de tabla |

---

## 4. Espacio y retícula

| | Sitio del shopper (Verificado) | Tablero de OIP (Propuesta) |
|---|---|---|
| Contenedor | `max-width: 72rem`, `padding: 20px` → 32px en `sm` | Igual en páginas de lectura; las tablas pueden ir a **90rem** |
| Separación de secciones | `py-16 sm:py-24` (64 → 96 px) | **24 → 32 px**: el tablero es denso, no es un sitio de marketing |
| Tarjeta | `rounded-2xl p-6 sm:p-8` | Igual en el detalle; `p-4` en las tarjetas de lista |
| Fila de tabla | — | Alto mínimo de 44 px (es también el área táctil) |
| Breakpoints | `sm` 640 · `md` 768 · `lg` 1024 · `xl` 1280 | Iguales. Por debajo de `md`, **las tablas se vuelven tarjetas** (§8) |

---

## 5. Componentes heredados (Verificado)

| Componente | Forma | En OIP |
|---|---|---|
| **Button** | Píldora (`rounded-full`). `primary` negro sobre blanco; `outline` con borde; `ghost` solo texto. Tamaños `md` (14 px) y `lg` (16 px). Deshabilitado al 40 % de opacidad | Igual. **Un solo `primary` por pantalla**: la acción principal, por ejemplo "Re-consultar tienda" |
| **Card** | `rounded-2xl`, `surface`, borde de 1px | Igual |
| **Chip** | Píldora, `aria-pressed`. Activo con `primary` y en reposo con `surface` | Filtros del tablero: nivel, canal, comercio, categoría |
| **OptionCard** | Tarjeta seleccionable con borde de 2px | Elegir modalidad en la búsqueda por artículo ("solo enlace" o "compra y entrega") |
| **Field** + `inputClass` | Etiqueta de 14 px; el obligatorio lleva `*`; ayuda de 12 px; input `rounded-xl` de 16 px | Captura de solicitudes (`client_request`) y de publicaciones de particulares. **16 px en el input** para que el teléfono no haga zoom al tocarlo |
| **Metric** | Cifra `headline-sm` tabular más una etiqueta | Resumen de la oportunidad: margen, rendimiento mensual, unidades |
| **Accordion** | `details/summary` nativo con un "+" que gira | Mostrar el "por qué" del nivel: fórmulas y fuentes |
| **Section** | Eyebrow, título, introducción | Solo en páginas de lectura |
| **Header** | Pegajoso, `background/85` con `backdrop-blur`, alto de 64 px, menú móvil | Igual |

---

## 6. Componentes nuevos para OIP (Propuesta)

| Componente | Forma | Reglas |
|---|---|---|
| **Insignia de estado** | Píldora pequeña (12 px, 600), fondo `*-soft`, texto e ícono en el color fuerte | Siempre con texto. Hasta 2 insignias por fila; el resto entra en "+N" |
| **Insignia de nivel** | Escala **monocroma** por intensidad (§7.1) | El nivel no usa color de estado: es una jerarquía, no una alarma |
| **Tabla densa** | Encabezado `.th` pegajoso, filas de 44 px, divisores `border`, hover `accent`, cifras a la derecha, orden por columna con `aria-sort` | Columnas fijas de una oportunidad: producto · comercio/sucursal · precio · descuento real · margen · rendimiento · nivel · confianza · hace cuánto |
| **Marca de tiempo relativa** | `.data-xs` con un reloj: "hace 3 h"; la hora exacta en `title` | Pasa a `warning` cuando el dato está cerca de su ventana de confianza (RN-007) y a `danger` cuando la excede |
| **Barra de aviso** | Franja de ancho completo bajo el header, borde izquierdo de 4px en color de estado y fondo `*-soft` | **Obligatoria** en `modo_red: desarrollo` (DEC-121), en `info`, y cuando una fuente está pausada por bloqueo, en `danger`. No se puede cerrar mientras dure la condición |
| **Desglose de cifras** | Lista `dl` en dos columnas: concepto a la izquierda, monto tabular a la derecha y el total en `.data-strong` con un divisor arriba | Para el margen (RN-001) y el viaje (RN-008). El shopper ya usa este patrón en su calculadora (Verificado: `<dd className="tabular-nums">`) |
| **Estado vacío** | Ilustración SVG con trazo en tokens, como `Art.tsx` del shopper (Verificado), más una frase y una acción | "Sin oportunidades hoy" no es un error: se dice con calma |
| **Esqueleto de carga** | Bloques `accent` con `aria-busy="true"` | Sin animación si `prefers-reduced-motion` |

---

## 7. Mapa de estados a apariencia

### 7.1 Eje 2: nivel de oportunidad de reventa (RN-009)

| Nivel | Insignia | Aviso |
|---|---|---|
| **Comprar ya** | Relleno `primary`, texto `primary-foreground` y un ícono de rayo | Inmediato |
| **Muy recomendable** | Relleno `foreground` al 75 % y texto `primary-foreground` | Inmediato |
| **Recomendable** | Borde de 2px `foreground` y texto `foreground` | Resumen de las 8:00 y las 18:00 |
| **Vigilar** | Borde de 1px `border` y texto `text-secondary` | Solo en el tablero |

### 7.2 Eje 1: calidad del precio (RN-012)

| Clase | Color | Texto |
|---|---|---|
| Oferta excepcional | `success`, ícono de estrella | "Oferta excepcional" |
| Buena oferta | `success`, sin ícono | "Buena oferta" |
| Precio competitivo | Neutro (`text-secondary`) | "Precio competitivo" |
| Descuento cuestionable | `warning`, ícono de alerta | "Descuento cuestionable" |

Los dos ejes se ven **a la vez**, sin mezclarse (DEC-131). El nivel es una insignia monocroma y la calidad es una insignia de color.

### 7.3 Resultado, confianza, disponibilidad y marcas

| Concepto | Valor | Color | Regla |
|---|---|---|---|
| Resultado (RN-009) | Descartada | `danger` (atenuado en la lista) | Solo en filtros o en el historial |
| | Solo referencia | Neutro | — |
| | **Revisión manual** | `warning` | Muestra el motivo: sin historial, no confirmada, vendedor externo, riesgo |
| Confianza (RN-007) | Alta / Media / Baja | `success` / `warning` / `danger` | Siempre junto a la marca de tiempo |
| Disponibilidad (DEC-134) | Disponible confirmada · existencia limitada · no confirmada · agotado | `success` · `warning` · neutro · `danger` | — |
| Marcas | Vendedor externo | `warning` | Nunca recomendada por defecto (DEC-135) |
| | Estimado (precio de venta local) | `info` | DEC-140 |
| | Coincidencia no confirmada | `warning` | RN-013 |
| | Requiere cuenta especial / membresía | Neutro con un ícono de candado | RN-011 |
| | Simulado (respuesta simulada, sin dato real) | `info` | DEC-124 |
| Fuente (RN-010) | Activa / pausada por bloqueo / `browser_stealth` | Neutro / `danger` / `warning` | Activar stealth es G5; se muestra quién y cuándo |

---

## 8. Móvil

- **Patrón:** por debajo de `md`, cada fila de tabla es una **tarjeta**:
  1. Arriba, el producto y la insignia de nivel.
  2. En medio, el `Metric` de margen y de rendimiento.
  3. Abajo, el comercio, la sucursal, la confianza y la marca de tiempo.
  4. Al pie, la acción principal.
- **Toque:** áreas de al menos **44 × 44 px**, la acción principal al alcance del pulgar (abajo) y nada que dependa de hover.
- **Pantallas de campo:** oportunidad, ruta de compra y registro de visita (encontrado / no encontrado / precio distinto). Botones grandes, `lg`, y un máximo de 3 acciones.
- **Zoom:** nunca bloqueado (Verificado: el `viewport` del shopper no lleva `maximum-scale`). Inputs de 16 px.

## 9. Modo oscuro

- **Cuándo:** sigue la preferencia del sistema y se puede forzar con `data-theme` (§2.3). Se usa de noche, en el auto o en la garita.
- **Contraste:** los valores oscuros de §2.1 y §2.2 están calculados y pasan AA.
- **Ilustraciones:** heredan los tokens y cambian solas.
- **Nada de sombras:** en oscuro se separa con `border` y `surface`, igual que en claro (el shopper no usa sombras, Verificado).

---

## 10. Avisos de Telegram (Inc. 1)

Es lo único de esta guía que aplica desde el Inc. 1. Telegram no tiene colores, así que la jerarquía se da con **emoji, negritas y orden**.

### 10.1 Emoji por nivel (Propuesta)

| Nivel | Emoji | Motivo |
|---|---|---|
| Comprar ya | ⚡ | Urgencia sin usar rojo (el rojo significa problema, §2.2) |
| Muy recomendable | ✅ | — |
| Recomendable (solo en el resumen) | 👍 | — |
| Vigilar | (no se avisa) | Solo en el tablero |
| Revisión manual | (no se avisa) | RN-009 |
| Problema operativo (fuente pausada, Worker caído) | 🛑 | Lo único que usa una señal de alarma |
| Modo desarrollo activo | 🧪 | DEC-121 |

> Esto **reemplaza** los 🔴🟠🟡⚪ de la arquitectura v1.3 §2.4, que eran de los nombres anteriores de los niveles.

### 10.2 Estructura del aviso inmediato

Modo de formato: **HTML** de Telegram (`<b>`, `<i>`, `<code>`, `<a>`), sin Markdown, porque se rompe con los símbolos de los precios.

Ejemplo **ilustrativo**: el nivel, el descuento real y el margen % son los del ejemplo A de RN-009; el resto de las cifras son inventadas para mostrar el formato.

```
✅ <b>Muy recomendable</b> · Amazon FBM
<b>Sierra circular</b>
Home Depot · Chula Vista (Zona 1)

Compra   <code>$  49.00</code>
Venta    <code>$ 199.00</code>
Margen   <code>$  70.12</code>  (143.1 %)
Desc. real 75.6 % · Rinde 61.2 %/mes · 3 u.

Buena oferta · Confianza Alta · hace 2 h
<a href="…">Ver en el comercio</a> · <a href="…">Abrir en OIP</a>
```

| Regla | Detalle |
|---|---|
| Orden fijo | Nivel y canal → producto → dónde → cifras → calidad, confianza y antigüedad → enlaces |
| Cifras | USD con 2 decimales y porcentajes con 1 decimal (DEC-060). Los montos en `<code>`, alineados a la derecha con espacios, porque Telegram usa letra de ancho fijo en `<code>` |
| Un aviso por cadena | Varias sucursales del mismo comercio van en un aviso, ordenadas por cercanía a la garita, con su confianza (RN-009 §4.4) |
| Marcas | Al final, en una línea: `⚠️ Estimado` (venta local) · `⚠️ No confirmada` |
| Botones (teclado en línea) | **Re-consultar tienda** (obligatorio en tienda física, arquitectura §6.3.1) y **Registrar visita** (encontrado / no encontrado / precio distinto) |
| Prohibido | Datos de clientes, tokens, IP y texto del HTML del comercio (P-09 del insumo del stack de tickets) |

### 10.3 Resumen (8:00 y 18:00) y agrupación

Ejemplo ilustrativo, con cifras inventadas:

```
👍 <b>Resumen 18:00</b> · 4 recomendables

1. <b>Licuadora Ninja BN701</b> · Walmart en línea
   Margen <code>$ 31.40</code> (38.2 %) · Rinde 22.0 %/mes
2. …

<a href="…">Ver todas en OIP</a>
```

- Ordenado por **rendimiento mensual** (RN-005).
- Si hay más de 10 avisos inmediatos en una hora (RN-009), se agrupan en un solo mensaje con este mismo formato y el encabezado `⚡ 12 oportunidades en la última hora`.
- **Modo desarrollo:** cada mensaje empieza con `🧪 <b>MODO DESARROLLO</b> — datos de prueba`.

---

## 11. Formato de cifras y textos

| Dato | Formato | Ejemplo |
|---|---|---|
| Monto | `$` + miles con coma + 2 decimales, siempre USD (DEC-011) | `$1,234.50` |
| Porcentaje | 1 decimal al mostrar; sin redondear al calcular (DEC-060) | `75.6 %` |
| Antigüedad | Relativa ("hace 3 h", "hace 2 días"), con la hora exacta de Tijuana en `title` | `hace 3 h` |
| Fecha | `16 nov 2026, 18:00` | — |
| Ausencia de dato | Raya larga `—`, nunca `0` ni vacío | `—` |
| Textos | En un solo archivo de textos, como `copy.ts` del shopper (Verificado), para no repetir frases | — |
| Tono | Español llano, frases cortas y los nombres exactos de las RN | "Revisión manual: vendedor externo" |

---

## 12. Qué no se toma del shopper

| Del shopper | Por qué no |
|---|---|
| Tema por tenant en tiempo de ejecución (`applyTheme(tenant)`, multitenant) | OIP es de un solo usuario. Se conserva la idea de **un solo punto de escritura** de los tokens, solo para claro y oscuro |
| Espaciado de marketing (`py-16 sm:py-24`), escala `display` | Un tablero necesita densidad (§4) |
| Prerender, SEO, Open Graph, presupuesto de JS público | OIP no es público (`noindex`, uso interno) |
| Botón de WhatsApp, contenido comercial | Otro producto |
| Fuente desde `rsms.me` | Se sirve local (§3) |
| Los `.md` de `docs/` del shopper | Fueron generados y tienen errores (rutas que no existen, afirmaciones sin sustento). La fuente es el código |

---

## 13. Lista para `oip-tester`

- [ ] Ningún color literal: `grep` de `#hex`, `rgb(` y clases de paleta fija sobre el código de la interfaz.
- [ ] Ningún estado se distingue solo por color.
- [ ] El contraste AA pasa en claro y en oscuro, también en `text-tertiary` y en las insignias.
- [ ] Las cifras usan `tabular-nums` y van alineadas a la derecha. Un dato ausente muestra `—`.
- [ ] El foco es visible en todo lo que se puede tocar; los chips y las opciones llevan `aria-pressed`; las tablas, `aria-sort`.
- [ ] En 375 px de ancho no hay scroll horizontal, las tablas se ven como tarjetas y las áreas de toque miden 44 px o más.
- [ ] La barra de modo desarrollo se ve cuando `modo_red = desarrollo`.
- [ ] Los avisos de Telegram siguen el §10: orden, formato de cifras, emoji, botones y nada prohibido.

---

## 14. Decisiones propuestas

Numeración provisional. Siguen a las propuestas del insumo del stack de tickets (DEC-173 a DEC-183); si esas cambian, se renumeran.

| ID | Decisión propuesta |
|---|---|
| DEC-184 | OIP adopta esta guía de estilo, de la **misma familia** visual que `prometheus-automation-shopper`. La guía es agnóstica de la tecnología de la interfaz |
| DEC-185 | Monocromo por defecto; color **solo** para estado, con 4 familias (`success`, `warning`, `danger`, `info`) que pasan AA; el estado nunca solo con color |
| DEC-186 | Niveles de RN-009 en una escala monocroma por intensidad; calidad del precio de RN-012 con color, visibles a la vez |
| DEC-187 | `--text-tertiary` al 44 % (el 60 % del shopper no pasa AA) |
| DEC-188 | Modo oscuro desde el Inc. 2, por preferencia del sistema y con selector manual |
| DEC-189 | Formato de los avisos de Telegram del §10. Los emoji ⚡ ✅ 👍 🛑 🧪 reemplazan los 🔴🟠🟡⚪ de la arquitectura §2.4 |
| DEC-190 | Inter servida localmente; tablero denso; tablas como tarjetas por debajo de `md` |
