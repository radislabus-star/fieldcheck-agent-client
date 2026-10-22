# Fieldcheck: behavioral checks for A2A agents

Call an A2A agent to check the behavior of another agent. Send a small contract,
receive pass/fail and JSON/JUnit evidence, and decide whether to continue a
deployment or delegate to that dependency.

Fieldcheck supports **A2A 1.0 JSON-RPC** through `SendMessage` and `GetTask`.
It does not use an LLM to turn prose into a contract. The client needs only
Python 3.10+ and HTTPX; it does not install the Fieldcheck server or its checker.

## Try the public beta

**Stable gateway address, checked 2026-10-22:**
<https://a2a-fieldcheck.radislabus.workers.dev>

The gateway keeps its address when the backend tunnel changes. The backend is
still a local beta reached through a development tunnel, without an availability
guarantee. It is unsuitable for a production dependency. Do not send secrets in
contracts. Use the supplied HTTPX client; Cloudflare rejected Python urllib's
default client with 403/1010 in the live check. See [endpoint details](docs/ENDPOINT.md).
The current beta has **20 free checks per workspace**. Paid checkout is disabled.

Public discovery record: [Global A2A Registry](https://www.a2a-registry.org/agent/dev.workers.a2a_fieldcheck).
The listing is unclaimed; it is not protocol certification or an endorsement.

- [Agent Card](https://a2a-fieldcheck.radislabus.workers.dev/.well-known/agent-card.json)
- [Machine integration, contract schema and limits](https://a2a-fieldcheck.radislabus.workers.dev/agents)
- [Optional operator dashboard](https://a2a-fieldcheck.radislabus.workers.dev/)

With [uv](https://docs.astral.sh/uv/guides/tools/), run the pinned client
without a manual clone or server installation. Client 0.3.0 works with the
current 0.2.2 server.

```bash
# Register explicitly once. The new file holds a secret; keep it private.
uvx --from git+https://github.com/radislabus-star/fieldcheck-agent-client.git@v0.3.0 fieldcheck-agent \
  --register --key-file ~/.fieldcheck-beta-key \
  --message-id first-demo --junit result.xml
```

The first run executes a real exchange with our deterministic demo agent; it
does not need a model key. It is a demonstration, not a customer success claim.
The key is saved with owner-only permissions and is not printed.
Use `--register --register-only --key-file NEW_PRIVATE_PATH` to create a
workspace without ordering the demo or consuming a check credit. Registration
is explicit; an existing key is never overwritten. Later calls reuse that key.

To install with pip, use a virtual environment and
`python -m pip install 'git+https://github.com/radislabus-star/fieldcheck-agent-client.git@v0.3.0'`;
then run `fieldcheck-agent` with the same arguments.

## Install the agent skill

The [a2a-fieldcheck skill](skills/a2a-fieldcheck/SKILL.md) teaches an agent how
to choose an assertion, preserve its retry ID, respect its workspace budget and
read the JSON/JUnit result. With Node.js 22.20+:

```bash
npx skills add radislabus-star/fieldcheck-agent-client --skill a2a-fieldcheck
```

The [skills CLI](https://github.com/vercel-labs/skills) lets you select your
coding agent and installs to the current project by default. Installing this
skill does not register a workspace, run a check or make a purchase.

## Check an authorized dependency

Copy `examples/router-contract.json` and replace its example origin with an
agent you are authorized to invoke. That target must accept unauthenticated
A2A 1.0 JSON-RPC or HTTP+JSON requests over public HTTPS on port 443.

```json
{
  "name": "Support routing before deployment",
  "url": "https://agent.example.com",
  "message": "A customer says their card was charged twice.",
  "data_path": "/queue",
  "data_equals": "billing-disputes",
  "trials": 1,
  "p95_seconds": 15
}
```

```bash
uvx --from git+https://github.com/radislabus-star/fieldcheck-agent-client.git@v0.3.0 fieldcheck-agent \
  --key-file ~/.fieldcheck-beta-key --contract my-contract.json \
  --message-id support-router-release-42 --junit router.xml
```

Exit codes: **0** assertion passed, **1** assertion failed, **2** client error.
Save the printed task ID to resume with `--resume TASK_ID`. For a network retry,
reuse the same `--message-id` and exact contract: the service returns the same
task without charging another credit. A new check needs a new message ID.

## Structured read-only example

The OpenQFR owner [invites public read-only interoperability tests](https://github.com/openqfr-dev/openqfr/issues/2).
The included `examples/openqfr-stats-contract.json` selects its advertised
HTTP+JSON binding, sends `{"operation":"stats"}` as a structured part and
expects an immediate Message. It asserts `/schemaVersion`, not the field's
internal Python spelling. It does not validate the research or trading results.
The [timestamped report](docs/OPENQFR_INTEROP.md) includes a direct reproduction,
the observed positive result and a deliberate failing assertion. It is operator
QA, not a customer activation or an endorsement by OpenQFR.

```bash
uvx --from git+https://github.com/radislabus-star/fieldcheck-agent-client.git@v0.3.0 fieldcheck-agent \
  --key-file ~/.fieldcheck-beta-key \
  --contract examples/openqfr-stats-contract.json \
  --message-id openqfr-stats-check-1 --junit openqfr.xml
```

Target defaults remain `transport: "JSONRPC"` and `response_state: "completed"`.
Optional `input_data` is one JSON object of at most 4096 UTF-8 bytes. It sends no
text unless `message` is supplied; supplying both sends both. Without either,
the original routing-demo message is used. The full contract must fit 16384
UTF-8 bytes. These fields select the target exchange; the client still orders
checks from Fieldcheck through JSON-RPC. The server must be 0.2.1 or later.

## Use from an orchestrator

```python
import os
from fieldcheck_agent import FieldcheckClient

client = FieldcheckClient(
    "https://a2a-fieldcheck.radislabus.workers.dev",
    key=os.environ["FIELDCHECK_KEY"],
)
try:
    client.discover()
    task = client.submit(
        {"name": "Demo contract", "url": "demo:healthy"},
        message_id="persist-a-unique-id-for-this-check",
    )
    task = client.wait(task)
    report = next(
        a["parts"][0]["data"] for a in task.get("artifacts", [])
        if a["name"] == "behavioral-check.json"
    )
    allow_delegation = report["passed"] is True
    # Apply this decision within your own workflow and authorization policy.
finally:
    client.close()
```

`TASK_STATE_COMPLETED` means the check finished; inspect `report["passed"]`
to decide whether the assertion passed. A failing assertion consumes one credit.
An infrastructure failure refunds it. Each check can invoke the target 1–3
times; the target's own provider charges are outside Fieldcheck credits. Owners
must approve the target, calls and budgets. A check proves only its stated
contract, not general correctness or full protocol conformance.

The client refuses an Agent Card endpoint on another origin and does not follow
redirects with the workspace key. It never purchases credits or transfers funds.
HTTP 402 stops the call and asks for owner-approved funding; do not evade the
limit by automatically registering another workspace.

## Status and implementation

This repository contains the small client, executable example and client tests.
The running beta adds workspaces, persisted tasks, a bounded queue, scheduled
checks through its REST API, credit accounting and private result history.
It uses [a2a-proof 0.16.0](https://pypi.org/project/a2a-proof/) by Alexey Larionov
for the behavioral checks; the client does not bundle that engine.

Streaming, push notifications, cancellation, authenticated targets, gRPC,
A2A 0.3, AP2 and x402 are not supported by this beta. No uptime, conversion or
revenue claim is made. There are no independent customer results yet.

To report a reproducible integration issue, open an issue with the sanitized
contract, task state and expected behavior. Never post workspace keys, cookies,
wallet information or sensitive target responses.

## Development

```bash
.venv/bin/python -m pip install '.[test]'
.venv/bin/python -m pytest
```

MIT license. See [LICENSE](LICENSE).
