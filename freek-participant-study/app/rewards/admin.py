"""Privacy-safe operational summaries for the separate reward ledger."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Iterable

from app.rewards.ledger import RewardRecord

REWARD_AUDIT_COLUMNS = (
    "reward_reference",
    "study_version",
    "is_test",
    "status",
    "provider",
    "provider_reward_id",
    "amount",
    "currency",
    "error_code",
    "created_at",
    "updated_at",
)


@dataclass(frozen=True)
class RewardOperationsOverview:
    """Counts and value needed to monitor reward delivery."""

    total_count: int
    issued_count: int
    declined_count: int
    failed_count: int
    issuing_count: int
    stuck_count: int
    issued_amount: Decimal
    currency: str | None


def filter_reward_records(
    records: Iterable[RewardRecord], *, include_test: bool | None
) -> tuple[RewardRecord, ...]:
    """Filter by test status; ``None`` includes both real and test records."""
    selected = tuple(
        record
        for record in records
        if include_test is None or record.is_test is include_test
    )
    return tuple(sorted(selected, key=lambda record: record.updated_at, reverse=True))


def build_reward_operations_overview(
    records: Iterable[RewardRecord],
    *,
    now: datetime | None = None,
    stuck_after: timedelta = timedelta(minutes=10),
) -> RewardOperationsOverview:
    records = tuple(records)
    current_time = now or datetime.now(UTC)
    if current_time.tzinfo is None:
        raise ValueError("Reward operations timestamp must include a timezone.")
    currencies = {record.currency for record in records if record.status == "issued"}
    return RewardOperationsOverview(
        total_count=len(records),
        issued_count=sum(record.status == "issued" for record in records),
        declined_count=sum(record.status == "declined" for record in records),
        failed_count=sum(record.status == "failed" for record in records),
        issuing_count=sum(record.status == "issuing" for record in records),
        stuck_count=sum(
            record.status == "issuing"
            and current_time - record.updated_at >= stuck_after
            for record in records
        ),
        issued_amount=sum(
            (record.amount for record in records if record.status == "issued"),
            start=Decimal("0"),
        ),
        currency=next(iter(currencies)) if len(currencies) == 1 else None,
    )


def reward_audit_rows(
    records: Iterable[RewardRecord],
) -> tuple[dict[str, object], ...]:
    """Return operational fields without raw sessions or redemption links."""
    return tuple(
        {
            "reward_reference": record.reward_reference,
            "study_version": record.study_version,
            "is_test": record.is_test,
            "status": record.status,
            "provider": record.provider,
            "provider_reward_id": record.provider_reward_id,
            "amount": str(record.amount),
            "currency": record.currency,
            "error_code": record.error_code,
            "created_at": record.created_at.isoformat(),
            "updated_at": record.updated_at.isoformat(),
        }
        for record in records
    )


def reward_audit_csv(records: Iterable[RewardRecord]) -> str:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=REWARD_AUDIT_COLUMNS)
    writer.writeheader()
    writer.writerows(reward_audit_rows(records))
    return output.getvalue()
