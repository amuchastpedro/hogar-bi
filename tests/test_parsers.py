"""Parsers: cada PDF de ejemplo contra los valores esperados del caso (`caso_hogar.md`).

Los PDFs de `ejemplos/` están fuera de git: si no están, los tests que los usan se saltan.
Las líneas se comparan con el caso por importe y por el concepto al que las
lleva la traducción de las semillas, que es independiente de los parsers. Dos desvíos aprobados
en el bloque 1 se aplican al caso: D2 (el canon del agua es una sola línea) y D5 (cada medición
guarda solo su lectura de cierre, así que las lecturas anteriores no se comparan).
"""

import json
import re
from decimal import Decimal
from pathlib import Path

import pytest
from pypdf import PdfWriter

import caso
from facturas import parsers
from facturas.carga.traduccion import traducir
from facturas.extraccion import ErrorExtraccion, FacturaExtraida
from facturas.parsers import aigues_agua, digi_convergente, naturgy_gas, naturgy_luz
from facturas.parsers.pdf import Documento, leer

RAIZ = Path(__file__).resolve().parents[1]
DIR_EJEMPLOS = RAIZ / "ejemplos"
EJEMPLOS = {
    "agua": aigues_agua, "gas": naturgy_gas, "luz": naturgy_luz, "fibra_movil": digi_convergente,
}
ARCHIVO_IDENTIFICADORES = DIR_EJEMPLOS / "identificadores_esperados.json"

# Formato de los identificadores, por categoría de contrato y para el número de factura.
FORMATO_NUMERO = {
    "agua": r"\d{11}", "gas": r"FE\d{14}", "luz": r"FE\d{14}", "fibra_movil": r"DGFC\d{10}",
}
FORMATO_CONTRATO = {
    "agua": r"\d{7}", "gas": r"ES\d{16}[A-Z]{2}", "luz": r"ES\d{16}[A-Z]{2}",
    "movil": r"\d{9}", "fibra": r"D\d{11}",
}


def _pdf(nombre: str) -> Path:
    ruta = DIR_EJEMPLOS / f"{nombre}.pdf"
    if not ruta.exists():
        pytest.skip(f"falta ejemplos/{nombre}.pdf: los PDFs de ejemplo no se versionan")
    return ruta


@pytest.fixture(scope="module")
def documentos():
    """El texto de cada ejemplo, leído una vez por módulo."""
    return {}


def documento(documentos, nombre: str) -> Documento:
    if nombre not in documentos:
        documentos[nombre] = leer(_pdf(nombre))
    return documentos[nombre]


def extraida(documentos, nombre: str) -> FacturaExtraida:
    doc = documento(documentos, nombre)
    return parsers.reconocer(doc).extraer(doc)


def _decimal_es(texto: str) -> Decimal:
    return Decimal(texto.replace(".", "").replace(",", "."))


# --- Cabecera y líneas contra el caso ---------------------------------------------------


@pytest.mark.parametrize("nombre", EJEMPLOS)
def test_cabecera_contra_el_caso(documentos, nombre):
    esperado = caso.valores_esperados()[nombre]
    factura = extraida(documentos, nombre)
    assert factura.formato == esperado["formato"] == EJEMPLOS[nombre].FORMATO
    assert factura.version_parser == EJEMPLOS[nombre].VERSION
    assert factura.tipo == "ordinaria" and factura.numero_factura_corregida is None
    assert factura.moneda == "EUR"
    assert (factura.periodo.inicio, factura.periodo.fin) == (esperado["inicio"], esperado["fin"])
    assert factura.fecha_emision == esperado["emision"]
    assert factura.fecha_vencimiento == esperado["vencimiento"]
    assert factura.importe_total_centimos == esperado["total"]


def _filas_esperadas(nombre: str) -> list[dict]:
    """Las filas del caso, con D2: el canon (parte fija y variable) es una sola línea."""
    filas = []
    for fila in caso.valores_esperados()[nombre]["filas"]:
        importe = caso._centimos(fila["Importe"])
        if filas and fila["Concepto"].startswith("Canon") and filas[-1]["Concepto"].startswith("Canon"):
            filas[-1] = {**filas[-1], "importe": filas[-1]["importe"] + importe}
            continue
        concepto = "Canon" if fila["Concepto"].startswith("Canon") else fila["Concepto"]
        filas.append({**fila, "Concepto": concepto, "importe": importe})
    return filas


