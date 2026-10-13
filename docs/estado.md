# Estado

Actualizado el 2026-10-13: el bloque 7 (cierre) está aprobado y guardado en el commit `bloque 7`; después, los importes reales salieron de lo versionado (commit `importes reales fuera de lo versionado`). La prueba de punta a punta pasó completa (bitácora, «Bloque 7»), así que el proyecto queda resuelto según `tarea.md`, salvo el plan B, que sigue en pausa.

- **Hecho:** bloques 1 a 5 y 7; bloque 6, parte A, en pausa (la parte B no se hizo); dashboard, etapas 1 a 4. `README.md`, `docs/guia_carga_historica.md` y `LICENSE` (MIT).
- **Siguiente:** los esquemas (Parte B de `prompt_esquemas.md`), que el README enlaza cuando se aprueben; publicar en GitHub (el repo no tiene remoto) en un solo commit con el estado final y el email privado de GitHub, porque el historial tiene los importes reales. El plan B queda pendiente, sin fecha (quizá en un futuro lejano).
- **Datos reales:** 68 facturas (4 nuevas el 2026-10-09, por el disparador), de ago 2024 a sep 2026, Z.ZXJ,JQ €, sin pendientes e I1 en todas. Última instantánea: `facturas_20261009_132111`. `config.toml` apunta a `G:\My Drive\facturas-bi-respaldo`. Disparador instalado (`c1de00ea`).
- **Tests:** `.venv\Scripts\python -m pytest -q` → 554 pasan y se salta 1 (el del plan B), en unos 3 a 4 min. Sin `ejemplos/`, los que usan los PDFs se saltan con su motivo (403 pasan y 152 se saltan).
- **Decisiones vigentes que se apartan de la especificación** (detalle en la bitácora y en `docs/diseno.md` §1.3 y §1.4):
  - bloques 1 a 4 y 6A, etapas del dashboard y fechas de `contrato`: sin cambios respecto de la nota anterior (`caso_hogar.md`, `requisitos.md` y `tests/caso.py` siguen desfasados en R2, R26, R29, R36, R41 y «Tipos de cargo»);
  - importes: en letras en la documentación y el caso; los reales, en `ejemplos/valores_esperados.md` y `ejemplos/importes_esperados.json` (locales); los tests de la base usan facturas ficticias (`tests/datos_prueba.py`, con `CONTROLES`);
  - bloque 7: aprobación del plan B con git y `Quitar-Worktree` (no hay scripts de aprobación); el README no explica fechas de alta ni de baja; el dashboard es la excepción a «lo específico del caso solo en el caso, las semillas y los parsers»; `config.toml` se lee aunque tenga BOM.
- **No verificado:** instalar las dependencias en un clon nuevo (en el scratchpad, la ruta era demasiado larga para `pip`). Conviene probarlo siguiendo el README en una ruta corta.
- **Preguntas abiertas:** ninguna. El plan B queda pendiente, sin fecha.
