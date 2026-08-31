"""Generic HTTP download with an on-disk cache, shared by the UESP scrapers."""
from requests import get as get_url

from app.cache import PAGES_CACHE_DIRECTORY


def download_data(url: str) -> bytes:
    """
    Download the data from a URL, caching the response on disk.

    Parameters
    ----------
    url : str
        The URL to download.

    Returns
    -------
    bytes
        The content of the page as bytes.
    """
    cache_file = PAGES_CACHE_DIRECTORY / (url.split(':')[-1] + ".html")

    if cache_file.exists():
        with open(cache_file, "rb") as f:
            return f.read()

    with get_url(url, stream=True, timeout=10) as response:
        content = b""
        for chunk in response.iter_content(chunk_size=8192):
            content += chunk

    with open(cache_file, "wb") as f:
        f.write(content)

    return content