@pytest.mark.parametrize("nombre", EJEMPLOS)
def test_lineas_contra_el_caso(documentos, base, nombre):
    factura = extraida(documentos, nombre)
    esperadas = _filas_esperadas(nombre)
    assert [linea.importe_centimos for linea in factura.lineas] == [f["importe"] for f in esperadas]

    categorias = {c.identificador_externo: c.categoria for c in factura.contratos}
    conceptos = []
    for linea, fila in zip(factura.lineas, esperadas, strict=True):
        categoria = categorias[linea.contrato]
        concepto_id = traducir(base, categoria, linea.seccion, linea.texto)
        assert categoria == fila.get("Contrato", categoria), linea.texto
        assert (linea.derivada_de is not None) == ("(derivada)" in fila["Texto en el PDF"]), linea.texto
        conceptos.append((categoria, fila["Concepto"], concepto_id))
    # Cada concepto del caso es un concepto de las semillas, y cada concepto de las semillas, uno del caso.
    assert len({(c, n) for c, n, _ in conceptos}) == len({(c, i) for c, _, i in conceptos}) == len(set(conceptos))


def test_el_texto_de_las_lineas_es_el_impreso_sin_espacios_de_mas(documentos):
    for nombre in EJEMPLOS:
        for linea in extraida(documentos, nombre).lineas:
            assert linea.texto == " ".join(linea.texto.split()) and linea.texto


def test_digi_marca_las_derivadas_y_reparte_el_iva(documentos):
    factura = extraida(documentos, "fibra_movil")
    esperado = caso.valores_esperados()["fibra_movil"]
    iva = caso._centimos(re.search(r"IVA ([\d.,]+)\)", esperado["texto"])[1])
    assert [(t.texto, t.importe_centimos) for t in factura.totales_repartidos] == [("IMPUESTOS (21.00% IVA)", iva)]
    derivadas = [linea for linea in factura.lineas if linea.derivada_de]
    assert [linea.importe_centimos for linea in derivadas] == [
        caso._centimos(fila["Importe"]) for fila in esperado["filas"] if "(derivada)" in fila["Texto en el PDF"]]
    assert [linea.seccion for linea in factura.lineas] == [
        "PRODUCTOS", "CONSUMO INCLUIDO EN EL PLAN", "CONSUMO ADICIONAL", None, "PRODUCTOS", None,
    ]
    assert factura.mediciones == ()
    assert [c.categoria for c in factura.contratos] == ["movil", "fibra"]


# --- Mediciones y atributos contra la prosa del caso ----------------------------------


def test_medicion_del_agua(documentos):
    texto = caso.valores_esperados()["agua"]["texto"]
    cantidad = re.search(r"Mediciones: (\d+) m³", texto)[1]
    lectura, fecha, tipo = re.search(r"actual (\d+) \(([\d-]+)\), (\w+)", texto).groups()
    (medicion,) = extraida(documentos, "agua").mediciones
    assert (medicion.magnitud, medicion.franja) == ("volumen", None)
    assert medicion.cantidad == cantidad and medicion.cantidad_contador is None
    assert (medicion.lectura.valor, medicion.lectura.fecha, medicion.lectura.tipo) == (lectura, fecha, "real")
    assert tipo == "real"


def test_medicion_del_gas(documentos):
    texto = caso.valores_esperados()["gas"]["texto"]
    kwh, m3, factor = re.search(r"Mediciones: (\d+) kWh = (\d+) m³ × ([\d,]+) kWh/m³", texto).groups()
    lectura, fecha, tipo = re.search(r"actual ([\d.]+) m³ \(([\d-]+), \**(\w+?)\**\)", texto).groups()
    (medicion,) = extraida(documentos, "gas").mediciones
    assert (medicion.magnitud, medicion.franja) == ("energia", None)
    assert medicion.cantidad == kwh and medicion.cantidad_contador == m3
    assert Decimal(medicion.factor_conversion) == _decimal_es(factor)
    assert Decimal(medicion.lectura.valor) == _decimal_es(lectura)
    assert (medicion.lectura.fecha, medicion.lectura.tipo) == (fecha, "estimada")
    assert tipo == "estimada"


def test_mediciones_y_potencias_de_la_luz(documentos):
    texto = caso.valores_esperados()["luz"]["texto"]
    fecha = re.search(r"lectura del ([\d-]+)", texto)[1]
    esperadas = {f.lower(): kwh for f, kwh in re.findall(r"(punta|llano|valle) (\d+) kWh", texto, re.IGNORECASE)}
    factura = extraida(documentos, "luz")
    assert {m.franja: m.cantidad for m in factura.mediciones} == esperadas
    assert all(m.lectura.fecha == fecha and m.lectura.tipo == "real" for m in factura.mediciones)
    assert all(m.cantidad_contador is None for m in factura.mediciones)
    p1, p2 = re.search(r"([\d,]+) kW en P1 y ([\d,]+) kW en P2", texto).groups()
    atributos = {a.atributo: Decimal(a.valor) for a in factura.contratos[0].atributos}
    assert atributos == {"potencia_p1": _decimal_es(p1), "potencia_p2": _decimal_es(p2)}


