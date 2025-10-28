from app import app

from db_to_json import export_to_json

from datetime import datetime


def do_backup():
    print("backup")
    export_to_json(
        "instance/app.db",
        app.config.get("BACKUP_PATH", "")
        + datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        + ".json",
    )
