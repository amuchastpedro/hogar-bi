"""Mide las consultas de referencia y los invariantes con 10 años de facturas simuladas (R38).

No es un test (pytest no lo recoge): se ejecuta a mano cuando cambian el esquema o
las vistas, y su resultado se anota en docs/diseno.md, sección 6.3.

    .venv\\Scripts\\python tests\\rendimiento.py

Simula las cuatro facturas de ejemplo repetidas con períodos contiguos: agua y
gas cada dos meses, luz y Digi cada mes. Son 360 facturas y 2.280 líneas.
"""

import copy
import datetime
import json
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import datos_prueba  # noqa: E402
from facturas.bd.conexion import conectar  # noqa: E402
from facturas.bd.construir import construir  # noqa: E402
from facturas.bd.invariantes import verificar  # noqa: E402

DIR_CONSULTAS = Path(__file__).resolve().parents[1] / "src" / "facturas" / "bd" / "consultas"
DESDE, ANIOS = datetime.date(2016, 1, 1), 10
PLANTILLAS = ((datos_prueba.FACTURA_AGUA, 2), (datos_prueba.FACTURA_GAS, 2),
              (datos_prueba.FACTURA_LUZ, 1), (datos_prueba.FACTURA_DIGI, 1))


def _sumar_meses(fecha, meses):
    total = fecha.month - 1 + meses
    return fecha.replace(year=fecha.year + total // 12, month=total % 12 + 1)


def facturas_simuladas():
    hasta = DESDE.replace(year=DESDE.year + ANIOS)
    for plantilla, meses in PLANTILLAS:
        inicio, numero = DESDE, 0
        while inicio < hasta:
            fin = _sumar_meses(inicio, meses) - datetime.timedelta(days=1)
            factura = copy.deepcopy(plantilla)
            factura.update(numero=f"{plantilla['numero']}-{numero}", inicio=inicio.isoformat(), fin=fin.isoformat(),
                           emision=(fin + datetime.timedelta(days=5)).isoformat())
            for medicion in factura["mediciones"]:
                medicion["fecha_lectura"] = fin.isoformat()
            yield factura
            inicio, numero = fin + datetime.timedelta(days=1), numero + 1


def _cronometrar(funcion):
    inicio = time.perf_counter()
    resultado = funcion()
    return time.perf_counter() - inicio, resultado


def main():
    with tempfile.TemporaryDirectory() as directorio:
        ruta = Path(directorio) / "facturas.db"
        construir(ruta)
        conexion = conectar(ruta, "escritura")
        facturas = list(facturas_simuladas())
        for factura in facturas[:-1]:
            datos_prueba.insertar(conexion, factura)
        lineas = conexion.execute("SELECT count(*) FROM linea").fetchone()[0]
        print(f"{len(facturas) - 1} facturas y {lineas} líneas cargadas; se mide la última aparte.")

        def cargar_ultima():
            conexion.execute("BEGIN IMMEDIATE")
            factura_id = datos_prueba.insertar_filas(conexion, facturas[-1])
            violaciones = verificar(conexion, factura_id)
            conexion.execute("COMMIT")
            return factura_id, violaciones

        segundos, (factura_id, violaciones) = _cronometrar(cargar_ultima)
        print(f"Carga de una factura con sus invariantes: {segundos:.2f} s ({len(violaciones)} violaciones)")
        segundos, _ = _cronometrar(lambda: verificar(conexion, factura_id))
        print(f"Invariantes de una factura: {segundos:.2f} s")

        parametros = {"categorias": json.dumps(["agua", "gas", "luz", "fibra", "movil"]), "categoria": "luz",
                      "conceptos": json.dumps(["consumo_electricidad"]), "mes_desde": "0000-01", "mes_hasta": "9999-12"}
        for archivo in sorted(DIR_CONSULTAS.glob("*.sql")):
            sql = archivo.read_text(encoding="utf-8")
            segundos, filas = _cronometrar(lambda: conexion.execute(sql, parametros).fetchall())
            print(f"{archivo.stem}: {segundos:.2f} s, {len(filas)} filas")
        conexion.close()


if __name__ == "__main__":
    main()
