# CASO-007 — Home Depot: ofertas del día y folleto de Black Friday (prueba del filtro previo)

```yaml
id: CASO-007
tipo: búsqueda de ofertas (A), descubrimiento en páginas de promociones
fecha_del_ejercicio: 2026-11-09 (datos) · 2026-11-11 (análisis)
moneda: USD
comercios: solo EE. UU.
reglas_que_prueba: [RN-003 v2 (filtro previo), RN-006, RN-012, RN-013, RN-015]
estado: EN ANÁLISIS (falta el precio de venta en cada canal)
```

> Datos tomados por Jesús de las páginas de Home Depot (ofertas del día, página principal y folleto de Black Friday del 5 al 25 de noviembre). **No se verificaron.**

## 1. Datos y resultado del filtro previo (RN-003 v2: 40% o más de descuento anunciado)

| Producto | Precio | Tachado | Anunciado | Filtro previo | Selección de Jesús |
|---|---|---|---|---|---|
| Husky gabinete metálico 48" | $339.89 | $453.19 | 25.00% | No pasa | — |
| Husky banco de trabajo ajustable | $224.25 | $299.00 | 25.00% | No pasa | — |
| Husky gabinete de pared | $111.75 | $149.00 | 25.00% | No pasa | — |
| Husky gabinete 36.6" | $314.25 | $419.00 | 25.00% | No pasa | — |
| DEWALT 20V MAX baterías 2 Ah, paquete de 2 | $79.00 | $169.00 | 53.25% | **Pasa** | Prioridad 1 |
| RYOBI ONE+ kit con baterías y multiherramienta | $99.00 | $178.00 | 44.38% | **Pasa** | Prioridad 2 |
| Ring Starter Set (timbre y cámara) | $59.99 | $139.99 | 57.15% | **Pasa** | Prioridad 3 |
| Milwaukee M12 bocina Bluetooth | $99.00 | $149.00 | 33.56% | **No pasa** | Prioridad 4 |
| Milwaukee SHOCKWAVE puntas, 60 piezas | $74.88 | $149.99 | 50.08% | **Pasa** | No seleccionado |
| LG refrigerador French Door | $1,699.00 | $3,099.00 | 45.18% | **Pasa** | No seleccionado |

**Folleto de Black Friday** (sin precio tachado): RYOBI multiherramienta kit 2 Ah $79 · lavadora LG 4.5 cu. ft. $589 · lavadora GE 4.6 cu. ft. $559 · timbre Wyze $65.98 · sierra circular RYOBI ONE+ 18V $49.97 · caja Milwaukee de dos cajones $179. **Ninguno pasa el filtro**, porque no hay descuento anunciado.

## 2. Lo que se espera de cada candidato (falta el precio de venta)

| Candidato | Lo que ya se sabe con las reglas v2 |
|---|---|
| DEWALT baterías | Lo vende Home Depot → riesgo **Bajo** (RN-015). Baterías de litio → posible material peligroso en Amazon (RN-006): probablemente solo **venta local** |
| RYOBI kit | Identificar el contenido exacto del kit (RN-013) antes de comparar |
| Ring Starter Set | Ring es una marca de Amazon: es probable que Amazon tenga el mismo precio o uno menor, y entonces no hay margen de reventa. Hay que verificarlo |
| SHOCKWAVE | Pasa el filtro y no se había seleccionado: conviene incluirlo |
| LG refrigerador | Voluminoso: el envío por Amazon FBM y la entrega local son difíciles. Falta una regla para productos voluminosos |

## 3. Huecos que descubrió

1. **Precios de folleto sin tachado:** el filtro previo de RN-003 los deja fuera. Propuesta: las publicaciones de **páginas de campaña** (folleto, Black Friday) pasan a investigarse si son de una categoría prioritaria de la temporada (DEC-153), o si su precio está por debajo del último precio que OIP observó.
2. **Calibración del filtro:** la bocina Milwaukee (33.56%) no pasa y Jesús la habría investigado. ¿40% es demasiado exigente para marcas reconocidas?
3. **Productos voluminosos o pesados:** refrigeradores y lavadoras; definir si se excluyen o se limitan a venta local con flete.
4. **Ventas concretadas de eBay** como evidencia del precio de venta efectivo: hoy eBay no es canal del Inc. 1 (DEC-151); serviría como **dato** de RN-016 y RN-014, de preferencia con captura manual.
5. **Páginas de promociones como fuentes recurrentes:** ya previstas en la arquitectura (URLs de entrada de ofertas y liquidaciones por comercio) y en los perfiles de temporada (DEC-003).
