# Bloque 2: Implementación de la base de datos

## Objetivo

Implementar en SQLite el diseño aprobado en el bloque 1: esquema, semillas, calendario, vistas, invariantes y generación del diccionario. Este bloque no lee PDFs: se prueba con datos que se cargan directamente.

## Antes de empezar

Leer `tarea.md`, `requisitos.md`, el archivo de caso, `bitacora.md` y `docs/diseno.md`.

## Qué hacer

- Crear el entorno virtual y el archivo de dependencias.
- Escribir el esquema SQL: tablas, restricciones, triggers y vistas.
- Implementar la función única de conexión, con un modo de escritura y otro de solo lectura. Tiene que activar las claves foráneas (R8), usar WAL y `busy_timeout` (R39) y verificar la versión del esquema (R40).
- Implementar la creación de la base desde cero: esquema, semillas, calendario y, si existe el archivo, los datos manuales (R41). Ejecutarla dos veces tiene que dar el mismo resultado.
- Crear los índices (R38) y verificar las consultas de referencia con `EXPLAIN QUERY PLAN`.
- Escribir las semillas del diccionario: categorías, tipos de cargo, conceptos, alias y proveedores conocidos.
- Implementar la verificación de invariantes (R33) como una función que devuelve la lista de violaciones. La carga del bloque 4 la usa dentro de su transacción.
- Implementar la generación de `docs/diccionario.md` desde la base, y generarlo.
- Guardar las consultas de referencia del bloque 1 como archivos SQL ejecutables.
- Preparar los datos de prueba: las facturas de ejemplo, escritas a mano a partir de los valores esperados del caso, con identificadores ficticios e insertadas sin pasar por los parsers.
- Al final, lanzar la revisión técnica independiente descrita en `requisitos.md` sobre lo implementado y resolver sus hallazgos. El resultado queda en `docs/revision_bloque_2.md`.

## Tests

- Las claves foráneas están activas en toda conexión obtenida con la función compartida.
- Una conexión de solo lectura no puede escribir.
- La base está en modo WAL, y una lectura no se bloquea mientras hay una escritura en curso.
- Al conectar se detecta una base con otra versión del esquema.
- Una base reconstruida conserva los datos manuales.
- Se rechaza una factura en una moneda que el caso no admite.
- La base rechaza:
  - una fecha inválida o en otro formato;
  - un período invertido;
  - un importe con decimales o en texto;
  - una línea con un concepto de otra categoría;
  - una factura duplicada;
  - un nulo en un campo obligatorio;
  - un solape entre facturas ordinarias del mismo contrato.
- Al borrar una factura se borran sus líneas y sus mediciones.
- Con las facturas de prueba:
  - la suma del prorrateo de cada factura es exactamente su total;
  - el reparto mensual coincide con los controles del caso (±1 céntimo por mes);
  - la cobertura coincide con los controles del caso;
  - los totales por categoría coinciden con los valores esperados del caso.
- Una rectificativa por sustitución desaparece de la vista de facturas vigentes y el gasto no se duplica.
- Una línea `puntual` cae entera en el mes de emisión y no cuenta para la cobertura.
- Los invariantes detectan una factura cuyas líneas no suman el total.
- Todas las consultas de referencia se ejecutan y devuelven los valores esperados con los datos de prueba.
- `docs/diccionario.md` coincide con la clasificación del caso.

## Entregables

- Esquema, módulo de conexión, creación de la base, semillas, invariantes, generador del diccionario, consultas de referencia, datos de prueba y tests.
- `docs/revision_bloque_2.md`, con el veredicto, los hallazgos y su resolución.

## Criterios de aceptación

- Todos los tests pasan.
- Las vistas responden todas las preguntas del dashboard del caso.
- La revisión técnica no deja abierto ningún hallazgo de severidad alta.

## Fuera de este bloque

La lectura de PDFs y el proceso de carga.
