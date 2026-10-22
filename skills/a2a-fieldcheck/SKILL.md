---
name: a2a-fieldcheck
description: Check an authorized A2A agent dependency against a JSON behavior contract and retrieve pass/fail evidence with JUnit. Use for deployment gates, routing regressions or checking an agent before delegation.
---

# A2A Fieldcheck

Call the hosted checker through A2A 1.0 JSON-RPC. The public beta offers 20 free
credits per workspace; checkout is disabled. The backend is a local beta with
no uptime guarantee. A caller's workspace key and authorized budget control use.

Run the pinned client without cloning its repository:

```bash
uvx --from git+https://github.com/radislabus-star/fieldcheck-agent-client.git@v0.3.0 fieldcheck-agent --help
```

Use an existing owner-only key file or `FIELDCHECK_KEY`. Never print or commit
the key. Create a free workspace only when registration is requested; reserve
a new path in an existing private directory:

```bash
uvx --from git+https://github.com/radislabus-star/fieldcheck-agent-client.git@v0.3.0 fieldcheck-agent \
  --register --register-only --key-file /private/directory/fieldcheck.key
```

Choose a meaningful assertion about the target the user authorized you to call.
The target must expose unauthenticated A2A 1.0 over public HTTPS port 443.
Read the current schema and limits at
https://a2a-fieldcheck.radislabus.workers.dev/agents before constructing a
contract. For a JSON-RPC target that completes a Task, a contract can be:

```json
{
  "name": "Billing route before delegation",
  "url": "https://YOUR-AUTHORIZED-AGENT.example",
  "message": "A customer says their card was charged twice.",
  "data_path": "/queue",
  "data_equals": "billing-disputes",
  "trials": 1,
  "p95_seconds": 15
}
```

For structured requests, `input_data` is one finite JSON object of at most
4096 UTF-8 bytes. Select `transport: "HTTP+JSON"` and/or
`response_state: "message"` only when the target advertises that exchange.
The whole contract must fit 16384 UTF-8 bytes. Do not send secrets in contracts.

```bash
uvx --from git+https://github.com/radislabus-star/fieldcheck-agent-client.git@v0.3.0 fieldcheck-agent \
  --key-file /private/directory/fieldcheck.key --contract contract.json \
  --message-id UNIQUE-RELEASE-AND-CONTRACT-ID --junit result.xml
```

Persist the message ID with the exact contract before sending. Reuse both for
a transport retry; changing the ID orders another check. Poll an existing task
with `--resume TASK_ID`. Stop when the supplied budget is exhausted: the client
does not buy credits or create replacement workspaces.

Stdout is the A2A Task JSON; stderr includes retry and task IDs. Exit 0 means
the behavioral assertion passed, 1 means it failed, and 2 means a client,
service or artifact error. `TASK_STATE_COMPLETED` alone is not a pass: inspect
`behavioral-check.json` and its boolean `passed`. Preserve the JUnit/JSON
evidence and distinguish assertion failures from transport errors.

Omitting `--contract` checks the operator's healthy demo. Such a run verifies
integration only; it is not a check of the user's dependency.
