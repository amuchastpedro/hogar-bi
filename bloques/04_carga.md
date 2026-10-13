# Bloque 4: Carga

## Objetivo

Un programa de línea de comandos que procesa los PDFs de `datos/entrada/`, los carga en la base y deja cada archivo en `datos/procesadas/` o en `datos/pendientes/`.

## Antes de empezar

- Leer `docs/estado.md` y la ficha del bloque (`docs/fichas/04_carga.md`), que dice qué secciones hacen falta; `CLAUDE.md` y `tarea.md` se leen siempre. Si la ficha no existe, leer de `docs/diseno.md` el flujo de carga y la organización de `src/`, y del archivo de caso «Copias de seguridad».
- El bloque se ejecuta en dos sesiones, cada una con su punto de control:
  - **parte A:** `cargar`, `reprocesar`, `estado` y `diccionario`, el procesamiento de cada PDF y los requisitos de la ejecución;
  - **parte B:** `contratos`, `contrato`, `respaldar` y `restaurar`.

  Los tests y los criterios de aceptación se reparten según el comando que prueban; la prueba manual va al final de la parte B.
- En la parte B, preguntar a la persona usuaria la ruta de la carpeta de respaldo (ver "Copias de seguridad" en el caso). Verificar que existe y que se puede escribir en ella, y guardarla en `datos/config.toml`.

## Comandos

- **`cargar`**: procesa todos los PDFs de `datos/entrada/` en una sola ejecución.
- **`reprocesar --pendientes`**: vuelve a intentar los PDFs de `datos/pendientes/`, por ejemplo después de aprobar una corrección.
- **`reprocesar --todo`**: reconstruye la base desde cero con los PDFs de `datos/procesadas/` y las semillas (R19). Si nada cambió, el contenido resultante es idéntico.
- **`estado`**: un resumen legible con las facturas por categoría, el último período cubierto por cada contrato, los meses incompletos y los PDFs pendientes con su motivo.
- **`diccionario`**: regenera `docs/diccionario.md`.
- **`contratos`**: lista los contratos con su alias, su categoría y sus fechas de alta y baja.
- **`contrato <alias> [--alias nuevo] [--alta fecha] [--baja fecha]`**: modifica los datos manuales de un contrato, en la base y en `datos/ajustes_manuales.json` a la vez (R41).
- **`respaldar`**: hace la copia de seguridad (R43). Se ejecuta solo al final de cada `cargar` que cambió algo.
- **`restaurar <instantánea>`**: restaura la base y los datos manuales desde una copia de seguridad.

## Procesamiento de cada PDF

1. Esperar a que el archivo termine de copiarse: el tamaño se mantiene estable durante unos segundos y el archivo se puede abrir.
2. Calcular el hash. Si ese PDF ya está cargado, registrarlo como duplicado y moverlo a `datos/duplicados/`. Nunca se borra un archivo de la persona usuaria.
3. Elegir el parser y extraer. Guardar la salida cruda en la tabla de cargas.
4. Traducir los textos a conceptos con el diccionario y registrar los contratos nuevos (R21).
5. Insertar en una transacción y verificar los invariantes antes de confirmar.
6. Si todo va bien, mover el PDF a `datos/procesadas/<categoría o proveedor>/<año>/` con el nombre normalizado `<inicio>_<fin>_<formato>_<nº factura>.pdf`.
7. Si algo falla en cualquier paso:
   - revertir la transacción;
   - registrar la carga como rechazada, con la etapa y el motivo;
   - mover el PDF a `datos/pendientes/`, junto a un archivo legible `<nombre>.motivo.txt`;
   - seguir con el siguiente PDF. Un PDF con problemas no detiene el lote.

## Requisitos de la ejecución

- Una sola ejecución a la vez. Si ya hay una en curso, la segunda termina sin hacer nada. El bloqueo se libera aunque el proceso falle.
- Al terminar, un resumen con las facturas cargadas, duplicadas y rechazadas.
- Códigos de salida (los bloques 5 y 6 dependen de ellos):
  - `0`: todo cargado, o nada que hacer;
  - `1`: hay PDFs nuevos en pendientes;
  - `2`: error del sistema.
- Logs en `datos/logs/`, con rotación.

## Tests

Siempre sobre copias de los ejemplos en carpetas temporales, nunca sobre `datos/`.

- Con todos los ejemplos en entrada, se carga una factura por ejemplo, los archivos quedan en procesadas y `estado` muestra los totales y la cobertura del caso.
- Ejecutar `cargar` dos veces no cambia nada.
- El mismo PDF con otro nombre se detecta como duplicado.
- Un PDF de formato desconocido va a pendientes con su motivo, y el resto del lote se carga.
- Un texto sin alias (se simula quitando un alias de las semillas de prueba) hace rechazar la factura, con el texto en el motivo. Después de agregar el alias, `reprocesar --pendientes` la carga.
- Si se simula un invariante roto, no queda nada parcial en la base.
- `reprocesar --todo` produce exactamente el mismo contenido.
- Si se lanzan dos ejecuciones simultáneas, la segunda no hace nada.
- Un cambio de alias hecho con `contrato` queda en la base y en el archivo de ajustes, y sobrevive a `reprocesar --todo`.
- Un respaldo hecho en una carpeta temporal contiene los PDFs, los datos manuales y una instantánea que pasa `PRAGMA integrity_check`.
- Un respaldo tomado mientras hay una escritura en curso es consistente.
- `restaurar` reproduce exactamente el contenido respaldado.
- La rotación conserva solo las últimas N instantáneas.

## Criterios de aceptación

- Todos los tests pasan.
- Prueba manual: copiar todos los ejemplos a `datos/entrada/`, ejecutar `cargar` y mostrar en el punto de control el resumen, la salida de `estado` y el respaldo creado en la carpeta de respaldo.

## Fuera de este bloque

La ejecución automática (bloque 5) y la corrección de errores con agente (bloque 6).
