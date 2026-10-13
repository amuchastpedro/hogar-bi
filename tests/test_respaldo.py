"""Copias de seguridad y restauración (bloque 4, parte B; R43, diseño sección 14.2).

La carpeta de respaldo es siempre una carpeta temporal: nunca se toca la de Google Drive.
"""

import json
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta

import pytest

import apoyo_carga
from facturas.__main__ import main
from facturas.bd.conexion import conectar
from facturas.operacion import respaldo as modulo_respaldo
from facturas.operacion.bloqueo import bloqueo
from facturas.operacion.respaldo import ErrorRespaldo, respaldar

MARCA = "20260101_000000"
AHORA = datetime(2026, 1, 1, 0, 0, 0)


@pytest.fixture
def cargadas(rutas, capsys):
    """Agua y luz cargadas, todavía sin carpeta de respaldo configurada."""
    apoyo_carga.poner(rutas, "agua.pdf", "luz.pdf")
    assert main(["cargar"], rutas, espera=0) == 0
    capsys.readouterr()
    return rutas


@pytest.fixture
def destino(rutas, tmp_path):
    """Una carpeta de respaldo vacía, escrita en `datos/config.toml` (una ruta de Windows, con barras invertidas)."""
    carpeta = tmp_path / "respaldo con espacios"
    carpeta.mkdir()
    rutas.config.write_text(f"carpeta_respaldo = '{carpeta}'\n", encoding="utf-8")
    return carpeta


def _instantaneas(destino):
    return sorted(p.name for p in (destino / "instantaneas").glob("facturas_*.db"))


def _pdfs(carpeta):
    return sorted(str(p.relative_to(carpeta)) for p in carpeta.rglob("*.pdf"))


def test_el_respaldo_tiene_la_instantanea_los_ajustes_y_los_pdfs(cargadas, destino, capsys):
    assert main(["contrato", "agua 1", "--alias", "casa"], cargadas) == 0
    capsys.readouterr()

    assert main(["respaldar"], cargadas) == 0

    (nombre,) = _instantaneas(destino)
    assert "Respaldo: " + nombre in capsys.readouterr().out
    instantanea = destino / "instantaneas" / nombre
    conexion = sqlite3.connect(instantanea)
    assert conexion.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
    conexion.close()
    assert apoyo_carga.volcado(instantanea) == apoyo_carga.volcado(cargadas.base)
    marca = nombre[len("facturas_"):-len(".db")]
    assert (destino / "instantaneas" / f"ajustes_{marca}.json").read_bytes() == cargadas.ajustes.read_bytes()
    assert _pdfs(destino / "procesadas") == _pdfs(cargadas.procesadas) and _pdfs(cargadas.procesadas)
    assert not list(destino.rglob("*.parcial"))
    assert not list(cargadas.datos.glob("respaldo_*"))  # la carpeta temporal se borra


def test_sin_ajustes_manuales_el_respaldo_guarda_una_lista_vacia(cargadas, destino):
    assert not cargadas.ajustes.exists()
    respaldar(cargadas, ahora=AHORA)
    assert json.loads((destino / "instantaneas" / f"ajustes_{MARCA}.json").read_text(encoding="utf-8")) == []


def test_un_segundo_respaldo_copia_solo_los_pdfs_que_faltan(cargadas, destino):
    assert respaldar(cargadas, ahora=AHORA).pdfs_copiados == 2
    copia = next((destino / "procesadas").rglob("*.pdf"))
    antes = copia.stat().st_mtime_ns

    assert respaldar(cargadas, ahora=AHORA).pdfs_copiados == 0
    assert copia.stat().st_mtime_ns == antes
    assert len(_instantaneas(destino)) == 2

    apoyo_carga.poner(cargadas, "gas.pdf")
    assert main(["cargar"], cargadas, espera=0) == 0  # respalda solo, con la hora de ahora
    assert len(_pdfs(destino / "procesadas")) == 3


def test_cargar_respalda_si_cargo_algo_y_no_si_no_cambio_nada(rutas, destino, capsys):
    apoyo_carga.poner(rutas, "agua.pdf")
    assert main(["cargar"], rutas, espera=0) == 0
    salida = capsys.readouterr().out
    assert "Respaldo: facturas_" in salida and "1 PDF nuevo" in salida
    assert len(_instantaneas(destino)) == 1

    assert main(["cargar"], rutas, espera=0) == 0  # nada que hacer
    apoyo_carga.poner(rutas, "agua.pdf")
    assert main(["cargar"], rutas, espera=0) == 0  # solo un duplicado
    assert "Respaldo" not in capsys.readouterr().out
    assert len(_instantaneas(destino)) == 1


