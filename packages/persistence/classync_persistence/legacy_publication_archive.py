"""Validate an explicit, archive-only mapping of legacy SQLite publications.

Legacy rows do not contain the canonical command or academic revision required
for replayable PostgreSQL publications. This module preserves the supplied
hashes and payload bytes without asserting that a row is current or replayable.
"""

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class LegacyPublicationError(ValueError):
    """A legacy publication is incomplete, corrupt, ambiguous, or unmapped."""


@dataclass(frozen=True)
class ArchivedPublication:
    tenant_id: str
    owner_uid: str
    source_tenant: str
    source_actor: str
    legacy_id: str
    source_sequence: int
    dataset: str
    period_id: str
    revision: int
    draft_id: str
    created_at: str
    idempotency_key: str
    request_hash: str
    payload: str
    checksum: str
    replayable: bool = False
    current: bool = False


def _required_text(row: Mapping, name: str) -> str:
    value = row.get(name)
    if not isinstance(value, str) or not value.strip():
        raise LegacyPublicationError(f"Legacy publication {name} is required")
    return value


def archive_legacy_publications(
    rows: Sequence[Mapping],
    *,
    owner_map: Mapping[tuple[str, str], tuple[str, str]],
) -> list[ArchivedPublication]:
    """Map generated/authorized source rows for immutable historical retention.

    `owner_map` must explicitly map each (source tenant, source actor) to a
    target (tenant, owner UID). No source identity is inferred or defaulted.
    Returned rows are intentionally non-replayable and non-current.
    """
    result = []
    seen_ids = set()
    seen_sequences = set()
    seen_keys = set()
    for row in rows:
        source_tenant = _required_text(row, "tenant")
        source_actor = _required_text(row, "actor")
        mapping = owner_map.get((source_tenant, source_actor))
        if (
            not isinstance(mapping, tuple)
            or len(mapping) != 2
            or any(not isinstance(value, str) or not value.strip() for value in mapping)
        ):
            raise LegacyPublicationError("An explicit target tenant and owner mapping is required")
        tenant_id, owner_uid = mapping

        legacy_id = _required_text(row, "id")
        sequence = row.get("sequence")
        revision = row.get("revision")
        if type(sequence) is not int or sequence < 1:
            raise LegacyPublicationError("Legacy publication sequence must be positive")
        if type(revision) is not int or revision < 1:
            raise LegacyPublicationError("Legacy publication revision must be positive")
        if (source_tenant, legacy_id) in seen_ids or sequence in seen_sequences:
            raise LegacyPublicationError("Legacy publication identity or sequence is duplicated")
        seen_ids.add((source_tenant, legacy_id))
        seen_sequences.add(sequence)

        dataset = _required_text(row, "dataset")
        if dataset not in {"institutional", "synthetic"}:
            raise LegacyPublicationError("Legacy publication dataset is unsupported")
        period_id = _required_text(row, "period_id")
        draft_id = _required_text(row, "draft_id")
        idempotency_key = _required_text(row, "idempotency_key")
        if not 8 <= len(idempotency_key) <= 120:
            raise LegacyPublicationError("Legacy idempotency key length is invalid")

        request_hash = _required_text(row, "request_hash")
        checksum = _required_text(row, "checksum")
        if not _SHA256.fullmatch(request_hash) or not _SHA256.fullmatch(checksum):
            raise LegacyPublicationError("Legacy hashes must be preserved SHA-256 values")
        payload = _required_text(row, "payload")
        observed_checksum = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        if observed_checksum != checksum:
            raise LegacyPublicationError("Legacy publication payload checksum does not match")
        try:
            decoded = json.loads(payload)
            draft = decoded["draft"]
            created_at = datetime.fromisoformat(_required_text(row, "created_at"))
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
            message = "Legacy publication payload or timestamp is invalid"
            raise LegacyPublicationError(message) from error
        if (
            not isinstance(decoded, dict)
            or not isinstance(draft, dict)
            or draft.get("id") != draft_id
            or draft.get("period_id") != period_id
            or draft.get("creator") != source_actor
            or not isinstance(decoded.get("calendar"), dict)
        ):
            raise LegacyPublicationError("Legacy publication payload scope does not match its row")
        if created_at.tzinfo is None or created_at.utcoffset() is None:
            raise LegacyPublicationError("Legacy publication timestamp must include a timezone")

        key = (tenant_id, dataset, idempotency_key)
        if key in seen_keys:
            raise LegacyPublicationError("Mapped legacy idempotency key is duplicated")
        seen_keys.add(key)
        result.append(
            ArchivedPublication(
                tenant_id=tenant_id,
                owner_uid=owner_uid,
                source_tenant=source_tenant,
                source_actor=source_actor,
                legacy_id=legacy_id,
                source_sequence=sequence,
                dataset=dataset,
                period_id=period_id,
                revision=revision,
                draft_id=draft_id,
                created_at=created_at.isoformat(),
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                payload=payload,
                checksum=checksum,
            )
        )
    return result


