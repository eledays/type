from pathlib import Path

from sqlalchemy import Engine, URL, create_engine, func, inspect, select, text
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db


class DatabaseTransferError(RuntimeError):
    """Ошибка безопасного переноса данных между базами."""


def import_sqlite_database(source_path: Path) -> dict[str, int]:
    """Копирует актуальную SQLite-базу в пустой PostgreSQL.

    :param source_path: Путь к SQLite-файлу с актуальной Alembic-схемой.
    :return: Количество перенесённых строк по таблицам.
    :raises DatabaseTransferError: Если источник несовместим или цель не пуста.
    """
    if db.engine.dialect.name != "postgresql":
        raise DatabaseTransferError(
            "Target DATABASE_URL must point to PostgreSQL"
        )

    source_engine = create_engine(URL.create(
        "sqlite+pysqlite",
        database=str(source_path.resolve()),
    ))
    try:
        return _copy_database(source_engine, db.engine)
    except SQLAlchemyError as error:
        raise DatabaseTransferError(str(error)) from error
    finally:
        source_engine.dispose()


def _copy_database(source_engine: Engine, target_engine: Engine) -> dict[str, int]:
    tables = db.metadata.sorted_tables
    required_tables = {table.name for table in tables} | {"alembic_version"}
    source_tables = set(inspect(source_engine).get_table_names())
    missing_tables = sorted(required_tables - source_tables)
    if missing_tables:
        raise DatabaseTransferError(
            "SQLite source is missing tables: " + ", ".join(missing_tables)
        )

    with source_engine.connect() as source, target_engine.begin() as target:
        source_revision = source.scalar(
            text("SELECT version_num FROM alembic_version")
        )
        target_revision = target.scalar(
            text("SELECT version_num FROM alembic_version")
        )
        if source_revision != target_revision:
            raise DatabaseTransferError(
                "Source and target Alembic revisions differ: "
                f"{source_revision!r} != {target_revision!r}"
            )

        populated_tables = [
            table.name
            for table in tables
            if target.scalar(select(func.count()).select_from(table))
        ]
        if populated_tables:
            raise DatabaseTransferError(
                "PostgreSQL target must be empty; data found in: "
                + ", ".join(populated_tables)
            )

        copied: dict[str, int] = {}
        for table in tables:
            rows = source.execute(select(table)).mappings().all()
            if rows:
                target.execute(table.insert(), [dict(row) for row in rows])
            copied[table.name] = len(rows)
            _reset_postgresql_sequence(target, table)
        return copied


def _reset_postgresql_sequence(connection, table) -> None:
    primary_keys = list(table.primary_key.columns)
    if len(primary_keys) != 1:
        return
    primary_key = primary_keys[0]
    if not primary_key.autoincrement:
        return

    sequence = connection.scalar(
        text("SELECT pg_get_serial_sequence(:table_name, :column_name)"),
        {"table_name": table.name, "column_name": primary_key.name},
    )
    if sequence is None:
        return
    maximum = connection.scalar(select(func.max(primary_key)))
    connection.execute(
        text(
            "SELECT setval(CAST(:sequence AS regclass), :value, :is_called)"
        ),
        {
            "sequence": sequence,
            "value": maximum if maximum is not None else 1,
            "is_called": maximum is not None,
        },
    )
