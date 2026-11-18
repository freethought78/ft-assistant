import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ft_assistant import updater
from ft_assistant.updater import Release

DAY = 24 * 3600


class Versions(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(updater.parse_version("v1.2.3"), (1, 2, 3, 1))
        self.assertEqual(updater.parse_version("1.2"), (1, 2, 0, 1))
        self.assertEqual(updater.parse_version("0.1.0.dev0"), (0, 1, 0, 0))
        self.assertIsNone(updater.parse_version("latest"))

    def test_newer(self):
        self.assertTrue(updater.is_newer("0.1.0", "0.1.0.dev0"))
        self.assertTrue(updater.is_newer("v0.2.0", "0.1.9"))
        self.assertFalse(updater.is_newer("0.1.0", "0.1.0"))
        self.assertFalse(updater.is_newer("0.0.9", "0.1.0.dev0"))
        self.assertFalse(updater.is_newer("garbage", "0.1.0"))


class Reminders(unittest.TestCase):
    def setUp(self):
        self.rel = Release("9.0.0", "notes", "u")

    def test_due(self):
        self.assertTrue(updater.due_for_check({}, now=1000))
        self.assertFalse(updater.due_for_check({"last_check": 1000}, now=1000 + DAY - 1))
        self.assertTrue(updater.due_for_check({"last_check": 1000}, now=1000 + DAY))

    def test_once_then_one_reminder(self):
        state, t = {}, 1_000_000
        self.assertTrue(updater.should_notify(self.rel, state, now=t))
        updater.mark_notified(state, "9.0.0", now=t)
        self.assertFalse(updater.should_notify(self.rel, state, now=t + DAY))
        self.assertTrue(updater.should_notify(self.rel, state, now=t + 3 * DAY))
        updater.mark_notified(state, "9.0.0", now=t + 3 * DAY)
        self.assertFalse(updater.should_notify(self.rel, state, now=t + 30 * DAY))
        # A newer release starts over.
        self.assertTrue(updater.should_notify(Release("9.1.0", "", ""), state, now=t + 30 * DAY))

    def test_not_now(self):
        state, t = {}, 1_000_000
        updater.mark_not_now(state, "9.0.0", now=t)
        self.assertFalse(updater.should_notify(self.rel, state, now=t + DAY))
        self.assertTrue(updater.should_notify(self.rel, state, now=t + 3 * DAY))

    def test_not_newer_never_notifies(self):
        self.assertFalse(updater.should_notify(Release("0.0.1", "", ""), {}))
        self.assertFalse(updater.should_notify(None, {}))


class Fetch(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = mock.patch.dict(os.environ, {"FT_ASSISTANT_CONFIG_DIR": self.tmp.name})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def release_file(self, data):
        p = Path(self.tmp.name, "latest.json")
        p.write_text(json.dumps(data))
        return p.as_uri()

    def test_parse_release(self):
        r = updater.parse_release({"tag_name": "v1.4.0", "body": " Fixes \n", "html_url": "h"})
        self.assertEqual(r, Release("1.4.0", "Fixes", "h"))
        self.assertIsNone(updater.parse_release({"tag_name": "v2.0.0", "prerelease": True}))
        self.assertIsNone(updater.parse_release({"tag_name": "v2.0.0", "draft": True}))
        self.assertIsNone(updater.parse_release({}))

    def test_check_update_and_state(self):
        url = self.release_file({"tag_name": "v9.0.0", "body": "New stuff", "html_url": "h"})
        with mock.patch.dict(os.environ, {"FT_ASSISTANT_UPDATE_URL": url}):
            self.assertEqual(updater.check(now=5), Release("9.0.0", "New stuff", "h"))
            self.assertEqual(updater.load_state()["last_check"], 5)
            self.assertEqual(updater.known_update().version, "9.0.0")
            self.assertEqual(updater.check_now()[0], "update")

    def test_check_latest_and_unreachable(self):
        url = self.release_file({"tag_name": "v0.0.1"})
        with mock.patch.dict(os.environ, {"FT_ASSISTANT_UPDATE_URL": url}):
            self.assertIsNone(updater.check())
            self.assertEqual(updater.check_now(), ("latest", None))
        missing = Path(self.tmp.name, "nope.json").as_uri()
        with mock.patch.dict(os.environ, {"FT_ASSISTANT_UPDATE_URL": missing}):
            self.assertIsNone(updater.check())
            self.assertEqual(updater.check_now(), ("unreachable", None))


if __name__ == "__main__":
    unittest.main()
