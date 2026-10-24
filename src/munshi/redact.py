import re
from urllib.parse import urlsplit

_URL = re.compile(r"\b(?:[a-zA-Z][a-zA-Z0-9+.-]*)://[^\s<>\"']+")
_WWW = re.compile(r"\bwww\.[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)+(?:/[^\s<>\"']*)?")
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
_RUN = re.compile(r"(?<![A-Za-z0-9+/=_-])[A-Za-z0-9+/=_-]{24,}(?![A-Za-z0-9+/=_-])")
_DIGITS = re.compile(r"\d{6,}")
_ALNUM = re.compile(r"[A-Za-z0-9]+")
_BASE64 = re.compile(r"[A-Za-z0-9+/=]+")
_SEP = re.compile(r"[_-]")


def _host(match: re.Match[str]) -> str:
    text = match.group(0)
    if text.lower().startswith("www."):
        text = "http://" + text
    host = urlsplit(text).hostname
    return host or "[url]"


def _mixed(text: str) -> bool:
    return any(c.isdigit() for c in text) and any(c.isalpha() for c in text)


def _is_token(part: str) -> bool:
    if len(part) < 24:
        return False
    if _ALNUM.fullmatch(part):
        return True
    if _BASE64.fullmatch(part):
        return _mixed(part)
    # snake/kebab names stay; prefixed keys like "ghp_<long>" have one long mixed segment
    return any(len(seg) >= 16 and _mixed(seg) for seg in _SEP.split(part))


def _token(match: re.Match[str]) -> str:
    text = match.group(0)
    if "/" in text:
        return "/".join("[token]" if _is_token(part) else part for part in text.split("/"))
    return "[token]" if _is_token(text) else text


def redact(text: str | None) -> str | None:
    """Remove private details from text before it is stored.

    Emails become "[email]", URLs keep only their host, long tokens (24+ chars of
    hex/base64/alphanumerics) become "[token]" and runs of 6+ digits become
    "[number]". Short numbers such as "#42" are kept.

    Args:
        text: A window title, commit subject, branch or file name; None passes through.

    Returns:
        The redacted text, or None.
    """
    if text is None:
        return None
    text = _URL.sub(_host, text)
    text = _WWW.sub(_host, text)
    text = _EMAIL.sub("[email]", text)
    text = _RUN.sub(_token, text)
    return _DIGITS.sub("[number]", text)
