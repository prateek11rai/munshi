from munshi.cli import main


def test_doctor_runs(capsys):
    assert main(["doctor"]) == 0
    assert "Python" in capsys.readouterr().out
