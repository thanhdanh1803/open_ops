"""Tests for checkpointer configuration and factory."""

import tempfile
from pathlib import Path

import pytest

from openops.storage.checkpointer import (
    SqliteCheckpointerFactory,
    get_checkpointer,
    get_checkpointer_from_config,
)


class TestSqliteCheckpointerFactory:
    def test_create_checkpointer(self, tmp_path):
        db_path = tmp_path / "checkpoints.db"
        factory = SqliteCheckpointerFactory(db_path)

        checkpointer = factory.create()

        assert checkpointer is not None
        # Note: SQLite file is created lazily when data is first written,
        # so we just verify the checkpointer was created successfully

    def test_creates_parent_directories(self, tmp_path):
        db_path = tmp_path / "nested" / "dirs" / "checkpoints.db"
        factory = SqliteCheckpointerFactory(db_path)

        checkpointer = factory.create()

        assert checkpointer is not None
        assert db_path.parent.exists()


class TestGetCheckpointer:
    def test_get_sqlite_checkpointer(self, tmp_path):
        db_path = tmp_path / "checkpoints.db"

        checkpointer = get_checkpointer(
            checkpointer_type="sqlite",
            db_path=db_path,
        )

        assert checkpointer is not None

    def test_sqlite_requires_db_path(self):
        with pytest.raises(ValueError, match="db_path is required"):
            get_checkpointer(checkpointer_type="sqlite")

    def test_unsupported_checkpointer_type(self, tmp_path):
        with pytest.raises(ValueError, match="Unsupported checkpointer type"):
            get_checkpointer(
                checkpointer_type="redis",  # type: ignore
                db_path=tmp_path / "test.db",
            )


class TestGetCheckpointerFromConfig:
    def test_creates_checkpointer_from_config(self, tmp_path):
        class MockConfig:
            data_dir = tmp_path
            checkpoints_db_path = tmp_path / "checkpoints.db"

            def ensure_data_dir(self):
                self.data_dir.mkdir(parents=True, exist_ok=True)

        config = MockConfig()

        checkpointer = get_checkpointer_from_config(config)

        assert checkpointer is not None
