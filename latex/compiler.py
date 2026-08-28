"""
Compiles a .tex string to PDF locally (tectonic preferred, pdflatex fallback).
Runs in an isolated scratch directory -- never touches Resources/. Errors are
always surfaced (full log + a short "! "-line summary), never swallowed.

Security: any authorized user (not just the Super User) can upload a LaTeX
project, so this must never let the source run arbitrary shell commands via
\\write18. Tectonic has no such capability at all (deliberate upstream design
-- there is no shell-escape to disable). The pdflatex fallback is invoked
with -no-shell-escape explicitly, rather than relying on it merely being
absent. Extra project files (images, .sty, .bib, fonts) are written under
the scratch dir with their paths validated to stay inside it -- rejecting
".." traversal -- before compilation ever runs.
"""
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

TIMEOUT_SECONDS = 120


class UnsafePathError(ValueError):
    pass


def _safe_join(scratch_dir: Path, relative_path: str) -> Path:
    dest = (scratch_dir / relative_path).resolve()
    if not dest.is_relative_to(scratch_dir.resolve()):
        raise UnsafePathError(f"Refusing to write outside the scratch directory: {relative_path!r}")
    return dest


@dataclass
class CompileResult:
    success: bool
    pdf_path: str | None
    log_text: str
    engine_used: str | None
    error_summary: str | None


def _detect_engine() -> str | None:
    if shutil.which("tectonic"):
        return "tectonic"
    if shutil.which("pdflatex"):
        return "pdflatex"
    return None


def compile_tex(tex_content: str, scratch_dir: Path, extra_files: dict[str, bytes] | None = None) -> CompileResult:
    """extra_files: relative-path -> bytes for any supporting project files
    (images, .sty, .bib, fonts) the main .tex references. Each path is
    validated to resolve inside scratch_dir before being written."""
    engine = _detect_engine()
    if engine is None:
        return CompileResult(
            success=False,
            pdf_path=None,
            log_text="",
            engine_used=None,
            error_summary=(
                "No LaTeX engine found on this machine. Install one to generate PDFs: "
                "`brew install tectonic` (recommended, no separate TeX Live needed) "
                "or a full TeX Live / MacTeX distribution for pdflatex."
            ),
        )

    scratch_dir.mkdir(parents=True, exist_ok=True)
    tex_path = scratch_dir / "resume.tex"
    tex_path.write_text(tex_content)

    for relative_path, content in (extra_files or {}).items():
        dest = _safe_join(scratch_dir, relative_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)

    if engine == "tectonic":
        cmd = ["tectonic", "--outdir", str(scratch_dir), str(tex_path)]
    else:
        cmd = [
            "pdflatex", "-interaction=nonstopmode", "-halt-on-error", "-no-shell-escape",
            "-output-directory", str(scratch_dir), str(tex_path),
        ]

    try:
        proc = subprocess.run(cmd, cwd=scratch_dir, capture_output=True, text=True, timeout=TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        return CompileResult(
            success=False, pdf_path=None, log_text="",
            engine_used=engine, error_summary=f"LaTeX compilation timed out after {TIMEOUT_SECONDS}s.",
        )

    log_text = (proc.stdout or "") + "\n" + (proc.stderr or "")
    pdf_path = scratch_dir / "resume.pdf"
    success = pdf_path.exists() and proc.returncode == 0

    error_summary = None
    if not success:
        error_lines = [line for line in log_text.splitlines() if line.startswith("!")]
        error_summary = "\n".join(error_lines) if error_lines else f"Compilation failed (exit code {proc.returncode})."

    return CompileResult(
        success=success,
        pdf_path=str(pdf_path) if success else None,
        log_text=log_text,
        engine_used=engine,
        error_summary=error_summary,
    )
