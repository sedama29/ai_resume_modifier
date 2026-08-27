import requests

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}
_TIMEOUT_SECONDS = 15


def fetch_job_description(url: str) -> str:
    """Fetch the raw HTML of a job posting URL. Raises requests.RequestException
    on failure -- callers should catch this and fall back to asking the user
    to paste the text instead."""
    response = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.text
