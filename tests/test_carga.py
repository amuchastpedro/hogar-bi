"""Carga: de los PDFs de entrada a la base, y de ahí a procesadas, pendientes o duplicados (bloque 4, parte A).

Todo sobre copias de los ejemplos en una raíz temporal. Los valores esperados salen del caso
(`caso.py`), no de lo que el código produce.
"""

import dataclasses
import json
import shutil
import sqlite3
from decimal import Decimal

import pytest

import apoyo_carga
import caso
import datos_prueba
from facturas.__main__ import main
from facturas.bd import construir as construir_modulo
from facturas.bd.conexion import conectar
from facturas.bd.invariantes import verificar
from facturas.bd.volcado import volcado_canonico
from facturas.carga import insercion
from facturas.carga.insercion import ErrorCarga, cargar_factura
from facturas.extraccion import FacturaExtraida
from facturas.operacion import proceso
from facturas.operacion.proceso import ErrorProceso, Rutas
from facturas.parsers import extraer


def _cargar(rutas, capsys=None):
    codigo = main(["cargar"], rutas, espera=0)
    return codigo, (capsys.readouterr().out if capsys else "")


def _volcado(rutas):
    conexion = conectar(rutas.base, "lectura")
    try:
        return volcado_canonico(conexion)
    finally:
        conexion.close()


def _consulta(rutas, sql, parametros=()):
    conexion = conectar(rutas.base, "lectura")
    try:
        return conexion.execute(sql, parametros).fetchall()
    finally:
        conexion.close()


def _nombres(carpeta):
    return sorted(p.name for p in carpeta.rglob("*") if p.is_file())


def test_con_todos_los_ejemplos_se_carga_una_factura_por_pdf_distinto(rutas, capsys):
    apoyo_carga.poner(rutas)
    codigo, salida = _cargar(rutas, capsys)

    assert codigo == 0
    assert f"Resumen: {apoyo_carga.DISTINTOS} cargadas, 3 duplicadas, 0 rechazadas" in salida
    assert _nombres(rutas.entrada) == []
    assert _nombres(rutas.pendientes) == []
    assert len(_nombres(rutas.duplicados)) == 6  # 3 PDFs y sus .motivo.txt
    assert _consulta(rutas, "SELECT count(*) FROM factura") == [(apoyo_carga.DISTINTOS,)]
    assert _consulta(rutas, "SELECT count(*) FROM carga WHERE estado = 'cargada'") == [(apoyo_carga.DISTINTOS,)]
    # Cada PDF quedó en procesadas/<categorías>/<año>/<inicio>_<fin>_<formato>_<número>.pdf
    destinos = sorted(p.relative_to(rutas.procesadas).parts[:2] for p in rutas.procesadas.rglob("*.pdf"))
    assert destinos == [("agua", "2024"), ("agua", "2025"), ("agua", "2026"), ("agua", "2026"),
                        ("fibra_movil", "2025"), ("fibra_movil", "2025"), ("fibra_movil", "2025"), ("fibra_movil", "2026"),
                        ("gas", "2024"), ("gas", "2025"), ("gas", "2025"), ("gas", "2026"), ("gas", "2026"),
                        ("luz", "2024"), ("luz", "2025"), ("luz", "2025"), ("luz", "2026"), ("luz", "2026")]
    assert list(rutas.procesadas.glob("agua/2026/2026-04-10_2026-06-08_aigues_agua_*.pdf"))
    # Los invariantes valen para todas las facturas cargadas.
    conexion = conectar(rutas.base, "lectura")
    try:
        for (factura_id,) in conexion.execute("SELECT factura_id FROM factura"):
            assert verificar(conexion, factura_id) == []
    finally:
        conexion.close()


