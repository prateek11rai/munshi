import stat

import pytest

from munshi.config import CONFIG_TEMPLATE, ConfigError, contains_word, ensure_home, load_config


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


def test_ignore_words_load_lower_cased(tmp_path):
    (tmp_path / "config.toml").write_text(
        'ignore_title_words = [" Acme ", ""]\nignore_process_words = ["ACME"]\n'
    )
    config = load_config(tmp_path)
    assert config.ignore_title_words == ["acme"]
    assert config.ignore_process_words == ["acme"]
    assert "ignore_title_words = []" in CONFIG_TEMPLATE


def test_unknown_keys_refused_without_echoing_values(tmp_path):
    (tmp_path / "config.toml").write_text('ignore_title_word = ["acme"]\n')
    with pytest.raises(ConfigError) as caught:
        load_config(tmp_path)
    assert "ignore_title_word" in str(caught.value) and "acme" not in str(caught.value)
    (tmp_path / "config.toml").write_text('ignore_process_words = "acme"\n')
    with pytest.raises(ConfigError) as caught:
        load_config(tmp_path)
    assert "ignore_process_words" in str(caught.value) and "acme" not in str(caught.value)
    (tmp_path / "config.toml").write_text('[apps]\nignore = ["Slack"]\nskip = ["acme"]\n')
    with pytest.raises(ConfigError) as caught:
        load_config(tmp_path)
    assert "apps.skip" in str(caught.value) and "acme" not in str(caught.value)


def test_contains_word():
    assert contains_word("Plan - ACME wiki", ["acme"])
    assert not contains_word("Plan", ["acme"]) and not contains_word(None, ["acme"])
    assert not contains_word("anything", [])
