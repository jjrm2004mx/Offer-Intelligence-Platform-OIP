# RN-009 — Niveles de oportunidad de reventa y avisos

```yaml
id: RN-009
titulo: Niveles de oportunidad de reventa y avisos
grupo: resultado
estado: EN_REVISION
version: 2
fecha: 2026-11-16
responsable: Jesús
revisor_negocio: Experto en negocios internacionales
depende_de: [RN-001, RN-002, RN-003, RN-004, RN-005, RN-006, RN-007, RN-008, RN-013, RN-015, RN-018]
```

> **Qué cambió en la v2 (2026-11-16):** esta regla es el **eje 2, oportunidad de reventa**; el eje 1, calidad del precio, es RN-012 (DEC-131). Los niveles **se renombran** para no chocar con RN-012: **Comprar ya · Muy recomendable · Recomendable · Vigilar**; el más bajo baja a **25% / 25%** para coincidir con RN-003; el mínimo por unidad es **el mayor entre $10 y el 10% del costo de compra**; se evalúa **por canal**; un comercio mucho más barato que Amazon **baja un nivel**; sin certeza o sin datos, **revisión manual**; vendedor externo, revisión manual (DEC-137); **un aviso por cadena**. Propuestas de Claude aceptadas por Jesús, [sesión 2](/sesiones/sesion-2-respuestas.md), bloque 9. La v1 queda en el historial: [RN-009 v1](https://github.com/jjrm2004mx/Offer-Intelligence-Platform-OIP/blob/1c1d4e04d5e5e2401dbb565782bf11061d8813f7/docs/negocio/reglas/RN-009-niveles-y-alertas.md).

## 1. ¿Qué queremos lograr?
Clasificar cada oferta que sobrevivió a los filtros en un **nivel de oportunidad de reventa**, y avisar a Jesús en el momento adecuado: de inmediato las mejores y en resumen las demás. Sin llenarlo de avisos repetidos.

## 2. ¿Qué incluye y qué no?
**Incluye:**
- Qué descarta una oferta y qué la manda a revisión manual.
- Niveles por canal y qué tipo de aviso genera cada uno.
- Cuándo no repetir un aviso.

**No incluye:**
- La calidad del precio para el consumidor (RN-012).
- Elegir el canal (RN-018): esta regla da el nivel de cada canal y RN-018 elige.
- La decisión del viaje a tienda (RN-008).

## 3. ¿Cómo funciona, en palabras?
Primero se revisa si la oferta se descarta o necesita revisión manual. Si no, se calcula su nivel **en cada canal** viable: el **nivel más alto cuyas dos condiciones cumpla** (descuento real mínimo y margen ajustado mínimo), siempre que deje un mínimo por unidad. En Amazon, si otro comercio lo vende bastante más barato, baja un nivel. RN-018 elige el canal y ese nivel decide el aviso.

## 4. La regla

**4.1 Orden de precedencia: DESCARTADA > REVISIÓN MANUAL > nivel**

| Resultado | Cuándo |
|---|---|
| **DESCARTADA** | MERCADO YA BARATO (RN-003); producto que se evita siempre (RN-015); ningún canal viable o margen ajustado negativo en todos |
| **SOLO REFERENCIA** | Descuento real de 20% a menos de 25% (RN-003): solo tablero |
| **REVISIÓN MANUAL** (tablero, sin aviso, con su nivel calculado) | SIN HISTORIAL SUFICIENTE o COINCIDENCIA NO CONFIRMADA (RN-003, RN-013); demanda desconocida en Amazon (RN-004) **cuando ningún otro canal tiene nivel**; **vendedor externo** (DEC-137); riesgo marcado por RN-015 |
| **Nivel** | Todo lo demás |

**4.2 Requisitos del canal** (para que un canal tenga nivel):
- **Amazon:** demanda SUFICIENTE (RN-004) y vendible, con comisión conocida (RN-006).
- **Venta local:** demanda local no baja (RN-017) y precio de venta local estimado (RN-016).
- **Mínimo por unidad:** margen ajustado ≥ **el mayor entre $10 y el 10% del costo de compra** (RN-005).
- **Tienda física:** confianza Alta o Media (RN-007).

**4.3 Niveles** — se asigna el más alto cuyas dos condiciones se cumplan, por canal:

| Nivel | Descuento real (RN-003) | Margen ajustado % (RN-005) | Aviso |
|---|---|---|---|
| **Comprar ya** | ≥ 80% | ≥ 50% | Inmediato |
| **Muy recomendable** | ≥ 70% | ≥ 40% | Inmediato |
| **Recomendable** | ≥ 50% | ≥ 30% | Resumen 2 veces al día |
| **Vigilar** | ≥ 25% | ≥ 25% | Solo en el tablero |

- **Competencia más barata** (RN-002): en el canal **Amazon** la oportunidad **baja un nivel** (Vigilar baja a "sin nivel").
- **Tienda lejana** (RN-008): solo se avisa si el viaje deja $150 o más; si no, solo tablero.
- **Orden:** dentro de cada nivel, por **rendimiento mensual** (RN-005), de mayor a menor.

**4.4 Avisos**
- **Un solo aviso por cadena:** si la misma oferta está en varias sucursales de un comercio, un aviso con las sucursales ordenadas por cercanía a la garita (Zona 1 primero) y su confianza.
- **No repetir** la misma oferta en **24 horas**, salvo que suba de nivel o su precio baje **5% o más**.

| Valor | Qué es | Valor inicial | ¿Confirmado? |
|---|---|---|---|
| Mínimo por unidad | El mayor entre | $10 y 10% del costo de compra | Aceptado por Jesús |
| Umbrales por nivel | Ver tabla | Ver tabla | Aceptado por Jesús; Vigilar bajó a 25% / 25% |
| Nombres de niveles | Para no chocar con RN-012 | Comprar ya · Muy recomendable · Recomendable · Vigilar | Aceptado por Jesús |
| Horarios del resumen | 2 veces al día | 8:00 y 18:00 (Tijuana) | Jesús |
| Ventana sin repetir | Horas | 24 h | Jesús |
| Baja de precio para repetir | % | 5% | Jesús |

Todos los valores son iniciales y configurables.

## 5. ¿Cómo sabremos que funciona? — Ejemplos con números

**Ejemplo A — Sierra circular en Amazon → Muy recomendable (aviso inmediato)**
- Descuento real 75.6%; margen ajustado 143.1% ($44.73 por unidad); demanda suficiente; vendible; confianza Alta; sin competencia más barata.
- Mínimo por unidad: mayor(10, 10% × 31.25 = 3.13) = $10 ✓.
- Comprar ya exige ≥ 80% ✗. Muy recomendable: 75.6% ≥ 70% ✓ y 143.1% ≥ 40% ✓ → **Muy recomendable**.

**Ejemplo B — Taladro → Vigilar en venta local**
- Amazon: 47.0% y 20.3% → Vigilar exige margen ≥ 25% ✗ → **sin nivel en Amazon**.
- Venta local: 47.0% y 25.2% ($21.48); mínimo mayor(10, 8.51) = $10 ✓ → **Vigilar** → RN-018 elige venta local → solo tablero.

**Ejemplo C — Lámpara → descartada**
- MERCADO YA BARATO (RN-003) → **DESCARTADA**.

**Ejemplo D — Descuento alto, margen moderado**
- 82% y 35%, $22 por unidad. Comprar ya: 35% < 50% ✗. Muy recomendable: 35% < 40% ✗. Recomendable: ✓ y ✓ → **Recomendable** → resumen.

**Ejemplo E — No repetir**
- La sierra se avisó a las 10:00. A las 14:00 sigue igual → no se avisa. A las 16:00 baja de $29 a $27 (6.9%) → **se vuelve a avisar**.

**Ejemplo F — Competencia más barata**
- La misma sierra, pero Target la vende hoy a $99 (RN-002, ejemplo B) → en Amazon baja de Muy recomendable a **Recomendable** → resumen.

**Ejemplo G — Mínimo por unidad proporcional**
- Costo de compra $520, margen ajustado $40 → mínimo mayor(10, 52) = **$52** → $40 no alcanza → **sin nivel**.

**Ejemplo H — Vendedor externo**
- Oferta con números de Muy recomendable, pero vendida por un vendedor externo → **REVISIÓN MANUAL**, marcada "vendedor externo", sin aviso.

## 6. ¿Qué información necesitamos?
- Resultados de RN-001 a RN-008, RN-013, RN-015 y RN-018.

## 7. ¿Qué obtenemos?
- Resultado (descartada, solo referencia, revisión manual o nivel), nivel por canal, aviso y lugar en el tablero.

## 8. ¿Quién participa?
- El sistema clasifica y avisa.
- Jesús recibe los avisos, revisa los casos manuales y decide.
- El experto valida los umbrales.

## 9. ¿De qué depende?
- De todas las reglas anteriores y de RN-018 (canal elegido).

## 10. Limitaciones
- Los umbrales son iniciales; se ajustan con los resultados reales de compra y venta.

## 11. ¿Qué pasa si…?
| Situación | Qué hace el sistema |
|---|---|
| Falla el envío del aviso | Reintenta; si sigue fallando, queda visible en el tablero |
| La oportunidad desaparece (se agotó o subió el precio) | Se marca "ya no disponible" en el tablero; no se avisa |
| Más de 10 avisos inmediatos en una hora | Se agrupan en un solo aviso |
| Ningún canal tiene nivel | Queda registrada como evaluada, sin nivel |

## 12. Preguntas para el experto
1. ¿Le parecen bien los nuevos nombres y que "Vigilar" empiece en 25% / 25%? (propuesta aceptada por Jesús)
2. ¿El mínimo por unidad como el mayor entre $10 y el 10% del costo? (propuesta aceptada por Jesús)

## 13. Decisiones tomadas
| Fecha | Decisión | Quién |
|---|---|---|
| 2026-11-08 | Los avisos llegan por mensaje al celular (Telegram) y además se ven en un tablero | Jesús |
| 2026-11-11 | Dos ejes: calidad del precio (RN-012) y oportunidad de reventa (esta regla) (DEC-131) | Jesús |
| 2026-11-11 | Vendedor externo → revisión manual (DEC-137) | Jesús |
| 2026-11-16 | Niveles renombrados; Vigilar desde 25% / 25% | Jesús (propuesta de Claude) |
| 2026-11-16 | Mínimo por unidad: mayor entre $10 y 10% del costo de compra | Jesús (propuesta de Claude) |
| 2026-11-16 | Sin certeza o sin datos → revisión manual sin aviso | Jesús (propuesta de Claude) |
| 2026-11-16 | Un aviso por cadena, sucursales por cercanía a la garita | Jesús (propuesta de Claude) |
| 2026-11-16 | Competencia mucho más barata que Amazon baja un nivel | Experto (umbral propuesto en RN-002) |

## 14. Revisión de consistencia
- Última revisión: 2026-11-16 (v2) — APROBADO CON OBSERVACIONES
- Detalle: [revisiones/RN-009.md](/revisiones/RN-009.md)