def test_estado_muestra_los_totales_y_la_cobertura_del_caso(rutas, capsys):
    apoyo_carga.poner(rutas, *apoyo_carga.CASO)
    assert _cargar(rutas)[0] == 0
    capsys.readouterr()
    assert main(["estado"], rutas) == 0
    salida = capsys.readouterr().out

    from facturas.operacion.estado import euros

    totales, reparto = caso.controles_prorrateo()
    for categoria, total in totales.items():
        linea = next(l for l in salida.splitlines() if l.strip().startswith(f"{categoria} ") and "factura" in l)
        assert euros(total) in linea
    # El reparto mensual de la base cargada desde los PDFs coincide con los controles del caso (±1 céntimo).
    por_mes = {(c, m): i for c, m, i in _consulta(
        rutas, "SELECT categoria_codigo, anio_mes, sum(importe_centimos) FROM v_hecho_gasto_mensual GROUP BY 1, 2")}
    assert set(por_mes) == set(reparto)
    for clave, esperado in reparto.items():
        assert abs(por_mes[clave] - esperado) <= 1, clave
    # Cobertura: los meses incompletos del caso aparecen con sus días; los completos, no.
    incompletos = salida.split("Meses incompletos", 1)[1].split("PDFs pendientes", 1)[0].splitlines()
    for (categoria, mes), (cubiertos, esperados) in datos_prueba.COBERTURA_CASO.items():
        linea = next(l for l in incompletos if l.strip().startswith(f"{categoria}:"))
        assert (f"{mes} {cubiertos}/{esperados}" in linea) == (cubiertos < esperados), (categoria, mes)
    assert "PDFs pendientes: 0" in salida
    assert "en las 4 facturas (I1)" in salida


def test_cargar_dos_veces_no_cambia_nada(rutas, capsys):
    apoyo_carga.poner(rutas)
    _cargar(rutas)
    antes = _volcado(rutas)
    cargas = _consulta(rutas, "SELECT count(*) FROM carga")

    apoyo_carga.poner(rutas)
    codigo, salida = _cargar(rutas, capsys)

    assert codigo == 0
    assert f"{apoyo_carga.DISTINTOS + 3} duplicadas" in salida
    assert _volcado(rutas) == antes
    assert _consulta(rutas, "SELECT count(*) FROM carga") == cargas
    assert _nombres(rutas.entrada) == []


def test_ejecutar_cargar_sin_pdfs_no_hace_nada(rutas, capsys):
    codigo, salida = _cargar(rutas, capsys)
    assert codigo == 0
    assert "Resumen: 0 cargadas, 0 duplicadas, 0 rechazadas" in salida


def test_el_mismo_pdf_con_otro_nombre_es_un_duplicado(rutas):
    apoyo_carga.poner(rutas, "agua.pdf")
    _cargar(rutas)
    antes = _volcado(rutas)

    apoyo_carga.poner(rutas, "agua.pdf", como="otro_nombre.pdf")
    codigo, _ = _cargar(rutas)

    assert codigo == 0
    assert _nombres(rutas.duplicados) == ["otro_nombre.motivo.txt", "otro_nombre.pdf"]
    assert "mismo hash" in (rutas.duplicados / "otro_nombre.motivo.txt").read_text(encoding="utf-8")
    assert _volcado(rutas) == antes
    assert len(list(rutas.procesadas.rglob("*.pdf"))) == 1


def test_dos_pdfs_iguales_en_el_mismo_lote_cargan_uno_solo(rutas):
    apoyo_carga.poner(rutas, "agua.pdf")
    apoyo_carga.poner(rutas, "agua.pdf", como="agua_copia.pdf")
    _cargar(rutas)
    assert _consulta(rutas, "SELECT count(*) FROM factura") == [(1,)]
    assert len(_nombres(rutas.duplicados)) == 2


def test_la_misma_factura_en_otro_pdf_es_un_duplicado_de_factura(rutas):
    apoyo_carga.poner(rutas, "agua.pdf")
    _cargar(rutas)
    # Otro PDF (otro hash) que la extracción lee como la misma factura.
    (rutas.entrada / "agua_reescaneada.pdf").write_bytes((apoyo_carga.ejemplo("agua.pdf")).read_bytes() + b"\n%x")
    codigo, _ = _cargar(rutas)

    assert codigo == 0
    assert "agua_reescaneada.pdf" in _nombres(rutas.duplicados)
    assert _consulta(rutas, "SELECT estado, etapa_rechazo FROM carga ORDER BY carga_id") == [
        ("cargada", None), ("rechazada", "duplicado")]
    assert _consulta(rutas, "SELECT count(*) FROM factura") == [(1,)]


