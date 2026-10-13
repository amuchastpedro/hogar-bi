# Tarea: dashboard de gastos del hogar

Especificación del dashboard en Streamlit (`caso_hogar.md`, «Herramienta del dashboard»). Se construye por etapas, con los estándares de `tarea.md` (ver «Forma de trabajo»).

## Cómo se usa

- Son 4 etapas (la 3, en tres partes). Se ejecutan en orden, cada una en una sesión nueva: *«Ejecutá la etapa N de task_dashboard.md»* (o *«la etapa 3a»*).
- La persona usuaria elige el modelo que sugiere la tabla de etapas y sigue lo demás de `tarea.md`, «Cómo se usa». En las etapas 2 y 3, abre la app cuando el agente lo indica y pide los cambios en la misma sesión, **juntos en un mensaje y sin pausas largas**: la caché caduca a los pocos minutos.
- Este archivo **no se lee entero**: cada etapa lee solo las secciones que le asigna «Etapas» (índice con `grep -n '^#' task_dashboard.md`).

## Objetivo

Un dashboard que lee `datos/facturas.db` y responde dos preguntas:

1. **Overview:** ¿cuánto gasto, en total y en cada servicio o combinación de servicios?
2. **Analysis:** en cada servicio, ¿por qué gasto lo que gasto?

Las preguntas de partida están en `caso_hogar.md`, «Preguntas que tiene que responder el dashboard». Donde esta tarea difiere, manda esta tarea.

Las decisiones de esta tarea las tomó la persona usuaria y no se vuelven a discutir. Lo que queda abierto está marcado como propuesta del agente.

## Interfaz

- La interfaz va entera en **inglés**: páginas, títulos, ejes, etiquetas y avisos. El código y la documentación siguen en español.
- No hay mock: el diseño visual lo propone el agente con la skill `dataviz`.
- Cada servicio tiene el mismo color en todas las páginas, y cada grupo, un color estable dentro de su pestaña.

### Página 1: Overview

Suma todas las líneas de las facturas vigentes, tasas e impuestos incluidos. El gasto se reparte por **mes calendario**, prorrateado por días (`v_hecho_gasto_mensual`).

- **Filtros**
  - Servicios: selector múltiple de agua, gas, luz, fibra y móvil (cualquier combinación). Fibra y móvil se eligen por separado.
  - Período: un mes, un año, todo el histórico, el año en curso (YTD), los últimos 12 meses y un **rango arbitrario**, con mes de inicio y mes de fin.
  - «Exclude incomplete months»: quita los meses incompletos de los KPIs y de los gráficos.
- **KPIs:** el gasto total del período, el de cada servicio elegido y el **gasto medio mensual**. Si el período tiene meses incompletos, los KPIs lo avisan.
- **Gráficos**
  - evolución mensual del gasto, apilada por servicio, con los meses incompletos marcados;
  - **reparto por servicio**: qué parte del total del período se lleva cada uno.
- El agente puede proponer más elementos en el punto de control, sin implementarlos antes.

### Página 2: Analysis (una pestaña por servicio)

Cuatro pestañas: **Water, Electricity, Gas, DIGI** (fibra y móvil).

El grano es **por factura**: cada punto es un período de facturación. Una rectificativa por diferencias se suma a la factura que corrige. Solo cuentan las facturas de `v_factura_vigente`.

**Contenido común a las cuatro pestañas:**

1. **Composición por grupo**: el importe de cada factura, apilado por grupo.
2. **Pesos de cada grupo** (wᵢ, con Σwᵢ = 1) y su evolución en el tiempo.
3. **Desglose por concepto** dentro de cada grupo.
4. En los servicios con volumen (agua, luz y gas):
   - la **evolución del volumen** (m³ o kWh);
   - el **precio unitario efectivo**: el importe de los conceptos variables dividido por el volumen;
   - la **cascada** entre dos facturas A y B, junto a los días de cada una.
5. Si cambia el contrato o la comercializadora, la serie del servicio sigue siendo una sola, con el cambio marcado en el eje.

**Cascada.** El orden es: el total de A, el efecto volumen, el efecto precio, la diferencia de cada uno de los demás grupos y el total de B. Con q el volumen, p el precio unitario efectivo y V = p·q el importe variable:

- efecto volumen = (q_B − q_A) · p_A
- efecto precio = (p_B − p_A) · q_B

Así, V_B − V_A = efecto volumen + efecto precio, exacto.

Por defecto compara la última factura con la del mismo período del año anterior. Un selector permite compararla con la factura anterior o elegir dos facturas cualesquiera.

