# Plantilla de Regla de Negocio (RN)

> Cómo usarla: copia este archivo como `reglas/RN-XXX-nombre-corto.md` y llena cada sección **en lenguaje llano**, sin términos técnicos.
> Si algo no aplica, escribe "No aplica" y explica por qué en una línea. No borres secciones.
>
> Cada sección responde a uno de los criterios que revisa `oip-revisor-rn`.
> Una RN bien llenada pasa la revisión de consistencia (`oip-revisor-rn`) a la primera. Las RN no se inspeccionan formalmente: lo que pasa por `oip-inspector` es el **requerimiento** (issue) que las referencia.

---

```yaml
id: RN-XXX
titulo: <nombre corto de la regla>
estado: BORRADOR            # BORRADOR | EN_REVISION | APROBADA | REEMPLAZADA
version: 1
fecha: AAAA-MM-DD
responsable: Jesús
revisor_negocio: <experto en negocios internacionales>
depende_de: []              # otras RN que esta regla necesita
```

## 1. ¿Qué queremos lograr?
<!-- Criterio 1: objetivo claro -->
Una o dos frases. ¿Qué problema resuelve esta regla y por qué importa para el negocio?

## 2. ¿Qué incluye y qué no?
<!-- Criterio 2: alcance delimitado -->
**Incluye:**
- …

**No incluye:**
- …

## 3. ¿Cómo funciona, en palabras?
<!-- Criterio 3: descripción funcional -->
Explica el funcionamiento como se lo contarías a alguien en una plática.

## 4. La regla
<!-- Criterio 4: reglas de negocio identificadas y comprensibles -->
Escribe la regla de forma precisa. Si hay una fórmula, escríbela en palabras **y** con símbolos sencillos.

| Valor | Qué es | Valor inicial | ¿Confirmado? |
|---|---|---|---|
| … | … | … | Por confirmar / Sí |

## 5. ¿Cómo sabremos que funciona? — Ejemplos con números
<!-- Criterios 5 y 14: criterios de aceptación verificables -->
Al menos **un ejemplo que sí cumple** y **uno que no**. Cada ejemplo con números completos, de modo que cualquiera pueda rehacer la cuenta.

**Ejemplo A — …**
- Datos: …
- Cuenta: …
- Resultado esperado: …

**Ejemplo B — …**

## 6. ¿Qué información necesitamos?
<!-- Criterio 6: datos de entrada -->
- … (y de dónde sale: tienda, Amazon, nosotros, el experto)

## 7. ¿Qué obtenemos?
<!-- Criterio 7: salidas -->
- …

## 8. ¿Quién participa?
<!-- Criterio 8: actores -->
- …

## 9. ¿De qué depende?
<!-- Criterio 9: dependencias -->
- Otras RN, fuentes de datos, decisiones pendientes.

## 10. Limitaciones
<!-- Criterio 10: restricciones -->
- …

## 11. ¿Qué pasa si…?
<!-- Criterio 11: casos raros y excepciones -->
| Situación | Qué hace el sistema |
|---|---|
| Falta un dato | … |
| El dato es viejo | … |

## 12. Preguntas para el experto
<!-- Alimenta los criterios 12 y 13: contradicciones y ambigüedades -->
1. …

## 13. Decisiones tomadas
| Fecha | Decisión | Quién |
|---|---|---|
| | | |

## 14. Revisión de consistencia
- Última revisión: <fecha> — <APROBADO / APROBADO CON OBSERVACIONES / RECHAZADO>
- Detalle: `revisiones/RN-XXX.md`
