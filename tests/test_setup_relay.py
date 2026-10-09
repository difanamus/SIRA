import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from dotenv import dotenv_values
from httpx import Client as HTTPClient

from backend import setup_relay

ORIGIN = "https://exam.workers.dev"
TOKEN = "demo-not-openai-" + "a" * 40


@pytest.fixture
def bootstrap(tmp_path, monkeypatch):
    monkeypatch.delenv("SIRA_RELAY_URL", raising=False)
    monkeypatch.delenv("SIRA_RELAY_TOKEN", raising=False)
    env = tmp_path / ".env"
    env.write_text("# Keep local settings\nSIRA_DATA_DIR=custom\nSIRA_RELAY_URL=\nSIRA_RELAY_TOKEN=\n")
    manifest = tmp_path / "relay.json"
    manifest.write_text(json.dumps({"installation_url": ORIGIN + "/installation"}))
    packet = {
        "relay_url": ORIGIN,
        "relay_token": TOKEN,
        "access": "public-demo",
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
    }
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json=packet)

    monkeypatch.setattr(
        setup_relay.httpx, "Client", lambda **kw: HTTPClient(transport=httpx.MockTransport(respond), **kw)
    )
    return env, manifest, packet, requests


def test_fresh_install_connects_atomically_and_preserves_local_settings(bootstrap, monkeypatch, capsys):
    env, manifest, _, requests = bootstrap
    monkeypatch.setattr("sys.argv", ["setup_relay", "--env-file", str(env), "--manifest", str(manifest)])
    setup_relay.main()
    values = dotenv_values(env)
    assert values["SIRA_RELAY_URL"] == ORIGIN and values["SIRA_RELAY_TOKEN"] == TOKEN
    assert values["SIRA_DATA_DIR"] == "custom"
    assert "# Keep local settings" in env.read_text()
    assert requests[0].url == ORIGIN + "/installation"
    assert "authorization" not in requests[0].headers
    assert TOKEN not in capsys.readouterr().out
    assert not list(env.parent.glob(".env.bootstrap-*"))


def test_existing_or_environment_configuration_is_never_overwritten(bootstrap, monkeypatch):
    env, manifest, _, requests = bootstrap
    original = "SIRA_RELAY_URL=https://private.example\nSIRA_RELAY_TOKEN=private-test\n"
    env.write_text(original)
    assert setup_relay.configure(env, manifest)["existing"]
    assert env.read_text() == original and not requests
    env.write_text("")
    monkeypatch.setenv("SIRA_RELAY_URL", "https://environment.example")
    monkeypatch.setenv("SIRA_RELAY_TOKEN", "environment-test")
    assert setup_relay.configure(env, manifest)["existing"]
    assert env.read_text() == "" and not requests


def test_partial_custom_configuration_is_not_replaced(bootstrap):
    env, manifest, _, requests = bootstrap
    env.write_text("SIRA_RELAY_URL=https://private.example\n")
    with pytest.raises(ValueError, match="terisi sebagian"):
        setup_relay.configure(env, manifest)
    assert env.read_text() == "SIRA_RELAY_URL=https://private.example\n" and not requests


@pytest.mark.parametrize(
    "field,value",
    [
        ("relay_url", "https://attacker.example"),
        ("relay_token", "sk-never-copy-an-openai-key"),
        ("expires_at", "2020-01-01T00:00:00Z"),
        ("expires_at", "2099-01-01"),
        ("access", "private"),
    ],
)
def test_invalid_response_leaves_configuration_unchanged(bootstrap, field, value):
    env, manifest, packet, _ = bootstrap
    original = env.read_bytes()
    packet[field] = value
    with pytest.raises(ValueError, match="belum berhasil"):
        setup_relay.configure(env, manifest)
    assert env.read_bytes() == original


@pytest.mark.parametrize("status", [301, 401, 403, 503])
def test_redirects_and_service_failures_do_not_publish_credentials(bootstrap, monkeypatch, status):
    env, manifest, _, _ = bootstrap
    original = env.read_bytes()
    transport = httpx.MockTransport(lambda request: httpx.Response(status, headers={"Location": "https://other.test"}))
    monkeypatch.setattr(setup_relay.httpx, "Client", lambda **kw: HTTPClient(transport=transport, **kw))
    with pytest.raises(ValueError, match="belum berhasil"):
        setup_relay.configure(env, manifest)
    assert env.read_bytes() == original
