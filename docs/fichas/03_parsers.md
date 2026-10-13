# Ficha del bloque 3: parsers

Complementa [`bloques/03_parsers.md`](../../bloques/03_parsers.md) con lo de este proyecto.

## Leer (solo esto; ~290 líneas)

- `caso_hogar.md`: «Parámetros del caso», «Proveedores y formatos», «Particularidades de cada formato» y «Valores esperados de los ejemplos».
- `docs/diseno.md`:
  - §11, el contrato «factura extraída»: tipos (11.1–11.5), validaciones de forma (11.6) y período de cada formato (11.7);
  - §16.1, la factura extraída de `fibra_movil.pdf` resuelta.
- Si hace falta un requisito: `requisitos.md`, R5, R10–R13, R23 y R31.

## Archivos

- Crea, según §14 de `docs/diseno.md`:
  - `src/facturas/extraccion.py`: tipos, validación de forma y JSON;
  - `src/facturas/parsers/__init__.py`, el registro;
  - `src/facturas/parsers/pdf.py`;
  - un parser por formato: `aigues_agua.py`, `naturgy_gas.py`, `naturgy_luz.py` y `digi_convergente.py`.
- Crea `tests/test_extraccion.py` y `tests/test_parsers.py`.
- Crea `ejemplos/identificadores_esperados.json`, fuera de git.
- Modifica `requirements.txt` (la biblioteca de PDF, fijada) y, si cambia algo del contrato, `docs/diseno.md` §1.1.

## Interfaces

- Produce la factura extraída de §11, que la carga del bloque 4 consume sin conocer PDFs.
- Reglas de dependencia, que verifica `tests/test_codigo.py`:
  - `extraccion` no importa nada del proyecto;
  - `parsers` importa solo `extraccion` y la biblioteca de PDF.
- Ejemplos en `ejemplos/`: `agua.pdf`, `gas.pdf`, `luz.pdf` y `fibra_movil.pdf`.
- `tests/caso.py` ya lee del caso la clasificación y los controles. Si hace falta leer «Valores esperados», se agrega una función ahí; no se copian valores a mano.

## Pendientes heredados (bitácora, bloques 1 y 2)

- Cada parser emite las cantidades tal como las imprime el documento.
- Un crédito parcial se tipifica como `rectificativa_diferencias`, no como abono. Naturgy (gas) emitió abonos parciales: pedirle a la persona usuaria uno del histórico para el parser del gas.
- Solo la luz emite franjas (revisión H5).
- Cada parser declara sus campos opcionales impresos (§11.6).
- Agua: verificar los días de cada factura con los promedios impresos (l/día y €/día).
- Digi:
  - confirmar la convención del período con dos facturas consecutivas del histórico;
  - comprobar si el IVA por servicio siempre suma el impreso (H12);
  - limpiar los rótulos de sección, que vienen subrayados;
  - riesgo: una línea nueva dentro de PRODUCTOS con un período entre paréntesis se traduciría como cuota.
- Verificar con el histórico que ningún texto real coincida con dos alias (riesgo de las palabras clave de B6). `traducir()` lo rechaza como ambiguo.

## Tests

- Del bloque: `.venv\Scripts\python -m pytest -q --tb=short tests\test_extraccion.py tests\test_parsers.py tests\test_codigo.py`
- Al cerrar, todos: `.venv\Scripts\python -m pytest -q --tb=line`
