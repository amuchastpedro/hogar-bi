"""Conexión única: claves foráneas, solo lectura, WAL y versión del esquema (R8, R39, R40)."""

import hashlib
import sqlite3
import time

import pytest

import facturas.bd.construir as construir_modulo
from facturas.bd.conexion import RUTA_ESQUEMA, VERSION_ESQUEMA, ErrorBase, conectar


@pytest.mark.parametrize("modo", ["lectura", "escritura"])
def test_claves_foraneas_activas(ruta_base, modo):
    conexion = conectar(ruta_base, modo)
    assert conexion.execute("PRAGMA foreign_keys").fetchone() == (1,)
    conexion.close()


def test_claves_foraneas_activas_al_crear(tmp_path):
    conexion = conectar(tmp_path / "nueva.db", "nueva")
    assert conexion.execute("PRAGMA foreign_keys").fetchone() == (1,)
    conexion.close()


def test_lectura_no_puede_escribir(ruta_base):
    conexion = conectar(ruta_base, "lectura")
    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        conexion.execute("INSERT INTO moneda (codigo) VALUES ('USD')")
    # Tampoco adjuntando el mismo archivo por otra vía.
    conexion.execute("ATTACH DATABASE ? AS otra", (str(ruta_base),))
    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        conexion.execute("INSERT INTO otra.moneda (codigo) VALUES ('USD')")
    conexion.close()


def test_modo_wal_y_lectura_durante_una_escritura(ruta_base):
    escritura = conectar(ruta_base, "escritura")
    lectura = conectar(ruta_base, "lectura")
    assert escritura.execute("PRAGMA journal_mode").fetchone() == ("wal",)
    assert lectura.execute("PRAGMA journal_mode").fetchone() == ("wal",)

    escritura.execute("BEGIN IMMEDIATE")
    escritura.execute("INSERT INTO moneda (codigo) VALUES ('USD')")
    inicio = time.perf_counter()
    # La lectura no espera al escritor (busy_timeout es de 5 s) y no ve lo que no se confirmó.
    assert lectura.execute("SELECT count(*) FROM moneda").fetchone() == (1,)
    assert time.perf_counter() - inicio < 1
    escritura.execute("COMMIT")
    assert lectura.execute("SELECT count(*) FROM moneda").fetchone() == (2,)
    lectura.close()
    escritura.close()


@pytest.mark.parametrize("modo", ["lectura", "escritura"])
def test_detecta_otra_version_del_esquema(ruta_base, modo):
    otra = sqlite3.connect(ruta_base)
    otra.execute(f"PRAGMA user_version = {VERSION_ESQUEMA + 1}")
    otra.close()
    with pytest.raises(ErrorBase, match="reconstruirla"):
        conectar(ruta_base, modo)


# Huella de esquema.sql (saltos de línea LF) de cada versión del esquema. Si cambia el
# esquema, hay que subir `PRAGMA user_version` en esquema.sql y anotar acá la huella
# nueva: así una base construida con el esquema anterior pide reconstruirse (R40).
HUELLA_POR_VERSION = {
    1: "ad1d2b1c38034a4702d44de0010a217ad1dec11b167ed5026e7cfca98e4f0ad2",
    2: "6bdb8b99525a2bba0fd022fb09326a87162b7ddaeccc9592086be51799e6f4dd",
    3: "e4ed9ecd8c3da51f836d26b32740942d32851047bebf43069369f0373b7326f7",
}


def test_cada_cambio_del_esquema_sube_su_version():
    huella = hashlib.sha256(RUTA_ESQUEMA.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    assert HUELLA_POR_VERSION.get(VERSION_ESQUEMA) == huella, (
        f"esquema.sql cambió (huella {huella}): subir PRAGMA user_version y anotar la huella en HUELLA_POR_VERSION")


def test_una_construccion_interrumpida_no_deja_una_base_valida(tmp_path, monkeypatch):
    # Revisión del bloque 2, H3: si el proceso muere a mitad de camino, el archivo queda,
    # pero vacío y con la versión 0, porque todo iba en una transacción.
    def morir(conexion):
        raise KeyboardInterrupt

    monkeypatch.setattr(construir_modulo, "_cargar_calendario", morir)
    monkeypatch.setattr(construir_modulo, "_borrar_base", lambda ruta: None)  # como si no llegara a limpiar
    ruta = tmp_path / "facturas.db"
    with pytest.raises(KeyboardInterrupt):
        construir_modulo.construir(ruta)
    assert ruta.exists()
    with pytest.raises(ErrorBase, match="tiene la versión 0 del esquema"):
        conectar(ruta, "lectura")


def test_no_crea_una_base_que_no_existe(tmp_path):
    with pytest.raises(ErrorBase, match="No existe"):
        conectar(tmp_path / "no_existe.db", "escritura")
    assert not (tmp_path / "no_existe.db").exists()


def test_nueva_no_pisa_una_base_existente(ruta_base):
    with pytest.raises(ErrorBase, match="ya existe"):
        conectar(ruta_base, "nueva")


def test_reemplazo_abre_una_base_de_otra_version_como_destino_de_un_backup(ruta_base, tmp_path):
    otra = sqlite3.connect(ruta_base)
    otra.execute(f"PRAGMA user_version = {VERSION_ESQUEMA + 1}")
    otra.close()
    with pytest.raises(ErrorBase):
        conectar(ruta_base, "escritura")

    nueva = tmp_path / "nueva.db"
    construir_modulo.construir(nueva)
    destino = conectar(ruta_base, "reemplazo")
    assert destino.execute("PRAGMA foreign_keys").fetchone() == (1,)
    origen = sqlite3.connect(nueva)
    origen.backup(destino)
    origen.close()
    destino.close()
    # Después del backup la base es la nueva y la versión coincide.
    conectar(ruta_base, "escritura").close()


def test_reemplazo_no_crea_una_base_que_no_existe(tmp_path):
    with pytest.raises(ErrorBase, match="No existe"):
        conectar(tmp_path / "no_existe.db", "reemplazo")
