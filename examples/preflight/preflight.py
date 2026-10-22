#!/usr/bin/env python3
"""Anonymous, read-only advertised target compatibility. Python 3.10+, stdlib."""
import argparse
import http.client
import ipaddress
import json
import re
import socket
import ssl
import sys
import time
from urllib.parse import urlsplit

MAX_BYTES = 65536
TIMEOUT = 8
USER_AGENT = 'Fieldcheck-Anonymous-Preflight/0.1 (Agent Card discovery only)'


def public_url(url):
    if not isinstance(url, str) or any(ord(c) <= 32 for c in url):
        raise ValueError('URL must be a public HTTPS URL without whitespace')
    p = urlsplit(url)
    if (p.scheme != 'https' or not p.hostname or p.port not in (None, 443)
            or p.username is not None or p.password is not None or p.query or p.fragment):
        raise ValueError('Require HTTPS port 443, no credentials, query or fragment')
    host = p.hostname.rstrip('.')
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        if host.lower() == 'localhost' or '.' not in host:
            raise ValueError('Require a public hostname or global IP address')
    else:
        if not address.is_global:
            raise ValueError('Non-public address rejected')
    return p


def fetch_card(url):
    p = public_url(url)
    addresses = socket.getaddrinfo(p.hostname, 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise ValueError('DNS must resolve exclusively to public addresses')
    # Pin the validated address; retain the original hostname for TLS/SNI.
    address = addresses[0][4][0]
    conn = http.client.HTTPSConnection(p.hostname, 443, timeout=TIMEOUT,
                                       context=ssl.create_default_context())
    conn._create_connection = lambda dest, timeout, source_address=None: socket.create_connection(
        (address, 443), timeout, source_address)
    deadline = time.monotonic() + 20
    try:
        conn.request('GET', p.path or '/', headers={
            'User-Agent': USER_AGENT, 'Accept': 'application/json, application/a2a+json',
            'Accept-Encoding': 'identity'})
        response = conn.getresponse()
        if response.status != 200:
            raise ValueError(f'HTTP {response.status}; redirects are never followed')
        if response.getheader('Content-Encoding', 'identity').lower() != 'identity':
            raise ValueError('Compressed responses are not accepted')
        size = response.getheader('Content-Length')
        if size is not None and (not size.isdigit() or int(size) > MAX_BYTES):
            raise ValueError('Invalid or oversized Content-Length')
        body = bytearray()
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('Read deadline exceeded')
            if conn.sock is not None:
                conn.sock.settimeout(min(TIMEOUT, remaining))
            chunk = response.read1(min(4096, MAX_BYTES + 1 - len(body)))
            if not chunk:
                break
            body.extend(chunk)
            if len(body) > MAX_BYTES:
                raise ValueError('Agent Card exceeds 65536 bytes')
        return json.loads(body.decode('utf-8'))
    finally:
        conn.close()


def auth_status(obj):
    req = obj.get('securityRequirements', [])
    if not isinstance(req, list):
        return 'unknown'
    if any(not isinstance(r, dict) or not isinstance(r.get('schemes'), dict) for r in req):
        return 'unknown'
    if any(r['schemes'] for r in req):
        # Deliberately do not infer an anonymous alternative from mixed requirements.
        return 'required' if all(r['schemes'] for r in req) else 'conditional'
    if obj.get('securitySchemes'):
        return 'unknown'
    if obj.get('security') or obj.get('authentication'):
        return 'unknown'  # legacy auth is not silently treated as anonymous
    return 'none_advertised'


def assess(card):
    if not isinstance(card, dict):
        raise ValueError('Agent Card must be a JSON object')
    auth = auth_status(card)
    notes = []
    if auth != 'none_advertised':
        notes.append('Target authentication is required, conditional or ambiguous; Fieldcheck cannot supply target credentials.')
    skills = card.get('skills', [])
    if not isinstance(skills, list) or any(not isinstance(s, dict) for s in skills):
        notes.append('Malformed skills; select and inspect the intended operation.')
    elif any(auth_status(s) != 'none_advertised' for s in skills):
        notes.append('A skill advertises authentication; anonymous access to the intended skill is unconfirmed.')
    caps = card.get('capabilities', {})
    if not isinstance(caps, dict):
        notes.append('Malformed capabilities.')
    elif caps.get('extensions'):
        notes.append('Extensions advertised; required extension compatibility has not been assessed.')
    interfaces = card.get('supportedInterfaces')
    if not isinstance(interfaces, list) or not interfaces:
        return {'status': 'unknown', 'authentication': auth, 'interfaces': [],
                'notes': notes + ['No A2A 1.0 supportedInterfaces list; legacy fields are not a substitute.'],
                'behavioral_acceptance': 'not_tested'}
    results = []
    for item in interfaces:
        if not isinstance(item, dict):
            results.append({'status': 'unknown', 'reasons': ['Malformed interface']})
            continue
        reasons = []
        version = item.get('protocolVersion')
        if not isinstance(version, str) or not re.fullmatch(r'1\.0(?:\.\d+)?', version):
            reasons.append('Requires advertised protocolVersion 1.0 or 1.0.x')
        if item.get('protocolBinding') not in ('JSONRPC', 'HTTP+JSON'):
            reasons.append('Requires JSONRPC or HTTP+JSON')
        try:
            public_url(item.get('url'))
        except (ValueError, TypeError):
            reasons.append('Endpoint must advertise public HTTPS port 443 without URL credentials/query/fragment')
        if auth == 'required':
            reasons.append('Target requires authentication; authenticated targets are unsupported')
        if item.get('tenant'):
            reasons.append('Tenant routing is not documented as supported by Fieldcheck')
        status = 'unsupported' if reasons else ('unknown' if notes else 'advertised_compatible')
        results.append({'url': item.get('url'), 'transport': item.get('protocolBinding'),
                        'protocol_version': version, 'status': status, 'reasons': reasons})
    statuses = [r['status'] for r in results]
    status = ('advertised_compatible' if 'advertised_compatible' in statuses else
              'unknown' if 'unknown' in statuses else 'unsupported')
    return {'status': status, 'authentication': auth, 'interfaces': results, 'notes': notes,
            'behavioral_acceptance': 'not_tested'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('card_url', help='Explicit public HTTPS Agent Card URL (not the task endpoint)')
    args = parser.parse_args(argv)
    try:
        result = assess(fetch_card(args.card_url))
        result['scope'] = 'Advertised anonymous TARGET compatibility only; no task, signup, endpoint probe or credit use.'
        print(json.dumps(result, indent=2))
        return {'advertised_compatible': 0, 'unsupported': 1, 'unknown': 2}[result['status']]
    except (ValueError, OSError, http.client.HTTPException, RecursionError) as exc:
        print(json.dumps({'status': 'error', 'error': str(exc)}))
        return 3


if __name__ == '__main__':
    sys.exit(main())
