import httpx
import pytest

from fieldcheck_agent import FieldcheckClient, FieldcheckError


def test_client_discovers_sends_contract_and_polls_without_cookie():
    requests = []
    def serve(request):
        requests.append(request)
        if request.url.path == "/.well-known/agent-card.json":
            assert "authorization" not in request.headers
            return httpx.Response(200, json={"supportedInterfaces": [{"url": "https://fieldcheck.example/a2a", "protocolBinding": "JSONRPC", "protocolVersion": "1.0"}]})
        if request.url.path == "/api/agent-workspaces":
            return httpx.Response(201, json={"id": "workspace", "key": "secret", "credits": 20})
        assert request.headers["a2a-version"] == "1.0"
        assert request.headers["authorization"] == "Bearer secret"
        assert "cookie" not in request.headers
        import json
        payload = json.loads(request.content)
        if payload["method"] == "SendMessage":
            assert payload["params"]["message"]["messageId"] == "stable-id"
            return httpx.Response(200, json={"result": {"task": {"id": "task", "status": {"state": "TASK_STATE_SUBMITTED"}}}})
        return httpx.Response(200, json={"result": {"id": "task", "status": {"state": "TASK_STATE_COMPLETED"}}})
    with httpx.Client(transport=httpx.MockTransport(serve), follow_redirects=True) as http:
        c = FieldcheckClient("https://fieldcheck.example", http=http)
        c.discover()
        assert "key" not in c.register()
        receipt = c.submit({"name": "One", "url": "demo:healthy"}, message_id="stable-id")
        assert c.wait(receipt, poll_seconds=0)["status"]["state"] == "TASK_STATE_COMPLETED"
    assert len(requests) == 4


def test_cross_origin_discovery_does_not_send_key():
    requests = []
    def serve(request):
        requests.append(request)
        return httpx.Response(200, json={"supportedInterfaces": [{"url": "https://thief.example/a2a", "protocolBinding": "JSONRPC", "protocolVersion": "1.0"}]})
    with httpx.Client(transport=httpx.MockTransport(serve)) as http:
        c = FieldcheckClient("https://fieldcheck.example", "secret", http=http)
        with pytest.raises(FieldcheckError, match="another origin"):
            c.submit({}, message_id="retry")
    assert len(requests) == 1
    assert "authorization" not in requests[0].headers


def test_client_never_follows_redirect_with_credentials_or_buys_credits():
    requests = []
    def serve(request):
        requests.append(request)
        return httpx.Response(302, headers={"Location": "https://thief.example/a2a"})
    with httpx.Client(transport=httpx.MockTransport(serve), follow_redirects=True) as http:
        c = FieldcheckClient("https://fieldcheck.example", "secret", http=http)
        c.endpoint = "https://fieldcheck.example/a2a"
        with pytest.raises(httpx.HTTPStatusError):
            c.submit({}, message_id="retry")
    assert len(requests) == 1
    def exhausted(request):
        return httpx.Response(402, json={"error": {"code": -32000, "message": "No budget"}})
    with httpx.Client(transport=httpx.MockTransport(exhausted)) as http:
        c = FieldcheckClient("https://fieldcheck.example", "secret", http=http)
        c.endpoint = "https://fieldcheck.example/a2a"
        with pytest.raises(FieldcheckError, match="no purchase was made"):
            c.submit({}, message_id="retry")
