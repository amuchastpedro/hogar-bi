"""Plan B (bloque 6, parte A): `plan_b.ps1` y `al_haber_pendientes.ps1`.

Siempre sobre una copia mínima del proyecto en una carpeta temporal (un repositorio git propio) y
con un `claude` falso primero en el PATH, que anota cómo lo llamaron: con qué argumentos, en qué
carpeta y con qué variables de entorno. Nunca se invoca al `claude` real.
"""

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from apoyo_carga import pdf_con_texto

RAIZ = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.skipif(
    sys.platform != "win32" or not shutil.which("powershell") or not shutil.which("git"),
    reason="el plan B usa PowerShell y git en Windows",
)

# Variables que harían facturar por API; una muestra de cada familia que nombra la documentación.
VARIABLES_FACTURACION = {
    "ANTHROPIC_API_KEY": "clave-falsa",
    "ANTHROPIC_AUTH_TOKEN": "token-falso",
    "ANTHROPIC_BASE_URL": "https://pasarela.invalid",
    "ANTHROPIC_FOUNDRY_API_KEY": "clave-falsa",
    "ANTHROPIC_VERTEX_PROJECT_ID": "proyecto-falso",
    "CLAUDE_CODE_USE_BEDROCK": "1",
    "CLAUDE_CODE_USE_VERTEX": "1",
    "CLAUDE_CODE_USE_FOUNDRY": "1",
    "AWS_BEARER_TOKEN_BEDROCK": "token-falso",
}

CLAUDE_FALSO = r'''
import json, os, re, subprocess, sys, time
from pathlib import Path

registro = Path(os.environ["FALSO_CLAUDE_REGISTRO"])
registro.mkdir(exist_ok=True)
args = sys.argv[1:]
datos = {"args": args, "cwd": os.getcwd(), "env": dict(os.environ)}
destino = registro / f"llamada_{len(list(registro.glob('llamada_*.json')))}.json"
if args[:2] == ["auth", "status"]:
    destino.write_text(json.dumps(datos), encoding="utf-8")
    metodo = os.environ.get("FALSO_CLAUDE_AUTH", "claude.ai")
    print(json.dumps({"loggedIn": metodo != "ninguno", "authMethod": metodo}))
    sys.exit(0)
datos["stdin"] = sys.stdin.buffer.read().decode("utf-8")
destino.write_text(json.dumps(datos), encoding="utf-8")
modo = os.environ.get("FALSO_CLAUDE_MODO", "propuesta")
if modo == "limite":
    print("Claude AI usage limit reached|1760000000")
    sys.exit(1)
if modo == "dormir":
    time.sleep(120)
if modo == "propuesta":
    informe = Path(re.search(r"Informe a escribir: (\S+)", datos["stdin"]).group(1))
    informe.parent.mkdir(parents=True, exist_ok=True)
    informe.write_text("# Propuesta\n\nSe agrega un alias.\n", encoding="utf-8")
    Path("src/nuevo_alias.txt").write_text("alias\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], check=True)
    subprocess.run(["git", "commit", "-q", "-m", "propuesta del agente"], check=True)
print(json.dumps({"type": "result", "is_error": False, "result": "listo"}))
'''


def _git(raiz: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(raiz), *args], check=True, capture_output=True, text=True,
                          encoding="utf-8").stdout.strip()


def _quitar_enlace(ruta: Path) -> None:
    """Quita un enlace (junction) sin tocar su destino."""
    if ruta.is_junction():
        os.rmdir(ruta)


