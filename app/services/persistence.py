from pathlib import Path

from fastlite import database


class PersistenceService:
    """Centralizes database and storage path bootstrap for route modules."""

    DATA_DIR = Path("data")
    DB_PATH = DATA_DIR / "bimguard.sqlite"
    UPLOADS_DIR = DATA_DIR / "uploads"
    _db = None

    @classmethod
    def get_db(cls):
        cls.DATA_DIR.mkdir(exist_ok=True)
        if cls._db is None:
            cls._db = database(str(cls.DB_PATH))
        return cls._db

    @classmethod
    def get_table(
        cls,
        table_name: str,
        schema: dict,
        pk: str = "id",
        required_columns: dict | None = None,
    ):
        table = cls.get_db()[table_name]
        table.create(schema, pk=pk, if_not_exists=True)

        for column_name, column_type in (required_columns or {}).items():
            if column_name not in table.columns_dict:
                table.add_column(column_name, column_type)

        return table

    @classmethod
    def uploads_dir(cls, *parts: str) -> Path:
        path = cls.UPLOADS_DIR.joinpath(*parts)
        path.mkdir(parents=True, exist_ok=True)
        return path
