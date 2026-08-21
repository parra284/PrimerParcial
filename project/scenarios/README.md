# Scenarios

Instancia de la misión que recibe el agente y el frontend.

El archivo de trabajo es `scenario.json`. Es la **fuente de verdad** de esta
demo; el profesor puede enviar otro JSON con las mismas reglas.

## Contenido del demo

- 5 zonas: CONTROL, STORAGE, WORKSHOP, GENERATOR_BAY, COMMAND_DECK
- 3 puertas corredizas (cyan / yellow / magenta) + llaves del mismo color
- 3 herramientas (MULTITOOL, SOLDERING, WIRE_CUTTER) + materiales (FUSE, CHIP, CABLE)
- 3 paneles dañados y 3 estaciones (GENERATOR, COMMAND, ARTILLERY)
- 1 cargador en WORKSHOP
- **Capacidad de carga 3** (es intencional: obliga a `DROP` reales)
- Batería inicial 55 (el plan artesanal recarga porque cuesta 99; un plan
  mejor podría o no recargar, según su costo)
- Grafo con costos distintos y rutas alternativas (apto para UCS)

## Cómo leer este mapa

Cinco zonas no quieren decir «cinco estados». Cada objeto que el robot puede
soltar tiene una posición, y `DROP` en cualquier casilla combina esas
posiciones. El plan de `demo_plan.py` usa varios `DROP` precisamente porque la
capacidad es 3: hay que hacer hueco. Si su UCS no termina, no suba la
capacidad ni borre objetos: formule mejor `Applicable` (ver enunciado §2.2 y
`design.md`).

El `meta.description` dice *Resolvable by UCS*. Lo es, con un generador de
sucesores que no trate cada `DROP` legal como una decisión distinta.

## Instancia mínima para probar la API

`ejemplo_minimo.json` es una versión reducida de `scenario.json` con la misma
estructura (dos zonas, una puerta con llave, un panel que exige herramienta +
material, una estación objetivo). Responde en menos de un segundo y sirve para
verificar `POST /api/solve` sin esperar la misión completa. Plan óptimo: 8
operaciones, costo 14. Ver [`../README.md`](../README.md).

## Instancias del Entregable 3 (validación)

Cada archivo aísla una propiedad y la explica en su propio `meta.description`.
Son instancias **para el motor**: no traen la sección `layout`, así que no se
visualizan en el frontend. Se ejecutan desde `project/backend/tests/`.

| Archivo | Caso | Qué aísla |
|---|---|---|
| `caso2_bateria_relevante.json` | 2 | La misma configuración física alcanzada con dos baterías distintas (directo vs. pasando por el cargador); solo la recargada puede cruzar el corredor de 30. |
| `caso3_costo_vs_pasos.json` | 3 | Atajo de 2 acciones y costo 22 contra rodeo de 4 acciones y costo 5. |
| `caso4_dependencia_circular.json` | 4 | Dependencia mutua entre dos estaciones: insoluble, pero con un espacio de estados real que la búsqueda debe agotar. |
| `caso4_bateria_insuficiente.json` | 4 | `Applicable(s₀)` vacío: FAILURE inmediato. |
| `caso5_rutas_alternativas.json` | 5 | Dos rutas del mismo largo al mismo estado del mundo, con costos 10 y 16. |

El **Caso 1** (estados equivalentes) usa `scenario.json` sin variante: ya trae
llaves que mueren al abrirse su puerta, dos unidades de `FUSE` intercambiables y
acciones conmutativas.
