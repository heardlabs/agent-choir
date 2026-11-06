import pytest


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    from choir import config
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path / "cfg")
    monkeypatch.setattr(config, "STATE_DIR", tmp_path / "state")
    for k in ("FAL_KEY", "ELEVENLABS_API_KEY", "ANTHROPIC_API_KEY", "CHOIR_MUTE", "TMUX_PANE",
              "HERDR_PANE_ID", "TERM_SESSION_ID", "ITERM_SESSION_ID", "WEZTERM_PANE", "KITTY_WINDOW_ID",
              "WT_SESSION", "ZELLIJ_PANE_ID"):
        monkeypatch.delenv(k, raising=False)
    yield