# --- Identificadores --------------------------------------------------------------------


@pytest.mark.parametrize("nombre", EJEMPLOS)
def test_identificadores_con_el_formato_esperado(documentos, nombre):
    factura = extraida(documentos, nombre)
    assert re.fullmatch(FORMATO_NUMERO[nombre], factura.numero)
    for contrato in factura.contratos:
        assert re.fullmatch(FORMATO_CONTRATO[contrato.categoria], contrato.identificador_externo)
    assert factura.identificador_fiscal == EJEMPLOS[nombre].IDENTIFICADOR_FISCAL


@pytest.mark.parametrize("nombre", EJEMPLOS)
def test_identificadores_exactos_si_existe_el_archivo_local(documentos, nombre):
    if not ARCHIVO_IDENTIFICADORES.exists():
        pytest.skip("falta ejemplos/identificadores_esperados.json (archivo local, fuera de git)")
    esperado = json.loads(ARCHIVO_IDENTIFICADORES.read_text(encoding="utf-8"))[nombre]
    factura = extraida(documentos, nombre)
    assert factura.numero == esperado["numero"]
    assert {c.categoria: c.identificador_externo for c in factura.contratos} == esperado["contratos"]


# --- Reconocimiento ---------------------------------------------------------------------


@pytest.mark.parametrize("nombre", EJEMPLOS)
def test_cada_parser_reconoce_solo_su_ejemplo(documentos, nombre):
    doc = documento(documentos, nombre)
    assert [p.FORMATO for p in parsers.PARSERS if p.reconoce(doc)] == [EJEMPLOS[nombre].FORMATO]
    assert parsers.reconocer(doc) is EJEMPLOS[nombre]


def test_extraer_desde_la_ruta_del_pdf(documentos):
    assert parsers.extraer(_pdf("gas")) == extraida(documentos, "gas")


def test_un_documento_de_otro_formato_no_lo_reconoce_ningun_parser():
    ajeno = Documento(texto="Factura de otra empresa. NIF B12345678. Total a pagar 10,00 €", diseno="")
    assert not any(p.reconoce(ajeno) for p in parsers.PARSERS)
    with pytest.raises(ErrorExtraccion, match="ningún parser"):
        parsers.reconocer(ajeno)


def test_el_nif_de_un_proveedor_conocido_sin_la_marca_del_documento_no_alcanza():
    # Naturgy figura con su NIF, pero ni de gas ni de luz: ningún parser lo toma.
    assert not any(p.reconoce(Documento("Naturgy Clientes NIF A 67760876. Contrato de servicios.", "")) for p in parsers.PARSERS)


def test_un_documento_que_reconocen_dos_parsers_es_un_error(monkeypatch):
    monkeypatch.setattr(parsers, "PARSERS", (naturgy_gas, naturgy_gas))
    doc = Documento("NIF A 67760876. Período gas del 30/04/2026 al 25/06/2026", "")
    with pytest.raises(ErrorExtraccion, match="varios parsers"):
        parsers.reconocer(doc)


# --- PDFs vacíos o dañados --------------------------------------------------------------


def test_pdf_danado_vacio_o_sin_texto_da_un_error_claro(tmp_path):
    inexistente = tmp_path / "no_existe.pdf"
    vacio = tmp_path / "vacio.pdf"
    vacio.write_bytes(b"")
    basura = tmp_path / "basura.pdf"
    basura.write_bytes(b"%PDF-1.4 esto no es un pdf")
    en_blanco = tmp_path / "en_blanco.pdf"
    escritor = PdfWriter()
    escritor.add_blank_page(200, 200)
    with en_blanco.open("wb") as archivo:
        escritor.write(archivo)

    for ruta, fragmento in ((inexistente, "no existe"), (vacio, "no se pudo leer"), (basura, "no se pudo leer"),
                            (en_blanco, "no tiene texto")):
        with pytest.raises(ErrorExtraccion, match=fragmento) as error:
            parsers.extraer(ruta)
        assert ruta.name in str(error.value)


# --- Errores explícitos ante cambios del documento --------------------------------------


def modificada(doc: Documento, anterior: str, nuevo: str) -> Documento:
    """El documento con un texto cambiado, en las dos formas; el cambio tiene que existir en alguna."""
    if anterior not in doc.texto and anterior not in doc.diseno:
        raise AssertionError(f"el texto {anterior!r} no está en el documento: el test está desactualizado")
    return Documento(doc.texto.replace(anterior, nuevo), doc.diseno.replace(anterior, nuevo))


