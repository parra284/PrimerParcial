# Diseño del agente

Este documento define la estructura formal del espacio de estados y el modelo de acciones para el agente de búsqueda clásica (AIMA, cap. 3).

El entorno es **totalmente observable, determinista, secuencial, estático, discreto y de agente único**. Bajo estas propiedades, la solución corresponde a un **plan completo** obtenido mediante algoritmos de búsqueda gráfica.

---

## Estado

### Definición formal

s = ⟨ pos, b, P, R, E, O ⟩

- **pos**: Posición actual del robot.
  pos ∈ {Z_1, Z_2, ..., Z_n}
- **b**: Nivel de batería actual del robot.
  b ∈ [0, 100]
- **P**: Estado de las puertas (tupla de tamaño m).
  P_i ∈ {0, 1} (0: cerrada, 1: abierta)
- **R**: Estado de los paneles de reparación (tupla de tamaño k).
  R_i ∈ {0, 1} (0: pendiente, 1: reparado)
- **E**: Estado de las estaciones (tupla de tamaño e).
  E_j ∈ {0, 1} (0: OFFLINE, 1: ONLINE)
- **O**: Ubicación de cada objeto i (tupla de tamaño N).
  O_i ∈ {Z_1, Z_2, ..., Z_n, EN_INVENTARIO, USADO}

---

### Por qué cada variable es necesaria

- **pos**: Determina las acciones de movimiento disponibles (conexiones del mapa) y la interacción con elementos presentes en la zona actual.
- **b**: Condiciona la viabilidad de ejecutar acciones futuras y determina la necesidad de desplazarse a una estación de carga.
- **P**: Modifica de forma permanente la conectividad del grafo de movimiento entre zonas.
- **R**: Rastrea la reparación de paneles intermedios necesarios para desbloquear dependencias de las estaciones.
- **E**: Representa el progreso real hacia el objetivo final del problema (activación de estaciones de mando, artillería, generadores, etc.).
- **O**: Rastrea de forma unificada la localización de cualquier objeto móvil (llaves, herramientas reutilizables y materiales consumibles) sin sobrecargar la representación del estado.

---

### Qué información se deriva y NO se almacena

#### Información fija (estática)
- Capacidad máxima de batería (100).
- Capacidad máxima del inventario (3 objetos).
- Ubicación espacial de puertas, paneles, estaciones y estaciones de carga.
- Grafo de adyacencia de corredores entre zonas.
- **Mapeo estático de requisitos y tipos:**
  - Tablas/Diccionarios estáticos que asocian cada puerta $P_i$ o panel $R_i$ con sus objetos requeridos ($Obj_i$).
  - **Grafo de dependencias de estaciones:** Mapeo estático que define qué paneles ($R$) y qué otras estaciones ($E$) deben estar activas ($== 1$) para poder activar una estación $E_j$.
  - Clasificación fija de cada objeto según su tipo: `LLAVE`, `HERRAMIENTA` (reutilizable) o `MATERIAL` (consumible).

#### Información derivada (no almacenada en el estado)
- **Contenido del inventario**: Conjunto de objetos $i$ tales que $O[i] == EN\_INVENTARIO$.
- **Espacio disponible en inventario**: $Capacidad\_Maxima - |\{i \mid O[i] == EN\_INVENTARIO\}|$.
- **Costo de las acciones**: Determinado por el tipo de acción y la distancia entre zonas.

---

### Qué pertenece al historial de búsqueda y no al estado físico

Variables exclusivas de los nodos del árbol/grafo de búsqueda que **NO** forman parte del estado del mundo s:

- **Costo acumulado g(n)**: Consumo total de batería consumida desde el estado inicial.
- **Nodo padre**: Referencia al nodo antecesor para la reconstrucción del camino solución.
- **Acción**: La acción ejecutada para transicionar desde el nodo padre hasta el nodo actual.

---

### Cuándo dos configuraciones son el mismo estado

Para asegurar el correcto funcionamiento de **Graph Search** y evitar la exploración de estados duplicados, los componentes del estado utilizan estructuras canónicas e inmutables (tuplas).

Dos estados s1 y s2 son **idénticos** (s1 == s2) si y solo si:

pos1 = pos2 Y b1 = b2 Y P1 = P2 Y R1 = R2 Y E1 = E2 Y O1 = O2

---

### Relevancia: objetos que ya no cambian a futuro

