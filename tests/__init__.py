
# No test may touch the user's real "FT Assistant sessions" folder: every test run gets a
# throwaway one.
import atexit as _atexit
import os as _os
import shutil as _shutil
import tempfile as _tempfile

_SESSIONS = _tempfile.mkdtemp(prefix="ft-test-sessions-")
_os.environ["FT_ASSISTANT_SESSIONS_DIR"] = _SESSIONS
_atexit.register(_shutil.rmtree, _SESSIONS, True)