def import_legacy_publications(
    engine,
    *,
    tenant_id: str,
    firebase_project_id: str,
    principal,
    source_fingerprint: str,
    rows: Sequence[Mapping],
    owner_map: Mapping[tuple[str, str], tuple[str, str]],
) -> int:
    """Atomically store immutable history under a current verified Admin scope.

    This operation only inserts into `legacy_publication_archive`; archived
    rows never create a publication head and cannot become timetable state.
    Exact retries are no-ops. A changed retry aborts the whole transaction.
    """
    from classync_contracts.identity import (
        MembershipAuthorizationError,
        MembershipErrorCode,
        VerifiedPrincipal,
    )
    from sqlalchemy import text

    from .database import transaction
    from .memberships import identity_context

    if not isinstance(principal, VerifiedPrincipal):
        raise ValueError("Trusted verified principal required")
    if not isinstance(tenant_id, str) or not tenant_id.strip():
        raise ValueError("Explicit target tenant required")
    if not isinstance(firebase_project_id, str) or not firebase_project_id.strip():
        raise ValueError("Explicit Firebase project required")
    if not isinstance(source_fingerprint, str) or not _SHA256.fullmatch(source_fingerprint):
        raise ValueError("Source database SHA-256 fingerprint required")
    archived = archive_legacy_publications(rows, owner_map=owner_map)
    if any(row.tenant_id != tenant_id for row in archived):
        raise LegacyPublicationError("Archive owner mapping crosses the target tenant")
    columns = (
        "source_fingerprint", "source_tenant", "source_actor", "legacy_id",
        "source_sequence", "tenant_id", "owner_uid", "dataset", "period_id",
        "revision", "draft_id", "created_at", "idempotency_key", "request_hash",
        "payload", "checksum",
    )
    inserted = 0
    with transaction(engine) as connection:
        identity_context(connection, tenant_id=tenant_id, uid=principal.uid)
        connection.execute(
            text("SELECT set_config('classsync.project_id', :project, true), "
                 "set_config('classsync.role', 'administrator', true)"),
            {"project": firebase_project_id},
        )
        authorized = connection.scalar(
            # Reuse 0008's constrained helper: SELECT-only identity readers
            # cannot directly take PostgreSQL row locks without UPDATE grants.
            text("SELECT classsync_scheduling.lock_publication_authority()"),
            {"tenant": tenant_id, "uid": principal.uid, "project": firebase_project_id},
        )
        if not authorized:
            raise MembershipAuthorizationError(MembershipErrorCode.DENIED)
        select_existing = text("""
            SELECT source_fingerprint,source_tenant,source_actor,legacy_id,source_sequence,
                   tenant_id,owner_uid,dataset,period_id,revision,draft_id,created_at,
                   idempotency_key,request_hash,payload,checksum
            FROM classsync_scheduling.legacy_publication_archive
            WHERE source_fingerprint=:source_fingerprint AND source_tenant=:source_tenant
                AND legacy_id=:legacy_id
        """)
        # Archive rows are immutable; unique keys serialize competing inserts.
        # A row-locking read would require an intentionally absent UPDATE grant.
        insert_row = text("""
            INSERT INTO classsync_scheduling.legacy_publication_archive
                (source_fingerprint,source_tenant,source_actor,legacy_id,source_sequence,
                 tenant_id,owner_uid,dataset,period_id,revision,draft_id,created_at,
                 idempotency_key,request_hash,payload,checksum)
            VALUES (:source_fingerprint,:source_tenant,:source_actor,:legacy_id,:source_sequence,
                    :tenant_id,:owner_uid,:dataset,:period_id,:revision,:draft_id,:created_at,
                    :idempotency_key,:request_hash,:payload,:checksum)
            ON CONFLICT DO NOTHING
        """)
        for row in archived:
            values = {
                "source_fingerprint": source_fingerprint,
                **{name: getattr(row, name) for name in columns if name != "source_fingerprint"},
                "created_at": datetime.fromisoformat(row.created_at),
            }
            existing = connection.execute(select_existing, values).mappings().one_or_none()
            if existing is not None:
                same = all(
                    existing[name] == values[name]
                    for name in columns
                    if name != "created_at"
                ) and existing["created_at"] == values["created_at"]
                if not same:
                    raise LegacyPublicationError(
                        "Legacy archive retry differs from stored evidence"
                    )
                continue
            outcome = connection.execute(insert_row, values)
            if outcome.rowcount == 1:
                inserted += 1
                continue
            # Another transaction may have inserted the same source row. The
            # table's unique keys and next transactional read distinguish an
            # exact retry from a collision in every other unique scope.
            existing = connection.execute(select_existing, values).mappings().one_or_none()
            if existing is None or any(
                existing[name] != values[name]
                for name in columns
                if name not in {"source_fingerprint", "source_tenant", "legacy_id", "created_at"}
            ) or existing["created_at"] != values["created_at"]:
                raise LegacyPublicationError("Legacy archive row conflicts with stored evidence")
    return inserted
