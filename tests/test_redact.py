import pytest

from munshi.redact import redact


@pytest.mark.parametrize(
    ("raw", "want"),
    [
        ("Mail from ana@example.org - Inbox", "Mail from [email] - Inbox"),
        ("https://github.com/tidepool/tidepool/pull/42?tab=files", "github.com"),
        ("Docs at http://user:pw@docs.example.com:8080/a/b", "Docs at docs.example.com"),
        ("see www.example.com/path?q=1 now", "see www.example.com now"),
        ("Fix #42 in tidepool", "Fix #42 in tidepool"),
        ("Issue #18 · tidepool", "Issue #18 · tidepool"),
        ("call 9876543210 now", "call [number] now"),
        ("order 12345 ok", "order 12345 ok"),
        ("token ghp_Ab12Cd34Ef56Gh78Ij90Kl12Mn34 here", "token [token] here"),
        ("sha 3f2a9c7e1b4d5f60718293a4b5c6d7e8f9012345", "sha [token]"),
        ("key QWxhZGRpbjpvcGVuIHNlc2FtZQ==abcdefgh", "key [token]"),
        (
            "~/code/tidepool/src/tidepool/cache/tide_chart.py",
            "~/code/tidepool/src/tidepool/cache/tide_chart.py",
        ),
        ("cache.py — tidepool", "cache.py — tidepool"),
        ("tide-tables-2026.pdf", "tide-tables-2026.pdf"),
        ("", ""),
    ],
)
def test_redact(raw, want):
    assert redact(raw) == want


def test_redact_none():
    assert redact(None) is None


def test_redact_token_inside_path():
    out = redact("/srv/a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6/logs")
    assert out == "/srv/[token]/logs"


def test_long_snake_names_survive_but_prefixed_keys_do_not():
    assert redact("test_file_scan_names_only_outs0") == "test_file_scan_names_only_outs0"
    assert redact("sk_live_4eC39HqLyjWDarjtT1zdp7dc") == "[token]"
