import os
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[1]


def _write_fake_compose(path: Path) -> None:
    path.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
printf '%s\\n' \"$*\" >> \"$COMPOSE_LOG\"
if [[ \"$*\" == *\"pg_dump\"* ]]; then
    printf 'valid custom dump'
elif [[ \"$*\" == *\"pg_restore --list\"* ]]; then
    grep -q 'valid custom dump'
elif [[ \"$*\" == *\"pg_restore\"* ]]; then
    grep -q 'valid custom dump'
fi
""",
        encoding="utf-8",
    )
    path.chmod(0o755)


def test_backup_is_verified_and_mirrored_atomically(tmp_path: Path) -> None:
    env_file = tmp_path / "production.env"
    env_file.write_text("POSTGRES_USER=type\nPOSTGRES_DB=type\n")
    compose = tmp_path / "compose"
    _write_fake_compose(compose)
    backup_dir = tmp_path / "backups"
    mirror_dir = tmp_path / "mirror"
    environment = os.environ | {
        "ENV_FILE": str(env_file),
        "BACKUP_DIR": str(backup_dir),
        "BACKUP_MIRROR_DIR": str(mirror_dir),
        "COMPOSE_SCRIPT": str(compose),
        "COMPOSE_LOG": str(tmp_path / "compose.log"),
    }

    result = subprocess.run(
        [PROJECT_ROOT / "scripts/backup_postgres.sh"],
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )

    backups = list(backup_dir.glob("type-*.dump"))
    assert len(backups) == 1
    assert backups[0].read_text() == "valid custom dump"
    mirrored = mirror_dir / backups[0].name
    assert mirrored.read_text() == "valid custom dump"
    assert not list(backup_dir.glob(".*.dump"))
    assert "created and verified" in result.stdout


def test_restore_uses_disposable_database_and_drops_it(tmp_path: Path) -> None:
    env_file = tmp_path / "production.env"
    env_file.write_text("POSTGRES_USER=type\nPOSTGRES_DB=type\n")
    compose = tmp_path / "compose"
    _write_fake_compose(compose)
    dump = tmp_path / "type-20260918T000000Z.dump"
    dump.write_text("valid custom dump")
    log = tmp_path / "compose.log"
    environment = os.environ | {
        "ENV_FILE": str(env_file),
        "COMPOSE_SCRIPT": str(compose),
        "COMPOSE_LOG": str(log),
    }

    subprocess.run(
        [PROJECT_ROOT / "scripts/restore_test_postgres.sh", dump],
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )

    calls = log.read_text()
    assert "createdb" in calls
    assert "pg_restore" in calls
    assert "SELECT 1 FROM alembic_version" in calls
    assert "dropdb --if-exists --force" in calls
