import json
import stat

import pytest

from fieldcheck_agent import agent_cli


@pytest.fixture
def fake_client(monkeypatch):
    class Client:
        calls = []
        passed = True
        missing_report = False
        key = "fixture-only-secret"

        def __init__(self, origin, key):
            self.calls.append(("init", origin, key))

        def discover(self):
            self.calls.append(("discover",))

        def register(self, name):
            self.calls.append(("register", name))
            return {"id": "fixture-workspace", "credits": 20}

        def submit(self, contract, *, message_id):
            self.calls.append(("submit", contract, message_id))
            return {"id": "fixture-task"}

        def get_task(self, task_id):
            self.calls.append(("get_task", task_id))
            return {"id": task_id}

        def wait(self, task):
            return {"id": task["id"], "status": {"state": "TASK_STATE_COMPLETED"},
                "artifacts": [{"name": "fieldcheck.xml", "parts": [{"text": "<testsuite/>"}]}] +
                    ([] if self.missing_report else [{"name": "behavioral-check.json", "parts": [{"data": {"passed": self.passed}}]}])}

        def close(self):
            self.calls.append(("close",))

    monkeypatch.delenv("FIELDCHECK_KEY", raising=False)
    monkeypatch.setattr(agent_cli, "FieldcheckClient", Client)
    return Client


def test_register_only_saves_private_key_without_ordering_check(fake_client, tmp_path, capsys):
    key = tmp_path / "workspace.key"
    assert agent_cli.main(["--register", "--register-only", "--key-file", str(key)]) == 0
    assert key.read_text().strip() == fake_client.key
    assert stat.S_IMODE(key.stat().st_mode) == 0o600
    output = capsys.readouterr()
    assert fake_client.key not in output.out + output.err
    assert json.loads(output.out) == {"workspace_id": "fixture-workspace", "credits": 20,
        "key_saved": True, "check_submitted": False}
    assert not any(call[0] in {"submit", "get_task"} for call in fake_client.calls)


def test_register_retry_never_overwrites_existing_key(fake_client, tmp_path):
    key = tmp_path / "workspace.key"
    key.write_text("existing-key")
    with pytest.raises(SystemExit) as error:
        agent_cli.main(["--register", "--key-file", str(key)])
    assert error.value.code == 2
    assert key.read_text() == "existing-key"
    assert fake_client.calls == []


@pytest.mark.parametrize("passed,exit_code", [(True, 0), (False, 1)])
def test_completed_task_result_and_retry_id_are_preserved(fake_client, tmp_path, monkeypatch, capsys, passed, exit_code):
    monkeypatch.setenv("FIELDCHECK_KEY", "fixture-existing-key")
    fake_client.passed = passed
    junit = tmp_path / "result.xml"
    assert agent_cli.main(["--message-id", "persisted-contract-id", "--junit", str(junit)]) == exit_code
    assert [(call[1], call[2]) for call in fake_client.calls if call[0] == "submit"] == [
        ({"name": "Agent quickstart demo", "url": "demo:healthy"}, "persisted-contract-id")]
    assert junit.read_text() == "<testsuite/>"
    assert json.loads(capsys.readouterr().out)["id"] == "fixture-task"


def test_resume_does_not_submit_and_missing_result_is_error(fake_client, monkeypatch, capsys):
    monkeypatch.setenv("FIELDCHECK_KEY", "fixture-existing-key")
    fake_client.missing_report = True
    assert agent_cli.main(["--resume", "already-running"]) == 2
    assert ("get_task", "already-running") in fake_client.calls
    assert not any(call[0] == "submit" for call in fake_client.calls)
    assert "no boolean" in capsys.readouterr().err


def test_invalid_contract_does_not_create_workspace(fake_client, tmp_path, capsys):
    contract = tmp_path / "contract.json"
    contract.write_text("[]")
    key = tmp_path / "workspace.key"
    assert agent_cli.main(["--register", "--key-file", str(key), "--contract", str(contract)]) == 2
    assert fake_client.calls == []
    assert not key.exists()
    assert "JSON object" in capsys.readouterr().err


def test_shared_key_permissions_fail_before_network(fake_client, tmp_path, capsys):
    key = tmp_path / "workspace.key"
    key.write_text("private-fixture")
    key.chmod(0o644)
    assert agent_cli.main(["--key-file", str(key)]) == 2
    assert fake_client.calls == []
    assert "chmod 600" in capsys.readouterr().err