def test_un_pdf_de_formato_desconocido_va_a_pendientes_y_el_resto_se_carga(rutas, capsys):
    apoyo_carga.poner(rutas, "agua.pdf", "luz.pdf")
    (rutas.entrada / "desconocido.pdf").write_bytes(apoyo_carga.pdf_con_texto("Factura de un proveedor nuevo"))
    (rutas.entrada / "roto.pdf").write_bytes(b"esto no es un pdf")
    codigo, salida = _cargar(rutas, capsys)

    assert codigo == 1
    assert "2 cargadas" in salida and "2 rechazadas" in salida
    assert _nombres(rutas.pendientes) == ["desconocido.motivo.txt", "desconocido.pdf", "roto.motivo.txt", "roto.pdf"]
    motivo = (rutas.pendientes / "desconocido.motivo.txt").read_text(encoding="utf-8")
    assert "Etapa: formato" in motivo and "ningún parser reconoce" in motivo
    assert "no se pudo leer como PDF" in (rutas.pendientes / "roto.motivo.txt").read_text(encoding="utf-8")
    assert _consulta(rutas, "SELECT nombre_archivo, formato, etapa_rechazo, extraccion_json FROM carga "
                            "WHERE estado = 'rechazada' ORDER BY nombre_archivo") == [
        ("desconocido.pdf", None, "formato", None), ("roto.pdf", None, "formato", None)]
    assert _consulta(rutas, "SELECT count(*) FROM factura") == [(2,)]
    assert len(list(rutas.procesadas.rglob("*.pdf"))) == 2


def test_un_error_de_extraccion_deja_el_formato_pero_no_la_extraccion(rutas, monkeypatch):
    def falla(ruta):
        raise ErrorProceso("extraccion", "falta el campo obligatorio 'numero'", "aigues_agua", "1.0.0")

    monkeypatch.setattr(proceso, "extraer_pdf", falla)
    apoyo_carga.poner(rutas, "agua.pdf")
    assert _cargar(rutas)[0] == 1
    assert _consulta(rutas, "SELECT formato, version_parser, etapa_rechazo, extraccion_json FROM carga") == [
        ("aigues_agua", "1.0.0", "extraccion", None)]
    assert _nombres(rutas.pendientes) == ["agua.motivo.txt", "agua.pdf"]


def test_una_excepcion_inesperada_del_parser_es_un_rechazo_y_no_detiene_el_lote(rutas, monkeypatch):
    from facturas.parsers import aigues_agua

    def explota(documento):
        raise KeyError("columna")

    monkeypatch.setattr(aigues_agua, "extraer", explota)
    apoyo_carga.poner(rutas, "agua.pdf", "luz.pdf")
    assert _cargar(rutas)[0] == 1
    assert _consulta(rutas, "SELECT etapa_rechazo, motivo_rechazo FROM carga WHERE estado = 'rechazada'")[0][0] == "extraccion"
    assert "KeyError" in (rutas.pendientes / "agua.motivo.txt").read_text(encoding="utf-8")
    assert _consulta(rutas, "SELECT count(*) FROM factura") == [(1,)]


def _semillas_sin_el_alias_de_la_cuota_del_agua(tmp_path):
    destino = tmp_path / "semillas"
    shutil.copytree(construir_modulo.DIR_SEMILLAS, destino)
    archivo = destino / "alias_concepto.csv"
    lineas = archivo.read_text(encoding="utf-8").splitlines(keepends=True)
    quitada = [l for l in lineas if l.startswith("agua,cuota_servicio,")]
    assert len(quitada) == 1
    archivo.write_text("".join(l for l in lineas if l not in quitada), encoding="utf-8")
    return destino, quitada[0]


