# Ficha del bloque 4: carga

Complementa [`bloques/04_carga.md`](../../bloques/04_carga.md) con lo de este proyecto. El bloque va en dos sesiones, la parte A y la parte B, cada una con su punto de control. **Las dos partes están hechas: la A (2026-10-03, aprobada) y la B (2026-10-04, aprobada). Lo que sigue es lo que quedó de la B y los cambios C9 a C13 de `docs/diseno.md` §1.3.**

## Leer (solo esto)

- Parte B:
  - `docs/diseno.md` §14.1 y §14.2 (datos manuales, copias de seguridad, restauración) y §13.4 (volcado canónico);
  - del caso, «Parámetros del caso» y «Copias de seguridad»;
  - `docs/diseno.md` §1.3, los cambios de la parte A (C4: nombre original de los PDFs; C5: archivo `.motivo.txt`).
- Si hace falta un requisito: `requisitos.md`, R19, R41–R43.

## Archivos (según `docs/diseno.md` §14)

- Hechos en la parte A: `__main__.py`, `carga/insercion.py`, `bd/volcado.py`, `operacion/{proceso,reconstruccion,estado,bloqueo,registro}.py`, `tests/{apoyo_carga,test_carga,test_operacion}.py`, el modo `reemplazo` de `conectar()`.
- Hechos en la parte B: `operacion/ajustes.py` (`contratos`, `modificar_contrato`), `operacion/respaldo.py` (`respaldar`, `restaurar`, `carpeta_de_respaldo`), `tests/{test_ajustes,test_respaldo}.py`, `Rutas.config`, `reemplazar_base()` pública en `reconstruccion.py` y los comandos de `__main__.py` y de `CLAUDE.md`. `datos/config.toml` (fuera de git) tiene `carpeta_respaldo` apuntando a Google Drive.

## Interfaces que ya existen

- `bd/conexion.py`: `conectar(ruta=RUTA_BASE, modo="lectura")`, con los modos `lectura`, `escritura`, `reemplazo` (destino de un backup, sin verificar versión) y `nueva`.
- `bd/construir.py`: `construir(ruta, directorio)`, `huella_semillas(directorio)`, `leer_ajustes(ruta)` y `aplicar_ajustes(conexion, ajustes)`.
- `bd/volcado.py`: `volcado_canonico(conexion) -> dict[tabla, filas]`. Dos bases tienen el mismo contenido si sus volcados son iguales. **`restaurar` debe comparar con esto** (§14.2). Incluye `carga.nombre_archivo` y excluye `fecha_hora` y las cargas rechazadas.
- `carga/insercion.py`: `cargar_factura(conexion, factura, sha256=, nombre_archivo=, ajustes=)`, `registrar_rechazo(...)`, `estado_de_carga(conexion, sha256)` y `ErrorCarga(etapa, motivo)`.
- `operacion/proceso.py`:
  - `Rutas(raiz, semillas)`: todas las rutas del proyecto (`base`, `ajustes`, `entrada`, `procesadas`, `bloqueo`, `logs`…). **La parte B agrega `config` (`datos/config.toml`).** Los tests construyen una `Rutas` sobre una raíz temporal;
  - `procesar_lote(rutas, conexion, pdfs, ajustes, espera=…)` → `Resumen` (`cargadas`, `duplicadas`, `rechazadas`, `omitidas`);
  - `listar_pdfs(carpeta)` y `sha256_de(ruta)`.
- `operacion/reconstruccion.py`: `preparar_base(rutas)`, `reconstruir(rutas)` y `ErrorReconstruccion`. El reemplazo de la base usa `sqlite3.connect(temporal).backup(conectar(base, "reemplazo"))` y comprueba `integrity_check` y el volcado canónico: **es el patrón que debe repetir `restaurar`**, en sentido inverso.
- `operacion/bloqueo.py`: `bloqueo(ruta)` (context manager; lanza `BloqueoOcupado`). `contrato`, `restaurar` y `respaldar` deben tomarlo (`rutas.bloqueo`); `__main__.main()` ya captura `BloqueoOcupado` (sale con 0) y los errores del sistema (sale con 2).
- `operacion/registro.py`: `configurar(directorio)` y `cerrar()`; `main()` ya los llama.
- `__main__.main(argv, rutas=None, espera=…)`: devuelve el código de salida. Los tests lo llaman con `espera=0` y una `Rutas` temporal.
- Datos manuales: `datos/ajustes_manuales.json`, una lista de objetos con `identificador_fiscal`, `identificador_externo` y, opcionalmente, `alias` (desde la versión 3 del esquema no hay fechas de alta ni de baja). La carga y la reconstrucción ya lo leen y lo aplican al registrar cada contrato; el alias por defecto no choca con los alias reservados ahí.
- Fixtures de `tests/conftest.py`: `ruta_base`, `base`, `base_ejemplos` y `rutas` (raíz temporal con carpetas y una base nueva). `tests/apoyo_carga.py`: `poner(rutas, *ejemplos)`, `pdf_con_texto()` y las listas `CASO` y `TODOS`.

## Pendientes heredados

- Parte B: hecha, sin pendientes de código. Quedan estos avisos para quien siga:
  - `respaldar` se prueba con escrituras sin confirmar en otra conexión y `restaurar` con un lector abierto en otro proceso; no se probó un respaldo concurrente con una carga real ni cómo trata Google Drive los archivos `.parcial` mientras se suben;
  - `restaurar` no admite una instantánea de otra versión del esquema (se recupera con los PDFs, los ajustes y `reprocesar --todo`): documentarlo en el README (ficha 07);
  - al reconstruir sin la base anterior, `carga.nombre_archivo` queda con el nombre normalizado de `procesadas/` (§1.3, C4); `restaurar` lo trae de la instantánea.

## Tests

- Mientras se trabaja:
  - parte A (ya pasan): `.venv\Scripts\python -m pytest -q --tb=short tests\test_carga.py tests\test_operacion.py tests\test_codigo.py`
  - parte B: `.venv\Scripts\python -m pytest -q --tb=short tests\test_ajustes.py tests\test_respaldo.py`
- Al cerrar cada parte, todos: `.venv\Scripts\python -m pytest -q --tb=line` (unos 90 s: los tests de carga leen los PDFs reales).
