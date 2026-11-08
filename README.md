# Offer Intelligence Platform (OIP)

Herramienta interna para detectar oportunidades de reventa: productos que se pueden comprar muy por debajo de su precio real de mercado y revender con margen.

**Proyecto personal y privado.** Todos los derechos reservados. No se concede licencia de uso, copia, modificación ni distribución.

## Estructura (en construcción)

| Carpeta | Contenido |
|---|---|
| `docs/negocio/` | Reglas de negocio en lenguaje llano (publicadas para revisión del experto) |
| `docs/arquitectura/` | Documento de arquitectura técnica |
| `.claude/agents/` | Agentes de desarrollo (Claude Code) |
| `openspec/` | Especificaciones técnicas (OpenSpec) |

## Flujo de trabajo

```
Regla de negocio (RN) → Inspección → Requerimiento (issue) → Análisis → Diseño
→ Tareas → Rama / PR → Código → Pruebas → Documentación
```

Ninguna regla de negocio pasa a desarrollo sin inspección aprobada.
