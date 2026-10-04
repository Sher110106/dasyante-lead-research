from pathlib import Path

from dasyante.jsonbin import JsonBinDatabase
from dasyante.web import WorkspaceHandler


class handler(WorkspaceHandler):
    """Vercel entrypoint: always use durable JSONBin, never an ephemeral disk DB."""

    @property
    def database_path(self):
        return Path(":memory:")

    def _open_database(self):
        return JsonBinDatabase.from_environment()

    @property
    def storage_backend(self):
        return "jsonbin"
