# Check an A2A Agent Card before signup

This small Python CLI reads a public Agent Card and reports whether its
advertised protocol, transport and authentication fit Fieldcheck's supported
targets. It uses Python 3.10+ and the standard library. No account, API key,
package installation or Fieldcheck credits are needed.

```bash
python3 preflight.py https://YOUR-AGENT/.well-known/agent-card.json
```

Supply the exact public HTTPS Card URL of your dependency. The script makes
one discovery GET and returns JSON; it never invokes the advertised task URL.

| Exit | Result | Meaning |
| --- | --- | --- |
| 0 | `advertised_compatible` | An interface advertises the supported version and transport, with no auth requirement detected. |
| 1 | `unsupported` | All advertised interfaces conflict with the target constraints. |
| 2 | `unknown` | Metadata, skill authentication, extensions or legacy interfaces require review. |
| 3 | `error` | The Card could not be fetched or parsed within the network limits. |

The metadata check supports A2A 1.0 JSONRPC and HTTP+JSON, public HTTPS port
443 and anonymous targets. It checks each interface separately. A zero exit
does not prove that the task endpoint works or that a behavioral contract will
pass. `behavioral_acceptance` remains `not_tested`.

After a compatible result, choose a meaningful assertion and follow the
[Fieldcheck client instructions](../../README.md#check-an-authorized-dependency)
for a real behavioral check. Select the reported transport explicitly when it
is HTTP+JSON. The contract URL is the target origin, not its Card URL.

For a discovery-only example, run:

```bash
python3 preflight.py https://a2a-fieldcheck.radislabus.workers.dev/.well-known/agent-card.json
```

This returns exit 1: Fieldcheck itself requires a workspace Bearer key, so it
cannot be an anonymous target of another Fieldcheck check. Authenticated
callers can use Fieldcheck to check other, anonymous agents.

Only public HTTPS destinations are fetched. DNS answers must all be global;
the selected address is pinned while TLS/SNI retain the hostname. Redirects,
URL credentials, query strings, fragments and compression are refused.
Responses are limited to 64 KiB. Socket operations have an eight-second
timeout and body reads a twenty-second deadline after DNS resolution. The OS
resolver controls DNS timing; this is not a wall-clock limit covering DNS.

Run the offline verification from this directory:

```bash
python3 -B -m unittest discover -s . -v
```

Ten tests cover fixture compatibility, per-interface selection, authentication,
version handling, URL/DNS restrictions, pinned connections, redirects, size,
compression, parsing and exit codes. Network boundary tests use mocks. A live
GET of the public Fieldcheck Card was also verified; no task or signup was made.

Fields follow the [A2A specification](https://a2a-protocol.org/latest/specification/)
and [Agent Discovery guide](https://a2a-protocol.org/latest/topics/agent-discovery/).
The narrower target constraints are documented in
[Fieldcheck's machine instructions](https://a2a-fieldcheck.radislabus.workers.dev/agents).