def test_un_texto_sin_alias_rechaza_la_factura_y_reprocesar_la_carga_al_agregarlo(rutas, tmp_path, capsys):
    semillas, fila = _semillas_sin_el_alias_de_la_cuota_del_agua(tmp_path)
    rutas = Rutas(rutas.raiz, semillas)
    rutas.base.unlink()
    construir_modulo.construir(rutas.base, semillas)
    apoyo_carga.poner(rutas, "agua.pdf", "luz.pdf")

    codigo, salida = _cargar(rutas, capsys)

    assert codigo == 1
    assert "etapa traduccion" in salida
    motivo = (rutas.pendientes / "agua.motivo.txt").read_text(encoding="utf-8")
    assert "Etapa: traduccion" in motivo and "Cuota del servicio" in motivo
    # Queda la extracción, para que un agente pueda proponer el alias; no queda ninguna fila de la factura.
    (extraccion,) = _consulta(rutas, "SELECT extraccion_json FROM carga WHERE etapa_rechazo = 'traduccion'")
    assert FacturaExtraida.desde_json(extraccion[0]).lineas
    assert _consulta(rutas, "SELECT count(*) FROM factura") == [(1,)]
    assert _consulta(rutas, "SELECT count(*) FROM contrato WHERE alias LIKE 'agua%'") == [(0,)]

    # Se agrega el alias a las semillas: la carga detecta que cambiaron y reconstruye antes de reintentar.
    archivo = semillas / "alias_concepto.csv"
    archivo.write_text(archivo.read_text(encoding="utf-8") + fila, encoding="utf-8")
    codigo = main(["reprocesar", "--pendientes"], rutas, espera=0)
    salida = capsys.readouterr().out

    assert codigo == 0
    assert "Cambiaron las semillas" in salida and "1 cargadas" in salida
    assert _nombres(rutas.pendientes) == []
    assert list(rutas.procesadas.glob("agua/2026/*.pdf"))
    assert _consulta(rutas, "SELECT count(*) FROM factura") == [(2,)]
    assert _consulta(rutas, "SELECT huella_semillas FROM construccion") == [(construir_modulo.huella_semillas(semillas),)]
    # La rechazada pasó a cargada en la misma fila de carga (R14).
    assert _consulta(rutas, "SELECT count(*) FROM carga") == [(2,)]


def test_un_invariante_roto_no_deja_nada_parcial_en_la_base(rutas, monkeypatch):
    monkeypatch.setattr(insercion, "verificar", lambda conexion, factura_id: ["I1: roto a propósito"])
    apoyo_carga.poner(rutas, "fibra_movil.pdf")  # dos contratos, mediciones y líneas derivadas

    assert _cargar(rutas)[0] == 1

    for tabla in ("factura", "linea", "medicion", "valor_atributo", "contrato"):
        assert _consulta(rutas, f"SELECT count(*) FROM {tabla}") == [(0,)], tabla
    assert _consulta(rutas, "SELECT estado, etapa_rechazo, motivo_rechazo FROM carga") == [
        ("rechazada", "invariantes", "I1: roto a propósito")]
    assert "I1: roto a propósito" in (rutas.pendientes / "fibra_movil.motivo.txt").read_text(encoding="utf-8")


def test_una_clave_foranea_rota_se_rechaza_antes_del_commit(rutas, monkeypatch):
    # Una línea con un concepto de otra categoría: las FK están diferidas, así que lo detecta I7 con las columnas.
    original = insercion.traducir
    monkeypatch.setattr(insercion, "traducir", lambda c, categoria, seccion, texto: original(c, "luz", None, "Consumo electricidad"))
    apoyo_carga.poner(rutas, "agua.pdf")

    assert _cargar(rutas)[0] == 1
    (etapa, motivo), = _consulta(rutas, "SELECT etapa_rechazo, motivo_rechazo FROM carga")
    assert etapa == "invariantes"
    assert "I5" in motivo or "linea → concepto (concepto_id, categoria_id)" in motivo
    assert _consulta(rutas, "SELECT count(*) FROM linea") == [(0,)]


