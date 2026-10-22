# Public beta endpoint

Canonical gateway: <https://a2a-fieldcheck.radislabus.workers.dev>.
Verified 2026-10-22, 08:40 UTC with HTTPX and an actual Chromium session.

- [A2A 1.0 Agent Card](https://a2a-fieldcheck.radislabus.workers.dev/.well-known/agent-card.json)
- [Machine instructions](https://a2a-fieldcheck.radislabus.workers.dev/agents)
- [Contract schema](https://a2a-fieldcheck.radislabus.workers.dev/agents/contract.schema.json)
- JSON-RPC: `POST /a2a`, using an explicitly created workspace Bearer key.

The fixed-origin Cloudflare Worker forwards to the existing isolated beta.
It advertises its stable address in discovery documents and onboarding replies.
It does not store workspace keys, wallet credentials or requests. Responses are
not cached. The beta remains on a local computer behind a temporary tunnel;
changing that tunnel requires an operator update. A stable address does not
provide continuous availability or a production SLA.

The live checks passed discovery, explicit agent onboarding, authenticated
workspace access, Secure/HttpOnly browser login, successful and deliberately
failing A2A demo contracts, JSON/JUnit artifacts, and idempotent replay. A foreign
browser Origin was rejected with 403; a body over 32 KiB was rejected with 413.
These were operator checks, not independent customers or revenue.

Use the Python HTTPX client supplied in this repository. Its default client and
Chromium both passed. Python urllib's default user agent received Cloudflare
403/1010 before reaching the gateway. No claim is made that every HTTP client
or every network can reach this beta.

The beta includes 20 free credits per workspace. Checkout remains disabled.
