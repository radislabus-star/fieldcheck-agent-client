"""Order an authorized A2A behavior check or explicitly create a free workspace."""
import argparse
import json
import os
from pathlib import Path
import stat
import sys
from uuid import uuid4

import httpx

from .client import FieldcheckClient, FieldcheckError

PUBLIC_SERVICE = "https://a2a-fieldcheck.radislabus.workers.dev"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--service", default=PUBLIC_SERVICE)
    parser.add_argument("--key-file", type=Path, help="Owner-only existing key, or a new destination with --register")
    parser.add_argument("--register", action="store_true", help="Explicitly create one free workspace; requires a new --key-file")
    parser.add_argument("--register-only", action="store_true", help="Create the workspace without ordering a check; requires --register")
    parser.add_argument("--workspace-name", default="Agent workspace")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--contract", type=Path, help="JSON behavioral contract; omit for the operator's healthy demo")
    selection.add_argument("--resume", help="Retrieve an existing task without submitting a new check")
    parser.add_argument("--message-id", help="Reuse this ID with the exact contract for transport retries")
    parser.add_argument("--junit", type=Path)
    args = parser.parse_args(argv)
    if args.register_only and (not args.register or args.contract or args.resume or args.message_id or args.junit):
        parser.error("--register-only requires --register and cannot order, resume or export a check")
    key = os.environ.get("FIELDCHECK_KEY")
    if args.register:
        if not args.key_file or args.key_file.exists() or key or args.resume:
            parser.error("--register requires a new --key-file, without an existing FIELDCHECK_KEY or --resume")
    elif not args.key_file and not key:
        parser.error("Use --key-file or FIELDCHECK_KEY; creating a workspace requires --register explicitly")

    client = None
    old_umask = os.umask(0o077)
    try:
        # Reject unreadable or malformed local input before creating a workspace.
        contract = None
        if not args.register_only and not args.resume:
            if args.contract:
                raw = args.contract.read_bytes()
                if len(raw) > 16384:
                    raise FieldcheckError("Contract must fit 16384 UTF-8 bytes")
                contract = json.loads(raw)
                if not isinstance(contract, dict):
                    raise FieldcheckError("Contract must be a JSON object")
            else:
                contract = {"name": "Agent quickstart demo", "url": "demo:healthy"}
        if not args.register and args.key_file:
            if stat.S_IMODE(args.key_file.stat().st_mode) & 0o077:
                raise FieldcheckError("Key file must be accessible only to its owner (chmod 600)")
            key = args.key_file.read_text().strip()
            if not key:
                raise FieldcheckError("Key file is empty; no registration or check was attempted")
        client = FieldcheckClient(args.service, key)
        client.discover()
        if args.register:
            # Reserve the destination before the remote mutation. Never overwrite
            # an existing key or silently create another workspace on a retry.
            with args.key_file.open("x") as key_file:
                try:
                    registration = client.register(args.workspace_name)
                    key_file.write(client.key + "\n")
                    key_file.flush()
                    os.fsync(key_file.fileno())
                except BaseException:
                    args.key_file.unlink(missing_ok=True)
                    raise
            if args.register_only:
                print(json.dumps({"workspace_id": registration["id"], "credits": registration["credits"],
                    "key_saved": True, "check_submitted": False}))
                return 0
        if args.resume:
            task = client.get_task(args.resume)
        else:
            message_id = args.message_id or str(uuid4())
            print(json.dumps({"message_id": message_id,
                "note": "Persist this ID and the exact contract to retry without a second charge"}), file=sys.stderr)
            task = client.submit(contract, message_id=message_id)
            print(json.dumps({"task_id": task["id"]}), file=sys.stderr)
        task = client.wait(task)
        print(json.dumps(task, ensure_ascii=False))
        report = next((part.get("data") for artifact in task.get("artifacts", [])
            if artifact.get("name") == "behavioral-check.json"
            for part in artifact.get("parts", []) if isinstance(part.get("data"), dict)), None)
        if report is None or type(report.get("passed")) is not bool:
            raise FieldcheckError("Task has no boolean behavioral-check result; inspect its state and resume with its task ID")
        if args.junit:
            junit = next((part["text"] for artifact in task.get("artifacts", [])
                if artifact.get("name") == "fieldcheck.xml"
                for part in artifact.get("parts", []) if isinstance(part.get("text"), str)), None)
            if junit is None:
                raise FieldcheckError("Task has no JUnit artifact")
            args.junit.write_text(junit)
        return 0 if report["passed"] else 1
    except (FieldcheckError, TimeoutError, httpx.HTTPError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    finally:
        if client is not None:
            client.close()
        os.umask(old_umask)


if __name__ == "__main__":
    raise SystemExit(main())
