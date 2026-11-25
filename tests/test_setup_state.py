"""The Assistant key while the setup screen is open (the user's request, 2026-11-25): it keeps
working, a newly chosen key works before Save, Cancel goes back, and it pauses only while
"Change key" waits for a press."""
import json
import os
import tempfile
import unittest
from unittest import mock

from ft_assistant import config, setup_state

try:
    from ft_assistant import app          # needs numpy (FT Assistant's own Python has it)
except ImportError:
    app = None

SAVED = {"type": "button", "button": 12}
TRIAL = {"type": "key", "keysym": "Scroll_Lock"}


class SharedFile(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.env = mock.patch.dict(os.environ, {"FT_ASSISTANT_CONFIG_DIR": self.dir.name})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.dir.cleanup()

    def test_round_trip(self):
        setup_state.write(TRIAL, capturing=True)
        self.assertEqual(setup_state.read(lambda pid: True), {"trigger": TRIAL, "capturing": True})

    def test_only_the_key_and_the_process(self):
        setup_state.write(TRIAL, False)
        self.assertEqual(set(json.loads(setup_state.path().read_text())),
                         {"pid", "trigger", "capturing"})

    def test_left_behind_by_a_closed_setup_is_ignored(self):
        setup_state.write(TRIAL, False)
        self.assertIsNone(setup_state.read(lambda pid: False))

    def test_a_bad_key_is_ignored(self):
        setup_state.write({"type": "button", "button": 1}, False)      # the left button: never
        self.assertIsNone(setup_state.read(lambda pid: True))

    def test_clear_removes_only_its_own(self):
        setup_state.write(TRIAL, False)
        setup_state.clear()
        self.assertFalse(setup_state.path().exists())
        setup_state.path().write_text(json.dumps({"pid": os.getpid() + 1, "trigger": TRIAL}))
        setup_state.clear()
        self.assertTrue(setup_state.path().exists())       # another setup screen's

    @unittest.skipIf(os.name == "nt", "Linux")
    def test_linux_knows_a_setup_screen_by_its_name(self):
        from ft_assistant import platform_linux
        self.assertFalse(platform_linux.setup_running(os.getpid()))   # the tests aren't setup
        self.assertFalse(platform_linux.setup_running(999999999))


@unittest.skipIf(app is None, "numpy isn't installed")
class AppFollowsSetup(unittest.TestCase):
    def make_app(self):
        a = app.App.__new__(app.App)
        a.settings = config.Settings(harness="claude", trigger=dict(SAVED))
        a.active_trigger, a.caps_trigger = dict(SAVED), False
        a.setup_open = a.setup_capturing = a.down = False
        a.listener = mock.Mock()
        a.setup_proc = None
        return a

    def tick(self, a, state, saved=SAVED):
        with mock.patch.object(app.setup_state, "read", return_value=state), \
                mock.patch.object(app.config, "load",
                                  return_value=config.Settings(harness="claude", trigger=saved)):
            a.watch_setup(once=True)

    def test_key_keeps_working_while_setup_is_open(self):
        a = self.make_app()
        self.tick(a, {"trigger": SAVED, "capturing": False})
        self.assertTrue(a.setup_open)
        self.assertFalse(a.setup_capturing)
        a.listener.stop.assert_not_called()                 # same key: nothing to switch

    def test_a_new_key_works_before_save(self):
        a = self.make_app()
        self.tick(a, {"trigger": TRIAL, "capturing": False})
        self.assertEqual(a.active_trigger, TRIAL)
        a.listener.stop.assert_called_once()                # main() starts the new listener

    def test_cancel_goes_back_to_the_saved_key(self):
        a = self.make_app()
        self.tick(a, {"trigger": TRIAL, "capturing": False})
        self.tick(a, None)                                  # closed without saving
        self.assertEqual(a.active_trigger, SAVED)
        self.assertFalse(a.setup_open)

    def test_save_keeps_the_new_key(self):
        a = self.make_app()
        self.tick(a, {"trigger": TRIAL, "capturing": False})
        self.tick(a, None, saved=TRIAL)                     # closed after Save
        self.assertEqual(a.active_trigger, TRIAL)
        self.assertEqual(a.settings.trigger, TRIAL)

    def test_paused_only_while_change_key_waits(self):
        a = self.make_app()
        a.rec, a.ctl = mock.Mock(), app.threading.Lock()
        self.tick(a, {"trigger": SAVED, "capturing": True})
        a.on_press()
        a.rec.start.assert_not_called()
        self.assertFalse(a.down)

    def test_never_switches_mid_dictation(self):
        a = self.make_app()
        a.down = True
        self.tick(a, {"trigger": TRIAL, "capturing": False})
        self.assertEqual(a.active_trigger, SAVED)
        a.listener.stop.assert_not_called()

    def test_only_one_setup_screen(self):
        a = self.make_app()
        a.setup_open = True                                  # opened from the menu, say
        with mock.patch.object(app.subprocess, "Popen") as popen:
            a.open_setup()
        popen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
