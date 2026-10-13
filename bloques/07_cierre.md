# Bloque 7: Cierre

## Objetivo

Dejar el proyecto listo para operar, para mostrarlo a otras personas y para replicarlo con otros datos.

## Antes de empezar

Leer `docs/estado.md` y la ficha del bloque (`docs/fichas/07_cierre.md`), que dice qué secciones hacen falta; `CLAUDE.md` y `tarea.md` se leen siempre. Si la ficha no existe, leer del archivo de caso «Contexto» y «Preguntas que tiene que responder el dashboard», y de la bitácora el campo «Cómo verificarlo» de cada entrada.

## Qué hacer

### `README.md`, para personas

- Qué hace el proyecto, en un párrafo, con el diagrama del flujo.
- Instalación desde cero: requisitos, entorno virtual, creación de la base e instalación del disparador.
- Operación diaria:
  - dejar los PDFs en `datos/entrada/`;
  - qué notificaciones llegan;
  - cómo revisar y aprobar propuestas;
  - cómo consultar el estado.
- Mantenimiento:
  - reconstruir la base;
  - restaurar desde una copia de seguridad;
  - agregar un proveedor a mano;
  - cambiar el alias de un contrato;
  - registrar una fecha de alta o de baja.
- Cómo replicarlo con otros datos: qué archivos copiar y cómo escribir un archivo de caso.
- Cómo se construyó: enlaces a `tarea.md`, `bloques/` y `bitacora.md`.

### Guía de carga histórica (`docs/guia_carga_historica.md`)

Los pasos para cargar las facturas históricas que menciona el caso:

- cómo dejarlas;
- qué esperar: algunas pueden ir a pendientes si el formato era distinto;
- cómo revisar huecos y solapes con `estado`;
- cómo verificar que los totales por año son razonables.

### Revisión final

- Ejecutar todos los tests.
- Buscar datos personales en todos los archivos versionados, además de lo que ya controla el hook.
- Verificar que lo específico del caso vive solo en el archivo de caso, las semillas y los parsers: buscar nombres de categorías, proveedores y conceptos en el resto del código.
- Verificar que la base se puede reconstruir desde cero con `reprocesar --todo`.
- Probar una restauración completa desde la carpeta de respaldo.

### Prueba de punta a punta

Es el criterio de "proyecto resuelto" (ver "Definición de terminado" en `tarea.md`). Se ejecuta sin alterar los datos reales, por ejemplo en una copia del proyecto con su propio disparador temporal, y se documenta cómo se hizo.

1. Con el disparador instalado, se deja un PDF de ejemplo en `datos/entrada/` y, sin intervenir, se comprueba que:
   - la factura se carga;
   - el gasto mensual y la cobertura se actualizan;
   - se crea el respaldo;
   - llega la notificación.
2. Se deja un PDF que no se puede cargar. Termina en `datos/pendientes/` y, con el plan B en modo simulación, en una propuesta revisable. Al rechazarla, todo queda como estaba.
3. Se ejecutan todas las consultas de referencia. Cada pregunta del dashboard tiene respuesta, y los valores coinciden con los del caso.
4. `reprocesar --todo` reconstruye la base con un resultado idéntico.
5. Se restaura desde el respaldo, con un resultado idéntico.

## Criterios de aceptación

- La prueba de punta a punta pasa completa, y su resultado queda en la bitácora.
- Alguien que no participó puede instalar y operar el sistema siguiendo solo el README.
- La revisión final no encuentra datos personales ni lógica del caso fuera de su lugar.
