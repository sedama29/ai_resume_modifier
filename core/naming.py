import re


def sanitize_component(text: str) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "", text)
    return text or "Unknown"


def resume_name(company: str, job_title: str, year_month: str, version_number: int) -> str:
    """Resume_CompanyName_JobTitle_YYYY-MM_vN"""
    return (
        f"Resume_{sanitize_component(company)}_{sanitize_component(job_title)}_"
        f"{year_month}_v{version_number}"
    )


def next_version_number(latest_version_number: int | None, overwrite: bool) -> int:
    """Overwrite reuses the current vN; Create New always increments to vN+1."""
    if latest_version_number is None:
        return 1
    return latest_version_number if overwrite else latest_version_number + 1
