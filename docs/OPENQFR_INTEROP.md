# OpenQFR A2A read-only interoperability check

Verified **2026-10-22, 01:29–01:32 UTC**. This is Fieldcheck operator QA,
not an independent Fieldcheck customer, endorsement, payment or revenue.
The OpenQFR maintainer [invites reproducible public read-only checks](https://github.com/openqfr-dev/openqfr/issues/2).
No credentials, private records or mutations were submitted.

## Environment and exact scope

- Fieldcheck server 0.2.1; Python 3.13.13; httpx 0.28.1.
- Behavioral engine: MIT-licensed [a2a-proof 0.16.0](https://pypi.org/project/a2a-proof/)
  by Alexey Larionov.
- Discovery: <https://openqfr.dev/.well-known/agent-card.json>.
- Advertised interface: A2A 1.0, `HTTP+JSON`, base URL
  `https://openqfr.dev/a2a/v1`.
- Read-only operation: `stats`, with `{"operation":"stats"}` in a data part.
- Expected A2A response: a Message containing structured data; assert
  `/schemaVersion == "0.1.0-pilot"`.

Only this A2A path and assertion were checked. MCP/REST parity, search/get,
provenance and general protocol conformance were not tested. One trial does
not establish availability or a latency distribution.

## Results

| Check | Observed result |
| --- | --- |
| Read the live Card and select its declared HTTP+JSON interface | PASS |
| Positive contract through the public Fieldcheck A2A endpoint | PASS; target Message, expected schema version, 99 ms engine duration |
| Same target with deliberately wrong expected schema | FAIL as expected; actual `0.1.0-pilot`, 128 ms engine duration |
| Positive check JSON and JUnit artifacts | Present and retrieved |
| Reuse the positive message ID and identical contract | Same task; zero additional credits |
| Replay a task created before the Fieldcheck 0.2.1 update | Same task; zero additional credits |

Both target checks completed as Fieldcheck tasks. The negative assertion is a
successful detection of an intentionally wrong expectation, not an OpenQFR
defect. Together they consumed two free check credits; replays consumed none.
These durations describe single checks at the stated time, not a benchmark.

The target's wire data uses camelCase `schemaVersion`. The expected response
is an A2A Message, so a contract requiring a completed Task would be wrong for
this operation. These are contract settings, not reported target bugs.

## Reproduce directly, without Fieldcheck

Install `httpx>=0.28.1,<1`, then run this public read-only request:

```python
from uuid import uuid4
import httpx

origin = "https://openqfr.dev"
with httpx.Client(timeout=20, follow_redirects=False) as client:
    response = client.get(origin + "/.well-known/agent-card.json")
    response.raise_for_status()
    card = response.json()
    interface = next(i for i in card["supportedInterfaces"]
                     if i["protocolBinding"] == "HTTP+JSON"
                     and i["protocolVersion"] == "1.0")
    assert interface["url"] == origin + "/a2a/v1"
    response = client.post(interface["url"] + "/message:send",
        headers={"Content-Type": "application/a2a+json", "A2A-Version": "1.0"},
        json={"message": {"messageId": str(uuid4()), "role": "ROLE_USER",
                          "parts": [{"data": {"operation": "stats"}}]}})
    response.raise_for_status()
    message = response.json()["message"]
    data = next(part["data"] for part in message["parts"] if "data" in part)
    assert data["schemaVersion"] == "0.1.0-pilot", data
    print({"passed": True, "schemaVersion": data["schemaVersion"]})
```

## Reproduce through Fieldcheck

Use the [client instructions](../README.md) and
[`examples/openqfr-stats-contract.json`](../examples/openqfr-stats-contract.json).
Register a workspace explicitly once and preserve its key and message IDs.
The beta offers 20 free checks. It uses a temporary development tunnel and
paid checkout is disabled. Target calls must remain within the target owner's
read-only scope.

```bash
python examples/check_agent.py \
  --service https://ver-feels-passing-carb.trycloudflare.com \
  --key-file fieldcheck.key \
  --contract examples/openqfr-stats-contract.json \
  --message-id my-openqfr-schema-001 --junit openqfr.xml
```

Set `data_equals` to `"intentionally-wrong-schema"` and use a **new** message
ID to reproduce the negative control. An altered contract must not reuse the
original message ID. The Fieldcheck entry point uses A2A JSON-RPC; the checker
selects HTTP+JSON for the target according to the contract.