def test_reprocesar_pendientes_tambien_respalda(rutas, destino):
    shutil.copyfile(apoyo_carga.ejemplo("agua.pdf"), rutas.pendientes / "agua.pdf")
    assert main(["reprocesar", "--pendientes"], rutas, espera=0) == 0
    assert len(_instantaneas(destino)) == 1
    assert len(_pdfs(destino / "procesadas")) == 1


def test_reprocesar_todo_no_respalda(cargadas, destino):
    assert main(["reprocesar", "--todo"], cargadas, espera=0) == 0
    assert _instantaneas(destino) == []


def test_cargar_sin_carpeta_de_respaldo_avisa_pero_no_falla(rutas, capsys):
    apoyo_carga.poner(rutas, "agua.pdf")
    assert main(["cargar"], rutas, espera=0) == 0
    salida = capsys.readouterr().out
    assert "AVISO: no se hizo la copia de seguridad" in salida and "config.toml" in salida
    assert len(_pdfs(rutas.procesadas)) == 1  # la factura se cargó igual


def test_si_la_carpeta_de_respaldo_no_existe_cargar_termina_con_error_pero_la_carga_queda(rutas, destino, capsys):
    shutil.rmtree(destino)  # Google Drive sin sincronizar
    apoyo_carga.poner(rutas, "agua.pdf")

    assert main(["cargar"], rutas, espera=0) == 2

    capturado = capsys.readouterr()
    assert "1 cargadas" in capturado.out
    assert "las facturas se cargaron, pero no se pudo hacer la copia de seguridad" in capturado.err
    assert "la carpeta de respaldo no existe" in capturado.err
    assert apoyo_carga.consulta(rutas.base, "SELECT count(*) FROM factura") == [(1,)]
    assert not destino.exists()  # no se crea


def test_respaldar_sin_configuracion_es_un_error(cargadas, capsys):
    assert main(["respaldar"], cargadas) == 2
    assert "no hay carpeta de respaldo" in capsys.readouterr().err


@pytest.mark.parametrize("contenido, texto", [
    ("esto no es toml = = =", "no es un TOML válido"),
    ("otra_clave = 'x'\n", "falta carpeta_respaldo"),
    ("carpeta_respaldo = 3\n", "falta carpeta_respaldo"),
])
def test_una_configuracion_invalida_se_explica(cargadas, capsys, contenido, texto):
    cargadas.config.write_text(contenido, encoding="utf-8")
    assert main(["respaldar"], cargadas) == 2
    assert texto in capsys.readouterr().err


def test_una_configuracion_con_bom_se_acepta(rutas, destino):
    """`Out-File -Encoding utf8` de PowerShell 5.1 escribe UTF-8 con BOM."""
    rutas.config.write_text(rutas.config.read_text(encoding="utf-8"), encoding="utf-8-sig")
    assert modulo_respaldo.carpeta_de_respaldo(rutas) == destino


def test_la_rotacion_conserva_solo_las_ultimas_instantaneas(cargadas, destino):
    (destino / "instantaneas").mkdir()
    (destino / "instantaneas" / "notas.txt").write_text("no es un respaldo", encoding="utf-8")
    for dia in range(5):
        resultado = respaldar(cargadas, conservar=3, ahora=AHORA + timedelta(days=dia))

    assert _instantaneas(destino) == ["facturas_20260103_000000.db", "facturas_20260104_000000.db",
                                      "facturas_20260105_000000.db"]
    assert sorted(p.name for p in (destino / "instantaneas").glob("ajustes_*.json")) == [
        "ajustes_20260103_000000.json", "ajustes_20260104_000000.json", "ajustes_20260105_000000.json"]
    assert (destino / "instantaneas" / "notas.txt").exists()  # lo que no es de un respaldo no se toca
    assert resultado.eliminadas == ["20260102_000000"]


def test_la_rotacion_por_defecto_conserva_30(cargadas, destino):
    assert modulo_respaldo.CONSERVAR == 30


def test_dos_respaldos_en_el_mismo_segundo_no_se_pisan(cargadas, destino):
    primero = respaldar(cargadas, ahora=AHORA).instantanea.name
    segundo = respaldar(cargadas, ahora=AHORA).instantanea.name
    assert primero != segundo and _instantaneas(destino) == sorted([primero, segundo])


