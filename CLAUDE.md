# FT Assistant

This project is for **maintaining, updating and adding features to the user's push-to-talk voice dictation tool**:
hold a mouse button, speak, release, and local Whisper types what was said into whichever window has focus.

The user relies on it every day and dictates nearly everything they send (including messages to
Claude) through this tool. Treat it as production software: a broken build means the user can't
type comfortably.

## Where the live tool is

Since **2026-11-18 the user runs FT Assistant** (installed v0.1.0 from the GitHub release with the
setup file `FT-Assistant-setup.cmd`, then updated through the built-in updater; **v0.2.4** since
2026-11-19), at `~/.local/share/ft-assistant/`. The user wants to run the same rolling release
everyone else gets:

| Path | What |
|---|---|
| `~/.local/share/ft-assistant/` | The install: `app/ft_assistant/` (program), `python/` (a venv from the system Python 3.12 until the user installs 0.3.0, whose update moves it to FT Assistant's own pinned Python; old one kept as `python.old` until the app has started), `models/large-v3-turbo/`, launchers `ft-assistant`, `ft-assistant-settings` (called `ft-assistant-setup` before 0.2.5), `ft-assistant-uninstall`, `install.py`, `install.json`. |
| `~/.config/ft-assistant/` | `settings.json` (harness `claude`, Assistant key **mouse button 12**), `vocabulary.txt`, `ft-assistant.log` (**errors only** plus a start-up line since 0.2.0; never what the user says), `update-state.json`, `.lock` (holds the process id). |
| `~/.config/autostart/ft-assistant.desktop` | Starts it at login. |

The **old tool (voice-dictation) was retired on 2026-11-19** at the user's request: its install
was deleted and its files removed from the repo (still in git history). There's no rollback to it;
the user doesn't intend to go back. Fixes reach the user as FT Assistant releases.

`~/bin/start-whisper-stt` is an **older, unrelated** script (a whisper-fastapi server). It isn't part of this tool.

### Branches and releases

- **`main` = released code** (latest tag `v0.2.8`; the user runs v0.2.4 until they accept the update). **`next` = development**
  (now 0.3.0.dev0).
- **Changes reach the user as releases, through the built-in updater**, not by copying files:
  merge `next` into `main`, set the version, tag `vX.Y.Z`, `python3 installer/build.py`, and
  `gh release create vX.Y.Z dist/FT-Assistant-Installer.cmd dist/FT-Assistant-setup.cmd` (as
  freethought78; the second is the same file under its pre-0.3.0 name, for a release or two). The app notices
  within a day (or via "Check for updates") and asks the user. The v0.1.0 -> v0.2.0 update on
  the user's own install worked (2026-11-18).
- **FT Assistant's own Python is pinned** in `installer/install.py` (`RUNTIME_*`). The Linux
  setup window's smooth-text Tk is built by hand with `bash installer/build-smooth-tk.sh` (no
  GitHub automation, the user's decision) and kept on GitHub as the **pre-release**
  `smooth-tk-<version>` (pre-release, so the update check never sees it). Changing the runtime
  means rebuilding and re-uploading it; the script's header lists the steps.
- Only with the user's go-ahead: commits, pushes, releases, and anything that restarts the tool.
- **Tests:** `python3 -m unittest discover -s tests -t .`
- **Try a dev build next to the live tool:** `./run-dev.sh` (borrows the install's Python, model
  and word list; own settings/log in
  `~/.config/ft-assistant-dev/`, Assistant key Scroll Lock there; **never button 12**, which the
  live tool uses). Tell the user before starting it, and stop it after testing.
- **Run a branch in place of the live tool:** `./run-branch.sh <branch>` (its latest commit, from
  a snapshot in `.worktrees/`) or `./run-branch.sh .` (this folder with uncommitted changes); back
  with `./run-branch.sh --back` or the menu entry "FT Assistant: back to the installed version";
  `--status` says which is running. It stops the installed copy and runs on button 12, so it
  **restarts the tool: only with the user's go-ahead**, and confirm the `ready:` line it prints.
  Own settings (fresh copy of the live ones)/log in `~/.config/ft-assistant-branch/`. If the test
  build stops by itself, the installed copy restarts automatically; login always starts the
  installed copy.
- **Windows testing** uses only the existing Bottles bottle **`DannyRando-Test`** (Flatpak Bottles).
  **One Wine session at a time:** every `bottles-cli run` starts its own sandbox with its own
  wineserver, so two runs at once (e.g. Notepad in one, the app in another) fight over the same
  bottle, crash it, and keep key presses from reaching the app. Start everything a test needs
  from a single `.cmd` in one `bottles-cli run` (use `start` inside it), wait for it to finish,
  and check no DannyRando-Test processes are left (match `WINEPREFIX` in `/proc/<pid>/environ`)
  before starting the next. Never kill a run halfway unless it's stuck. Never create new bottles
  for this project, and never run anything in the user's other bottles (they're games and apps).

