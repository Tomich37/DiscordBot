import unittest
from datetime import datetime, timedelta

from sqlalchemy import create_engine

import app.modules.database as database_module
from app.modules.alchemy_connect import Base, Session, SportChallenge, SportProgressEntry
from app.modules.database import Database


class SportDatabaseTests(unittest.TestCase):
    """Проверяет выбор и отмену отдельных спортивных фиксаций."""

    def setUp(self) -> None:
        self.original_engine = database_module.engine
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(
            self.engine,
            tables=[SportChallenge.__table__, SportProgressEntry.__table__],
        )
        database_module.engine = self.engine
        self.db = Database()

    def tearDown(self) -> None:
        database_module.engine = self.original_engine
        self.engine.dispose()

    def _create_challenge(self, *, target: int = 100, status: str = "active") -> int:
        with Session(bind=self.engine) as session:
            challenge = SportChallenge(
                guild_id=1,
                channel_id=2,
                creator_id=3,
                activity_name="Тестовый челлендж",
                unit_name="повторов",
                target_amount=target,
                status=status,
                started_at=datetime.utcnow(),
                ends_at=datetime.utcnow() + timedelta(days=1),
                finish_reason="target_reached" if status == "completed" else None,
                finished_at=datetime.utcnow() if status == "completed" else None,
                result_announced=status == "completed",
            )
            session.add(challenge)
            session.commit()
            return challenge.id

    def _add_entry(self, challenge_id: int, user_id: int, amount: int) -> int:
        with Session(bind=self.engine) as session:
            entry = SportProgressEntry(
                challenge_id=challenge_id,
                user_id=user_id,
                amount=amount,
            )
            session.add(entry)
            session.commit()
            return entry.id

    def test_progress_entries_are_returned_newest_first(self):
        challenge_id = self._create_challenge()
        first_id = self._add_entry(challenge_id, user_id=10, amount=20)
        second_id = self._add_entry(challenge_id, user_id=20, amount=30)

        entries = self.db.get_sport_progress_entries(challenge_id)

        self.assertEqual([entry["id"] for entry in entries], [second_id, first_id])

    def test_progress_entries_are_filtered_by_selected_user(self):
        challenge_id = self._create_challenge()
        selected_id = self._add_entry(challenge_id, user_id=10, amount=20)
        self._add_entry(challenge_id, user_id=20, amount=30)

        entries = self.db.get_sport_progress_entries(challenge_id, user_id=10)

        self.assertEqual([entry["id"] for entry in entries], [selected_id])
        self.assertEqual(entries[0]["user_id"], 10)

    def test_cancelling_target_entry_reopens_active_challenge(self):
        challenge_id = self._create_challenge(target=100, status="completed")
        remaining_id = self._add_entry(challenge_id, user_id=10, amount=40)
        cancelled_id = self._add_entry(challenge_id, user_id=20, amount=60)

        result = self.db.cancel_sport_progress(challenge_id, cancelled_id)

        self.assertEqual(result["status"], "cancelled")
        self.assertTrue(result["reopened"])
        self.assertEqual(result["challenge"]["status"], "active")
        self.assertEqual(result["challenge"]["total_amount"], 40)
        self.assertFalse(result["challenge"]["result_announced"])
        entries = self.db.get_sport_progress_entries(challenge_id)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["id"], remaining_id)
        self.assertEqual(entries[0]["user_id"], 10)
        self.assertEqual(entries[0]["amount"], 40)

    def test_entry_from_another_challenge_cannot_be_cancelled(self):
        first_challenge_id = self._create_challenge()
        second_challenge_id = self._create_challenge()
        entry_id = self._add_entry(second_challenge_id, user_id=10, amount=20)

        result = self.db.cancel_sport_progress(first_challenge_id, entry_id)

        self.assertEqual(result["status"], "not_found")
        self.assertEqual(len(self.db.get_sport_progress_entries(second_challenge_id)), 1)

    def test_entry_from_another_user_cannot_be_cancelled(self):
        challenge_id = self._create_challenge()
        entry_id = self._add_entry(challenge_id, user_id=20, amount=30)

        result = self.db.cancel_sport_progress(
            challenge_id,
            entry_id,
            user_id=10,
        )

        self.assertEqual(result["status"], "not_found")
        self.assertEqual(len(self.db.get_sport_progress_entries(challenge_id)), 1)


if __name__ == "__main__":
    unittest.main()