FALLAS = {
    "agua sin fecha de emisión": ("agua", "Fecha emisi", "Fecha de", "aigues_agua.*fecha_emision"),
    "agua con promedios de 61 días": ("agua", "de 250", "de 246", "aigues_agua.*promedios"),
    "gas sin período": ("gas", " al 25/06/2026", " a 25/06/2026", "naturgy_gas.*periodo"),
    "gas sin factor de conversión": ("gas", "11,470", "—", "naturgy_gas.*lectura de cierre"),
    "gas con días que no son los del período": ("gas", "57 días\nPeríodo", "58 días\nPeríodo", "naturgy_gas.*imprime 58"),
    "luz con una franja menos": ("luz", "Valle real", "Valle", "naturgy_luz.*franjas"),
    "luz sin potencia contratada": ("luz", "Potencia contratada P2", "Potencia", "naturgy_luz.*potencia_p2"),
    "digi sin fecha de vencimiento": ("fibra_movil", "Fecha de vencimiento", "Vence", "digi_convergente.*fecha_vencimiento"),
}


@pytest.mark.parametrize("nombre, anterior, nuevo, patron", FALLAS.values(), ids=FALLAS.keys())
def test_un_cambio_en_el_documento_falla_nombrando_campo_y_formato(documentos, nombre, anterior, nuevo, patron):
    cambiado = modificada(documento(documentos, nombre), anterior, nuevo)
    with pytest.raises(ErrorExtraccion, match=patron):
        EJEMPLOS[nombre].extraer(cambiado)


# Un importe impreso con un céntimo más. El importe sale de la fila del caso (`ejemplos/valores_esperados.md`),
# y la plantilla dice cómo aparece en el documento.
IMPORTES_QUE_NO_CUADRAN = {
    "agua con un tramo que no suma su subtotal": ("agua", "Tramo hasta 12 m³ (consumo)", "{}", "aigues_agua.*suma"),
    "luz con un importe que no cuadra": ("luz", "Consumo electricidad", "{} €", "naturgy_luz.*suman"),
}


def _importe_del_caso(nombre: str, texto: str) -> str:
    return next(f["Importe"] for f in caso.valores_esperados()[nombre]["filas"] if f["Texto en el PDF"] == texto)


@pytest.mark.parametrize("nombre, fila, plantilla, patron", IMPORTES_QUE_NO_CUADRAN.values(),
                         ids=IMPORTES_QUE_NO_CUADRAN.keys())
def test_un_importe_que_no_cuadra_falla_nombrando_campo_y_formato(documentos, nombre, fila, plantilla, patron):
    importe = _importe_del_caso(nombre, fila)
    cambiado = modificada(documento(documentos, nombre), plantilla.format(importe),
                          plantilla.format(caso.mas_centimos(importe)))
    with pytest.raises(ErrorExtraccion, match=patron):
        EJEMPLOS[nombre].extraer(cambiado)


def test_digi_rechaza_un_servicio_cuyas_lineas_no_suman_su_total(documentos):
    sms = _importe_del_caso("fibra_movil", "SMS (consumo adicional)")
    cambiado = modificada(documento(documentos, "fibra_movil"), f"SMS 1 {sms} €", f"SMS 1 {caso.mas_centimos(sms)} €")
    with pytest.raises(ErrorExtraccion, match="digi_convergente.*no suman"):
        digi_convergente.extraer(cambiado)


def test_digi_rechaza_una_linea_fuera_de_las_secciones(documentos):
    cambiado = modificada(documento(documentos, "fibra_movil"), "PRODUCTOS___", "XX___")
    with pytest.raises(ErrorExtraccion, match="digi_convergente"):
        digi_convergente.extraer(cambiado)


def test_digi_limpia_los_rotulos_subrayados_con_guiones_intercalados(documentos):
    cambiado = modificada(documento(documentos, "fibra_movil"), "PRODUCTOS___", "P__R_O__D__U_C__T_O__S___")
    secciones = {linea.seccion for linea in digi_convergente.extraer(cambiado).lineas}
    assert "PRODUCTOS" in secciones


def test_digi_rechaza_un_servicio_que_no_es_movil_ni_fibra(documentos):
    cambiado = modificada(documento(documentos, "fibra_movil"), "Identificador Fibra Digi", "Identificador Fibra Otro")
    with pytest.raises(ErrorExtraccion, match="digi_convergente.*identificador de fibra"):
        digi_convergente.extraer(cambiado)


@pytest.mark.parametrize("nombre", EJEMPLOS)
def test_una_rectificativa_o_un_abono_se_rechaza(documentos, nombre):
    doc = documento(documentos, nombre)
    rectificativa = Documento(doc.texto + "\nFACTURA RECTIFICATIVA", doc.diseno)
    with pytest.raises(ErrorExtraccion, match=f"{EJEMPLOS[nombre].FORMATO}.*rectificativa"):
        EJEMPLOS[nombre].extraer(rectificativa)
