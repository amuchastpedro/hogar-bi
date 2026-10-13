# Bloque 1: Diseño de la base de datos

## Objetivo

Diseñar el modelo de datos, el contrato entre parsers y carga, y el flujo de carga, y dejar el proyecto inicializado. Todos los bloques siguientes se construyen sobre este diseño, así que este es el punto de control más importante.

## Antes de empezar

- Leer `tarea.md`, `requisitos.md`, el archivo de caso y `bitacora.md`.
- Abrir los PDFs de `ejemplos/` y contrastar el diseño con los documentos reales, no solo con la descripción del caso.

## Qué hacer

### 1. Preparar el proyecto

- Verificar que estén instalados Python, git y el CLI de Claude Code (`claude --version`), y la versión de SQLite que trae Python (`sqlite3.sqlite_version`; hace falta ≥ 3.37). Anotar las versiones en la bitácora. Si falta algo, detenerse y avisar.
- Inicializar git y crear un `.gitignore` que excluya `datos/`, `ejemplos/`, `.venv/`, las bases de datos, los logs y los archivos temporales de Python.
- Instalar un hook de git `pre-commit` que bloquee los commits con datos personales. Tiene que buscar los patrones de datos personales que lista el caso en los archivos que se van a commitear, dejando pasar los identificadores fiscales de los proveedores del caso. Probarlo con un archivo de prueba.
- Crear la estructura de carpetas de `CLAUDE.md`.

### 2. Diseñar el modelo (`docs/diseno.md`)

- Diagrama entidad-relación en Mermaid.
- Para cada tabla:
  - propósito;
  - columnas con su tipo, nulabilidad y significado;
  - clave primaria y clave natural;
  - claves foráneas;
  - restricciones `CHECK` y triggers.
- Una tabla de trazabilidad requisito → mecanismo que cubra todos los requisitos de `requisitos.md`, de R1 a R43. Si alguno no aplica, explicar por qué.
- La justificación de la normalización (R35): para cada tabla, por qué está en tercera forma normal o qué desnormalización tiene y por qué.
- La convención de nombres (R37).
- Los índices (R38), cada uno con la consulta que lo justifica.
- Las vistas para el dashboard, cada una con su nombre, su grano (qué representa una fila) y sus columnas. Como mínimo:
  - facturas vigentes;
  - líneas con su categoría y su tipo de cargo;
  - gasto diario y mensual (mes × categoría × tipo de cargo × concepto);
  - consumo mensual (mes × contrato × magnitud × franja × tipo de lectura);
  - cobertura, por contrato y por categoría.
- El algoritmo de prorrateo en céntimos con reparto de restos, con un ejemplo numérico sobre una factura del caso.
- Los invariantes de R33, cada uno con su fórmula y su tolerancia.
- Consultas de referencia: para cada pregunta del dashboard del archivo de caso, la consulta SQL sobre las vistas que la responde. Si una pregunta no se puede responder con las vistas, el diseño está incompleto.
- Un ejemplo resuelto: las filas que generaría en cada tabla la factura de ejemplo que indica el caso, con identificadores ficticios.

### 3. Diseñar el contrato parser → carga

En `docs/diseno.md`, la estructura de la "factura extraída" que devuelven todos los parsers:

- campos de cabecera;
- contratos, con su identificador externo y su categoría;
- líneas: texto literal, sección del documento, contrato, cantidad, unidad, precio, importe, base y tipo si es un impuesto, período si difiere del de la factura, y una marca si es derivada;
- mediciones y lecturas.

Para cada campo: tipo, obligatoriedad y formato (fechas ISO, importes en céntimos, precios sin pérdida de decimales). La estructura no contiene conceptos: los parsers devuelven textos y la carga los traduce.

### 4. Proponer el diccionario inicial

A partir del archivo de caso, definir:

- los conceptos, con su categoría, su tipo de cargo y su imputación por defecto;
- los alias: los textos de los PDFs de ejemplo;
- el formato de los archivos de semillas;
- cómo se resuelven las partes variables de los textos (R31).

### 5. Describir el flujo de carga

Los estados por los que pasa un PDF, qué se registra en cada paso y qué pasa ante cada tipo de fallo:

- formato desconocido;
- campo que falta;
- texto sin alias;
- invariante roto;
- factura duplicada;
- solape con otra factura.

El bloque 4 lo implementa.

### 6. Definir la organización de `src/`

Los módulos y sus responsabilidades, respetando la separación de `tarea.md`: los parsers no importan nada de la base, y la carga no importa nada de lectura de PDFs.

### 7. Revisión técnica

Lanzar la revisión técnica independiente descrita en `requisitos.md` sobre `docs/diseno.md` y resolver sus hallazgos. El resultado queda en `docs/revision_bloque_1.md`.

## Entregables

- `docs/diseno.md` con todas las secciones anteriores.
- `docs/revision_bloque_1.md`, con el veredicto, los hallazgos y su resolución.
- Proyecto inicializado: git, `.gitignore`, hook de datos personales y estructura de carpetas.
- La entrada del bloque en `bitacora.md`.

## Criterios de aceptación

- Cada requisito, de R1 a R43, tiene un mecanismo concreto (no vale "se tendrá en cuenta").
- La revisión técnica no deja abierto ningún hallazgo de severidad alta.
- Cada pregunta del dashboard tiene una consulta de referencia.
- Todas las facturas de ejemplo se pueden representar completas, sin perder ningún valor de la sección "Valores esperados" del caso.
- Ningún nombre de categoría, proveedor o concepto del caso aparece en el diseño de las tablas ni en el código genérico: viven en las semillas y en los parsers.
- El hook bloquea un commit de prueba que contiene un dato personal ficticio.

## Fuera de este bloque

El código de la base, de los parsers y de la carga.
