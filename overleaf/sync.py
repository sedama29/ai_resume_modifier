"""V1 STUB. Local LaTeX compilation (latex/compiler.py) is the primary PDF path;
Overleaf sync is optional and deferred. Real implementation would drive a
persistent-profile Chrome session (see selenium_driver.py) to open the target
Overleaf project, replace its main.tex content, and trigger a compile."""
from dataclasses import dataclass


@dataclass
class SyncResult:
    success: bool
    project_url: str | None
    error: str | None


def push_to_overleaf(tex_content: str, project_url: str | None, profile_dir: str) -> SyncResult:
    return SyncResult(
        success=False,
        project_url=project_url,
        error="Overleaf sync isn't implemented yet -- use the local PDF download instead.",
    )
