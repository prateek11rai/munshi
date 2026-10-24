import base64
from importlib.resources import files

STATIC = files("munshi.ui") / "static"
TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".svg": "image/svg+xml",
}


def read(name: str) -> str:
    """Read a static UI file.

    Args:
        name: File name inside `ui/static`.

    Returns:
        The file's text.
    """
    return (STATIC / name).read_text(encoding="utf-8")


def inline(name: str) -> str:
    """Return an HTML page with its stylesheet, script and image inlined.

    The app windows load pages this way so pywebview needs no file access and no
    local HTTP server.

    Args:
        name: "card.html" or "buddy.html".

    Returns:
        Self-contained HTML.
    """
    page = read(name)
    page = page.replace(
        '<link rel="stylesheet" href="theme.css">', f"<style>\n{read('theme.css')}</style>"
    )
    page = page.replace('<script src="card.js"></script>', f"<script>\n{read('card.js')}</script>")
    svg = base64.b64encode(read("munshi.svg").encode()).decode()
    data = f"data:image/svg+xml;base64,{svg}"
    return page.replace('src="munshi.svg"', f'src="{data}"').replace(
        'href="munshi.svg"', f'href="{data}"'
    )
