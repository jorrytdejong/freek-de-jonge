"""Server-side Supabase Postgres storage for participant progress."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from app.storage.base import SavedProgress
from app.storage.csv_storage import AlreadySubmittedError, ProgressStorageError


class SupabaseProgressStorage:
    """Progress adapter using the private Supabase Postgres schema."""

    def __init__(self, connection_string: str) -> None:
        self.connection_string = connection_string.strip()
        if not self.connection_string:
            raise ProgressStorageError("Supabase database connection is empty.")

    def _connect(self):
        try:
            import psycopg
        except ImportError as error:
            raise ProgressStorageError("Supabase storage requires psycopg.") from error
        try:
            return psycopg.connect(self.connection_string)
        except Exception as error:
            raise ProgressStorageError("Supabase storage could not be initialized.") from error

    @staticmethod
    def _record(row: Mapping[str, Any], submissions: tuple[dict[str, object], ...]) -> SavedProgress:
        return SavedProgress(
            session_id=row["session_id"], study_version=row["study_version"],
            is_test=row["is_test"], current_page=row["current_page"],
            profile=row["profile"], responses=row["responses"], drafts=row["drafts"],
            status=row["status"], final_comment=row["final_comment"],
            submissions=submissions, created_at=row["created_at"], updated_at=row["updated_at"],
        )

    @staticmethod
    def _json(value: object) -> object:
        from psycopg.types.json import Jsonb

        return Jsonb(json.loads(json.dumps(value)))

    def load_progress(self, session_id: str) -> SavedProgress | None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("""
                select session_id, study_version, is_test, current_page, profile,
                       responses, drafts, status, final_comment, created_at, updated_at
                from private.study_progress where session_id = %s
            """, (session_id,))
            row = cursor.fetchone()
            if row is None:
                return None
            columns = [description.name for description in cursor.description]
            record = dict(zip(columns, row, strict=True))
            cursor.execute("""
                select submission_id, submission_number, study_version, is_test,
                       profile, responses, final_comment, submitted_at
                from private.study_submissions
                where session_id = %s order by submission_number
            """, (session_id,))
            events = tuple({
                "submission_id": event[0], "submission_number": event[1],
                "study_version": event[2], "is_test": event[3], "profile": event[4],
                "responses": event[5], "final_comment": event[6],
                "submitted_at": event[7].isoformat(),
            } for event in cursor.fetchall())
            return self._record(record, events)

    def list_progress(self) -> tuple[SavedProgress, ...]:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("select session_id from private.study_progress order by session_id")
            session_ids = [row[0] for row in cursor.fetchall()]
        return tuple(record for sid in session_ids if (record := self.load_progress(sid)))

    def save_progress(self, **kwargs: object) -> SavedProgress:
        saved_at = kwargs.pop("now", None) or datetime.now(UTC)
        existing = self.load_progress(str(kwargs["session_id"]))
        if existing and existing.status == "submitted" and not existing.is_test:
            raise AlreadySubmittedError(f"Real session {existing.session_id} is already submitted.")
        record = SavedProgress(
            session_id=str(kwargs["session_id"]), study_version=str(kwargs["study_version"]),
            is_test=bool(kwargs["is_test"]), current_page=str(kwargs["current_page"]),
            profile=kwargs["profile"], responses=kwargs["responses"], drafts=kwargs["drafts"],
            status="submitted" if kwargs.get("submissions") else "in_progress",
            final_comment=str(kwargs.get("final_comment", "")),
            submissions=tuple(kwargs.get("submissions", ())),
            created_at=existing.created_at if existing else saved_at, updated_at=saved_at,
        )
        self._write(record)
        return record

    def submit_response(self, **kwargs: object) -> SavedProgress:
        submitted_at = kwargs.pop("now", None) or datetime.now(UTC)
        session_id = str(kwargs["session_id"])
        existing = self.load_progress(session_id)
        if existing and existing.submissions and not bool(kwargs["is_test"]):
            raise AlreadySubmittedError(f"Real session {session_id} is already submitted.")
        previous = existing.submissions if existing else ()
        number = len(previous) + 1
        event = {
            "submission_id": f"{session_id}-submission-{number:03d}",
            "submission_number": number, "submitted_at": submitted_at.isoformat(),
            "study_version": kwargs["study_version"], "is_test": kwargs["is_test"],
            "profile": kwargs["profile"], "responses": kwargs["responses"],
            "final_comment": kwargs["final_comment"],
        }
        record = SavedProgress(
            session_id=session_id, study_version=str(kwargs["study_version"]),
            is_test=bool(kwargs["is_test"]), current_page="debrief", profile=kwargs["profile"],
            responses=kwargs["responses"], drafts={}, status="submitted",
            final_comment=str(kwargs["final_comment"]), submissions=(*previous, event),
            created_at=existing.created_at if existing else submitted_at, updated_at=submitted_at,
        )
        self._write(record)
        return record

    def _write(self, record: SavedProgress) -> None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute("""
                insert into private.study_progress
                (session_id, study_version, is_test, current_page, profile, responses,
                 drafts, status, final_comment, created_at, updated_at, source_updated_at)
                values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                on conflict (session_id) do update set
                  study_version=excluded.study_version, is_test=excluded.is_test,
                  current_page=excluded.current_page, profile=excluded.profile,
                  responses=excluded.responses, drafts=excluded.drafts,
                  status=excluded.status, final_comment=excluded.final_comment,
                  updated_at=excluded.updated_at, source_updated_at=excluded.source_updated_at
            """, (record.session_id, record.study_version, record.is_test, record.current_page,
                  self._json(record.profile), self._json(record.responses), self._json(record.drafts),
                  record.status, record.final_comment, record.created_at, record.updated_at,
                  record.updated_at))
            for event in record.submissions:
                cursor.execute("""
                    insert into private.study_submissions
                    (submission_id, session_id, submission_number, study_version, is_test,
                     profile, responses, final_comment, submitted_at, import_source)
                    values (%s,%s,%s,%s,%s,%s,%s,%s,%s,'app_shadow')
                    on conflict (submission_id) do nothing
                """, (event["submission_id"], record.session_id, event["submission_number"],
                      event["study_version"], event["is_test"], self._json(event["profile"]),
                      self._json(event["responses"]), event["final_comment"],
                      datetime.fromisoformat(str(event["submitted_at"]))))