def test_un_respaldo_con_una_escritura_en_curso_es_consistente(cargadas, destino):
    escritor = conectar(cargadas.base, "escritura")
    escritor.execute("BEGIN IMMEDIATE")
    escritor.execute("UPDATE contrato SET alias = 'sin confirmar' WHERE alias = 'agua 1'")
    escritor.execute("DELETE FROM factura")  # una escritura grande y sin confirmar: se llevaría las líneas
    try:
        respaldar(cargadas, ahora=AHORA)
    finally:
        escritor.execute("ROLLBACK")
        escritor.close()

    instantanea = destino / "instantaneas" / f"facturas_{MARCA}.db"
    conexion = sqlite3.connect(instantanea)
    assert conexion.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
    assert conexion.execute("SELECT count(*) FROM contrato WHERE alias = 'sin confirmar'").fetchone() == (0,)
    assert conexion.execute("SELECT count(*) FROM linea").fetchone()[0] > 0
    conexion.close()
    assert apoyo_carga.volcado(instantanea) == apoyo_carga.volcado(cargadas.base)


def test_si_la_copia_no_coincide_con_el_original_no_queda_nada_con_el_nombre_definitivo(cargadas, destino, monkeypatch):
    monkeypatch.setattr(modulo_respaldo.shutil, "copyfile", lambda origen, copia: open(copia, "wb").write(b"truncado"))
    with pytest.raises(ErrorRespaldo, match="no coincide con el original"):
        respaldar(cargadas, ahora=AHORA)
    assert _instantaneas(destino) == []
    assert not list(destino.rglob("*.parcial"))


# --- restaurar -------------------------------------------------------------------------------


@pytest.fixture
def con_respaldo(cargadas, destino):
    """Agua y luz cargadas con el alias `casa` y una instantánea con la marca MARCA."""
    assert main(["contrato", "agua 1", "--alias", "casa"], cargadas) == 0
    respaldar(cargadas, ahora=AHORA)
    return cargadas, destino, destino / "instantaneas" / f"facturas_{MARCA}.db"


def _cambiar_despues_de_la_instantanea(rutas):
    """Escrituras posteriores a la instantánea: otra factura, otro alias y un PDF menos en procesadas/."""
    apoyo_carga.poner(rutas, "gas.pdf")
    assert main(["cargar"], rutas, espera=0) == 0
    assert main(["contrato", "casa", "--alias", "cambiado"], rutas) == 0


def test_restaurar_reproduce_exactamente_el_contenido_respaldado(con_respaldo, capsys):
    rutas, destino, instantanea = con_respaldo
    esperado = apoyo_carga.volcado(instantanea)
    ajustes = (destino / "instantaneas" / f"ajustes_{MARCA}.json").read_bytes()
    _cambiar_despues_de_la_instantanea(rutas)
    assert apoyo_carga.volcado(rutas.base) != esperado
    perdido = next(rutas.procesadas.rglob("*.pdf"))
    perdido.unlink()
    capsys.readouterr()

    assert main(["restaurar", str(instantanea)], rutas) == 0

    salida = capsys.readouterr().out
    assert "Restaurada facturas_" in salida and "se repusieron 1 PDFs" in salida
    assert "AVISO: 1 PDFs de procesadas/ no están en esa copia" in salida  # el de gas, posterior
    assert apoyo_carga.volcado(rutas.base) == esperado
    assert rutas.ajustes.read_bytes() == ajustes
    assert perdido.exists()
    conexion = conectar(rutas.base, "lectura")
    assert conexion.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
    conexion.close()
    conectar(rutas.base, "escritura").close()  # la base queda usable por la carga
    assert main(["estado"], rutas) == 0


def test_restaurar_acepta_la_marca_en_lugar_de_la_ruta(con_respaldo):
    rutas, _, instantanea = con_respaldo
    esperado = apoyo_carga.volcado(instantanea)
    _cambiar_despues_de_la_instantanea(rutas)

    assert main(["restaurar", MARCA], rutas) == 0

    assert apoyo_carga.volcado(rutas.base) == esperado


