"""Conversão DWG -> DXF.

O DWG é um formato fechado; a leitura é feita sobre DXF. São suportados dois
conversores externos (o primeiro encontrado é usado):

* ODA File Converter (gratuito, Windows/Linux/macOS) - mais fiável;
* LibreDWG ``dwg2dxf`` (open source).

Pode indicar o executável pelas variáveis de ambiente ``ODA_CONVERTER`` ou
``DWG2DXF``.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ODA_CANDIDATES = [
    "ODAFileConverter",
    r"C:\Program Files\ODA\ODAFileConverter\ODAFileConverter.exe",
    "/usr/bin/ODAFileConverter",
    "/Applications/ODAFileConverter.app/Contents/MacOS/ODAFileConverter",
]
DWG2DXF_CANDIDATES = ["dwg2dxf", str(Path.home() / ".local/bin/dwg2dxf")]


class ConversionError(RuntimeError):
    pass


def _oda_windows() -> list[str]:
    """O instalador do ODA usa pastas com a versão (ex.: 'ODAFileConverter 25.12.0')."""
    import glob
    out = []
    for base in (r"C:\Program Files\ODA", r"C:\Program Files (x86)\ODA"):
        out += sorted(glob.glob(base + r"\ODAFileConverter*\ODAFileConverter.exe"), reverse=True)
    return out


def _which(cands: list[str]) -> str | None:
    for c in cands:
        p = shutil.which(c) or (c if Path(c).is_file() else None)
        if p:
            return p
    return None


def find_converter() -> tuple[str, str] | None:
    """Devolve (tipo, executável) do conversor disponível, ou None."""
    oda = os.environ.get("ODA_CONVERTER") or _which(ODA_CANDIDATES + _oda_windows())
    if oda:
        return "oda", oda
    lib = os.environ.get("DWG2DXF") or _which(DWG2DXF_CANDIDATES)
    if lib:
        return "libredwg", lib
    return None


def dwg_to_dxf(dwg_path: str | Path, out_dir: str | Path | None = None, timeout: int = 600) -> Path:
    dwg_path = Path(dwg_path)
    out_dir = Path(out_dir or tempfile.mkdtemp(prefix="dwg2dxf_"))
    out_dir.mkdir(parents=True, exist_ok=True)
    conv = find_converter()
    if conv is None:
        raise ConversionError(
            "Nenhum conversor DWG->DXF encontrado. Instale o ODA File Converter "
            "(https://www.opendesign.com/guestfiles/oda_file_converter) ou o LibreDWG "
            "(scripts/install_libredwg.sh), ou carregue diretamente um DXF."
        )
    kind, exe = conv
    out = out_dir / (dwg_path.stem + ".dxf")
    if kind == "oda":
        src_dir = Path(tempfile.mkdtemp(prefix="oda_in_"))
        shutil.copy(dwg_path, src_dir / dwg_path.name)
        cmd = [exe, str(src_dir), str(out_dir), "ACAD2018", "DXF", "0", "1", dwg_path.name]
    else:
        cmd = [exe, "-y", "-o", str(out), str(dwg_path)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if not out.exists():
        raise ConversionError(f"Conversão falhou ({kind}): {proc.stderr[-2000:]}")
    return out
