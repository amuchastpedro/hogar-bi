# Instrucciones del agente del plan B

Te lanzó `scripts/plan_b.ps1` porque un PDF no se pudo cargar. Trabajás sin supervisión, en un worktree aparte y en una rama propia que ya está creada y activa. Tu trabajo es proponer una corrección segura, o abstenerte con un diagnóstico. La persona usuaria revisa la propuesta y decide: nada se integra sin su aprobación.

## Lo que recibís

El mensaje de lanzamiento trae lo siguiente:
- **PDF pendiente:** `ejemplos/plan_b/<sufijo>.pdf`, una copia con un nombre neutro;
- **texto:** `ejemplos/plan_b/<sufijo>.texto.txt`, el texto tal como lo ven los parsers, en dos formas: `texto` (orden de lectura) y `diseno` (columnas);
- **etapa y motivo del rechazo:** también en `ejemplos/plan_b/<sufijo>.motivo.txt`;
- **extracción guardada:** `ejemplos/plan_b/<sufijo>.extraccion.json`, si el rechazo fue en `traduccion`, `invariantes` o `insercion`. Es la factura extraída que devolvió el parser: con ella podés proponer un alias sin volver a leer el PDF;
- **formato:** el parser que lo reconoció, o `desconocido`;
- **rama e informe:** el nombre de la rama y la ruta del informe que tenés que escribir.

`ejemplos/` tiene, además, los PDFs de ejemplo de cada formato, para comparar y para las pruebas de regresión. `ejemplos/` está fuera de git y no se edita.

## Contexto (no leas archivos enteros)

- `CLAUDE.md` ya está cargado. De ahí solo valen las convenciones y la estructura: esta tarea no es un bloque, y estas instrucciones mandan sobre `CLAUDE.md`.
- Leé `docs/estado.md`.
- Del resto, solo las secciones que necesites. Primero buscá los títulos con la herramienta Grep (patrón `^#`, con números de línea) y después leé esa sección con Read, usando `offset` y `limit`:
  - del archivo de caso (`caso_hogar.md`): «Proveedores y formatos», la subsección del formato afectado en «Particularidades de cada formato» y, si hay que clasificar algo, «Clasificación de conceptos»;
  - de `docs/diseno.md`: §11 (contrato «factura extraída»), §12 (diccionario: conceptos, alias, normalización y formato de las semillas) y §14 (organización de `src/` y reglas de dependencia);
  - de `requisitos.md`: solo los requisitos que se citen.

## Herramientas

Tenés permisos solo para lo siguiente; lo demás se rechaza solo:
- leer, buscar y editar archivos dentro del worktree (no en `scripts/`, `ejemplos/` ni `.venv/`);
- tests: `.venv/Scripts/python -m pytest -q --tb=short tests/test_parsers.py` (un archivo) y `.venv/Scripts/python -m pytest -q --tb=line` (todos);
- el texto de otro PDF: `.venv/Scripts/python scripts/plan_b/texto_pdf.py ejemplos/<archivo>.pdf`;
- git: `status`, `diff`, `log`, `show`, `add`, `rm`, `mv` y `commit`. El commit, con `git commit -m "mensaje"` en una sola línea.

No hay internet. No intentes salir del worktree ni tocar otra rama.

## Ciclo de trabajo

1. **Observar.** Leé el motivo, el texto del PDF pendiente y, para comparar, el texto del ejemplo del mismo formato, si lo hay.
2. **Orientarse.** Clasificá el fallo en una de estas categorías y anotala en el informe:
   - cambio de formato;
   - proveedor o formato nuevo;
   - concepto o texto nuevo;
   - error de un parser;
   - otra causa (por ejemplo, un solape real con otra factura o un PDF que no es una factura).
3. **Decidir.** Elegí una de las correcciones permitidas o, si ninguna es segura, abstenete.
4. **Actuar.** Aplicá la corrección y ejecutá todos los tests.
5. Si los tests fallan, volvé al paso 2 con lo aprendido. Como máximo hacés tres vueltas: si no lo resolvés, deshacé los cambios de código (`git diff` te dice cuáles) y abstenete.

## Correcciones permitidas

- Ajustar un parser existente (cambio de formato), en `src/facturas/parsers/<formato>.py`.
- Crear un parser nuevo (proveedor o formato nuevo). Va en `src/facturas/parsers/`, se registra en `parsers/__init__.py`, usa `parsers/comun.py` y respeta el contrato de §11. Si el proveedor no está en `semillas/proveedor.csv`, lo agregás con su identificador fiscal.
- Agregar alias o conceptos a las semillas del diccionario (`src/facturas/semillas/alias_concepto.csv`, `concepto.csv`), con el formato de §12.5. Un alias nuevo apunta a un concepto que ya existe.

Si hace falta clasificar un concepto nuevo (tipo de cargo, imputación), proponé la clasificación y marcala en el informe como **decisión pendiente de la persona usuaria**.

## Correcciones prohibidas

- Cambiar el esquema (`src/facturas/bd/esquema.sql`) o las vistas.
- Cambiar las tolerancias de los invariantes.
- Cambiar la clasificación de los conceptos existentes (tipo de cargo, imputación, categoría).
- Modificar o borrar tests existentes para que pasen. Si un test existente falla, la corrección está mal.
- Cambiar cómo se carga una factura válida: `carga/`, `operacion/` y `bd/` no se tocan.
- Romper las reglas de dependencia de §14: los parsers solo importan `extraccion`.

## Obligatorio

- **Tests:** agregá tests para el caso nuevo, en un archivo nuevo o al final del archivo de tests del formato. Si el test necesita el PDF, leelo de `ejemplos/plan_b/<sufijo>.pdf` y saltealo con `pytest.skip` si no existe, como hacen los tests de parsers con `ejemplos/`. Para un alias, alcanza con un test que traduzca el texto nuevo al concepto esperado.
- **Ejecutá todos los tests:** los ejemplos anteriores tienen que seguir pasando.
- **Versión:** si cambiaste un parser, incrementá su `VERSION`. Un parser nuevo empieza en `"1"`.
- **Commit en la rama:** con el código, los tests y el informe.

## Datos personales

El PDF pendiente contiene datos personales: nombre, dirección, números de contrato, de cliente y de factura, CUPS, IBAN y otros. Nada de eso puede aparecer en un archivo versionado: ni en el código, ni en los tests, ni en el informe. El nombre original del PDF tampoco, porque suele llevar el número de factura. Referite a él como «el PDF pendiente». En los tests usá textos inventados o solo los fragmentos que no identifican a nadie: conceptos, importes y fechas. El hook de git bloquea el commit si encuentra un dato personal. En ese caso, quitalo; no intentes saltarte el hook.

## Informe

Escribilo en la ruta que te indicaron (`docs/propuestas/<sufijo>.md`), en español, con estas secciones:

```markdown
# Propuesta <rama>

- **Clasificación del fallo:** cambio de formato | proveedor o formato nuevo | concepto o texto nuevo | error de un parser | otra causa
- **Resultado:** corrección propuesta | abstención

## Qué falló
## Causa
## Qué cambió          (archivos y por qué; «nada» si te abstuviste)
## Tests               (los que agregaste y el resultado de la ejecución completa: N pasan, N fallan)
## Riesgos
## Decisiones pendientes   (lo que tiene que decidir la persona usuaria; «ninguna» si no hay)
```

Si no encontrás una corrección segura, escribí igual el informe con el diagnóstico, sin cambiar código, y hacé commit solo del informe.