def test_mas_de_tres_decimales_en_una_cantidad_es_un_rechazo_de_extraccion(base):
    factura = extraer(apoyo_carga.ejemplo("gas.pdf"))
    medicion = dataclasses.replace(factura.mediciones[0], cantidad="344.0005")
    factura = dataclasses.replace(factura, mediciones=(medicion,))

    with pytest.raises(ErrorCarga) as error:
        cargar_factura(base, factura, sha256="a" * 64, nombre_archivo="gas.pdf")

    assert error.value.etapa == "extraccion" and "más de 3 decimales" in error.value.motivo
    assert base.execute("SELECT count(*) FROM carga").fetchone() == (0,)


def test_las_cantidades_decimales_se_convierten_sin_perder_nada():
    assert insercion.milesimas("4.400", "x") == 4400
    assert insercion.milesimas("-0.344", "x") == -344
    assert insercion.milesimas("15577", "x") == 15577000
    assert insercion.milesimas("0.1", "x") == 100  # con float daría 100.00000000000001
    with pytest.raises(ErrorCarga):
        insercion.milesimas("1.0001", "x")


def test_un_proveedor_o_una_moneda_desconocidos_se_rechazan_con_un_motivo_legible(base):
    factura = extraer(apoyo_carga.ejemplo("agua.pdf"))
    with pytest.raises(ErrorCarga, match="proveedor desconocido: Z1234") as error:
        cargar_factura(base, dataclasses.replace(factura, identificador_fiscal="Z1234"), sha256="a" * 64, nombre_archivo="x.pdf")
    assert error.value.etapa == "traduccion"
    with pytest.raises(ErrorCarga, match="moneda no admitida: USD"):
        cargar_factura(base, dataclasses.replace(factura, moneda="USD"), sha256="b" * 64, nombre_archivo="x.pdf")
    assert base.execute("SELECT count(*) FROM carga").fetchone() == (0,)


def test_un_solape_se_rechaza_y_el_motivo_nombra_la_factura_con_la_que_choca(base):
    gas = extraer(apoyo_carga.ejemplo("gas.pdf"))
    cargar_factura(base, gas, sha256="a" * 64, nombre_archivo="gas.pdf")
    otra = dataclasses.replace(gas, numero="OTRA-1")

    with pytest.raises(ErrorCarga) as error:
        cargar_factura(base, otra, sha256="b" * 64, nombre_archivo="otra.pdf")

    assert error.value.etapa == "insercion"
    assert error.value.motivo.startswith("solape")
    assert f"con la factura {gas.numero} (2026-04-30 a 2026-06-25)" in error.value.motivo
    assert base.execute("SELECT count(*) FROM factura").fetchone() == (1,)


def test_contratos_nuevos_con_alias_por_defecto_que_no_choca_con_los_ajustes(base):
    agua = extraer(apoyo_carga.ejemplo("agua.pdf"))
    externo = agua.contratos[0].identificador_externo
    ajustes = [
        {"identificador_fiscal": agua.identificador_fiscal, "identificador_externo": "OTRO-CONTRATO", "alias": "agua 1"},
        {"identificador_fiscal": agua.identificador_fiscal, "identificador_externo": externo},
    ]
    cargar_factura(base, agua, sha256="a" * 64, nombre_archivo="agua.pdf", ajustes=ajustes)

    # "agua 1" está reservado para otro contrato: el nuevo toma "agua 2". Un ajuste sin campos no cambia nada.
    assert base.execute("SELECT alias FROM contrato").fetchall() == [("agua 2",)]


def test_un_ajuste_de_alias_se_aplica_al_registrar_el_contrato(base):
    agua = extraer(apoyo_carga.ejemplo("agua.pdf"))
    ajustes = [{"identificador_fiscal": agua.identificador_fiscal,
                "identificador_externo": agua.contratos[0].identificador_externo, "alias": "casa"}]
    cargar_factura(base, agua, sha256="a" * 64, nombre_archivo="agua.pdf", ajustes=ajustes)
    assert base.execute("SELECT alias FROM contrato").fetchall() == [("casa",)]


