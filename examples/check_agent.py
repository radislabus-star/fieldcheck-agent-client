#!/usr/bin/env python3
"""Explicitly register once or reuse a secret key, then order one A2A check."""
import argparse
import json
import os
from pathlib import Path
import stat
import sys
from uuid import uuid4

from fieldcheck_agent import FieldcheckClient, FieldcheckError


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--service", default="http://127.0.0.1:8844")
    p.add_argument("--key-file", type=Path, help="Private file containing an existing key, or destination when --register is explicit")
    p.add_argument("--register", action="store_true", help="Explicitly create a free workspace once; --key-file must be a new path")
    p.add_argument("--workspace-name", default="Agent quickstart")
    p.add_argument("--contract", type=Path, help="JSON MonitorSpec. Omit for the deterministic demo, which is not customer demand")
    p.add_argument("--message-id", default=None, help="Persist and reuse for transport retries; changing it orders another check")
    p.add_argument("--resume", help="Poll an existing task instead of ordering another check")
    p.add_argument("--junit", type=Path)
    args = p.parse_args()
    os.umask(0o077)
    key = os.environ.get("FIELDCHECK_KEY")
    if args.register:
        if not args.key_file or args.key_file.exists() or key:
            p.error("--register requires a new --key-file, without an existing FIELDCHECK_KEY")
    elif args.key_file:
        if stat.S_IMODE(args.key_file.stat().st_mode) & 0o077:
            p.error("Key file must be accessible only to its owner (chmod 600)")
        key = args.key_file.read_text().strip()
    if not key and not args.register:
        p.error("Use an existing --key-file or FIELDCHECK_KEY; registration requires --register explicitly")
    client = FieldcheckClient(args.service, key)
    try:
        client.discover()
        if args.register:
            # Reserve the destination before any request. O_EXCL prevents an
            # overwrite/race and makes a failed registration visible to caller.
            with args.key_file.open("x") as key_file:
                try:
                    client.register(args.workspace_name)
                    key_file.write(client.key + "\n")
                    key_file.flush()
                    os.fsync(key_file.fileno())
                except BaseException:
                    args.key_file.unlink(missing_ok=True)
                    raise
        if args.resume:
            task = client.get_task(args.resume)
        else:
            contract = json.loads(args.contract.read_text()) if args.contract else {"name": "Agent quickstart demo", "url": "demo:healthy"}
            message_id = args.message_id or str(uuid4())
            print(json.dumps({"message_id": message_id, "note": "Persist this ID to retry the same request without a second charge"}), file=sys.stderr)
            task = client.submit(contract, message_id=message_id)
            print(json.dumps({"task_id": task["id"]}), file=sys.stderr)
        task = client.wait(task)
        print(json.dumps(task, ensure_ascii=False))
        if args.junit:
            junit = next((a["parts"][0]["text"] for a in task.get("artifacts", []) if a.get("name") == "fieldcheck.xml"), None)
            if junit is not None:
                args.junit.write_text(junit)
        passed = task.get("artifacts", [{}])[0].get("parts", [{}])[0].get("data", {}).get("passed", False)
        return 0 if passed else 1
    except (FieldcheckError, TimeoutError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
