import stat

import pytest

from munshi.config import ConfigError, ensure_home, load_config


def test_home_created_private_with_commented_config(tmp_path):
    home = tmp_path / "home"
    path = ensure_home(home)
    assert stat.S_IMODE(home.stat().st_mode) == 0o700
    text = path.read_text()
    assert text.startswith("# Munshi settings")
    assert 'model = "gemma4:e4b"' in text
    config = load_config(home)
    assert config.allowed_roots == []
    assert config.keep_events_days == 14
    assert config.apps.mode == "all"


def test_env_overrides(tmp_path, monkeypatch):
    monkeypatch.setenv("MUNSHI_MODEL", "other:1b")
    monkeypatch.setenv("MUNSHI_OLLAMA_URL", "http://localhost:9999")
    config = load_config(tmp_path)
    assert config.model == "other:1b"
    assert config.ollama_url == "http://localhost:9999"


def test_remote_model_refused_unless_allowed(tmp_path, monkeypatch):
    monkeypatch.setenv("MUNSHI_OLLAMA_URL", "http://gpu.example.com:11434")
    with pytest.raises(ConfigError):
        load_config(tmp_path)
    (tmp_path / "config.toml").write_text("allow_remote_model = true\n")
    assert load_config(tmp_path).ollama_url == "http://gpu.example.com:11434"


def test_bad_values_refused(tmp_path):
    ensure_home(tmp_path)
    (tmp_path / "config.toml").write_text('[apps]\nmode = "some"\n')
    with pytest.raises(ConfigError):
        load_config(tmp_path)
    (tmp_path / "config.toml").write_text("model = \n")
    with pytest.raises(ConfigError):
        load_config(tmp_path)


def test_app_rules(tmp_path):
    (tmp_path / "config.toml").write_text('[apps]\nignore = ["Slack"]\n')
    apps = load_config(tmp_path).apps
    assert not apps.records("1Password")
    assert not apps.records("slack")
    assert apps.records("Code")
    (tmp_path / "config.toml").write_text('[apps]\nmode = "only"\nonly = ["Code"]\n')
    apps = load_config(tmp_path).apps
    assert apps.records("Code")
    assert not apps.records("Google Chrome")
    assert not apps.records("Keychain Access")
