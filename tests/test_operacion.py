"""Operación: una sola ejecución a la vez, códigos de salida, logs, estado y espera de archivos (bloque 4, parte A)."""

import logging
import subprocess
import sys
from pathlib import Path

import pytest

import apoyo_carga
from facturas.__main__ import main
from facturas.bd import diccionario
from facturas.bd.conexion import RAIZ, conectar
from facturas.operacion import registro
from facturas.operacion.bloqueo import BloqueoOcupado, bloqueo
from facturas.operacion.estado import euros
from facturas.operacion.proceso import esperar_estables

RAIZ_PROYECTO = Path(__file__).resolve().parents[1]


def test_una_segunda_ejecucion_en_el_mismo_proceso_no_hace_nada(rutas, capsys):
    apoyo_carga.poner(rutas, "agua.pdf")
    with bloqueo(rutas.bloqueo):
        codigo = main(["cargar"], rutas, espera=0)

    assert codigo == 0
    assert "No se hizo nada: hay otra ejecución en curso" in capsys.readouterr().out
    assert [p.name for p in rutas.entrada.iterdir()] == ["agua.pdf"]  # no se tocó
    assert list(rutas.procesadas.rglob("*.pdf")) == []
    # Al soltarse el bloqueo, la siguiente ejecución sí trabaja.
    assert main(["cargar"], rutas, espera=0) == 0
    assert len(list(rutas.procesadas.rglob("*.pdf"))) == 1


def test_dos_ejecuciones_simultaneas_en_procesos_distintos(rutas):
    codigo = (
        "import sys; sys.path.insert(0, 'src')\n"
        "from pathlib import Path\n"
        "from facturas.operacion.bloqueo import bloqueo, BloqueoOcupado\n"
        "try:\n"
        "    with bloqueo(Path(sys.argv[1])): print('tomado')\n"
        "except BloqueoOcupado: print('ocupado')\n"
    )
    with bloqueo(rutas.bloqueo):
        ocupado = subprocess.run([sys.executable, "-c", codigo, str(rutas.bloqueo)], cwd=RAIZ_PROYECTO,
                                 capture_output=True, text=True, check=True)
    libre = subprocess.run([sys.executable, "-c", codigo, str(rutas.bloqueo)], cwd=RAIZ_PROYECTO,
                           capture_output=True, text=True, check=True)
    assert ocupado.stdout.strip() == "ocupado"
    assert libre.stdout.strip() == "tomado"


def test_el_bloqueo_se_libera_aunque_el_proceso_falle(tmp_path):
    ruta = tmp_path / "x.lock"
    with pytest.raises(RuntimeError):
        with bloqueo(ruta):
            raise RuntimeError("falla a mitad de la carga")
    with bloqueo(ruta):  # se puede tomar de nuevo
        with pytest.raises(BloqueoOcupado):
            with bloqueo(ruta):
                pass


def test_un_proceso_que_muere_con_el_bloqueo_no_lo_deja_tomado(rutas):
    codigo = (
        "import sys, os; sys.path.insert(0, 'src')\n"
        "from pathlib import Path\n"
        "from facturas.operacion.bloqueo import bloqueo\n"
        "with bloqueo(Path(sys.argv[1])):\n"
        "    os._exit(3)  # muere sin pasar por los finally\n"
    )
    resultado = subprocess.run([sys.executable, "-c", codigo, str(rutas.bloqueo)], cwd=RAIZ_PROYECTO)
    assert resultado.returncode == 3
    with bloqueo(rutas.bloqueo):
        pass


def test_codigos_de_salida_0_1_y_2(rutas, capsys):
    assert main(["cargar"], rutas, espera=0) == 0  # nada que hacer

    apoyo_carga.poner(rutas, "agua.pdf")
    assert main(["cargar"], rutas, espera=0) == 0  # todo cargado

    (rutas.entrada / "nuevo.pdf").write_bytes(apoyo_carga.pdf_con_texto("formato nuevo"))
    assert main(["cargar"], rutas, espera=0) == 1  # hay PDFs nuevos en pendientes
    assert main(["cargar"], rutas, espera=0) == 0  # el pendiente de antes no cuenta como nuevo
    assert main(["reprocesar", "--pendientes"], rutas, espera=0) == 1  # sigue sin poder cargarse

    rutas.base.write_bytes(b"esto no es una base de datos sqlite" * 50)
    capsys.readouterr()
    assert main(["cargar"], rutas, espera=0) == 2  # error del sistema
    assert "Error del sistema" in capsys.readouterr().err
    assert main(["estado"], rutas) == 2


def test_estado_sin_base_es_un_error_del_sistema(rutas, capsys):
    rutas.base.unlink()
    assert main(["estado"], rutas) == 2
    assert "No existe la base" in capsys.readouterr().err


def test_estado_lista_los_pdfs_pendientes_con_su_motivo(rutas, capsys):
    apoyo_carga.poner(rutas, "luz.pdf")
    (rutas.entrada / "nuevo.pdf").write_bytes(apoyo_carga.pdf_con_texto("formato nuevo"))
    main(["cargar"], rutas, espera=0)
    capsys.readouterr()

    assert main(["estado"], rutas) == 0
    salida = capsys.readouterr().out
    assert "PDFs pendientes: 1" in salida
    assert "nuevo.pdf: formato ningún parser reconoce el documento" in salida


