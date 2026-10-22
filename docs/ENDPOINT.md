# Public beta endpoint

Canonical gateway: <https://a2a-fieldcheck.radislabus.workers.dev>.
Amsterdam hosting accepted 2026-10-22, 10:52 UTC; server 0.2.2 checked with
HTTPX and an actual authenticated Chromium session.

- [A2A 1.0 Agent Card](https://a2a-fieldcheck.radislabus.workers.dev/.well-known/agent-card.json)
- [Machine instructions](https://a2a-fieldcheck.radislabus.workers.dev/agents)
- [Contract schema](https://a2a-fieldcheck.radislabus.workers.dev/agents/contract.schema.json)
- JSON-RPC: `POST /a2a`, using an explicitly created workspace Bearer key.

The fixed-origin Cloudflare Worker forwards through a persistent named tunnel
to the isolated beta on an Amsterdam VPS.
It advertises its stable address in discovery documents and onboarding replies.
It does not store workspace keys, wallet credentials or requests. Responses are
not cached. The serving path no longer depends on the operator's workstation.
App, tunnel and egress guard have enabled boot units; an actual server reboot
has not been tested. This beta has no production SLA.

The live checks passed discovery, explicit agent onboarding, authenticated
workspace access, Secure/HttpOnly browser login, successful and deliberately
failing A2A demo contracts, JSON/JUnit artifacts, and idempotent replay. A foreign
browser Origin was rejected with 403; a body over 32 KiB was rejected with 413.
These were operator checks, not independent customers or revenue.

Use the Python HTTPX client supplied in this repository. Its default client and
Chromium both passed. Python urllib's default user agent received Cloudflare
403/1010 before reaching the gateway. No claim is made that every HTTP client
or every network can reach this beta.

## Entry for ordinary non-browser clients

The same hosted service also accepts direct HTTPS requests at
<https://fieldcheck-origin.cdn-storage-api.com>. On 2026-10-22 at 22:52–22:53 UTC,
Python urllib with its default User-Agent passed discovery, authenticated
workspace access and A2A `GetTask` for an existing QA task. Actual Chromium
login and the disabled-checkout page passed. The existing 17-credit QA balance
did not change; no workspace or new check was created.

Use this origin explicitly when a client receives 403/1010 on workers.dev. Its
Agent Card advertises its own `/a2a` URL. The CLI supports
`--service https://fieldcheck-origin.cdn-storage-api.com`; use the same service
origin for discovery, onboarding and subsequent authenticated calls. Do not
automatically forward a key across an arbitrary redirect or another hostname.

The compatibility change disables Cloudflare Browser Integrity Check only for
the exact project hostname, using one `http_config_settings` rule. The zone's
global Browser Integrity Check remains on. App authentication, browser Origin
validation, request-size limits and disabled checkout passed negative controls.
The workers.dev hostname still rejects default urllib and is not claimed fixed.
This is an entry correction, not independent adoption or payment acceptance.

The beta includes 20 free credits per workspace. Checkout remains disabled.
Server 0.2.2 adds an isolated, receive-only verification connection. It does not
enable paid checkout: funded mainnet payment acceptance is still untested.
