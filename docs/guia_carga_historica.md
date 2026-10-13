# Guía de carga histórica

Cómo cargar las facturas de años anteriores y cómo comprobar que quedaron bien. Antes, el proyecto tiene que estar instalado ([README](../README.md), «Instalación desde cero»). Los comandos son de PowerShell, desde la raíz del proyecto, con `$env:PYTHONPATH = "src"` en la sesión.

## 1. Dejar las facturas

Copiá todos los PDFs juntos en `datos/entrada/`, con cualquier nombre y en cualquier orden:

- la carga ordena el lote por fecha de emisión, así que da igual en qué orden lleguen;
- si dos facturas se solapan por un error de orden, la que choca se reintenta al final del lote;
- un PDF repetido (el mismo archivo, aunque tenga otro nombre, o la misma factura) va a `datos/duplicados/` con su motivo; nunca se borra nada.

Con el disparador instalado, la carga empieza 20 segundos después del último PDF y termina con una notificación. Sin él:

```powershell
.venv\Scripts\python -m facturas cargar
```

La salida termina con un resumen: `Resumen: 39 cargadas, 0 duplicadas, 25 rechazadas, 0 omitidas`. Una «omitida» es un PDF que todavía se estaba copiando; se recoge en la vuelta siguiente.

## 2. Qué esperar: algunas van a pendientes

Los parsers se escribieron con las facturas de ejemplo, que son recientes. Las viejas pueden traer un formato anterior o variantes que los ejemplos no tenían, y esas van a `datos/pendientes/` con un `<nombre>.motivo.txt`:

```
Etapa: extraccion
Motivo: …
Fecha: …
```

La etapa dice dónde falló: `formato` (ningún parser reconoce el documento), `extraccion` (el parser lo reconoce pero algo no cuadra), `traduccion` (un texto que el diccionario no conoce), `insercion` o `invariantes` (los datos chocan con lo cargado o no suman). `estado` lista los pendientes con su motivo.

En este proyecto, la primera pasada del histórico (64 facturas, de agosto de 2024 a agosto de 2026) cargó 39 y rechazó 25. Las causas fueron, entre otras:

- un formato anterior: las facturas de luz y gas de 2024 las emitía Naturgy Iberia, con otro diseño;
- variantes de formatos conocidos: lecturas con «(hasta)», fechas con el año en dos cifras, un tramo de un día, la primera factura de un contrato de agua (que cuenta también el día del alta), cantidades con unidad en Digi…;
- conceptos nuevos: la inspección periódica del gas y un servicio de mantenimiento;
- el mismo suministro de luz, con y sin el punto frontera del CUPS, había quedado en dos contratos.

Se corrigieron por grupos, ampliando los parsers y el diccionario con cada PDF como ejemplo nuevo (bitácora, «Carga del histórico»). Cada corrección se hace a pedido, como explica el README («Arreglar un PDF pendiente»), y después:

```powershell
.venv\Scripts\python -m facturas reprocesar --pendientes
```

Conviene empezar por los grupos más grandes: un mismo cambio suele arreglar varias facturas.

Todavía no tienen soporte un abono total (anula una factura entera) ni una rectificativa de la luz o del agua: llegan a pendientes con un error explícito hasta que haya un ejemplo real. La rectificativa por diferencias del gas sí se lee.

## 3. Revisar huecos y solapes con `estado`

```powershell
.venv\Scripts\python -m facturas estado
```

- **Último período cubierto por contrato:** la fecha hasta la que llega la última factura de cada contrato. Un contrato que terminó (por ejemplo, un cambio de compañía) se queda en su fecha final.
- **Meses incompletos:** por servicio, desde el primer hasta el último mes con gasto, los meses que no tienen todos sus días cubiertos por alguna factura (`2026-06 8/30` es 8 días de 30). Que el primer y el último mes sean incompletos es normal, porque los períodos de facturación no empiezan el día 1. Un mes incompleto en el medio, o un `0/31`, es una factura que falta: buscala entre los pendientes o en el área de clientes del proveedor.
- **Solapes:** la base no admite dos facturas del mismo contrato con períodos que se pisan. Una que choca y no se resuelve al final del lote queda en pendientes con el motivo; suele ser una factura corregida (rectificativa) o la misma factura en otro PDF.

Los meses incompletos también se ven en el dashboard: barras atenuadas en el Overview.

## 4. Comprobar que los totales por año son razonables

En el dashboard (`scripts\dashboard.ps1`), Overview, período «A year»: el total del año y el de cada servicio. O con un comando:

```powershell
.venv\Scripts\python -c "import sqlite3; c = sqlite3.connect('file:datos/facturas.db?mode=ro', uri=True); print(*c.execute('SELECT substr(anio_mes, 1, 4), categoria_codigo, round(sum(importe_centimos) / 100.0, 2) FROM v_hecho_gasto_mensual GROUP BY 1, 2'), sep=chr(10))"
```

Compará esos totales con lo que pagaste: los cargos del banco o el resumen anual del proveedor. Hay que tener en cuenta que el gasto se reparte por días entre los meses del período de cada factura. Una factura del 15 de diciembre al 14 de febrero suma parte a cada año, así que el total de un año no es igual a la suma de las facturas emitidas ese año. La suma de todos los años sí es igual a la suma de todas las facturas, y `estado` muestra al final que las líneas de cada factura suman su total.

## 5. Al terminar

- **Alias de los contratos.** `contratos` los lista. El alias por defecto (`luz 1`, `luz 2`…) se numera por orden de llegada, así que fijalos ahora para que una reconstrucción no los cambie: `contrato "luz 1" --alias "luz 1"`, o con un nombre propio (`--alias "luz piso"`).
- **Copia de seguridad.** La carga la hace sola si cargó algo. Comprobá que en la carpeta de respaldo apareció una instantánea nueva.

## Particularidades de las facturas de este caso

- **Naturgy, 2024:** las facturas de luz y gas las emitía Naturgy Iberia, otro proveedor con otro NIF y otro formato. Sus contratos son distintos de los de Naturgy Clientes (de 2025 en adelante), aunque el suministro sea el mismo; por eso aparecen dos contratos de luz y dos de gas.
- **Luz y gas:** el contrato se identifica por los 20 caracteres del CUPS, sin el punto frontera (los dos caracteres finales que algunas facturas agregan).
- **Digi:** algunas facturas de 2025 imprimen su NIF anterior; el parser las asigna al vigente, porque es el mismo proveedor. El teléfono fijo de 2025 («DIGI tel») cuenta como fibra. Con las 20 facturas del histórico se comprobó que todas las líneas que se traducen como cuota son cuotas (fibra, fijo y planes móviles); el riesgo de que otra línea con un período entre paréntesis se leyera como cuota no apareció.
- **Sin verificar con facturas reales:** que ningún texto coincida con dos alias del diccionario a la vez. Si pasara, esa factura iría a pendientes y no se cargaría con un concepto al azar.