def test_estado_detecta_un_insert_or_replace_hecho_a_mano(rutas, capsys):
    apoyo_carga.poner(rutas, "agua.pdf", "luz.pdf")
    main(["cargar"], rutas, espera=0)
    conexion = conectar(rutas.base, "escritura")
    # La base impide editar un hecho suelto, pero no reemplazar la fila de una factura:
    # la cascada borra sus líneas y el total queda sin respaldo.
    conexion.execute(
        """INSERT OR REPLACE INTO factura
           SELECT factura_id, carga_id, proveedor_id, moneda_id, numero, tipo, numero_factura_corregida,
                  fecha_emision, fecha_vencimiento, fecha_inicio, fecha_fin, importe_total_centimos + 100
           FROM factura WHERE fecha_emision = (SELECT min(fecha_emision) FROM factura)""")
    conexion.close()
    capsys.readouterr()

    assert main(["estado"], rutas) == 2
    salida = capsys.readouterr().out
    assert "ATENCIÓN: 1 de 2 facturas no cumplen I1" in salida
    assert "líneas 0,00 €" in salida


def test_euros_usa_el_formato_espanol():
    assert euros(4321) == "43,21 €"
    assert euros(0) == "0,00 €"
    assert euros(-1507) == "-15,07 €"
    assert euros(123456789) == "1.234.567,89 €"


def test_el_comando_diccionario_reproduce_el_versionado(rutas):
    assert main(["diccionario"], rutas) == 0
    generado = (rutas.raiz / "docs" / "diccionario.md").read_text(encoding="utf-8")
    assert generado == (RAIZ / "docs" / "diccionario.md").read_text(encoding="utf-8")
    assert diccionario.RUTA_DICCIONARIO == RAIZ / "docs" / "diccionario.md"


def test_el_log_se_escribe_en_datos_logs_y_rota(rutas, monkeypatch):
    apoyo_carga.poner(rutas, "agua.pdf")
    main(["cargar"], rutas, espera=0)
    texto = (rutas.logs / "facturas.log").read_text(encoding="utf-8")
    assert "INFO facturas.proceso: Cargada" in texto

    monkeypatch.setattr(registro, "MAX_BYTES", 300)
    monkeypatch.setattr(registro, "COPIAS", 2)
    logger = registro.configurar(rutas.logs)
    try:
        for numero in range(60):
            logger.info("línea de relleno número %d para forzar la rotación del archivo", numero)
    finally:
        registro.cerrar()
    archivos = sorted(p.name for p in rutas.logs.iterdir())
    assert archivos == ["facturas.log", "facturas.log.1", "facturas.log.2"]  # solo las últimas 2 copias


def test_configurar_el_log_dos_veces_no_duplica_los_manejadores(tmp_path):
    registro.configurar(tmp_path)
    registro.configurar(tmp_path)
    try:
        assert len(logging.getLogger(registro.NOMBRE).handlers) == 1
    finally:
        registro.cerrar()
    assert logging.getLogger(registro.NOMBRE).handlers == []


def test_espera_a_que_el_archivo_deje_de_crecer(tmp_path):
    pdf = tmp_path / "copiandose.pdf"
    pdf.write_bytes(b"a" * 10)
    estable = tmp_path / "estable.pdf"
    estable.write_bytes(b"b" * 10)
    esperas = []

    def dormir(segundos):
        esperas.append(segundos)
        if len(esperas) <= 2:  # el archivo sigue copiándose durante las dos primeras esperas
            with pdf.open("ab") as archivo:
                archivo.write(b"a" * 10)

    estables, inestables = esperar_estables([pdf, estable], segundos=3, dormir=dormir)

    assert estables == sorted([pdf, estable]) and inestables == []
    assert esperas == [3, 3, 3]  # tres rondas: dos con cambios y una estable


def test_un_archivo_que_nunca_se_estabiliza_se_deja_para_otra_ejecucion(tmp_path):
    pdf = tmp_path / "infinito.pdf"
    pdf.write_bytes(b"a")

    def dormir(segundos):
        with pdf.open("ab") as archivo:
            archivo.write(b"a")

    estables, inestables = esperar_estables([pdf], segundos=3, limite=10, dormir=dormir)

    assert estables == [] and inestables == [pdf]


def test_un_archivo_que_desaparece_durante_la_espera_se_ignora(tmp_path):
    pdf = tmp_path / "fugaz.pdf"
    pdf.write_bytes(b"a")
    estables, inestables = esperar_estables([pdf], segundos=0, dormir=lambda s: pdf.unlink())
    assert estables == [] and inestables == []


def test_un_archivo_bloqueado_para_lectura_no_se_considera_estable(tmp_path, monkeypatch):
    pdf = tmp_path / "bloqueado.pdf"
    pdf.write_bytes(b"a")
    intentos = []

    def se_puede_abrir(ruta):
        intentos.append(ruta)
        return len(intentos) > 1  # el programa que lo copia lo suelta después de la primera ronda

    monkeypatch.setattr("facturas.operacion.proceso._se_puede_abrir", se_puede_abrir)
    estables, _ = esperar_estables([pdf], segundos=0, dormir=lambda s: None)
    assert estables == [pdf] and len(intentos) == 2
