# MOP — LexObra 360

Backend del motor de gestión y auditoría legal para contratos de Obras Públicas
(MOP, Dirección de Vialidad). Implementa un **Gemelo Digital Legal** del contrato,
que recorre cinco fases desde la toma de razón hasta el cierre del expediente,
conforme al DS 75/2004 MOP (RCOP) y a la normativa laboral, penal y ambiental que
se cruza con él.

## Arquitectura

```
Motor determinista (reglas)  ──►  alertas, bloqueos, plazos, borradores
          │
          └── estado del contrato ──►  Consultor IA (Claude)  ──►  análisis y redacción
```

- **Las alertas y los bloqueos los calcula un motor de reglas determinista**, no el
  modelo de lenguaje. Un plazo fatal o un tope legal no puede depender de una
  respuesta probabilística. Cada alerta sale en el formato obligatorio: riesgo
  (Bajo/Medio/Alto), artículo del RCOP, ley especial cruzada y plan de acción
  inmediato (borrador de carta, asiento en el Libro de Obras, bloqueo o carga de un
  documento).
- **La capa de IA** (`lexobra/ia`) recibe el estado del motor y el prompt maestro.
  Su trabajo es redactar y explicar, sin recalcular nada. Usa `claude-opus-5-5`
  con salida JSON estructurada y fallback ante rechazos del lado del servidor
  (`fallbacks: "default"`).
- **Bóveda**: sella el expediente con un árbol de Merkle SHA-256. Ese sello prueba
  la integridad del expediente, pero no reemplaza la firma electrónica avanzada
  (Ley 19.799). Para que el sello sea plenamente oponible, la raíz debe firmarse
  o sellarse en el tiempo con un prestador acreditado.

| Módulo | Contenido |
|---|---|
| `lexobra/normativa.py` | Catálogo de normas con su estado de verificación y parámetros legales configurables por contrato |
| `lexobra/modelos.py` | Modelo del Gemelo Digital (hitos, subcontratos, estados de pago, modificaciones, garantías…) |
| `lexobra/calendario.py` | Días hábiles (Ley 19.880 Art. 25), días corridos y meses |
| `lexobra/calculos.py` | Valor vigente, retenciones, subcontratación, vigencia mínima del canje |
| `lexobra/reglas/fase1..5.py` | Reglas de cruce normativo por fase |
| `lexobra/motor.py` | Fase actual, evaluación y operaciones con bloqueo preventivo |
| `lexobra/borradores.py` | Cartas y asientos del Libro de Obras |
| `lexobra/boveda.py` | Sellado y verificación del expediente |
| `lexobra/ia/` | Prompt maestro y consultor sobre Claude |
| `lexobra/api.py` | API REST (FastAPI) |

## Puesta en marcha

```bash
pip install -r requirements-dev.txt
pytest
export ANTHROPIC_API_KEY=...        # sólo para /consultas
uvicorn lexobra.api:app --reload    # documentación interactiva en /docs
```

Todos los endpoints de evaluación aceptan `?hoy=AAAA-MM-DD` para simular escenarios.
El repositorio actual guarda los datos en memoria y debe reemplazarse por uno
persistente antes de pasar a producción.

## Estado de verificación normativa

Cada referencia del catálogo (`GET /normativa`) declara uno de tres estados:
`verificado`, `pendiente_verificacion` o `discrepante`. Antes de pasar a
producción, la gerencia legal debe cotejar todas las referencias con el texto
consolidado del DS 75 en LeyChile.

Al contrastar el diseño funcional con los extractos de LeyChile aparecieron estas
diferencias:

| Materia | Diseño funcional | Fuente consultada | Implementación |
|---|---|---|---|
| Tope de subcontratación | 50% (DS 156/2023) | Art. 101: 30% del valor total, salvo excepción fundada del Director | 30% por defecto, configurable por contrato |
| Tope de modificaciones | 35%, o hasta 50% con fundamentación especial (Art. 106) | Art. 106: 35% conjunto, neto de disminuciones y reajustado; al alcanzarlo se liquida el contrato | Bloqueo al 35%. El tramo de 50% no se implementó |
| Retenciones | 10% hasta el 5% | Art. 158: 10% hasta el 5% del contrato con sus aumentos; las Bases pueden fijar más | Implementado. El tope crece con los aumentos |
| Devolución de garantías | — | El Decreto 150/2026 la vincula a la resolución de liquidación totalmente tramitada | Considerado en la Fase 5 |

Los plazos que siguen están **parametrizados** porque aún no se han verificado o
dependen de las Bases: protocolización (15 días), entrega de la garantía de fiel
cumplimiento (15), entrega de terreno (15), designación e informe de la comisión
(20 + 20 días hábiles), plazo de garantía de la obra (12 meses) y propuesta de
liquidación (30 días).
