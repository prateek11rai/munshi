import pytest

from munshi.cli import main, minutes


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MUNSHI_HOME", str(tmp_path / "real"))
    monkeypatch.setenv("MUNSHI_OLLAMA_URL", "http://127.0.0.1:9")


def test_minutes():
    assert minutes("30m") == 30 and minutes("1h") == 60 and minutes("90") == 90
    with pytest.raises(ValueError):
        minutes("soon")


def test_doctor_creates_nothing(tmp_path, capsys):
    assert main(["doctor"]) == 0
    out = capsys.readouterr().out
    assert "Python" in out and "Ollama not reachable" in out
    assert not (tmp_path / "real").exists()


def test_demo_commands(tmp_path, capsys):
    assert main(["demo", "load"]) == 0
    assert (tmp_path / ".data" / "demo" / "munshi.db").exists()
    assert main(["journal", "--demo"]) == 0
    out = capsys.readouterr().out
    assert "## Timeline" in out and "Active 6 h 45 min" in out
    assert main(["hours", "--demo", "--csv"]) == 0
    assert capsys.readouterr().out.startswith("date,project,topic,hours\n")
    assert main(["pause", "--demo", "--for", "30m"]) == 0
    assert "Paused until" in capsys.readouterr().out
    assert main(["resume", "--demo"]) == 0
    assert main(["forget", "--demo", "--last", "60m"]) == 0
    assert "Forgot the last 60 min" in capsys.readouterr().out
    assert main(["write", "--demo"]) == 0
    out = capsys.readouterr().out
    assert "Ollama is not reachable" in out and "blocks written" in out
    assert main(["eval", "--demo"]) == 1
    assert main(["eval"]) == 1 and "needs --demo or --real" in capsys.readouterr().out
    assert main(["eval", "--real"]) == 1 and "Nothing recorded yet" in capsys.readouterr().out
    assert main(["stats", "--demo"]) == 0
    out = capsys.readouterr().out
    assert "(numbers only)" in out and "slots written" in out and "tidepool" not in out
    assert main(["demo", "clear"]) == 0
    assert not (tmp_path / ".data" / "demo").exists()
    assert not (tmp_path / "real").exists()


def test_bad_duration_exit_code():
    assert main(["pause", "--demo", "--for", "soon"]) == 2