**Grupos de cada servicio:**

| Servicio | Grupo | Conceptos |
|---|---|---|
| Agua | Ciclo del agua (w₁) | Cuota del servicio, consumo de agua, canon del agua, tasa de alcantarillado, IVA |
| Agua | Residuos (w₂) | Tasa de recogida de residuos municipales, tasa metropolitana de tratamiento de residuos (TMTR) |
| Luz | Energía | Consumo de electricidad |
| Luz | Potencia | Término de potencia P1 y P2 |
| Luz | Otros fijos | Alquiler de contador, financiación del bono social |
| Luz | Impuestos | Impuesto sobre la electricidad, IVA |
| Gas | Energía | Consumo de gas |
| Gas | Fijo | Término fijo |
| Gas | Otros fijos | Inspección periódica, otros productos y servicios |
| Gas | Impuestos | Impuesto especial sobre hidrocarburos, IVA |
| DIGI | Una por línea (contrato) | Fibra, móvil 1, móvil 2 |
| DIGI | Dentro de cada línea | Cuota (de fibra o del plan), consumo adicional; el IVA aparte |

**Contenido específico:**

| Pestaña | Además del contenido común |
|---|---|
| Electricity | El consumo por franja (punta, llano y valle); las lecturas estimadas frente a las reales. |
| Gas | Las lecturas estimadas frente a las reales, con las facturas estimadas marcadas. |
| DIGI | Los cambios de cuota marcados. Sin volumen ni cascada. |

## Capa semántica

- **Archivo:** `src/facturas/dashboard/semantica.toml`. Para cada categoría tiene:
  - los grupos, con nombre y orden;
  - el concepto (`concepto_codigo`) → grupo;
  - si el concepto es **variable**, es decir, si escala con el volumen;
  - la magnitud que da el volumen.

  Es lo único específico del caso fuera del archivo de caso, `parsers/` y `semillas/`. La base no se usa para interpretar: el dashboard no lee `tipo_cargo` ni las vistas de cobertura.
- **Conceptos variables (propuesta del agente):** el agente propone cuáles son y lo verifica con los datos. Un concepto variable mantiene estable su importe por unidad entre facturas de una misma tarifa. Hay que mirarlo sobre todo en el canon del agua y la tasa de alcantarillado, y decidir con evidencia si el IVA del agua entra en el precio por m³.
- **Cobertura (propuesta del agente):** un mes está completo para un servicio si sus facturas vigentes cubren todos los días del mes, con cualquier contrato y sin usar fechas de baja. Con varios servicios elegidos, el mes está completo si lo está para todos.
- **Validaciones** (R34). Fallan con un mensaje que nombra el concepto y la categoría:
  - todo concepto presente en `v_linea` tiene un grupo;
  - ningún concepto está en dos grupos;
  - los grupos y los códigos del TOML existen en la base.

  Un concepto nuevo sin clasificar no tumba el dashboard: aparece en el grupo «Unclassified», con un aviso.
- **Acceso a datos:**
  - solo vistas (R32), con `facturas.bd.conexion.conectar(ruta, "lectura")` (R39);
  - consultas cacheadas con `st.cache_data`;
  - la ruta de la base, relativa a la raíz del proyecto.

## Organización del código

```
src/facturas/dashboard/
├── semantica.toml     grupos, conceptos variables y magnitud de cada servicio
├── semantica.py       carga y valida el TOML; cobertura por servicio
├── datos.py           consultas a las vistas → tablas por mes y por factura (sin Streamlit, se puede testear)
├── app.py             punto de entrada: navegación entre Overview y Analysis
├── paginas/
│   ├── overview.py
│   └── analysis.py    una pestaña por servicio, a partir de un patrón común
└── graficos.py        funciones de gráficos compartidas
```

- **Reglas de dependencia:** `dashboard` importa solo `bd`. Se agrega a `PERMITIDOS` en `tests/test_codigo.py`.
- **Dependencias:** `streamlit` y `plotly`, fijadas en `requirements.txt` en la etapa 2. La etapa 1 usa solo la biblioteca estándar (`tomllib`). No agregar otras sin consultar.
- **Comando:** `scripts\dashboard.ps1`, que lanza `streamlit run` desde la raíz con `PYTHONPATH=src`. Lo crea la etapa 2 y lo agrega a «Comandos de este proyecto» en `CLAUDE.md`.

## Etapas

