"""Datos de la tabla `carga` de un PDF rechazado, para el plan B: formato y extracción.

Uso, desde la raíz: .venv/Scripts/python scripts/plan_b/carga_pendiente.py <sha256> <destino.json>
Escribe en <destino.json> la extracción guardada (si la hay) y muestra en una línea el formato
(`desconocido` si ningún parser lo reconoció o no hay registro). Abre la base en modo lectura.
"""

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

from facturas.bd.conexion import conectar  # noqa: E402

RUTA_BASE = RAIZ / "datos" / "facturas.db"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if len(sys.argv) != 3:
        print("Uso: carga_pendiente.py <sha256> <destino.json>", file=sys.stderr)
        return 2
    sha, destino = sys.argv[1], Path(sys.argv[2])
    fila = None
    if RUTA_BASE.exists():
        conexion = conectar(RUTA_BASE, "lectura")
        try:
            fila = conexion.execute(
                "SELECT formato, extraccion_json FROM carga WHERE sha256 = ?", (sha,)
            ).fetchone()
        finally:
            conexion.close()
    formato, extraccion = (fila[0], fila[1]) if fila else (None, None)
    if extraccion:
        destino.write_text(json.dumps(json.loads(extraccion), ensure_ascii=False, indent=2), encoding="utf-8")
    print(formato or "desconocido")
    return 0


if __name__ == "__main__":
    sys.exit(main())
