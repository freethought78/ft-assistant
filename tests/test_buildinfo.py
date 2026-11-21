import subprocess
import tempfile
import unittest
from pathlib import Path

from ft_assistant import buildinfo


class VersionLine(unittest.TestCase):
    def test_installed_copy_shows_plain_version(self):
        with tempfile.TemporaryDirectory() as t:          # no .git: an installed copy
            self.assertEqual(buildinfo.describe({}, Path(t), "0.2.8"), "0.2.8")
            self.assertFalse(buildinfo.is_test_build({}, Path(t)))

    def test_branch_from_run_branch(self):
        with tempfile.TemporaryDirectory() as t:
            env = {"FT_ASSISTANT_BUILD": "conversation-management"}
            self.assertEqual(buildinfo.describe(env, Path(t), "0.3.0.dev0"),
                             "0.3.0 test build (conversation-management): not a public release")

    def test_next_is_a_release_candidate(self):
        with tempfile.TemporaryDirectory() as t:
            env = {"FT_ASSISTANT_BUILD": "next", "FT_ASSISTANT_BUILD_NOTE": "with uncommitted changes"}
            self.assertEqual(buildinfo.describe(env, Path(t), "0.3.0.dev0"),
                             "0.3.0 release candidate (next, with uncommitted changes): "
                             "not a public release")

    def test_git_checkout_names_its_branch(self):
        with tempfile.TemporaryDirectory() as t:
            run = lambda *a: subprocess.run(["git", "-C", t] + list(a), check=True,
                                            capture_output=True)
            run("init", "-q", "-b", "idea")
            self.assertEqual(buildinfo.describe({}, Path(t), "0.3.0.dev0"),
                             "0.3.0 test build (idea): not a public release")


class BranchScript(unittest.TestCase):
    def test_script_parses(self):
        script = Path(__file__).resolve().parent.parent / "run-branch.sh"
        subprocess.run(["bash", "-n", str(script)], check=True)


if __name__ == "__main__":
    unittest.main()
