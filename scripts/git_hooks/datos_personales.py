"""Hook pre-commit: bloquea commits que contienen datos personales.

Revisa el contenido preparado (staged) de los archivos que se van a commitear y busca:

1. Los patrones que lista el archivo de caso: DNI/NIE, IBAN, CUPS, teléfonos
   españoles y emails.
2. Los valores literales de la lista local `datos/datos_privados.txt` (fuera de
   git): nombre, dirección y números de contrato, de cliente o de factura, que no
   tienen un formato reconocible. Un valor por línea; `#` empieza un comentario.

Deja pasar los identificadores fiscales de los proveedores conocidos, que se leen
de las semillas (`src/facturas/semillas/proveedor.csv`).

Solo usa la biblioteca estándar, para funcionar sin el entorno virtual.
Termina con código 1 si encuentra algo, y 0 si no.
"""

import csv
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

ARCHIVO_PROVEEDORES = Path("src/facturas/semillas/proveedor.csv")
ARCHIVO_PRIVADOS = Path("datos/datos_privados.txt")

# Un identificador no puede estar pegado a otra letra o dígito: así no se detectan
# trozos de hashes ni de números más largos.
_ANTES = r"(?<![0-9A-Za-z])"
_DESPUES = r"(?![0-9A-Za-z])"

PATRONES = {
    "DNI": re.compile(_ANTES + r"\d{8}[- ]?[A-HJ-NP-TV-Z]" + _DESPUES, re.IGNORECASE),
    "NIE": re.compile(_ANTES + r"[XYZ][- ]?\d{7}[- ]?[A-Z]" + _DESPUES, re.IGNORECASE),
    "IBAN": re.compile(_ANTES + r"ES[0-9*]{2}(?:[ -]?[0-9*]{4}){5}" + _DESPUES, re.IGNORECASE),
    "CUPS": re.compile(
        _ANTES + r"ES ?\d{4} ?\d{4} ?\d{4} ?\d{4} ?[A-Z]{2}(?:\d[FPCRXYZ])?" + _DESPUES,
        re.IGNORECASE,
    ),
    "teléfono": re.compile(r"(?<![0-9])(?:(?:\+|00)34[ -]?)?[6789](?:[ -]?\d){8}(?![0-9])"),
    "email": re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"),
}


def normalizar(texto: str) -> str:
    """Minúsculas, sin tildes y con los espacios colapsados."""
    sin_tildes = unicodedata.normalize("NFKD", texto)
    sin_tildes = "".join(c for c in sin_tildes if not unicodedata.combining(c))
    return " ".join(sin_tildes.lower().split())


def solo_alfanumerico(texto: str) -> str:
    return re.sub(r"[^0-9A-Za-z]", "", texto).upper()


def identificadores_permitidos(raiz: Path) -> set[str]:
    archivo = raiz / ARCHIVO_PROVEEDORES
    if not archivo.exists():
        return set()
    with archivo.open(encoding="utf-8", newline="") as f:
        return {solo_alfanumerico(fila["identificador_fiscal"]) for fila in csv.DictReader(f)}


def valores_privados(raiz: Path) -> list[re.Pattern]:
    archivo = raiz / ARCHIVO_PRIVADOS
    if not archivo.exists():
        return []
    patrones = []
    for linea in archivo.read_text(encoding="utf-8").splitlines():
        valor = normalizar(linea.split("#", 1)[0])
        if valor:
            patrones.append(re.compile(_ANTES + re.escape(valor) + _DESPUES))
    return patrones


def enmascarar(valor: str) -> str:
    """Muestra solo los extremos, para no repetir el dato completo en la consola."""
    valor = valor.strip()
    if len(valor) <= 4:
        return "*" * len(valor)
    return valor[:2] + "*" * (len(valor) - 4) + valor[-2:]


def buscar(texto: str, permitidos: set[str], privados: list[re.Pattern]) -> list[tuple[int, str, str]]:
    """Devuelve (número de línea, tipo, valor enmascarado) por cada hallazgo."""
    hallazgos = []
    for numero, linea in enumerate(texto.splitlines(), start=1):
        for tipo, patron in PATRONES.items():
            for coincidencia in patron.finditer(linea):
                if solo_alfanumerico(coincidencia.group()) in permitidos:
                    continue
                hallazgos.append((numero, tipo, enmascarar(coincidencia.group())))
        linea_normalizada = normalizar(linea)
        for patron in privados:
            for coincidencia in patron.finditer(linea_normalizada):
                hallazgos.append((numero, "valor privado", enmascarar(coincidencia.group())))
    return hallazgos


def git(*argumentos: str) -> bytes:
    return subprocess.run(["git", *argumentos], check=True, capture_output=True).stdout


def archivos_preparados() -> list[str]:
    salida = git("diff", "--cached", "--name-only", "-z", "--diff-filter=ACMR")
    return [nombre for nombre in salida.decode("utf-8").split("\0") if nombre]


def contenido_preparado(nombre: str) -> str | None:
    """Contenido del archivo tal como se va a commitear; None si es binario."""
    datos = git("show", f":{nombre}")
    if b"\0" in datos:
        return None
    return datos.decode("utf-8", errors="replace")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raiz = Path(git("rev-parse", "--show-toplevel").decode("utf-8").strip())
    permitidos = identificadores_permitidos(raiz)
    # En un worktree (plan B) no hay `datos/`: la lista privada está en la copia de trabajo principal.
    principal = Path(git("rev-parse", "--path-format=absolute", "--git-common-dir").decode("utf-8").strip()).parent
    privados = valores_privados(raiz) or valores_privados(principal)

    encontrados = []
    for nombre in archivos_preparados():
        texto = contenido_preparado(nombre)
        if texto is None:
            continue
        for numero, tipo, valor in buscar(texto, permitidos, privados):
            encontrados.append(f"  {nombre}:{numero}: {tipo} ({valor})")

    if not encontrados:
        return 0
    print("Commit bloqueado: hay datos personales en los archivos preparados.")
    print("\n".join(encontrados))
    print("Quitalos del archivo (o usá datos ficticios que no tengan ese formato) y volvé a intentar.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
