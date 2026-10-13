"""Muestra el texto de un PDF tal como lo ven los parsers: `texto` (orden de lectura) y `diseno` (columnas).

Uso, desde la raíz: .venv/Scripts/python scripts/plan_b/texto_pdf.py <ruta.pdf>
Lo usa el agente del plan B para comparar un PDF pendiente con el ejemplo de su formato.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from facturas.parsers.pdf import leer  # noqa: E402


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if len(sys.argv) != 2:
        print("Uso: texto_pdf.py <ruta.pdf>", file=sys.stderr)
        return 2
    documento = leer(sys.argv[1])
    print("=== texto (orden de lectura) ===")
    print(documento.texto)
    print("=== diseno (columnas) ===")
    print(documento.diseno)
    return 0


if __name__ == "__main__":
    sys.exit(main())
