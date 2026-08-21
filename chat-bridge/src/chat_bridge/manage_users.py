"""Operator CLI for provisioning accounts.

Signup is closed -- no HTTP endpoint creates users -- so this is the only
way to add one. Run via `docker exec -it` (the -it matters: `add` prompts
for a password rather than taking it as an argument, so it never lands in
shell history or `docker inspect`'s recorded process list):

    docker exec -it rosetta-chat-bridge /app/.venv/bin/python -m chat_bridge.manage_users add you@example.com
    docker exec -it rosetta-chat-bridge /app/.venv/bin/python -m chat_bridge.manage_users list
    docker exec -it rosetta-chat-bridge /app/.venv/bin/python -m chat_bridge.manage_users remove you@example.com
"""

import argparse
import datetime
import getpass
import sys

from argon2 import PasswordHasher

from . import user_store

_hasher = PasswordHasher()


def _cmd_add(args: argparse.Namespace) -> None:
    password = getpass.getpass("Password: ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("Passwords did not match.", file=sys.stderr)
        raise SystemExit(1)
    try:
        user_store.add_user(args.email, _hasher.hash(password))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
    print(f"Added {args.email}")


def _cmd_remove(args: argparse.Namespace) -> None:
    # Does not invalidate an already-issued JWT for this user -- see
    # user_store.remove_user's docstring and the Phase 8 report.
    if user_store.remove_user(args.email):
        print(f"Removed {args.email}")
    else:
        print(f"No such user: {args.email}", file=sys.stderr)
        raise SystemExit(1)


def _cmd_list(_args: argparse.Namespace) -> None:
    users = user_store.list_users()
    if not users:
        print("No users.")
        return
    for email, created_at in users:
        when = datetime.datetime.fromtimestamp(created_at, tz=datetime.timezone.utc)
        print(f"{email}\t{when.isoformat()}")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="manage_users", description="Provision chat-bridge accounts (signup is closed)."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    add_p = sub.add_parser("add", help="Create a new account (prompts for password)")
    add_p.add_argument("email")
    add_p.set_defaults(func=_cmd_add)

    remove_p = sub.add_parser("remove", help="Delete an account")
    remove_p.add_argument("email")
    remove_p.set_defaults(func=_cmd_remove)

    list_p = sub.add_parser("list", help="List accounts")
    list_p.set_defaults(func=_cmd_list)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