1. **Prohibición de recogida obsoleta**: Se descarta la acción `PICKUP(Obj)` si las puertas o paneles asociados a `Obj` ya fueron resueltos ($P_i == 1$ o $R_i == 1$), evitando explorar ramas inútiles.
2. **Liberación de materiales consumibles**: Al usar un `MATERIAL` consumible en un `REPAIR`, su posición en $O$ cambia a `USADO`, liberando automáticamente el espacio en el inventario. Las `HERRAMIENTAS` reutilizables permanecen en `EN_INVENTARIO`.
3. **Poda por dominancia de batería**: Si dos nodos poseen la misma configuración $(pos, P, R, E, O)$, el nodo con menor nivel de batería $b$ está estrictamente dominado y se descarta de la búsqueda.

---

## Acciones

### Condición global de ejecución
Toda acción $a$ exige que la batería actual sea suficiente para cubrir su costo:
$b \ge Costo(a)$

---

### Tabla de Acciones

| Acción | Precondiciones | Efectos en el estado sucesor (s') | Costo |
| :--- | :--- | :--- | :--- |
| **MOVE(Z)** | - Z es adyacente a pos.<br>- Si la conexión requiere la puerta P_i, entonces P_i == 1.<br>- b >= Costo_Movimiento | - pos' = Z<br>- b' = b - Costo_Movimiento | Según distancia o corredor |
| **PICKUP(Obj)** | - O[Obj] == pos<br>- Espacio disponible en inventario > 0<br>- La puerta o panel asociado a Obj está pendiente (0)<br>- b >= Costo | - O'[Obj] = EN_INVENTARIO<br>- b' = b - Costo | 1 |
| **DROP(Obj)** | - O[Obj] == EN_INVENTARIO<br>- b >= Costo | - O'[Obj] = pos<br>- b' = b - Costo | 1 |
| **OPEN_DOOR(P_i, Llave)** | - pos es adyacente a P_i<br>- P_i == 0<br>- O[Llave] == EN_INVENTARIO<br>- b >= Costo | - P'_i = 1<br>- b' = b - Costo | 2 |
| **REPAIR(R_i, Obj)** | - pos es la zona del panel R_i<br>- R_i == 0<br>- O[Obj] == EN_INVENTARIO<br>- b >= Costo | - R'_i = 1<br>- Si Obj es MATERIAL (consumible): O'[Obj] = USADO<br>*(Si es HERRAMIENTA se mantiene EN_INVENTARIO)*<br>- b' = b - Costo | 2 |
| **ACTIVATE(E_j)** | - pos es la zona de la estación E_j<br>- E_j == 0 (OFFLINE)<br>- Todos los paneles requeridos tienen R_k == 1<br>- Todas las estaciones requeridas tienen E_k == 1<br>- b >= Costo | - E'_j = 1 (ONLINE)<br>- b' = b - Costo | 2 |
| **RECHARGE()** | - pos es una Estación de Carga<br>- b < 97<br>- b >= Costo | - b' = 100 - Costo<br>- b' = 97 | 3 |

---

### Reglas de Poda en la Generación de Sucesores

Para reducir el factor de ramificación sin duplicar el trabajo del control de estados visitados (`CLOSED`) ni de la dominancia de batería, se aplican únicamente las siguientes restricciones en la función de transición:

1. **Poda de Objetos Obsoletos (`PICKUP`)**:
   - No se genera la acción `PICKUP(Obj)` si las puertas o paneles asociados a `Obj` ya fueron resueltos ($P_i == 1$ y $R_i == 1$).

2. **Poda de `DROP` por Ineficiencia**:
   - La acción `DROP(Obj)` solo se genera cuando el inventario está lleno y la zona actual contiene un objeto relevante que requiere ser recogido.

3. **Poda de Recarga Ineficiente**:
   - No se genera `RECHARGE()` si el nivel de batería actual es $b \ge 97$.

---

## Modelo de transición

s --a--> s' solo si a ∈ Applicable(s)

El modelo de transición define el comportamiento del entorno mediante la función de estado sucesor $Result(s, a) = s'$. La función es **determinista y parcial**: produce exactamente un estado sucesor único para cada par estado-acción válido, y no está definida cuando $a \notin Applicable(s)$.

---

### Función de Acciones Aplicables $Applicable(s)$

Un operador $a$ pertenece a $Applicable(s)$ si y solo si cumple simultáneamente con:
1. Sus **precondiciones lógicas** sobre el estado dinámico $s$ (especificadas en la Tabla de Acciones).
2. La **condición de batería mínima**: $b \ge Costo(a)$.
3. Las **reglas de poda en la generación de sucesores** (evitando generar acciones ineficientes como recargas con $b \ge 97$, recogida de objetos obsoletos o soltar objetos sin necesidad de espacio).

---

### Cambios y Preservación en $Result(s, a)$

Al ejecutar una acción aplicable $a$ sobre el estado $s = \langle pos, b, P, R, E, O \rangle$, se genera un estado sucesor $s' = \langle pos', b', P', R', E', O' \rangle$ bajo la siguiente lógica de conservación:

#### Variables que pueden cambiar:
- **Posición ($pos'$):** Modificada únicamente por la acción `MOVE(Z)` a la nueva zona $Z$. En cualquier otra acción, $pos' = pos$.
- **Nivel de batería ($b'$):** Se decrementa por el costo exacto de la acción ($b' = b - Costo(a)$). En el caso de `RECHARGE()`, se establece en 100.
- **Entorno persistente ($P'$, $R'$ y $E'$):** 
  - `OPEN_DOOR(P_i)` actualiza $P'_i = 1$.
  - `REPAIR(R_i)` actualiza $R'_i = 1$.
  - `ACTIVATE_STATION(E_j)` actualiza $E'_j = 1$.
- **Ubicación de objetos ($O'$):**
  - `PICKUP(Obj)` asigna $O'[Obj] = EN\_INVENTARIO$.
  - `DROP(Obj)` asigna $O'[Obj] = pos$.
  - `REPAIR` asigna $O'[Obj] = USADO$ únicamente si el objeto es de tipo consumible.

#### Variables que se preservan (Frame Problem):
Toda variable $v \in \{pos, b, P, R, E, O\}$ que no sea explícitamente modificada por la acción $a$ mantiene exactamente su valor anterior en el estado sucesor ($v' = v$).

---

### Canonicalización del Estado Sucesor

Para garantizar que $s'$ sea directamente utilizable por **Graph Search** y compatible con las operaciones de tabla Hash / `CLOSED`:

1. **Estructuras inmutables:** $P'$, $R'$, $E'$ y $O'$ se construyen de forma estricta como **tuplas ordenadas**.
2. **Representación compacta de $O'$:** Los objetos marcados como `USADO` mantienen su identificador en la tupla $O'$ con dicho valor constante, liberando implícitamente la capacidad en el cálculo de la variable derivada *Espacio disponible en inventario*.
3. **Invariante de Batería:** El valor de $b'$ se acota siempre en el rango discreto entero $[0, 100]$.
## Prueba de meta

Goal(s) ⟺ ∀ j ∈ Estaciones_Objetivo, E_j == 1

La función `IsGoal(s)` es un predicado booleano que evalúa si el estado dinámico $s = \langle pos, b, P, R, E, O \rangle$ satisface la condición final de la misión.

---

### Distinción entre Objetivos y Medios

1. **Objetivos finales (Fines):** Representados exclusivamente por el vector de estaciones $E$. La misión se considera completada si y solo si todas las estaciones especificadas como objetivo en la instancia actual están en estado activo ($E_j == 1$, ONLINE).
2. **Prerrequisitos del entorno (Medios):** La apertura de puertas ($P_i == 1$) y la reparación de paneles ($R_k == 1$) son únicamente **condiciones intermedias o medios habilitadores** necesarios para acceder a las zonas o cumplir los requisitos de activación de las estaciones. Por lo tanto, no se exige que todas las puertas estén abiertas ni que todos los paneles estén reparados para alcanzar la meta, salvo aquellos estrictamente requeridos para activar las estaciones objetivo.

---

### Propiedades del Test de Meta

- **Evaluación sobre el Estado Físico:** Se verifica directamente sobre el estado del mundo $s$ en el nodo evaluado, de forma independiente al historial de acciones o al costo acumulado $g(n)$.
- **Independencia de Posición e Inventario:** No se imponen restricciones sobre la ubicación final del robot ($pos$), el nivel de batería restante ($b$) ni los objetos que permanezcan en el inventario ($O$), optimizando el camino hacia el primer estado válido de meta.

---

## Función de costo

g(n) = ∑_{i=1}^{k} Costo(a_i)

La función de costo acumulado $g(n)$ representa el **consumo total de batería invertido** desde el estado inicial $s_0$ hasta alcanzar el estado actual en el nodo $n$, sumando el costo individual de cada una de las $k$ acciones ejecutadas en el camino.

---

### Definición formal del costo por acción $Costo(a)$

El costo de cada acción se mide estrictamente en unidades de energía (batería):

- **MOVE(Z):** Variable, equivalente a $Distancia(pos, Z)$ o a la dificultad del corredor entre zonas.
- **PICKUP(Obj) / DROP(Obj):** Costo fijo de $1$ unidad.
- **OPEN_DOOR(P_i, Llave) / REPAIR(R_i, Obj) / ACTIVATE_STATION(E_j):** Costo fijo de $2$ unidades.
- **RECHARGE():** Costo fijo de $3$ unidades.

---

### Por qué minimizar pasos ≠ minimizar costo

1. **Heterogeneidad de los Corredores de Movimiento:**
   El espacio de navegación no es un retículo uniforme. Moverse entre zonas adyacentes implica costos de batería variables según la distancia física o la topología del terreno (p. ej., un corredor  puede costar $1$ unidad de batería, mientras que otro puede costar $5$ unidades).

2. **Acciones no de navegación con costos diferenciados:**
   Las acciones operativas consumen distintas cantidades de batería independientemente del desplazamiento. Por ejemplo, la acción `PICKUP` cuesta $1$ unidad, mientras que `OPEN_DOOR` cuesta $2$ unidades y `RECHARGE` cuesta $3$.

4. **Garantía de Optimidad Energética:**
   Al utilizar el costo real de batería en $g(n)$, algoritmos como **Uniform Cost Search (Dijkstra)** garantizan encontrar la secuencia de acciones que minimiza el desgaste total del robot, permitiendo completar la misión dentro de las restricciones de la batería.

---

## Estrategia de búsqueda

Para resolver el problema planteado se selecciona la estrategia **Uniform Cost Search (UCS)** o **Algoritmo de Dijkstra** en su variante de **Graph Search**.

Esta elección se justifica directamente por la presencia de **costos heterogéneos** en el entorno (diferentes costos en corredores de movimiento y acciones con consumos variables de batería) y la necesidad imperativa de encontrar el plan que **minimice el costo total consumido ($g(n)$)** en lugar del número de pasos.

---

### Análisis de Propiedades Formales

- **Completitud:**
  Es **completo**. Dado que todos los costos de las acciones están estrictamente acotados por abajo por una constante positiva $\epsilon > 0$ (el costo mínimo de una acción es $1$), el número de estados con costo $g(n) \le C^*$ es finito, lo que impide que la búsqueda caiga en bucles infinitos de costo cero.

- **Optimalidad y Test de Meta:**
  Es **óptimo**. La prueba de meta **se realiza estrictamente al extraer el nodo de la cola de prioridad `OPEN`**, NO al generarlo. Probar la meta al generar el nodo invalidaría la garantía de optimidad, ya que el primer camino generado hacia un estado de meta no es necesariamente el de menor costo acumulado $g(n)$.

- **Costo de Camino:**
  El costo asignado a cada nodo es $g(n) = \sum C(a_i)$, correspondiente al consumo total de batería desde el estado inicial. `OPEN` se implementa como una cola de prioridad ordenada de menor a mayor valor de $g(n)$.

- **Complejidad en Tiempo y Espacio:**
  - **Factor de ramificación efectivo ($b^*$):** El factor de ramificación peligroso no está dado por las conexiones del mapa físico, sino por la combinación de acciones operativas en la zona actual (`PICKUP`, `DROP`, `OPEN_DOOR`, `REPAIR`, `ACTIVATE_STATION`). En zonas con múltiples objetos en inventario y en el suelo, las combinaciones de `DROP` y `PICKUP` elevan significativamente $b^*$.
  - **Complejidad Temporal y Espacial:** $O(b^{1 + \lfloor C^* / \epsilon \rfloor})$, donde $C^*$ es el costo de la solución óptima y $\epsilon$ es el costo de acción más pequeño. Ambas complejidades son exponenciales debido al almacenamiento en memoria de las listas `OPEN` y `CLOSED`.

---

### Ruptura de Garantías Formales

Las garantías de completitud y optimidad de UCS se rompen ante cualquiera de los siguientes escenarios:

1. **Costos 0 o Negativos:** Si existiera una acción con costo $\le 0$, el algoritmo podría entrar en bucles de costo nulo o negativo, invalidando la propiedad de orden decreciente en la exploración de $g(n)$.
2. **Estados Mal Canonicalizados:** Si dos representaciones lógicas distintas corresponden a la misma situación física (p. ej., inventario desordenado como `[ObjA, ObjB]` vs `[ObjB, ObjA]`), el algoritmo las tratará como estados diferentes, provocando reexploración redundante e incrementando el costo en espacio.
3. **Lista `OPEN` que no se Vacía (Explosión Combinatoria):** Ocurre cuando las reglas de poda son insuficientes y se generan combinaciones infinitas de acciones inútiles (como intercalar `DROP` y `PICKUP` sin avanzar en la misión), consumiendo la memoria del sistema antes de alcanzar la meta.

---

### Control de Reexploración con Graph Search y Lista `CLOSED`

Para evitar la reexploración de estados previamente visitados, el algoritmo mantiene un conjunto `CLOSED` estructurado como una **Tabla Hash** de estados canónicos $s = \langle pos, b, P, R, E, O \rangle$.

1. **Mecanismo de Evaluación:**
   Al extraer un nodo $n$ con estado $s$ de `OPEN`:
   - Si $s \in CLOSED$, el nodo se descarta inmediatamente por existir un camino previamente procesado con costo acumulado menor o igual.
   - Si $s \notin CLOSED$, se añade $s$ a `CLOSED` y se expanden sus sucesores.

2. **Garantía de No Reexploración:**
   Debido a que UCS expande los nodos en orden monótonamente creciente de $g(n)$, la primera vez que un estado $s$ es extraído de `OPEN`, se garantiza que se ha encontrado el **camino óptimo (de menor costo)** para llegar a esa configuración física particular. Insertarlo en `CLOSED` evita procesar rutas redundantes o menos eficientes que conduzcan al mismo estado del mundo.

### Batería como recurso y Regla de Dominancia

El nivel de batería $b$ forma parte del estado dinámico $s = \langle pos, b, P, R, E, O \rangle$. Sin embargo, tratar cada valor entero de $b$ como una dimensión completamente independiente en la lista `CLOSED` generaría una explosión combinatoria al explorar múltiples desvíos o trayectos inútiles que solo reducen la batería.

---

#### Principio de Dominancia de Estados

Sean dos nodos $n_1$ y $n_2$ alcanzados durante la búsqueda con estados $s_1$ y $s_2$ respectivamente:

$$s_1 = \langle pos, b_1, P, R, E, O \rangle \quad \text{y} \quad s_2 = \langle pos, b_2, P, R, E, O \rangle$$

Donde ambas configuraciones del mundo físico son **exactamente idénticas** ($pos, P, R, E, O$).

- El nodo $n_1$ **domina** a $n_2$ si y solo si:
  $$b_1 \ge b_2 \quad \text{y} \quad g(n_1) \le g(n_2)$$

Un nodo dominado ($n_2$) posee una batería menor o igual tras haber consumido un costo acumulado mayor o igual. Dado que la función de costo $g(n)$ rastrea directamente el consumo de energía, $n_2$ no puede ofrecer ninguna solución futura de menor costo que no sea también alcanzable por $n_1$. Por lo tanto, $n_2$ puede descartarse de forma segura.

---

#### Aprovechamiento de la Dominancia en la Lista `CLOSED`

Para implementar esta regla de dominancia en **Graph Search** sin romper la lógica del algoritmo:

1. **Estructura de `CLOSED` como Mapa Hash:**
   En lugar de almacenar estados completos $s$, la lista `CLOSED` almacena un mapeo desde la **configuración física estricta** $S_{fisico} = \langle pos, P, R, E, O \rangle$ hacia el **mayor nivel de batería registrado** $b_{max}$ para esa configuración:
   
   $$\text{CLOSED}: \langle pos, P, R, E, O \rangle \longrightarrow b_{max}$$

2. **Criterio de Inserción y Filtrado:**
   Al extraer un nodo $n$ con estado $s = \langle S_{fisico}, b \rangle$ de `OPEN`:
   - **Si $S_{fisico} \in \text{CLOSED}$ y $b \le \text{CLOSED}[S_{fisico}]$:** El nodo $n$ está dominado y se descarta inmediatamente sin expandir sus sucesores.
   - **Si $S_{fisico} \notin \text{CLOSED}$ o $b > \text{CLOSED}[S_{fisico}]$:** Se actualiza el registro con $\text{CLOSED}[S_{fisico}] = b$ y se procede a expandir el nodo.

3. **Prevención de Desvíos Inútiles:**
   Dado que **Uniform Cost Search** procesa nodos en orden monótonamente creciente de $g(n)$, cualquier camino alternativo que llegue a la misma situación física con un consumo $g(n)$ mayor y un nivel de batería menor quedará podado en tiempo constante $O(1)$, evitando que el algoritmo consuma memoria explorando variaciones redundantes del historial de batería.

---

## Formulación y tamaño del espacio

### 1. ¿Por qué «5 zonas, ~10 objetos, capacidad 3» genera millones de nodos en un UCS ingenuo?

Aunque el mapa geográfico sea pequeño, el espacio de estados sufre un **crecimiento combinatorio**. 

El tamaño de la tupla de objetos $O$ sola es de $(N_{zonas} + 2)^{10} = 7^{10} \approx 282.4 \text{ millones}$ de combinaciones posibles (cada objeto puede estar en una de las 5 zonas, en el inventario o en estado usado). Al multiplicar esto por las combinaciones de zonas ($5$), niveles de batería ($101$), puertas ($2^m$), paneles ($2^k$) y estaciones ($2^e$), el espacio de estados alcanzable es colosal. 

Un UCS ingenuo sin podas explora combinaciones irrelevantes de transporte de objetos por el mapa, generando una explosión en la memoria.

---

### 2. ¿Qué papel tiene `DROP` en esa explosión?

La acción `DROP` es el principal motor de la **ramificación inútil** (*branching factor explosion*). 

En un estado donde el robot lleva 3 objetos en el inventario y se encuentra en una zona con otros objetos, la permutación de acciones de soltar y recoger objetos en diferentes órdenes genera un número masivo de estados físicos equivalentes. 

Sin restricciones, el agente puede intercalar secuencias infinitas de `DROP` y `PICKUP` alternando objetos entre el suelo y el inventario, o creando "almacenes intermedios" de objetos en cualquier zona del mapa, saturando la cola de prioridad `OPEN` con permutaciones sin valor táctico.

---

### 3. Podas y abstracciones aplicadas (y por qué conservan la optimidad / son *sound*)

Para controlar la explosión combinatoria sin perder la solución óptima, se aplican tres reglas de poda en la generación de sucesores:

1. **Poda de Recogida Obsoleta (`PICKUP`)**:
   - *Regla*: No se genera la acción `PICKUP(Obj)` si las puertas o paneles asociados a `Obj` ya fueron resueltos ($P_i == 1$ y $R_i == 1$).
   - *Preservación del Óptimo*: Los objetos tienen como único fin abrir puertas o reparar paneles. Una vez resuelto el elemento del entorno, el objeto pierde todo valor operativo futuro. Ignorarlo elimina ramas redundantes sin afectar ninguna acción válida hacia la meta.

2. **Poda de `DROP` por Ineficiencia**:
   - *Regla*: La acción `DROP(Obj)` solo se genera cuando el inventario está completamente lleno (capacidad = 3) **Y** la zona actual contiene un objeto relevante pendiente que el robot necesita recoger.
   - *Preservación del Óptimo*: Soltar un objeto en una zona vacía o con espacio libre en el inventario solo incrementa el costo $g(n)$ en $1$ (por el `DROP`) y en costos futuros (al tener que re-ejecutar `PICKUP`), sin aportar ningún progreso. Toda secuencia óptima mantendrá los objetos en el inventario hasta utilizarlos o hasta requerir liberar espacio obligatoriamente.

3. **Dominancia de Batería en `CLOSED`**:
   - *Regla*: Se descarta cualquier estado $s_2$ con una configuración física idéntica a un estado $s_1$ ya visitado si $b_2 \le b_1$.
   - *Preservación del Óptimo*: Como $g(n)$ mide el consumo acumulado de batería, llegar a la misma situación del mundo con igual o menor energía restante consumiendo mayor o igual costo jamás podrá derivar en una solución de menor costo total final.

---

### 4. Por qué los "parches rápidos" NO son una solución válida

- **Subir la capacidad del inventario**: Empeora masivamente el problema. Si bien reduce la necesidad de hacer `DROP`, incrementa el número de combinaciones en el inventario ($\binom{N}{capacidad}$) y expande exponencialmente el número de acciones aplicables por estado, acelerando el colapso de memoria.
- **Bajar las estaciones (reducir metas)**: Cambia el problema subyacente en lugar de resolverlo. Reduce artificialmente la profundidad de la búsqueda $d$, pero no soluciona la mala formulación del espacio de estados ni previene ciclos ineficientes en problemas más complejos.
- **Ignorar la batería**: Transforma el problema en uno de costo unitario donde la energía es infinita. Esto destruye el realismo del entorno, invalida la necesidad de planificar rutas hacia las estaciones de carga y evita encontrar el plan energéticamente óptimo.
