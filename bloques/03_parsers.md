# Bloque 3: Parsers

## Objetivo

Un parser por formato, que convierte un PDF en una "factura extraída" (el contrato definido en el bloque 1), probado contra los PDFs de ejemplo.

## Antes de empezar

Leer `docs/estado.md` y la ficha del bloque (`docs/fichas/03_parsers.md`), que dice qué secciones hacen falta; `CLAUDE.md` y `tarea.md` se leen siempre. Si la ficha no existe, leer del archivo de caso «Particularidades de cada formato» y «Valores esperados de los ejemplos», y de `docs/diseno.md` la sección del contrato «factura extraída».

## Qué hacer

- Implementar la estructura de la factura extraída: tipos, validación de forma y serialización a JSON.
- Elegir una biblioteca gratuita para extraer texto de PDFs, preferentemente en Python puro y sin dependencias del sistema. Anotar la elección en la bitácora.
- Implementar un registro de parsers. Cada parser expone:
  - el nombre del formato;
  - su versión;
  - una función que dice si reconoce un documento (por el identificador fiscal del proveedor y una marca del tipo de documento);
  - una función que extrae la factura.

  Si ningún parser, o más de uno, reconoce un documento, es un error.
- Implementar un parser para cada formato del caso.

## Reglas para los parsers

- Extraen solo lo que está impreso. No inventan valores por defecto ni completan datos que faltan.
- Si un campo obligatorio no aparece, lanzan un error explícito que nombra el campo y el formato.
- Convierten los importes, que vienen en el formato numérico que indica el caso, a céntimos, y las fechas a ISO. Los textos de los conceptos salen literales (solo se recortan los espacios).
- Se apoyan en etiquetas estables del documento, no en posiciones absolutas ni en zonas con texto ilegible.
- Marcan las líneas derivadas (R5) como tales y verifican que su suma coincide con el total impreso.
- Cada cambio en un parser incrementa su versión.

## Tests

- Para cada PDF de ejemplo, la salida completa (cabecera, líneas y mediciones) coincide con los valores esperados del caso.
- Los identificadores se validan por su formato. Si existe el archivo local `ejemplos/identificadores_esperados.json` (fuera de git), también se comparan con sus valores exactos. El bloque crea ese archivo con los valores leídos de los PDFs, y la persona usuaria los confirma en el punto de control.
- Cada parser reconoce solo su propio ejemplo.
- Ningún parser reconoce un PDF que no es de un formato conocido. Un PDF vacío o dañado da un error claro.
- Si los PDFs de ejemplo no están, los tests que los necesitan se saltan con un mensaje claro, en lugar de fallar.
- Los tests de parsers corren en segundos, porque son la red de seguridad del plan B (bloque 6).

## Entregables

La estructura de factura extraída, el registro de parsers, un parser por formato y los tests.

## Criterios de aceptación

- Todos los tests pasan.
- Los parsers no importan nada de la base de datos ni del diccionario.

## Fuera de este bloque

La traducción de textos a conceptos y la escritura en la base.