def test_un_contrato_que_ya_existe_conserva_su_alias(base):
    gas = extraer(apoyo_carga.ejemplo("gas.pdf"))
    cargar_factura(base, gas, sha256="a" * 64, nombre_archivo="gas.pdf")
    base.execute("UPDATE contrato SET alias = 'cocina'")
    ajuste = extraer(apoyo_carga.ejemplo("gas_ajuste.pdf"))
    cargar_factura(base, ajuste, sha256="b" * 64, nombre_archivo="ajuste.pdf")
    assert base.execute("SELECT alias FROM contrato").fetchall() == [("cocina",)]
    assert base.execute("SELECT count(*) FROM factura").fetchone() == (2,)


def _con_abono(factura, numero, corrige, emision):
    """El abono que anula entera `factura`: las mismas líneas y cantidades con el signo cambiado."""
    return dataclasses.replace(
        factura, numero=numero, tipo="abono", numero_factura_corregida=corrige, fecha_emision=emision,
        importe_total_centimos=-factura.importe_total_centimos,
        lineas=tuple(dataclasses.replace(l, importe_centimos=-l.importe_centimos) for l in factura.lineas),
        mediciones=tuple(dataclasses.replace(
            m, cantidad=str(-Decimal(m.cantidad)),
            cantidad_contador=None if m.cantidad_contador is None else str(-Decimal(m.cantidad_contador)))
            for m in factura.mediciones),
    )


def _falsificar_extraccion(monkeypatch, facturas):
    """Hace que los PDFs de prueba (cualquier contenido) se lean como las facturas dadas, por nombre."""
    monkeypatch.setattr(proceso, "extraer_pdf", lambda ruta: facturas[ruta.name])


def _pdf_falso(rutas, nombre):
    (rutas.entrada / nombre).write_bytes(f"contenido de {nombre}".encode())


def test_un_solape_se_reintenta_al_final_del_lote_cuando_llega_el_abono(rutas, monkeypatch):
    gas = extraer(apoyo_carga.ejemplo("gas.pdf"))
    refacturada = dataclasses.replace(gas, numero="REFACTURA-1", fecha_emision="2026-07-01")
    abono = _con_abono(gas, "ABONO-1", gas.numero, "2026-07-02")
    _falsificar_extraccion(monkeypatch, {"a.pdf": gas, "b.pdf": refacturada, "c.pdf": abono})
    for nombre in ("a.pdf", "b.pdf", "c.pdf"):
        _pdf_falso(rutas, nombre)

    # Por fecha de emisión se carga primero la original, luego la refacturación (que choca) y por último el abono.
    assert _cargar(rutas)[0] == 0

    assert _nombres(rutas.pendientes) == []
    assert _consulta(rutas, "SELECT numero, tipo FROM factura ORDER BY numero") == [
        ("ABONO-1", "abono"), (gas.numero, "ordinaria"), ("REFACTURA-1", "ordinaria")]
    # Vigente: solo la refacturación (la original y el abono se anulan entre sí).
    assert _consulta(rutas, "SELECT numero FROM v_factura_vigente") == [("REFACTURA-1",)]


def test_un_solape_que_no_se_resuelve_queda_en_pendientes_con_su_motivo(rutas, monkeypatch):
    gas = extraer(apoyo_carga.ejemplo("gas.pdf"))
    otra = dataclasses.replace(gas, numero="OTRA-1", fecha_emision="2026-07-01")
    _falsificar_extraccion(monkeypatch, {"a.pdf": gas, "b.pdf": otra})
    _pdf_falso(rutas, "a.pdf")
    _pdf_falso(rutas, "b.pdf")

    assert _cargar(rutas)[0] == 1

    assert _nombres(rutas.pendientes) == ["b.motivo.txt", "b.pdf"]
    motivo = (rutas.pendientes / "b.motivo.txt").read_text(encoding="utf-8")
    assert "Etapa: insercion" in motivo and f"factura {gas.numero}" in motivo


