"""Small A2A client for an orchestrator calling Fieldcheck without a browser."""
import time
from urllib.parse import urlsplit
from uuid import uuid4

import httpx


class FieldcheckError(Exception):
    pass


class FieldcheckClient:
    def __init__(self, origin, key=None, *, http=None):
        self.origin = origin.rstrip("/")
        parsed = urlsplit(self.origin)
        local = parsed.hostname in {"127.0.0.1", "localhost", "::1"}
        if (not parsed.hostname or parsed.username is not None or parsed.password is not None
                or parsed.query or parsed.fragment or parsed.path not in {"", "/"}
                or (parsed.scheme != "https" and not (parsed.scheme == "http" and local))):
            raise ValueError("Use an HTTPS Fieldcheck origin; loopback HTTP is allowed for development")
        self.key = key
        self.http = http or httpx.Client(timeout=20, follow_redirects=False)
        self._owns_http = http is None
        self.endpoint = None

    def close(self):
        if self._owns_http:
            self.http.close()

    def discover(self):
        response = self.http.get(self.origin + "/.well-known/agent-card.json", follow_redirects=False)
        response.raise_for_status()
        card = response.json()
        candidates = [i for i in card.get("supportedInterfaces", [])
                      if i.get("protocolBinding") == "JSONRPC" and i.get("protocolVersion", "").split(".")[:2] == ["1", "0"]]
        if not candidates:
            raise FieldcheckError("No supported A2A 1.0 JSON-RPC interface")
        endpoint = candidates[0]["url"]
        # Discovery metadata must not redirect a workspace credential to another
        # origin. This client is for Fieldcheck, not a general credential broker.
        if urlsplit(endpoint)[:2] != urlsplit(self.origin)[:2]:
            raise FieldcheckError("Agent Card points to another origin; key was not sent")
        self.endpoint = endpoint
        return card

    def register(self, name="Agent workspace", source="sdk"):
        if self.key:
            raise FieldcheckError("A workspace key is already configured")
        response = self.http.post(self.origin + "/api/agent-workspaces", json={"name": name, "source": source}, follow_redirects=False)
        response.raise_for_status()
        registration = response.json()
        self.key = registration["key"]
        return {k: v for k, v in registration.items() if k != "key"}

    def rpc(self, method, params):
        if not self.key:
            raise FieldcheckError("Provide an existing key or explicitly register a workspace")
        if not self.endpoint:
            self.discover()
        response = self.http.post(self.endpoint, json={"jsonrpc": "2.0", "id": str(uuid4()), "method": method, "params": params},
                                  headers={"Authorization": "Bearer " + self.key, "A2A-Version": "1.0"}, follow_redirects=False)
        if response.status_code == 402:
            raise FieldcheckError("Check credits exhausted. Owner-approved funding is required; no purchase was made.")
        response.raise_for_status()
        body = response.json()
        if "error" in body:
            raise FieldcheckError(f"A2A error {body['error']['code']}: {body['error']['message']}")
        return body["result"]

    def submit(self, contract, *, message_id, context_id=None):
        message = {"messageId": message_id, "role": "ROLE_USER", "parts": [{"data": {"command": "check", "contract": contract}}]}
        if context_id:
            message["contextId"] = context_id
        return self.rpc("SendMessage", {"message": message, "configuration": {"returnImmediately": True}})["task"]

    def get_task(self, task_id):
        return self.rpc("GetTask", {"id": task_id})

    def wait(self, task, *, timeout=120, poll_seconds=1):
        deadline = time.monotonic() + timeout
        while task["status"]["state"] in {"TASK_STATE_SUBMITTED", "TASK_STATE_WORKING"}:
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Task {task['id']} is still running; resume with get_task, without submitting a new message")
            time.sleep(min(poll_seconds, max(0, deadline - time.monotonic())))
            task = self.get_task(task["id"])
        return task
