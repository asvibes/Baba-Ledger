"""
backend/storage/temp_manager.py

Implements PRD Section 13 (Privacy, Storage & Cleanup) via the
JobWorkspace interface app.py expects:

    storage.temp_manager.JobWorkspace(job_id: str)
        .path -> str (temp dir for this job's files)
        .cleanup() -> None (deletes upload + all intermediate + output
        files)

Design notes
------------
app.py creates a JobWorkspace once in /api/analyze (to get .path for
saving the upload) and creates a *second, separate* JobWorkspace
instance later in /api/analyze/<job_id> DELETE just to call
.cleanup(). For that second instance to find the right directory,
the path must be deterministic from job_id alone — never a fresh
random tempfile.mkdtemp() per instantiation.

job_id is generated internally via uuid.uuid4().hex (app.py), so it is
always a safe, fixed-length hex string. As a defensive measure anyway
(PRD 14.4 spirit: never trust input blindly), we still validate the
job_id shape before touching the filesystem, since a malformed/foreign
job_id used in a path join could otherwise be a path-traversal risk.
"""
import re
import shutil
import tempfile
from pathlib import Path

try:
    # Optional: define TEMP_DIR in config.py to control where job
    # workspaces live (PRD 14.5 — tunables belong in config, not
    # scattered through business logic). Falls back to the system
    # temp dir if not set there.
    from ..config import TEMP_DIR as _CONFIGURED_TEMP_DIR
except (ImportError, AttributeError):
    _CONFIGURED_TEMP_DIR = None

_BASE_DIR = Path(_CONFIGURED_TEMP_DIR) if _CONFIGURED_TEMP_DIR else (
    Path(tempfile.gettempdir()) / "baba-ledger-jobs"
)

# job_id is uuid.uuid4().hex in app.py: 32 lowercase hex chars. Anything
# else is rejected rather than silently used to build a filesystem path.
_JOB_ID_PATTERN = re.compile(r"^[a-f0-9]{32}$")


class InvalidJobIdError(ValueError):
    """Raised when a job_id doesn't match the expected uuid4 hex shape."""


class JobWorkspace:
    """
    One temporary directory per analysis job. All uploaded, intermediate,
    and generated files for a job should live under .path so that a
    single .cleanup() call removes everything for that job in one shot
    (PRD 13: delete uploaded PDF + all intermediate + output files).
    """

    def __init__(self, job_id: str):
        if not _JOB_ID_PATTERN.match(job_id):
            raise InvalidJobIdError(f"Invalid job_id: {job_id!r}")

        self.job_id = job_id
        self._dir = _BASE_DIR / job_id
        self._dir.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> str:
        return str(self._dir)

    def cleanup(self) -> None:
        """
        Delete this job's entire temp directory (upload, OCR artifacts,
        highlighted PDF, report PDF — everything). Safe to call more
        than once and safe to call even if the directory was already
        removed or never fully populated.
        """
        shutil.rmtree(self._dir, ignore_errors=True)

    @staticmethod
    def cleanup_all_orphaned() -> int:
        """
        Remove any job directories left behind by jobs that crashed or
        were never explicitly cleaned up (e.g. after an unclean server
        restart). Not called automatically anywhere yet — intended to
        be wired into app startup (create_app / __main__) so orphaned
        uploads never linger indefinitely, per the PRD 13 privacy
        guarantee that no document is permanently stored.

        Returns the number of directories removed.
        """
        if not _BASE_DIR.exists():
            return 0

        removed = 0
        for child in _BASE_DIR.iterdir():
            if child.is_dir() and _JOB_ID_PATTERN.match(child.name):
                shutil.rmtree(child, ignore_errors=True)
                removed += 1
        return removed