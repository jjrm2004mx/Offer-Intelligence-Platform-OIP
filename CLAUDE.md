# CLAUDE.md — OIP (repo del Core)

Reglas obligatorias para Claude Code en este repo. Proyecto personal y privado de Jesús. Todo en español.

## 1. Qué manda

| Tema | Fuente |
|---|---|
| Qué y por qué | El requerimiento (issue con etiqueta `Requerimiento`) y las RN de `docs/negocio/reglas/`, en la versión que cita el REQ |
| Cómo | `docs/arquitectura/arquitectura-tecnica.md` (v2.2, ADR-001 a ADR-028) |
| Decisiones | `docs/proceso/registro-de-decisiones.md` (DEC-xxx). Una DEC `REEMPLAZADA` no aplica |
| Proceso | `docs/proceso/flujo-general.md` |
| Avisos e interfaz | `docs/diseno/guia-de-estilo.md` |

En reglas de negocio mandan las RN; en decisiones técnicas, la arquitectura. Si dos fuentes se contradicen, no elijas: repórtalo.

## 2. Reglas que no se negocian

1. **La IP de casa nunca consulta comercios** (DEC-041, DEC-122, DEC-194). Desde este equipo **no consultes** Home Depot, Walmart, Target, Best Buy, GameStop, Nintendo ni Amazon: ni con `curl`, `wget`, `Invoke-WebRequest`, WebFetch, un navegador o un script. Los fixtures son **sintéticos** o vienen de datos guardados en el VPS. `.claude/settings.json` lo refuerza con reglas `deny`, pero esas reglas son una barrera parcial: la regla vale aunque un comando no esté bloqueado.
2. **El Core no tiene spiders** ni clientes HTTP hacia comercios (DEC-173). Todo acceso a comercios vive en el Worker y sale por `oip-egress`. Lo verifica el gate `scripts/check-egress.sh`.
3. **Dinero con `Decimal`** y `ROUND_HALF_UP` a centavos, solo en los montos de la lista cerrada del REQ y una sola vez al final de cada fórmula; porcentajes sin redondear para calcular y comparar, mostrados con 1 decimal (DEC-060, precisada por DEC-207 y DEC-222). Nunca `float` para montos.
4. **Parámetros** del REQ (§6) en la configuración versionada, no fijos en el código.
5. **Secretos** solo como `podman secret`; nunca en el código, los logs, las pruebas ni los commits.
6. **Datos personales:** clientes solo por alias; de particulares solo la publicación (R-20).
7. **Gates humanos (G1 a G5) son de Jesús.** Ningún agente aprueba un PR, hace merge, pone la etiqueta `aprobado-jesus` ni cambia `access_mode` (DEC-195).

## 3. Trazabilidad

- Rama y PR hacia `main` (DEC-071). Nunca commits directos a `main`.
- Cada commit con los trailers `Change: <id>` y `Refs: #N`. Excepción: los commits solo de documentación llevan `Change: docs` y pueden omitir `Refs` (DEC-193).
- Activa el hook una vez por clon: `git config core.hooksPath .githooks`.
- Pruebas por escenario con `@pytest.mark.scenario("B1")`, con el ID del REQ.
- Traza `OIP_TRACE` en el issue del requerimiento, con el formato de cada agente.

## 4. Comandos

En Windows usa **`py -3`**: `python3` abre la Microsoft Store (DEC-196).

| Qué | Comando |
|---|---|
| Entorno | `py -3 -m venv .venv` y `.venv\Scripts\pip install -e ".[dev]"` |
| Calidad | `ruff check .` y `ruff format --check .` |
| Pruebas | `pytest` (cobertura: `pytest --cov=oip`) |
| Egress estático | `bash scripts/check-egress.sh src` |
| OpenSpec | `openspec validate --all --no-interactive` |

## 5. OpenSpec

- Versión fijada: **`@fission-ai/openspec@2.1.0`** (DEC-192). Instalación: `npm i -g @fission-ai/openspec@2.1.0`; comprueba con `openspec --version`.
- OpenSpec 2.1 no trae comandos `/opsx:*`: trae **skills** en `.claude/skills/`. Equivalencias:

| Antes (DEC-072) | Skill |
|---|---|
| `/opsx:propose` | `openspec-propose` |
| `/opsx:apply` | `openspec-apply-change` |
| `/opsx:archive` | `openspec-archive-change` |

- Un subagente sin la herramienta Skill lee `.claude/skills/<skill>/SKILL.md` y sigue sus pasos con el CLI `openspec`.
- `openspec/config.yaml` tiene el contexto y las reglas de OIP para cada artefacto.

## 6. Etiquetas de PR

| Etiqueta | La pone | La quita |
|---|---|---|
| `IMPLEMENTATION READY` | `oip-developer` al dejar el PR listo para pruebas | `oip-tester` al terminar su pasada (DEC-195) |
| `aprobado-jesus` | **Solo Jesús, a mano** (G2, G3, G4) | Jesús |

## 7. Agentes

`oip-revisor-rn` (Etapa 1), `oip-inspector` (Etapa 2), `oip-analista` y `oip-disenador` (propuesta, Etapa 4, DEC-229), `oip-developer` y `oip-tester` (Etapa 4), en `.claude/agents/`. Cada uno trae su revisión previa, su estado final y sus límites.