class Proyecto:
    def __init__(self, tmp_path: Path):
        self.raiz = tmp_path / "proyecto"
        self.worktrees = tmp_path / "proyecto-propuestas"
        self.registro = tmp_path / "llamadas"
        self.bin = tmp_path / "bin"
        shutil.copytree(RAIZ / "scripts", self.raiz / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(RAIZ / "src", self.raiz / "src", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copyfile(RAIZ / ".gitignore", self.raiz / ".gitignore")
        self.pendientes = self.raiz / "datos" / "pendientes"
        self.pendientes.mkdir(parents=True)
        self.poner_pendiente("factura_rara", "Factura de un proveedor desconocido")
        subprocess.run(["git", "init", "-q", "-b", "main", str(self.raiz)], check=True)
        _git(self.raiz, "config", "user.email", "pruebas-plan-b")
        _git(self.raiz, "config", "user.name", "pruebas")
        _git(self.raiz, "add", "-A")
        _git(self.raiz, "commit", "-q", "-m", "inicial")
        subprocess.run(["cmd", "/c", "mklink", "/J", str(self.raiz / ".venv"), str(RAIZ / ".venv")],
                       check=True, capture_output=True)
        self.bin.mkdir()
        (self.bin / "falso_claude.py").write_text(CLAUDE_FALSO, encoding="utf-8")
        (self.bin / "claude.cmd").write_text(f'@"{sys.executable}" "%~dp0falso_claude.py" %*\r\n', encoding="ascii")

    def poner_pendiente(self, nombre: str, texto: str) -> Path:
        pdf = self.pendientes / f"{nombre}.pdf"
        pdf.write_bytes(pdf_con_texto(texto))
        (self.pendientes / f"{nombre}.motivo.txt").write_text(
            "Etapa: formato\nMotivo: ningún parser reconoce el documento\nFecha: 2026-10-06 10:00:00\n",
            encoding="utf-8")
        return pdf

    def entorno(self, sin_claude: bool = False, **extra: str) -> dict:
        rutas = [d for d in os.environ["PATH"].split(os.pathsep)
                 if not (sin_claude and d and shutil.which("claude", path=d))]
        if not sin_claude:
            rutas.insert(0, str(self.bin))
        return {**os.environ, "PATH": os.pathsep.join(rutas), "FALSO_CLAUDE_REGISTRO": str(self.registro),
                "FACTURAS_SIN_AVISOS": "1", **extra}

    def comando(self, script: str, *args: str) -> list[str]:
        return ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                str(self.raiz / "scripts" / script), *args]

    def ejecutar(self, script: str, *args: str, sin_claude: bool = False, **extra: str):
        return subprocess.run(self.comando(script, *args), env=self.entorno(sin_claude, **extra),
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)

    def llamadas(self) -> list[dict]:
        archivos = sorted(self.registro.glob("llamada_*.json"), key=lambda p: int(p.stem.split("_")[1]))
        return [json.loads(p.read_text(encoding="utf-8")) for p in archivos]

    def ramas(self) -> list[str]:
        return _git(self.raiz, "branch", "--list", "propuesta/*", "--format=%(refname:short)").split()

    def intentos(self) -> list[list[str]]:
        archivo = self.raiz / "datos" / "plan_b_intentos.tsv"
        if not archivo.exists():
            return []
        return [linea.split("\t") for linea in archivo.read_text(encoding="utf-8-sig").splitlines() if linea]

    def log(self) -> str:
        archivo = self.raiz / "datos" / "logs" / "plan_b.log"
        return archivo.read_text(encoding="utf-8-sig") if archivo.exists() else ""

    def limpiar(self) -> None:
        for worktree in self.worktrees.glob("*"):
            _quitar_enlace(worktree / ".venv")
        _quitar_enlace(self.raiz / ".venv")


@pytest.fixture
def proyecto(tmp_path):
    p = Proyecto(tmp_path)
    yield p
    p.limpiar()


def test_el_proceso_hijo_no_recibe_variables_de_facturacion(proyecto):
    resultado = proyecto.ejecutar("plan_b.ps1", "factura_rara.pdf", FACTURAS_TESTIGO="si", **VARIABLES_FACTURACION)

    assert resultado.returncode == 0, resultado.stdout + resultado.stderr + proyecto.log()
    llamadas = proyecto.llamadas()
    assert [ll["args"][:2] for ll in llamadas] == [["auth", "status"], ["-p", "--model"]]
    for llamada in llamadas:
        assert llamada["env"].get("FACTURAS_TESTIGO") == "si"  # el resto del entorno sí llega
        assert not set(VARIABLES_FACTURACION) & set(llamada["env"])


def test_claude_trabaja_en_el_worktree_con_herramientas_restringidas(proyecto):
    proyecto.ejecutar("plan_b.ps1", "factura_rara.pdf")

    llamada = proyecto.llamadas()[-1]
    args = llamada["args"]
    (rama,) = proyecto.ramas()
    sufijo = rama.removeprefix("propuesta/")
    assert rama.startswith("propuesta/desconocido-")  # rechazo en la etapa formato: sin formato
    assert Path(llamada["cwd"]) == proyecto.worktrees / sufijo
    assert args[args.index("--permission-mode") + 1] == "dontAsk"
    assert args[args.index("--tools") + 1] == "Read,Edit,Write,Glob,Grep,Bash"
    assert args[args.index("--settings") + 1].endswith(r"scripts\plan_b\permisos.json")
    assert args[args.index("--setting-sources") + 1] == "project"
    assert "--strict-mcp-config" in args
    assert f"ejemplos/plan_b/{sufijo}.pdf" in llamada["stdin"]
    assert f"docs/propuestas/{sufijo}.md" in llamada["stdin"]
    assert "scripts/plan_b/instrucciones.md" in llamada["stdin"]


def test_la_propuesta_queda_en_su_rama_y_la_principal_no_cambia(proyecto):
    antes = _git(proyecto.raiz, "rev-parse", "main")

    resultado = proyecto.ejecutar("plan_b.ps1", "factura_rara.pdf")

    assert "propuesta" in resultado.stdout
    assert _git(proyecto.raiz, "rev-parse", "main") == antes
    assert _git(proyecto.raiz, "status", "--porcelain") == ""
    (rama,) = proyecto.ramas()
    sufijo = rama.removeprefix("propuesta/")
    cambiados = _git(proyecto.raiz, "diff", "--name-only", "main", rama).split()
    assert sorted(cambiados) == [f"docs/propuestas/{sufijo}.md", "src/nuevo_alias.txt"]
    (intento,) = proyecto.intentos()
    assert intento[2:] == ["factura_rara.pdf", rama, "propuesta"]
    assert f"Propuesta lista para factura_rara.pdf. Rama {rama}: cómo revisarla, en el README (Plan B)" in proyecto.log()
    assert (proyecto.pendientes / "factura_rara.pdf").exists()


def test_simular_hace_todo_menos_invocar_a_claude(proyecto):
    antes = _git(proyecto.raiz, "rev-parse", "main")

    resultado = proyecto.ejecutar("plan_b.ps1", "factura_rara.pdf", "-Simular", sin_claude=True)

    assert resultado.returncode == 0, resultado.stdout + resultado.stderr + proyecto.log()
    assert proyecto.llamadas() == []
    (rama,) = proyecto.ramas()
    sufijo = rama.removeprefix("propuesta/")
    worktree = proyecto.worktrees / sufijo
    informe = worktree / "docs" / "propuestas" / f"{sufijo}.md"
    assert "SIMULACIÓN" in informe.read_text(encoding="utf-8")
    assert _git(proyecto.raiz, "diff", "--name-only", "main", rama) == f"docs/propuestas/{sufijo}.md"
    assert _git(proyecto.raiz, "rev-parse", "main") == antes
    # El agente tendría lo que no está en git: el PDF con un nombre neutro, el motivo, el texto y el .venv.
    entrada = worktree / "ejemplos" / "plan_b"
    assert (entrada / f"{sufijo}.pdf").read_bytes() == (proyecto.pendientes / "factura_rara.pdf").read_bytes()
    assert "Etapa: formato" in (entrada / f"{sufijo}.motivo.txt").read_text(encoding="utf-8")
    assert "proveedor desconocido" in (entrada / f"{sufijo}.texto.txt").read_text(encoding="utf-8")
    assert (worktree / ".venv").is_junction()
    assert proyecto.intentos()[0][4] == "simulacion"


def test_un_solo_intento_automatico_por_pdf(proyecto):
    proyecto.poner_pendiente("otra_rara", "Otra factura distinta")

    proyecto.ejecutar("plan_b.ps1", "-Automatico", "-Simular")
    proyecto.ejecutar("plan_b.ps1", "-Automatico", "-Simular")

    assert sorted(i[2] for i in proyecto.intentos()) == ["factura_rara.pdf", "otra_rara.pdf"]
    assert len(proyecto.ramas()) == 2


@pytest.mark.parametrize("caso, opciones, en_el_log", [
    ("sin claude", {"sin_claude": True}, "Claude Code no está instalado"),
    ("sin sesión", {"FALSO_CLAUDE_AUTH": "ninguno"}, "no hay una sesión iniciada"),
    ("con clave de API", {"FALSO_CLAUDE_AUTH": "api_key"}, "no usa la suscripción"),
    ("límite de uso", {"FALSO_CLAUDE_MODO": "limite"}, "se alcanzó el límite de uso del plan"),
])
def test_sin_claude_utilizable_queda_pendiente_y_avisa(proyecto, caso, opciones, en_el_log):
    resultado = proyecto.ejecutar("plan_b.ps1", "-Automatico", **opciones)

    assert resultado.returncode == 2
    assert en_el_log in proyecto.log()
    assert "Aviso: Plan B: no se pudo lanzar" in proyecto.log()
    assert (proyecto.pendientes / "factura_rara.pdf").exists()
    # No cuenta como intento (se vuelve a probar en el próximo disparo) y no deja ramas ni worktrees.
    assert proyecto.intentos() == []
    assert proyecto.ramas() == []
    assert list(proyecto.worktrees.glob("*")) == []


def test_un_intento_que_supera_la_duracion_maxima_se_detiene(proyecto):
    inicio = time.monotonic()
    resultado = proyecto.ejecutar("plan_b.ps1", "factura_rara.pdf", "-LimiteMinutos", "0.05", FALSO_CLAUDE_MODO="dormir")

    assert time.monotonic() - inicio < 60  # el agente falso dormiría 120 s
    assert resultado.returncode == 1
    (rama,) = proyecto.ramas()
    sufijo = rama.removeprefix("propuesta/")
    informe = _git(proyecto.raiz, "show", f"{rama}:docs/propuestas/{sufijo}.md")
    assert "superó la duración máxima" in informe
    assert proyecto.intentos()[0][4] == "tiempo_agotado"


def test_no_hay_dos_planes_b_a_la_vez(proyecto):
    proyecto.poner_pendiente("otra_rara", "Otra factura distinta")
    primero = subprocess.Popen(
        proyecto.comando("plan_b.ps1", "factura_rara.pdf", "-LimiteMinutos", "0.25"),
        env=proyecto.entorno(FALSO_CLAUDE_MODO="dormir"), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        limite = time.monotonic() + 60
        while not any(ll["args"][0] == "-p" for ll in proyecto.llamadas() if ll["args"]):
            assert time.monotonic() < limite, "el primer plan B no llegó a lanzar el agente"
            time.sleep(0.5)

        segundo = proyecto.ejecutar("plan_b.ps1", "otra_rara.pdf")

        assert segundo.returncode == 0
        assert "Ya hay un plan B en curso" in proyecto.log()
        assert len(proyecto.ramas()) == 1
    finally:
        primero.wait(timeout=120)


@pytest.mark.skipif(not (RAIZ / "scripts" / "al_haber_pendientes.ps1").exists(),
                    reason="plan B en pausa: al_haber_pendientes.ps1 se quitó de scripts/ (docs/estado.md)")
def test_al_haber_pendientes_vuelve_enseguida_y_lanza_el_plan_b_aparte(proyecto):
    inicio = time.monotonic()
    resultado = proyecto.ejecutar("al_haber_pendientes.ps1", "-Simular")

    assert resultado.returncode == 0, resultado.stdout + resultado.stderr + proyecto.log()
    assert time.monotonic() - inicio < 15
    limite = time.monotonic() + 90
    while not proyecto.intentos():
        assert time.monotonic() < limite, proyecto.log()
        time.sleep(0.5)
    assert proyecto.intentos()[0][2:] == ["factura_rara.pdf", proyecto.ramas()[0], "simulacion"]
    assert "Plan B lanzado en segundo plano" in proyecto.log()
    # Sin pendientes nuevos no lanza nada.
    proyecto.ejecutar("al_haber_pendientes.ps1", "-Simular")
    assert proyecto.log().count("Plan B lanzado en segundo plano") == 1