def test_el_orden_del_lote_es_por_fecha_de_emision_y_luego_por_ruta(rutas, monkeypatch):
    agua = extraer(apoyo_carga.ejemplo("agua.pdf"))
    # Dos facturas con la misma fecha de emisión y períodos distintos: se cargan por nombre de archivo.
    segunda = dataclasses.replace(
        agua, numero="AGUA-2", periodo=dataclasses.replace(agua.periodo, inicio="2026-06-09", fin="2026-08-07"),
        lineas=tuple(dataclasses.replace(l, periodo=None) for l in agua.lineas))
    primera = dataclasses.replace(
        agua, numero="AGUA-0", fecha_emision="2026-06-01",
        periodo=dataclasses.replace(agua.periodo, inicio="2026-02-09", fin="2026-04-09"))
    _falsificar_extraccion(monkeypatch, {"z.pdf": agua, "a.pdf": segunda, "m.pdf": primera})
    for nombre in ("z.pdf", "a.pdf", "m.pdf"):
        _pdf_falso(rutas, nombre)
    _cargar(rutas)
    assert _consulta(rutas, "SELECT c.nombre_archivo FROM carga AS c JOIN factura AS f USING (carga_id) "
                            "ORDER BY f.factura_id") == [("m.pdf",), ("a.pdf",), ("z.pdf",)]


def test_reprocesar_todo_produce_exactamente_el_mismo_contenido(rutas, capsys):
    apoyo_carga.poner(rutas)
    _cargar(rutas)
    antes = _volcado(rutas)
    procesadas = _nombres(rutas.procesadas)
    lector = conectar(rutas.base, "lectura")  # un dashboard abierto no impide reconstruir
    lector.execute("SELECT count(*) FROM factura").fetchone()
    capsys.readouterr()

    codigo = main(["reprocesar", "--todo"], rutas, espera=0)

    assert codigo == 0
    assert f"Base reconstruida con {apoyo_carga.DISTINTOS} facturas" in capsys.readouterr().out
    assert _volcado(rutas) == antes  # incluye los nombres originales de los PDFs (carga.nombre_archivo)
    assert _nombres(rutas.procesadas) == procesadas
    assert lector.execute("SELECT count(*) FROM factura").fetchone() == (apoyo_carga.DISTINTOS,)
    lector.close()
    # La base quedó usable por la carga.
    conectar(rutas.base, "escritura").close()
    assert not rutas.base.with_name("facturas.db.nueva").exists()


def test_reconstruir_aplica_los_datos_manuales(rutas):
    apoyo_carga.poner(rutas, "agua.pdf")
    _cargar(rutas)
    agua = extraer(next(rutas.procesadas.rglob("*.pdf")))
    rutas.ajustes.write_text(json.dumps([{
        "identificador_fiscal": agua.identificador_fiscal,
        "identificador_externo": agua.contratos[0].identificador_externo, "alias": "casa"}]),
        encoding="utf-8")

    assert main(["reprocesar", "--todo"], rutas, espera=0) == 0
    assert _consulta(rutas, "SELECT alias FROM contrato") == [("casa",)]


def test_si_un_pdf_no_se_puede_reconstruir_la_base_anterior_queda_intacta(rutas, capsys):
    apoyo_carga.poner(rutas, "agua.pdf", "luz.pdf")
    _cargar(rutas)
    antes = _volcado(rutas)
    roto = next(rutas.procesadas.glob("luz/*/*.pdf"))
    roto.write_bytes(b"ya no es un pdf")
    capsys.readouterr()

    codigo = main(["reprocesar", "--todo"], rutas, espera=0)

    assert codigo == 2
    texto = capsys.readouterr().err
    assert roto.name in texto and "la anterior sigue como estaba" in texto
    assert _volcado(rutas) == antes
    assert not rutas.base.with_name("facturas.db.nueva").exists()