| # | Etapa | Entregable principal | Depende de | Modelo sugerido |
|---|---|---|---|---|
| 1 | Capa semántica y datos | `semantica.toml`, `semantica.py`, `datos.py` y tests | — | Opus, esfuerzo alto |
| 2 | Esqueleto y Overview | App que arranca, página Overview aprobada, dependencias y comando | 1 | Sonnet, esfuerzo medio |
| 3a | Analysis: Water | La pestaña que fija el patrón común | 2 | Sonnet, esfuerzo alto |
| 3b | Analysis: Electricity y Gas | Las dos pestañas con energía | 3a | Sonnet, esfuerzo medio |
| 3c | Analysis: DIGI | La pestaña de fibra y móvil | 3a | Sonnet, esfuerzo medio |
| 4 | Interpretación fuera de la base | Sin `tipo_cargo` ni vistas de cobertura en la base | 3c | Sonnet, esfuerzo alto |

**Qué lee cada etapa de este archivo.** Siempre «Cómo se usa», «Objetivo», «Etapas» (hasta esta lista) y «Forma de trabajo»; además:

- etapa 1: «Interfaz» con sus dos páginas, «Capa semántica», «Organización del código» y «Etapa 1»;
- etapa 2: «Interfaz», «Página 1», «Organización del código» y «Etapa 2»;
- etapa 3: «Interfaz», «Página 2» y «Etapa 3»;
- etapa 4: «Capa semántica» y «Etapa 4».

Una sección o subsección, con Bash: `awk '/^## Capa semántica/{p=1;print;next} p&&/^##/{exit} p' task_dashboard.md` (con `### Página 2`, `### Etapa 1`, etc., igual). `## Interfaz` y `## Etapas` se cortan en su primera subsección, que se pide aparte.

### Etapa 1: capa semántica y datos

**Objetivo:** que los números del dashboard existan, cuadren y se puedan testear antes de dibujar nada.

**Requisitos:**

- Crear `semantica.toml`, `semantica.py` y `datos.py`, según «Capa semántica».
- `datos.py` devuelve:
  - el gasto mensual por servicio;
  - la cobertura por servicio y mes;
  - por factura: el importe por grupo y por concepto, el volumen, el precio unitario, los días y el contrato;
  - el consumo por franja y por tipo de lectura;
  - los datos de la cascada entre dos facturas.
- Actualizar `docs/diseno.md` §14: el árbol de `src/`, la regla de dependencias y la de lo específico del caso.

**Criterios de aceptación:**

- `tests/test_dashboard_semantica.py` y `tests/test_dashboard_datos.py` cubren:
  - las validaciones del TOML, incluido un concepto sin clasificar;
  - la suma de los grupos de cada factura es igual a su total (I1);
  - la suma mensual es igual a la suma de las facturas;
  - la cascada cuadra exacta;
  - un mes completo y uno incompleto;
  - la regla de dependencia.
- **Evidencia sobre la base real:** el total de todos los meses es igual a la suma de `importe_total_centimos` de `v_factura_vigente`.

**Punto de control.** Además de lo que pide `tarea.md`, mostrar con los datos reales, en tablas compactas (una fila por concepto, por factura o por mes; nunca la salida cruda de una consulta):

- la tabla de grupos;
- los conceptos variables propuestos, con la evidencia;
- w₁ y w₂ de cada factura del agua;
- los meses que hoy saldrían incompletos con la regla de cobertura propuesta.

**Fuera de esta etapa:** Streamlit y los gráficos.

### Etapa 2: esqueleto y Overview

**Objetivo:** la app arranca y la página Overview responde «¿cuánto gasto?».

**Requisitos:**

- `app.py` con la navegación. Analysis queda vacía, con sus cuatro pestañas.
- La página Overview, según «Página 1: Overview».
- `requirements.txt` y `scripts\dashboard.ps1`, según «Organización del código».
- Se itera con la persona usuaria viendo la app hasta que la apruebe. El agente propone, además, el formato de los importes (por ejemplo, `€1,234.56` o `1.234,56 €`).

**Criterios de aceptación:**

- `tests/test_dashboard_app.py`: con `streamlit.testing.v1.AppTest`, la app arranca y la página se ejecuta sin errores.
- El total del Overview para «todo el histórico» con todos los servicios es igual a la evidencia de la etapa 1.
- Un test sobre `datos.py` verifica que cada período (los predefinidos y un rango arbitrario) toma los meses correctos, y que la casilla excluye los meses incompletos del total.

**Fuera de esta etapa:** el contenido de Analysis.

### Etapa 3: Analysis

**Objetivo:** cada pestaña responde «¿por qué gasto lo que gasto?», según «Página 2: Analysis».