def test_restaurar_con_un_lector_abierto_en_otro_proceso_y_escrituras_posteriores(con_respaldo):
    """Con el dashboard abierto no se puede reemplazar ni copiar el archivo: se usa la API de backup (§14.2)."""
    rutas, _, instantanea = con_respaldo
    esperado = apoyo_carga.volcado(instantanea)
    _cambiar_despues_de_la_instantanea(rutas)
    lector = (
        "import sys; sys.path.insert(0, 'src')\n"
        "from pathlib import Path\n"
        "from facturas.bd.conexion import conectar\n"
        "c = conectar(Path(sys.argv[1]), 'lectura')\n"
        "c.execute('BEGIN')\n"
        "print(c.execute('SELECT count(*) FROM factura').fetchone()[0], flush=True)\n"
        "sys.stdin.readline()\n"
        "print(c.execute('SELECT count(*) FROM factura').fetchone()[0], flush=True)\n"
        "c.execute('COMMIT')\n"
        "print(c.execute('SELECT count(*) FROM factura').fetchone()[0], flush=True)\n"
    )
    proceso = subprocess.Popen([sys.executable, "-c", lector, str(rutas.base)], cwd=apoyo_carga.DIR_EJEMPLOS.parent,
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    try:
        assert proceso.stdout.readline().strip() == "3"  # agua, luz y gas

        assert main(["restaurar", str(instantanea)], rutas) == 0

        proceso.stdin.write("\n")
        proceso.stdin.flush()
        assert proceso.stdout.readline().strip() == "3"  # su transacción sigue viendo la foto que tenía
        assert proceso.stdout.readline().strip() == "2"  # al terminarla, ve la base restaurada
    finally:
        proceso.stdin.close()
        proceso.wait(timeout=30)
    assert apoyo_carga.volcado(rutas.base) == esperado
    assert not list(rutas.base.parent.glob("*.nueva*"))


def test_restaurar_en_un_equipo_sin_base_ni_pdfs_y_reconstruir_da_lo_mismo(con_respaldo):
    rutas, _, instantanea = con_respaldo
    esperado = apoyo_carga.volcado(instantanea)
    for sufijo in ("", "-wal", "-shm"):
        rutas.base.with_name(rutas.base.name + sufijo).unlink(missing_ok=True)
    shutil.rmtree(rutas.procesadas)
    rutas.ajustes.unlink()

    assert main(["restaurar", MARCA], rutas) == 0

    assert apoyo_carga.volcado(rutas.base) == esperado
    assert len(_pdfs(rutas.procesadas)) == 2
    assert main(["reprocesar", "--todo"], rutas, espera=0) == 0  # los PDFs y los ajustes repuestos bastan
    assert apoyo_carga.volcado(rutas.base) == esperado


@pytest.mark.parametrize("instantanea, texto", [
    ("20200101_000000", "no existe la instantánea"),
    ("no_existe.db", "no existe la instantánea"),
])
def test_restaurar_una_instantanea_que_no_existe_no_cambia_nada(con_respaldo, capsys, instantanea, texto):
    rutas, _, _ = con_respaldo
    antes = apoyo_carga.volcado(rutas.base)
    assert main(["restaurar", instantanea], rutas) == 2
    assert texto in capsys.readouterr().err
    assert apoyo_carga.volcado(rutas.base) == antes


def test_restaurar_un_archivo_que_no_es_una_instantanea_no_cambia_nada(con_respaldo, tmp_path, capsys):
    rutas, _, _ = con_respaldo
    ajeno = tmp_path / "otra.db"
    ajeno.write_bytes(b"x")
    antes = apoyo_carga.volcado(rutas.base)
    assert main(["restaurar", str(ajeno)], rutas) == 2
    assert "no tiene el nombre de una instantánea" in capsys.readouterr().err
    assert apoyo_carga.volcado(rutas.base) == antes


def test_restaurar_sin_los_ajustes_de_la_misma_marca_no_cambia_nada(con_respaldo, capsys):
    rutas, destino, _ = con_respaldo
    (destino / "instantaneas" / f"ajustes_{MARCA}.json").unlink()
    antes = apoyo_carga.volcado(rutas.base)
    assert main(["restaurar", MARCA], rutas) == 2
    assert "falta ajustes_" in capsys.readouterr().err
    assert apoyo_carga.volcado(rutas.base) == antes


def test_restaurar_una_instantanea_danada_no_cambia_nada(con_respaldo, capsys):
    rutas, _, instantanea = con_respaldo
    instantanea.write_bytes(b"esto no es una base de SQLite" * 100)
    antes = apoyo_carga.volcado(rutas.base)
    assert main(["restaurar", MARCA], rutas) == 2
    assert "la instantánea" in capsys.readouterr().err
    assert apoyo_carga.volcado(rutas.base) == antes


def test_restaurar_una_instantanea_de_otra_version_del_esquema_no_cambia_nada(con_respaldo, capsys):
    rutas, _, instantanea = con_respaldo
    conexion = sqlite3.connect(instantanea)
    conexion.execute("PRAGMA user_version = 99")
    conexion.close()
    antes = apoyo_carga.volcado(rutas.base)
    assert main(["restaurar", MARCA], rutas) == 2
    assert "versión 99" in capsys.readouterr().err
    assert apoyo_carga.volcado(rutas.base) == antes


def test_restaurar_toma_el_bloqueo_de_la_carga(con_respaldo, capsys):
    rutas, _, _ = con_respaldo
    _cambiar_despues_de_la_instantanea(rutas)
    despues = apoyo_carga.volcado(rutas.base)
    with bloqueo(rutas.bloqueo):
        assert main(["restaurar", MARCA], rutas) == 0
        assert main(["respaldar"], rutas) == 0
    assert capsys.readouterr().out.count("No se hizo nada") == 2
    assert apoyo_carga.volcado(rutas.base) == despues