def test_una_base_de_otra_version_se_reconstruye_desde_los_pdfs_procesados(rutas, capsys):
    apoyo_carga.poner(rutas, "agua.pdf")
    _cargar(rutas)
    antes = _volcado(rutas)
    otra = sqlite3.connect(rutas.base)
    otra.execute("PRAGMA user_version = 99")
    otra.close()
    capsys.readouterr()

    assert _cargar(rutas, capsys)[0] == 0

    assert _volcado(rutas) == antes
    conectar(rutas.base, "escritura").close()


def test_si_falta_la_base_se_reconstruye_con_los_pdfs_procesados(rutas):
    apoyo_carga.poner(rutas, "agua.pdf", "gas.pdf")
    _cargar(rutas)
    antes = _volcado(rutas)
    for sufijo in ("", "-wal", "-shm"):
        rutas.base.with_name("facturas.db" + sufijo).unlink(missing_ok=True)

    assert _cargar(rutas)[0] == 0
    despues = _volcado(rutas)
    # Sin la base anterior no hay de dónde sacar el nombre original de cada PDF: queda el de procesadas/.
    assert [(f[0], *f[2:]) for f in despues["carga"]] == [(f[0], *f[2:]) for f in antes["carga"]]
    assert {tabla: filas for tabla, filas in despues.items() if tabla != "carga"} == {
        tabla: filas for tabla, filas in antes.items() if tabla != "carga"}


def test_reconstruir_con_un_lector_abierto_en_otro_proceso(rutas):
    """Con el dashboard abierto, os.replace falla y copiar el archivo deja la base vieja: se usa la API de backup."""
    import subprocess
    import sys

    apoyo_carga.poner(rutas, "agua.pdf", "gas.pdf")
    _cargar(rutas)
    antes = _volcado(rutas)
    lector = (
        "import sys; sys.path.insert(0, 'src')\n"
        "from pathlib import Path\n"
        "from facturas.bd.conexion import conectar\n"
        "c = conectar(Path(sys.argv[1]), 'lectura')\n"
        "c.execute('BEGIN')\n"
        "print(c.execute('SELECT count(*) FROM factura').fetchone()[0], flush=True)\n"
        "sys.stdin.readline()\n"
        "print(c.execute('SELECT count(*) FROM factura').fetchone()[0], flush=True)\n"
    )
    proceso_lector = subprocess.Popen(
        [sys.executable, "-c", lector, str(rutas.base)], cwd=apoyo_carga.DIR_EJEMPLOS.parent,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    try:
        assert proceso_lector.stdout.readline().strip() == "2"  # el lector tiene una transacción abierta

        assert main(["reprocesar", "--todo"], rutas, espera=0) == 0

        proceso_lector.stdin.write("\n")
        proceso_lector.stdin.flush()
        # Su transacción sigue viendo la foto que tenía: no se rompió.
        assert proceso_lector.stdout.readline().strip() == "2"
    finally:
        proceso_lector.stdin.close()
        proceso_lector.wait(timeout=30)
    assert _volcado(rutas) == antes


def test_si_la_reconstruccion_por_cambio_de_semillas_falla_el_lote_no_procesa_nada(rutas, tmp_path, capsys):
    semillas = tmp_path / "semillas"
    shutil.copytree(construir_modulo.DIR_SEMILLAS, semillas)
    rutas = Rutas(rutas.raiz, semillas)
    apoyo_carga.poner(rutas, "agua.pdf")
    _cargar(rutas)
    antes = _volcado(rutas)
    # Cambian las semillas y, a la vez, un PDF ya procesado deja de poder leerse.
    archivo = semillas / "alias_concepto.csv"
    archivo.write_text(archivo.read_text(encoding="utf-8") + "agua,tmtr,*,*alias nuevo*\n", encoding="utf-8")
    next(rutas.procesadas.rglob("*.pdf")).write_bytes(b"ya no es un pdf")
    apoyo_carga.poner(rutas, "luz.pdf")
    capsys.readouterr()

    assert main(["cargar"], rutas, espera=0) == 2

    assert "la anterior sigue como estaba" in capsys.readouterr().err
    assert [p.name for p in rutas.entrada.iterdir()] == ["luz.pdf"]  # no se procesó nada
    assert _volcado(rutas) == antes
