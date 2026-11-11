# Offer Intelligence Platform (OIP)

Herramienta para buscar productos en distintos comercios, con **dos funcionalidades** que comparten el mismo motor de búsqueda:

- **A. Búsqueda automatizada de ofertas:** detecta productos que se pueden comprar muy por debajo de su precio real de mercado y revender con margen.
- **B. Búsqueda particular por artículo:** servicio a clientes. Encuentra dónde está más económico y disponible un producto que pide un cliente.

**Proyecto personal y privado.** Todos los derechos reservados. No se concede licencia de uso, copia, modificación ni distribución.

## Estructura (en construcción)

| Carpeta | Contenido |
|---|---|
| `docs/negocio/` | Reglas de negocio en lenguaje llano (publicadas para revisión del experto): `reglas/` RN-001 a RN-011, `revisiones/` revisión de consistencia de cada RN y preguntas consolidadas, `casos/` casos reales que sirven como escenarios de prueba (CASO-001), `glosario.md`, `plantilla-rn.md`. Sitio: https://oip-negocio.vercel.app |
| `docs/arquitectura/` | Documento de arquitectura técnica: `arquitectura-tecnica.md` (vigente, v1.3). Las versiones anteriores están enlazadas al inicio del documento |
| `docs/proceso/` | Cómo se trabaja: `flujo-general.md`, `flujo-negocio-a-requerimiento.md` y `registro-de-decisiones.md` (todas las decisiones tomadas, DEC-xxx) |
| `.claude/agents/` | Agentes de desarrollo (Claude Code): `oip-revisor-rn` (consistencia de RN) y `oip-inspector` (inspección formal de requerimientos). El resto se agrega en el arranque técnico |
| `.github/ISSUE_TEMPLATE/` | Plantilla del issue **Requerimiento** (13 secciones, una por criterio de inspección) |
| `openspec/` | Especificaciones técnicas (OpenSpec). **Pendiente:** se crea en el arranque técnico (Etapa 3) |

## Issues

Los **requerimientos formales y sus inspecciones** viven como issues de GitHub, no como archivos. Cada uno se versiona editando el mismo issue (v1, v2…), y no se crean duplicados.

| Issue | Tipo | Contenido | Estado |
|---|---|---|---|
| [#2](https://github.com/jjrm2004mx/Offer-Intelligence-Platform-OIP/issues/2) | `Requerimiento` · milestone "Incremento 1" | **REQ-2026-0001**: requerimiento formal. Hoy cubre la **evaluación de ofertas** (motor de oportunidad): alcance, flujo, catálogo de resultados y precedencia, 22 criterios de aceptación con números, datos de entrada, errores y supuestos. Referencia RN-001 a RN-006 y RN-009 | Abierto · **v2** (correcciones de autor), sin reinspeccionar. **Pendiente:** reestructurarlo como requerimiento único con partes A (descubrimiento), B (evaluación), C (avisos y tablero) y D (búsqueda por artículo) |
| [#3](https://github.com/jjrm2004mx/Offer-Intelligence-Platform-OIP/issues/3) | `Inspeccion` · milestone "Incremento 1" | **Inspección formal de REQ-2026-0001** (agente `oip-inspector`): dictamen, 14 criterios, verificación de escenarios, defectos con historial por versión, preguntas y riesgos | Abierto · inspección **v1: RECHAZADO** (1 ALTA, 11 MEDIA, 7 BAJA). La v2 se hará después de la reestructuración y de tu visto bueno |

**Etiquetas:** `Requerimiento`, `Inspeccion`, `Regla de negocio`. **Milestone:** "Incremento 1".

## Flujo de trabajo

```
Regla de negocio (RN) → Revisión de consistencia → Experto → Requerimiento (issue)
→ Visto bueno de Jesús → Inspección formal → Análisis → Diseño → Tareas
→ Rama / PR → Código → Pruebas → Documentación
```

Ningún requerimiento pasa a desarrollo sin inspección aprobada. Detalle en `docs/proceso/flujo-general.md`.