## System

- Linux Mint (Cinnamon), **X11** session (Wayland isn't supported on Linux yet).
- NVIDIA RTX 4070 (12 GB). The engine loads in about 1 s and transcribes about 20 s of speech in about 0.5 s.
- The user's Assistant key: X11 **mouse button 12**, a spare button on their trackball, forwarded through input-remapper.

## Design decisions the user made (keep them unless they ask otherwise)

- **Their Assistant key is a mouse button** (button 12), not a keyboard key. (New installs default to Caps Lock.)
- **Free all resources when idle.** The worker subprocess and the mic stream start on the first press and are released
  **right after each dictation**. The user tried a 5-minute delay first and then asked for an immediate
  unload, because the roughly 1 s cold start is fine. Killing the subprocess is what guarantees GPU memory is returned.
- **Never mute, disable or reconfigure the system microphone.** Releasing only closes the tool's own input stream.
  The user specifically asked about this, so say "closes its mic stream", never "turns off the mic".
- **Privacy:** audio is kept only in memory and never written to disk, and transcript text is never logged. The model runs offline (`HF_HUB_OFFLINE=1`).
- **It works with background audio playing** (tested), and short taps or near-silent clips are ignored.
- Whisper's typical made-up phrases on silence ("Thank you.", "Thanks for watching!") are dropped when they are the whole result (`HALLUCINATIONS`).
- A start beep (880 Hz) means the mic is live, and a stop beep (587 Hz) means release was registered.

## Working on it safely

- **Restarting the tool cuts off the user's typing** until it's back, and they may be dictating to you through it.
  Say so before restarting, keep the downtime short, and confirm it's back (`ready:` line in
  `~/.config/ft-assistant/ft-assistant.log`). Restart:
  `pkill -f 'ft-assistant/python/bin/python3 -m [f]t_assistant'; sleep 1; setsid ~/.local/share/ft-assistant/ft-assistant >/dev/null 2>&1 < /dev/null &`
  (the `[f]` stops `pkill` from matching, and killing, the shell running the command itself).
  From 0.3.0 the processes are also named (`FT Assistant`, `FT Asst speech`, `FT Asst setup`,
  `FT Asst help`; Windows: `FT Assistant*.exe`), so `pgrep -x 'FT Assistant'` finds the program.
  A test build from `run-branch.sh` has the same names: tell them apart by their
  `FT_ASSISTANT_CONFIG_DIR` (as `run-branch.sh` does).
- Test changes before deploying them over the working version, and keep a way to roll back.
- **Never log what the user says, and no activity either.** On 2026-11-17 transcript logging was
  turned off; on 2026-11-18 the user chose an **errors-only log** (plus one start-up line) and had
  the old tool's log deleted. Don't add log lines (above debug level), debug prints or files that
  record what was said or when/how much anyone dictates; `tests/test_logging_policy.py` checks it.
  If debugging needs more, ask first and remove it afterwards.

- **Testing against Claude or OpenCode:** never type, send or create test input in any of the user's
  existing projects or sessions. Tests may only use a throwaway or neutral folder made for this
  project. (OpenCode's new-session shortcut lands in the last-used project, so it must not be
  used to send anything until it can be pointed at a neutral folder.)

## GitHub

- This project's GitHub home is the user's **older account, `freethought78`**. **Never use the
  `ftftft78` account** for this project (repo, releases, issues, PRs). Before any GitHub step,
  check `gh auth status` shows `freethought78` as the active account; if not, ask the user to
  sign in (`gh auth login`) or switch (`gh auth switch`) themselves.
- The repo is **public**: https://github.com/freethought78/ft-assistant (created 2026-11-18;
  releases: v0.1.0 to v0.2.8). Never commit personal details (health, other
  projects, emails); history was scrubbed once before the first push.

## Working with the user

- They dictate, so prefer one-click choices (buttons or options) over questions that need typed answers.
- They like concise reports.
- Never launch games or emulators: they steal focus while the user is playing.
