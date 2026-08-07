"""Separate, atomic local ledger for participant reward issuance."""

from __future__ import annotations

import csv
import json
import os
import tempfile
import threading
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from app.rewards.base import RewardClaim

DEFAULT_REWARD_LEDGER_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "runtime" / "acl_rewards.csv"
)
REWARD_FIELDNAMES = (
    "reward_reference",
    "study_version",
    "is_test",
    "status",
    "provider",
    "provider_reward_id",
    "provider_status",
    "last_checked_at",
    "amount",
    "currency",
    "error_code",
    "created_at",
    "updated_at",
)
PRE_RECONCILIATION_REWARD_FIELDNAMES = tuple(
    field
    for field in REWARD_FIELDNAMES
    if field not in {"provider_status", "last_checked_at"}
)
LEGACY_REWARD_FIELDNAMES = (
    "reward_reference",
    "study_version",
    "is_test",
    "status",
    "provider",
    "provider_reward_id",
    "redemption_url",
    "amount",
    "currency",
    "error_code",
    "created_at",
    "updated_at",
)
REWARD_STATUSES = frozenset({"declined", "issuing", "issued", "failed"})

_LOCKS_GUARD = threading.Lock()
_FILE_LOCKS: dict[Path, threading.RLock] = {}


class RewardLedgerError(RuntimeError):
    """Raised when reward state cannot be read or changed safely."""


class RewardBudgetExceededError(RuntimeError):
    """Raised before issuance when a configured hard limit is exhausted."""


class RewardIssuancePausedError(RuntimeError):
    """Raised before issuance while the operator kill switch is active."""


@dataclass(frozen=True)
class RewardControlState:
    """Persistent operator controls stored separately from reward records."""

    paused: bool = False
    updated_at: datetime | None = None


@dataclass(frozen=True)
class RewardRecord:
    """Pseudonymous reward state, deliberately separate from survey answers."""

    reward_reference: str
    study_version: str
    is_test: bool
    status: str
    provider: str
    provider_reward_id: str
    amount: Decimal
    currency: str
    error_code: str
    created_at: datetime
    updated_at: datetime
    provider_status: str = ""
    last_checked_at: datetime | None = None


def _file_lock(path: Path) -> threading.RLock:
    resolved = path.resolve()
    with _LOCKS_GUARD:
        return _FILE_LOCKS.setdefault(resolved, threading.RLock())


