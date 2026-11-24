from pathlib import Path

from apontarhoras.main import load_settings


def test_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv("APONTARHORAS_DADOS", str(tmp_path))
    settings, open_browser = load_settings([])
    assert (settings.host, settings.port, settings.data_dir) == ("127.0.0.1", 8080, tmp_path)
    assert open_browser


def test_ini_and_command_line(tmp_path):
    ini = tmp_path / "ApontarHoras.ini"
    ini.write_text(
        "; comentário\n[servidor]\nrede = sim\nporta = 9090\ndados = D:\\Dados\\%teste%\nabrir_navegador = nao\n",
        encoding="utf-8-sig",
    )
    settings, open_browser = load_settings(["--config", str(ini)])
    assert (settings.host, settings.port, settings.data_dir) == ("0.0.0.0", 9090, Path("D:\\Dados\\%teste%"))
    assert not open_browser
    settings, _ = load_settings(["--config", str(ini), "--porta", "7000"])  # linha de comando vale mais
    assert settings.port == 7000


def test_https_option_turns_on_secure_cookie(tmp_path):
    ini = tmp_path / "ApontarHoras.ini"
    ini.write_text("[servidor]\nhttps = sim\n", encoding="utf-8-sig")
    settings, _ = load_settings(["--config", str(ini), "--dados", str(tmp_path)])
    assert settings.secure_cookies
    ini.write_text("[servidor]\nrede = sim\n", encoding="utf-8-sig")
    settings, _ = load_settings(["--config", str(ini), "--dados", str(tmp_path)])
    assert not settings.secure_cookies  # padrão: sem HTTPS


def test_missing_ini_uses_defaults(tmp_path):
    settings, _ = load_settings(["--config", str(tmp_path / "nao-existe.ini"), "--dados", str(tmp_path)])
    assert settings.port == 8080