- **3a, Water.** Fija el patrón común en `graficos.py` y `analysis.py`.
- **3b, Electricity y Gas.** El patrón común, más su contenido específico.
- **3c, DIGI.** El patrón sin volumen, más su contenido específico.

En cada parte se itera con la persona usuaria viendo la app.

**Criterios de aceptación de cada parte:**

- Un test de humo por pestaña con `AppTest`.
- En la pestaña, cada factura suma su total.
- **Evidencia sobre la base real:** la cascada entre dos facturas reales cuadra.

**Fuera de esta etapa:** cambios en la base.

### Etapa 4: interpretación fuera de la base

**Objetivo:** que la base guarde solo los hechos de las facturas.

**Requisitos:**

1. Antes de tocar nada, listar los archivos afectados y pedir aprobación. La lista sale de `grep -rlE 'tipo_cargo|cobertura' src tests` más `docs/diseno.md` y `docs/diccionario.md`, sin explorar el resto. `caso_hogar.md` y `requisitos.md` definen «tipo de cargo» y la cobertura (R26), y `tests/caso.py` lee esa clasificación del caso: esos archivos solo se modifican con autorización expresa.
2. Quitar `tipo_cargo` (la tabla, la columna de `concepto`, la dimensión, las columnas de las vistas y la semilla) y las vistas de cobertura.
3. Hacer las demás tareas del cambio:
   - subir la versión del esquema;
   - ajustar `diccionario.py` y regenerar `docs/diccionario.md`;
   - revisar las consultas de referencia C1–C7 (C2–C5 usan `tipo_cargo` o la cobertura), `operacion/estado.py` y los tests;
   - reconstruir la base real con `reprocesar --todo`.
4. Actualizar `docs/diseno.md`.

**Criterios de aceptación:**

- Pasan todos los tests.
- El dashboard da los mismos números: la evidencia de la etapa 1 da el mismo total y los tests de humo pasan.
- `estado` sigue verificando I1 en todas las facturas.

## Forma de trabajo

Rigen «Forma de trabajo», «Definición de terminado» y «Punto de control» de `tarea.md`, con estas adaptaciones:

- **Especificación:** durante una etapa, esta tarea no se modifica; un error o una omisión se plantea en el punto de control. `caso_hogar.md` y `requisitos.md` solo se tocan en la etapa 4.
- **Límites (definición de terminado, punto 6):**
  - lo específico del caso también puede vivir en `semantica.toml`;
  - la interfaz muestra alias, nunca CUPS ni números de contrato, de línea, de cliente o de factura (R21).
- **Tests y evidencia:**
  - los tests usan las bases de prueba de `tests/conftest.py`, nunca `datos/facturas.db`;
  - mientras se trabaja, solo los tests de la etapa (los dice la ficha); todos, al cerrar;
  - la evidencia sobre la base real se presenta en el punto de control;
  - lo visual lo valida la persona usuaria, y el punto de control dice cómo abrir la app y qué mirar. El agente verifica con `AppTest`: no abre la app para mirarla, no toma capturas y no lee la salida de `streamlit run`, salvo que la persona usuaria lo pida.
- **Skills:** `dataviz` se carga en las etapas 2 y 3a, que dejan el estilo fijado en `graficos.py` (paleta, color de cada servicio, formato de importes); las etapas 3b y 3c lo reutilizan sin cargarla. De `developing-with-streamlit`, solo la referencia del tema que haga falta (por ejemplo, `AppTest` o la caché).
- **Referencias independientes:** los totales de `v_factura_vigente` y los valores de `tests/datos_prueba.py`.
- **Nombres en el punto de control:**
  - la entrada de la bitácora se titula `### Dashboard, etapa N: <título> (AAAA-MM-DD)`;
  - las fichas son `docs/fichas/dN_<nombre>.md` (3a, 3b y 3c comparten `d3_analysis.md`). Su lista de lectura toma de este archivo las secciones que indica «Etapas», nunca el archivo entero, y da las firmas de `datos.py` y `graficos.py` que usa la etapa, para que no haga falta leer el código para encontrarlas;
  - el commit es `dashboard N: <resumen>`.
- **Con la persona usuaria:**
  - proponer primero la opción más simple;
  - explicar con ejemplos de sus facturas, en lenguaje llano;
  - en decisiones de proceso o de arquitectura, presentar las opciones con sus características y una recomendación antes de preguntar.

## Fuera de esta tarea

- El plan B (en pausa).
- El bloque 7 de `tarea.md` (cierre). Su ficha recoge lo que el README tiene que decir del dashboard.
- Publicar el dashboard fuera de la PC.
