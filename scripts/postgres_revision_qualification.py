"""Prove deterministic stale-writer/rollback behavior in a new disposable cluster."""

import argparse
import json
import queue
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from classync_contracts.identity import MembershipState, VerifiedPrincipal
from classync_persistence.database import transaction
from classync_persistence.membership_changes import (
    MembershipRevisionConflict,
    change_membership_state,
)
from classync_persistence.memberships import identity_context
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from scripts.postgres_disposable import qualify
from scripts.postgres_driver_qualification import engine_for, require
from scripts.postgres_restore_qualification import exercise as restore_exercise


def exercise(connection):
    restored = restore_exercise(connection)
    owner = engine_for(connection, bootstrap=True)
    try:
        with transaction(owner) as session:
            migration_owner = session.scalar(text("""
                SELECT pg_get_userbyid(c.relowner) FROM pg_class c
                JOIN pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname='classsync_identity' AND c.relname='memberships'
            """))
        require(re.fullmatch(r"classsync_migrator_[a-f0-9]{32}", migration_owner) is not None,
                "Expected generated nonlogin migration owner")

        def scope(session):
            session.execute(text(f"SET LOCAL ROLE {migration_owner}"))
            session.execute(text("SET LOCAL lock_timeout='3s'"))
            session.execute(text("SET LOCAL statement_timeout='4s'"))
            identity_context(session, tenant_id="tenant-a", uid="uid-a")

        def update(session, *, expected=2, state=MembershipState.INACTIVE, **overrides):
            values = dict(tenant_id="tenant-a", uid="uid-a", expected_revision=expected,
                          state=state, actor=VerifiedPrincipal(uid="synthetic-operator"))
            return change_membership_state(session, **(values | overrides))

        pid_queue = queue.Queue()

        def competing_writer():
            try:
                with transaction(owner) as session:
                    scope(session)
                    pid_queue.put(session.scalar(text("SELECT pg_backend_pid()")))
                    return update(session, state=MembershipState.ACTIVE)
            except MembershipRevisionConflict:
                return "stale_conflict"

        # Both writers use revision2. The second must wait for the first row lock,
        # then PostgreSQL rechecks its revision predicate against committed rev3.
        with ThreadPoolExecutor(max_workers=1) as executor:
            first = owner.connect()
            first_tx = first.begin()
            try:
                scope(first)
                first_pid = first.scalar(text("SELECT pg_backend_pid()"))
                require(update(first) == 3, "First writer did not produce revision3")
                competing = executor.submit(competing_writer)
                second_pid = pid_queue.get(timeout=3)
                blocked = False
                deadline = time.monotonic() + 2
                with transaction(owner) as monitor:
                    while time.monotonic() < deadline:
                        blockers = monitor.scalar(text("SELECT pg_blocking_pids(:pid)"),
                                                  {"pid": second_pid})
                        if first_pid in blockers:
                            blocked = True
                            break
                        time.sleep(0.02)
                require(blocked, "Did not observe the intended competing row lock")
                first_tx.commit()
                require(competing.result(timeout=6) == "stale_conflict",
                        "Stale writer overwrote the committed winner")
            finally:
                if first_tx.is_active:
                    first_tx.rollback()
                first.close()
        try:
            with transaction(owner) as session:
                scope(session)
                require(update(session, expected=3, state=MembershipState.ACTIVE) == 4,
                        "Rollback test did not apply a candidate mutation")
                raise ValueError("synthetic application rollback")
        except ValueError:
            pass
        for context_uid, target_tenant, expected in (
            ("uid-a", "tenant-b", 1), ("unrelated", "tenant-a", 3),
        ):
            try:
                with transaction(owner) as session:
                    scope(session)
                    identity_context(session, tenant_id="tenant-a", uid=context_uid)
                    update(session, expected=expected, tenant_id=target_tenant)
            except MembershipRevisionConflict:
                pass
            else:
                raise RuntimeError("Out-of-scope state change succeeded")
        guards = ["state='active'", "revision=revision+2",
                  "uid='mutated', revision=revision+1",
                  "tenant_id='tenant-b', revision=revision+1"]
        for mutation in guards:
            try:
                with transaction(owner) as session:
                    scope(session)
                    session.execute(text(f"UPDATE classsync_identity.memberships SET {mutation} "
                                         "WHERE tenant_id='tenant-a' AND uid='uid-a'"))
            except DBAPIError as error:
                require(error.orig.sqlstate == "23514", "Wrong revision-guard SQLSTATE")
            else:
                raise RuntimeError("Direct revision/key mutation escaped database guard")
        with transaction(owner) as session:
            row = session.execute(text("""
                SELECT state,revision FROM classsync_identity.memberships
                WHERE tenant_id='tenant-a' AND uid='uid-a'
            """)).one()
            require(tuple(row) == ("inactive", 3), "Rollback/stale conflict changed winner")
            other = session.execute(text("""
                SELECT state,revision FROM classsync_identity.memberships
                WHERE tenant_id='tenant-b' AND uid='uid-a'
            """)).one()
            require(tuple(other) == ("active", 1), "Cross-tenant attempt changed authority")
        return {"restore": restored, "competing_lock_observed": True,
                "stale_writer_conflict": True, "rollback_preserved_revision": True,
                "tenant_uid_mutation_denied": True, "database_revision_guard": True,
                "winner_state": "inactive", "winner_revision": 3}
    finally:
        owner.dispose()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bin", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists() or not args.output.parent.is_dir():
        raise ValueError("Output must be a new file in an existing directory")
    evidence = qualify(args.bin, exercise)
    with args.output.open("x") as output:
        output.write(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