def _timestamp(value: str, *, reward_reference: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise RewardLedgerError(
            f"Reward {reward_reference} has invalid {field}."
        ) from error
    if parsed.tzinfo is None:
        raise RewardLedgerError(f"Reward {reward_reference} has timezone-free {field}.")
    return parsed


def parse_reward_row(row: dict[str, str], *, row_number: int) -> RewardRecord:
    reference = (row.get("reward_reference") or "").strip()
    if not reference:
        raise RewardLedgerError(f"Reward row {row_number} has no reference.")
    is_test_text = (row.get("is_test") or "").strip().lower()
    status = (row.get("status") or "").strip()
    if is_test_text not in {"true", "false"} or status not in REWARD_STATUSES:
        raise RewardLedgerError(f"Reward {reference} has invalid metadata.")
    try:
        amount = Decimal((row.get("amount") or "").strip())
    except InvalidOperation as error:
        raise RewardLedgerError(f"Reward {reference} has invalid amount.") from error
    currency = (row.get("currency") or "").strip().upper()
    study_version = (row.get("study_version") or "").strip()
    provider = (row.get("provider") or "").strip()
    provider_reward_id = (row.get("provider_reward_id") or "").strip()
    provider_status = (row.get("provider_status") or "").strip().upper()
    last_checked_text = (row.get("last_checked_at") or "").strip()
    if (
        not amount.is_finite()
        or amount <= 0
        or len(currency) != 3
        or not study_version
        or not provider
        or (status == "issued" and not provider_reward_id)
        or (
            provider_status
            and (
                len(provider_status) > 32
                or not provider_status.replace("_", "").isalnum()
            )
        )
        or (provider_status and not last_checked_text)
    ):
        raise RewardLedgerError(f"Reward {reference} has invalid values.")
    return RewardRecord(
        reward_reference=reference,
        study_version=study_version,
        is_test=is_test_text == "true",
        status=status,
        provider=provider,
        provider_reward_id=provider_reward_id,
        amount=amount,
        currency=currency,
        error_code=(row.get("error_code") or "").strip(),
        created_at=_timestamp(
            row.get("created_at") or "",
            reward_reference=reference,
            field="created_at",
        ),
        updated_at=_timestamp(
            row.get("updated_at") or "",
            reward_reference=reference,
            field="updated_at",
        ),
        provider_status=provider_status,
        last_checked_at=(
            _timestamp(
                last_checked_text,
                reward_reference=reference,
                field="last_checked_at",
            )
            if last_checked_text
            else None
        ),
    )


def serialize_reward_row(record: RewardRecord) -> dict[str, str]:
    return {
        "reward_reference": record.reward_reference,
        "study_version": record.study_version,
        "is_test": str(record.is_test).lower(),
        "status": record.status,
        "provider": record.provider,
        "provider_reward_id": record.provider_reward_id,
        "provider_status": record.provider_status,
        "last_checked_at": (
            record.last_checked_at.isoformat() if record.last_checked_at else ""
        ),
        "amount": str(record.amount),
        "currency": record.currency,
        "error_code": record.error_code,
        "created_at": record.created_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
    }


class CSVRewardLedger:
    """Persist exactly one current reward record per pseudonymous reference."""

    def __init__(self, path: Path = DEFAULT_REWARD_LEDGER_PATH) -> None:
        self.path = path
        self.control_path = path.with_suffix(f"{path.suffix}.control.json")
        self._lock = _file_lock(path)

    def _read_control(self) -> RewardControlState:
        if not self.control_path.exists():
            return RewardControlState()
        try:
            payload = json.loads(self.control_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise RewardLedgerError("Reward controls could not be read.") from error
        if not isinstance(payload, dict) or not isinstance(payload.get("paused"), bool):
            raise RewardLedgerError("Reward controls have invalid values.")
        updated_at_text = payload.get("updated_at")
        if not isinstance(updated_at_text, str):
            raise RewardLedgerError("Reward controls have no update timestamp.")
        return RewardControlState(
            paused=payload["paused"],
            updated_at=_timestamp(
                updated_at_text,
                reward_reference="controls",
                field="updated_at",
            ),
        )

    def load_control(self) -> RewardControlState:
        with self._lock:
            return self._read_control()

    def set_paused(
        self, paused: bool, *, now: datetime | None = None
    ) -> RewardControlState:
        changed_at = now or datetime.now(UTC)
        if changed_at.tzinfo is None:
            raise RewardLedgerError("Reward control timestamp must include a timezone.")
        state = RewardControlState(paused=paused, updated_at=changed_at)
        with self._lock:
            self.control_path.parent.mkdir(parents=True, exist_ok=True)
            temporary_path: Path | None = None
            try:
                descriptor, temporary_name = tempfile.mkstemp(
                    dir=self.control_path.parent,
                    prefix=f".{self.control_path.name}.",
                    suffix=".tmp",
                )
                temporary_path = Path(temporary_name)
                with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                    json.dump(
                        {
                            "paused": state.paused,
                            "updated_at": changed_at.isoformat(),
                        },
                        handle,
                        separators=(",", ":"),
                    )
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary_path, self.control_path)
            except OSError as error:
                raise RewardLedgerError(
                    "Reward controls could not be replaced."
                ) from error
            finally:
                if temporary_path is not None and temporary_path.exists():
                    temporary_path.unlink()
        return state

    def _read_all(self) -> dict[str, RewardRecord]:
        if not self.path.exists():
            return {}
        try:
            with self.path.open(encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                if tuple(reader.fieldnames or ()) not in {
                    REWARD_FIELDNAMES,
                    PRE_RECONCILIATION_REWARD_FIELDNAMES,
                    LEGACY_REWARD_FIELDNAMES,
                }:
                    raise RewardLedgerError(
                        "Reward ledger has an unexpected column contract."
                    )
                rows = list(reader)
        except OSError as error:
            raise RewardLedgerError("Reward ledger could not be read.") from error
        records: dict[str, RewardRecord] = {}
        for row_number, row in enumerate(rows, start=2):
            record = parse_reward_row(row, row_number=row_number)
            if record.reward_reference in records:
                raise RewardLedgerError(
                    f"Duplicate reward reference: {record.reward_reference}."
                )
            records[record.reward_reference] = record
        return records

    def _write_all(self, records: dict[str, RewardRecord]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            descriptor, temporary_name = tempfile.mkstemp(
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
            )
            temporary_path = Path(temporary_name)
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=REWARD_FIELDNAMES)
                writer.writeheader()
                for reference in sorted(records):
                    writer.writerow(serialize_reward_row(records[reference]))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, self.path)
        except OSError as error:
            raise RewardLedgerError("Reward ledger could not be replaced.") from error
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()

    def load(self, reward_reference: str) -> RewardRecord | None:
        with self._lock:
            return self._read_all().get(reward_reference)

    def list_records(self) -> tuple[RewardRecord, ...]:
        with self._lock:
            records = self._read_all()
            return tuple(records[reference] for reference in sorted(records))

    def update_provider_status(
        self,
        reward_reference: str,
        provider_status: str,
        *,
        now: datetime | None = None,
    ) -> RewardRecord:
        checked_at = now or datetime.now(UTC)
        if checked_at.tzinfo is None:
            raise RewardLedgerError("Reward check timestamp must include a timezone.")
        normalized = provider_status.strip().upper()
        if (
            not normalized
            or len(normalized) > 32
            or not normalized.replace("_", "").isalnum()
        ):
            raise RewardLedgerError("Reward provider status is invalid.")
        with self._lock:
            records = self._read_all()
            existing = records.get(reward_reference)
            if existing is None or existing.status != "issued":
                raise RewardLedgerError("Issued reward record was not found.")
            updated = replace(
                existing,
                provider_status=normalized,
                last_checked_at=checked_at,
                updated_at=checked_at,
            )
            records[reward_reference] = updated
            self._write_all(records)
            return updated

    def scrub_legacy_links(self) -> bool:
        """Rewrite a legacy ledger so bearer-style reward URLs are not retained."""
        with self._lock:
            if not self.path.exists():
                return False
            try:
                with self.path.open(encoding="utf-8", newline="") as handle:
                    fieldnames = tuple(csv.DictReader(handle).fieldnames or ())
            except OSError as error:
                raise RewardLedgerError("Reward ledger could not be read.") from error
            if fieldnames == REWARD_FIELDNAMES:
                return False
            records = self._read_all()
            self._write_all(records)
            return True

    def decline(
        self,
        *,
        reward_reference: str,
        study_version: str,
        is_test: bool,
        provider: str,
        amount: Decimal,
        currency: str,
        now: datetime | None = None,
    ) -> RewardRecord:
        declined_at = now or datetime.now(UTC)
        if declined_at.tzinfo is None:
            raise RewardLedgerError("Reward timestamp must include a timezone.")
        with self._lock:
            records = self._read_all()
            existing = records.get(reward_reference)
            if existing is not None:
                expected = (study_version, is_test, provider, amount, currency)
                actual = (
                    existing.study_version,
                    existing.is_test,
                    existing.provider,
                    existing.amount,
                    existing.currency,
                )
                if actual != expected:
                    raise RewardLedgerError(
                        f"Reward configuration changed for {reward_reference}."
                    )
                if existing.status in {"declined", "issued", "issuing"}:
                    return existing
            declined = RewardRecord(
                reward_reference=reward_reference,
                study_version=study_version,
                is_test=is_test,
                status="declined",
                provider=provider,
                provider_reward_id="",
                amount=amount,
                currency=currency,
                error_code="",
                created_at=existing.created_at if existing else declined_at,
                updated_at=declined_at,
            )
            records[reward_reference] = declined
            self._write_all(records)
            return declined

    def issue_once(
        self,
        *,
        reward_reference: str,
        study_version: str,
        is_test: bool,
        provider: str,
        amount: Decimal,
        currency: str,
        issuer: Callable[[], RewardClaim],
        max_issued_count: int = 25,
        budget_limit: Decimal = Decimal("85.00"),
        now: datetime | None = None,
    ) -> RewardRecord:
        issued_at = now or datetime.now(UTC)
        if issued_at.tzinfo is None:
            raise RewardLedgerError("Reward timestamp must include a timezone.")
        with self._lock:
            records = self._read_all()
            existing = records.get(reward_reference)
            if existing is not None:
                expected = (
                    study_version,
                    is_test,
                    provider,
                    amount,
                    currency,
                )
                actual = (
                    existing.study_version,
                    existing.is_test,
                    existing.provider,
                    existing.amount,
                    existing.currency,
                )
                if actual != expected:
                    raise RewardLedgerError(
                        f"Reward configuration changed for {reward_reference}."
                    )
                if existing.status == "issued":
                    return existing
            if self._read_control().paused:
                raise RewardIssuancePausedError("Reward issuance is paused.")
            reserved = tuple(
                record
                for reference, record in records.items()
                if reference != reward_reference
                and record.status in {"issuing", "issued"}
            )
            if any(record.currency != currency for record in reserved):
                raise RewardLedgerError(
                    "Reward ledger contains mixed currencies for one budget."
                )
            if len(reserved) >= max_issued_count:
                raise RewardBudgetExceededError("Reward count limit has been reached.")
            reserved_amount = sum(
                (record.amount for record in reserved), start=Decimal("0")
            )
            if reserved_amount + amount > budget_limit:
                raise RewardBudgetExceededError("Reward budget has been exhausted.")
            issuing = RewardRecord(
                reward_reference=reward_reference,
                study_version=study_version,
                is_test=is_test,
                status="issuing",
                provider=provider,
                provider_reward_id="",
                amount=amount,
                currency=currency,
                error_code="",
                created_at=existing.created_at if existing else issued_at,
                updated_at=issued_at,
            )
            records[reward_reference] = issuing
            self._write_all(records)
            try:
                claim = issuer()
                if (
                    claim.provider != provider
                    or claim.amount != amount
                    or claim.currency != currency
                    or not claim.reference
                ):
                    raise RewardLedgerError(
                        "Reward provider returned an inconsistent claim."
                    )
            except Exception as error:
                records[reward_reference] = replace(
                    issuing,
                    status="failed",
                    error_code=type(error).__name__,
                    updated_at=issued_at,
                )
                self._write_all(records)
                raise
            issued = replace(
                issuing,
                status="issued",
                provider_reward_id=claim.reference,
                updated_at=issued_at,
            )
            records[reward_reference] = issued
            self._write_all(records)
            return issued
