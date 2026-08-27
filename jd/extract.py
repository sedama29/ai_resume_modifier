import trafilatura


def extract_main_text(html: str) -> str | None:
    """Best-effort extraction of the main readable text from a job posting page.
    Returns None if extraction fails -- the UI should fall back to an editable
    textarea pre-filled with the raw HTML-stripped text (or ask the user to paste)
    rather than silently proceeding with garbage."""
    return trafilatura.extract(html, include_links=False, include_tables=False)
