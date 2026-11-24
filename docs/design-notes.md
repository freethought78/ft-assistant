# Design notes: the redesign (`next` branch)

Living document. Decisions agreed with the user are recorded here as the design is refined.
Nothing in it is built yet. Implementation starts only when the user says the design is ready.

Last updated: 2026-11-17 (full review and cleanup)

## Releases

- **v0.1.0** (2026-11-18): first release; the user switched their daily tool to it the same day
  (installed from the release's setup file, reusing Python and the model; Assistant key mouse
  button 12). The old tool was kept for rollback until 2026-11-19, when the user retired it
  (install deleted, its files removed from the repo).
- **v0.2.0** (2026-11-18): Dictation only, the choosable command word, the errors-only log, the
  launcher fix. **First real update:** the user's v0.1.0 found it with "Check for updates",
  "Update now" handed over to the new installer, and 0.2.0 started by itself; v0.1.0 is kept in
  `app.previous` for rollback.
- **v0.2.1** (2026-11-18): setup fix found by the first test on a real Windows PC: the
  install-folder prompt showed no folder (PowerShell read `$default?` as one variable name).
  Also tidied the size table. The app itself is unchanged.
- **v0.2.2** (2026-11-18): the friend's install never started: setup had reused a Python
  without Tcl/Tk, and the app imports the setup screen at start-up, so it crashed at once (no
  setup screen, no Assistant key, no log). Setup now only reuses a Python that can open a
  window (checked again by install.py, which falls back to a downloaded Python), stops a running
  copy before replacing files on Windows, and re-running it repairs such an install (tested in
  the bottle with a Tk-less Python). The installer no longer stops a process from a stale lock
  unless it is FT Assistant.
- **v0.2.3** (2026-11-18): a second tester's setup window was taller than his screen (Save and
  "Update now" out of reach). The window now fits the usable part of its monitor (taskbar and
  panels excluded, per monitor), scrolls, and keeps Save/Cancel pinned. Running a newer setup
  file offers the existing install's folder, so it updates in place: the way to deliver a fix
  when the in-app updater can't be reached.
- **v0.2.4** (2026-11-19): after a reboot, "Assistant" said Claude Code wasn't installed: it
  was installed with npm under nvm, whose folder only ~/.bashrc adds to the search path, and the
  app started at login never reads it. Claude Code and OpenCode are now also looked for in the
  usual install folders (nvm, npm, ~/.local/bin, their own installers' folders, Volta, Bun, asdf;
  Windows: npm, ~/.local/bin) and started by full path. Setup no longer looks in the retired
  old tool's folder for a model.
- **v0.2.5** (2026-11-19): a third tester's speech engine never started: his NVIDIA driver was
  too old for the engine ("CUDA driver version is insufficient"), and setup had only checked
  that an NVIDIA card exists. Now the worker falls back to the processor (same model) when the
  card fails at load or mid-dictation; the app says so once and skips the card until it
  restarts. Setup checks `nvidia-smi`'s CUDA version (12+ needed) and picks the processor for
  an older driver. His attempt to rerun setup also failed silently: Windows ignores case, so the
  install folder's settings launcher `ft-assistant-setup.cmd` had the same name as the
  downloaded `FT-Assistant-setup.cmd`. The launcher is now `ft-assistant-settings`, and
  updates rewrite the menu entries that point at it.
- **v0.2.6** (2026-11-19): the setup screen's Install buttons install the latest assistant
  directly. On Windows OpenCode had no direct route (its install script needs bash; without npm
  the button opened the website): its latest Windows release is now downloaded from GitHub into
  `~/.opencode/bin` (the folder its script uses; build picked by the same AVX2 check) and that
  folder is added to the user's PATH. The screen shows "Installing...", checks every 2 s for up
  to 30 min, then shows "Installed" and picks it if nothing was chosen. Tested for real in the
  bottle (OpenCode 1.19.6 installed and ran; test install removed afterwards).
- **v0.2.7** (2026-11-19): on a Windows tester's PC, "Assistant, ..." opened a window that
  closed at once. The assistant was started through Windows Terminal (`wt.exe`), which
  re-parses its command line (drops quotes, splits on ";"), so the folder "FT Assistant
  sessions" reached OpenCode in pieces. It now starts directly in a new console window
  (Windows 11 still shows it in Windows Terminal when that's the default). The same command
  worked in the bottle, which has no Windows Terminal; not yet confirmed from the tester's log.
- **v0.2.8** (2026-11-19): the same tester still got nothing. Two causes, found on his PC:
  (1) OpenCode itself quit at start, "Database is not empty and has no session table": the
  OpenCode desktop app had left `~/.local/share/opencode/opencode.db` in a form the terminal
  version rejects (fixed on his PC by renaming it; not something FT Assistant can fix). (2) Then
  FT Assistant's window stayed blank: `open_session` passed NUL as the agent's
  stdin/stdout/stderr, harmless on Linux (the terminal gives the agent its own) but on Windows
  the agent read and wrote nowhere. Windows now passes no handles. Wine doesn't reproduce (2);
  confirmed on the tester's PC by launching the fixed way with his install's own Python.
- **v0.3.0** (2026-11-21): everything planned for `next` (see "Planned" below):
  - FT Assistant's own pinned Python, reused on reruns, with updates moving installs over;
  - smooth text on Linux from a hand-built Tk (pre-release `smooth-tk-9.0.4`);
  - the setup window's text size following the desktop;
  - safe uninstall;
  - the install-folder window;
  - `run-branch.sh` and the branch label;
  - "Assistant help" / "Assistant stop" and the voice commands window;
  - the installer renamed to `FT-Assistant-Installer.cmd` (also attached under the old name);
  - processes named "FT Assistant";
  - real Windows Start menu shortcuts.

  **Released at the user's request with a known open report:** a Windows tester who updated
  from `next` (Caps Lock key) saw "FT Assistant" in Task Manager, but the Assistant key did
  nothing afterwards. The cause wasn't found yet. Suspect: the renamed `FT Assistant.exe` copy
  (a log and a plain-pythonw comparison were requested from the tester).
- **v0.3.1** (2026-11-21): two fixes for "Assistant, ..." found right after 0.3.0 (see "Agent
  windows opened again after an update" and "The agent's window is remembered" below):
  - after an update, no agent window opened while another terminal was open (the update
    window's terminal address was passed on to gnome-terminal); setup's install, update and
    uninstall windows had the same problem;
  - the agent's window is remembered across FT Assistant's restarts, for the login session, and
    a reused window number never gets a request typed into it.

  Tested live on the user's machine with `run-branch.sh next` (request sent to the open Claude
  Code window after a restart). The Windows tester's open report from 0.3.0 is unchanged.

## Carried over from the current tool (unchanged)

- **Push-to-talk:** hold the Assistant key, speak, release; local Whisper transcribes.
- **Free all resources when idle:** the speech engine and the tool's own mic stream are released
  right after each dictation (~1 s cold start is fine).
- **Never mute, disable or reconfigure the system microphone;** only the tool's own input stream
  is opened and closed.
- **Privacy:** audio stays in memory only, never on disk. The Whisper model runs offline.
  **Transcribed text is never logged.**
- **Errors-only log** (decided 2026-11-18, ships in 0.2.0): the log file holds only errors,
  warnings and one start-up line. No activity is recorded (not when, how long or how often anyone
  dictates). Activity lines exist at debug level for development and are never written. The file
  is capped at 200 KB (one old copy kept). `tests/test_logging_policy.py` enforces this.
- **Filters:** short taps and near-silent clips are ignored; Whisper's made-up phrases on silence
  ("Thank you.") and trailing subtitle credits ("Closed Captioning by …") are removed.
- **Beeps:** a start beep when the mic is live, a stop beep when release is registered.
- `vocabulary.txt`-style list of words Whisper should spell a certain way.

## Feature: the "Assistant" keyword

### Decided

1. **Normal dictation stays exactly as it is.** If a dictation doesn't start with the keyword,
   the tool types it into the focused window, as today.
2. **One keyword: "Assistant".** Only when it is the very first word of a dictation.
   "Claude" and "OpenCode" are not keywords and are typed like any other word.
3. **The keyword sends the rest of the dictation to the user's chosen assistant** (code harness):
   either **Claude Code** or **OpenCode**, picked in the setup screen.
4. **Always visible, never in the background.** The tool opens the chosen harness's
   **command-line (CLI) version in a visible terminal window**, starts it with the command,
   and the user watches the agent work there and can keep talking to it:
   - Claude Code → `claude "<text>"`
   - OpenCode → `opencode <folder> --prompt "<text>"`

   Changed 2026-11-17 (was: desktop apps). Reasons: OpenCode's desktop app can't be pointed at a
   folder from outside, and the user prefers one consistent approach. Both CLIs are full agents
   that **can make changes on the host system** (edit files, run shell commands), asking for
   permission as configured. No hidden or headless agent runs, ever.
5. **Routing depends on the focused window:**
   - **Already typing in a harness terminal** (Claude Code or OpenCode, **even if it's not the
     chosen one**) → strip "Assistant" from the start, type the rest into the current
     conversation **and send it** (press Enter). No new session. "Assistant" means "run this";
     plain dictation without the keyword still only types, so the user can review first.
   - **Anywhere else** → open the chosen harness in a **new terminal window** with a new session,
     and send the rest of the dictation as the first message.
   - **"Assistant" with nothing after it** → open the chosen harness in a new terminal window with
     an empty session. (If already in a harness terminal: nothing to type, so nothing happens.)
6. **New sessions start in a neutral folder, not a project.** A CLI always runs in some folder,
   so both harnesses start in a dedicated `FT Assistant sessions` folder in the user's home.
   That's only the starting point: agents can still work elsewhere when asked, and the user can
   turn a session into a project by saying so in it. Never an unrelated existing project.
   - **One ongoing conversation, no build-up** (decided 2026-11-18 after the first live test):
     "Assistant, …" from outside a harness terminal continues the **last conversation** in that
     folder (Claude Code `--continue`; OpenCode `--session <newest id in that folder>`), and if
     that conversation's window is still open it's brought to the front and the request is sent
     there instead of opening another window. A brand-new conversation only starts when none
     exists yet. Live-tested with Claude Code: both cases worked.
   - The folder-trust question appears once, the first time Claude Code sees the folder.
7. **Permission prompts are answered by keyboard only.** When an agent asks to approve a risky
   action, the user presses the key; voice never approves anything, so a misheard word can't
   authorize an action. (Claude Code's default auto mode keeps these prompts rare.)
8. **Terminal: the system default.** Linux: the desktop's default terminal (here GNOME Terminal).
   Windows: Windows Terminal if installed, otherwise the standard console.
9. **Only two harnesses for now: Claude Code and OpenCode.** OpenCode is the free option for users
   who can't or don't want to pay for Claude Code. Considered and set aside (2026-11-17): Google
   Antigravity (free plan with weekly limits) and Kilo Desktop (beta). Gemini CLI and Qwen Code no
   longer have free tiers. Adding more later should stay possible.

## Feature: the setup screen ("Assistant setup")

1. **Opens automatically on first install**, so a harness is always chosen before the keyword is
   used. Saying **"Assistant setup"** reopens it any time.
2. **Tells the user how to get back to it,** naming their actual key, e.g. "To open this screen
   again, hold Caps Lock and say 'Assistant setup'." That key is called the **Assistant key**.
3. **Built with Tkinter:** comes with Python (no extra download), same on Windows and Linux.
4. **Harness choice:** **OpenCode** (free) or **Claude Code** (with a subscription, or by
   preference). If the chosen harness isn't installed, the screen explains and helps install it.
   **Nothing is downloaded automatically** outside this screen.
5. **Assistant key:** a button starts capture; the next key or mouse button press becomes the
   Assistant key. Easy to change again.
   - **Default for a new install: Caps Lock** (every keyboard has it, on both systems).
   - **Any keyboard key** and **any extra mouse button** (side buttons, Fn buttons) are allowed.
   - **Refused:** left, right and middle click, and the scroll wheel (up/down, tilt), each with a
     short message saying why.
   - **Guidance** next to the button (draft wording):
     - *Good choices:* Caps Lock, Scroll Lock, Pause, Insert, the Menu key, F13–F24 if your
       keyboard has them, or a spare side button on your mouse. Pick one you can hold
       comfortably while speaking.
     - *Best avoided:* letters, numbers, Space, Enter, Tab, Backspace and arrows (you need them to
       type); Shift, Ctrl, Alt and the Windows/Super key (used in shortcuts); Esc and Print Screen
       (other programs use them).
     - Choosing a "best avoided" key shows a short warning and asks to confirm; still allowed.
6. Also on this screen: **Check for updates** and **Uninstall** (see below).
7. **Dark mode** (user request, 2026-11-18): the screen and its Yes/No dialogs use a dark theme.

**Build status (phase 2, 2026-11-18):** built in `ft_assistant/setup_ui.py` (own process, the
Assistant key is paused while it's open; a changed key restarts the app). Live-tested by the user:
first-run opening, choosing a harness, refusing left click, capturing a new key, saving and
restarting, and reopening with "Assistant setup". **Not yet run: the Install… button** (both
CLIs were already installed; it runs the official installers `curl -fsSL https://claude.ai/install.sh
| bash` and `curl -fsSL https://opencode.ai/install | bash` in a visible terminal after asking).
Check for updates and Uninstall are placeholders until their phases.

## Planned for the first release (added 2026-11-18, not started)

Requested by the user to be built before the first release. Documented only; no code yet.

### "Dictation only" choice (built 2026-11-18, for 0.2.0)

- **The first choice in the assistant list** on the setup screen, above OpenCode and Claude Code:
  **"Dictation only: just typing, no assistant"**. Stored as `"harness": "none"`.
- **Save never warns** that an assistant isn't installed; nothing about assistants is checked.
- **The keyword is off:** "Assistant, ..." is typed as ordinary text (`textproc.route`).
- **"Assistant setup" still opens the setup screen**, so there's always a spoken way back.
- **The privacy note** reads "Everything stays on this computer: nothing you say is sent anywhere."
- **First run:** preselected when neither Claude Code nor OpenCode is installed; otherwise nothing
  is preselected.
- Tested by the user with the dev build: "Assistant, hello there" was typed, "Assistant setup"
  opened the screen with Dictation only selected, Save closed without questions.

### Choosing the command word (built 2026-11-18, for 0.2.0)

- Named **"command word"** (the user called it a wake word): the word that turns dictation into a
  command. The key keeps its name, "Assistant key". Default: "Assistant". Stored as `"keyword"`.
- A **"Command word" field** on the setup screen, under the Assistant key. Rules
  (`textproc.check_keyword`): one word, letters only (accented letters allowed), 2-20 letters,
  first letter capitalized. Words that often start sentences ("okay", "so", "the", ...) get a
  warning but are allowed.
- Everything follows the word: "<word>, request", "<word> setup", the setup screen's reopen line,
  privacy note and explanation, the notifications, and the Whisper hint words
  ("<word>, <word> setup" before the vocabulary; the worker re-reads it for every dictation).
  With another word, "Assistant" is ordinary text. In Dictation only, just "<word> setup" counts.
- **Speech test** (synthetic phrases, 12 per word, both models, with/without hints): Jarvis
  12/11 vs 10/9, Computer 11/12 vs 12/12, Atlas 11/12 vs 10/11, Nova 10/9 vs 6/10. Hints help
  most words; some words are simply harder. The setup screen suggests trying the word after saving.
- Tested by the user with the dev build: changed to "Computer"; "Computer, say hello" went to
  Claude Code; "Assistant, hello there" was typed; "Computer setup" opened the screen.
- Later idea: a "Try it" button that listens once and shows whether the word was caught.

## Feature: distribution as one small setup script

### Decided

1. **One setup script for both Windows and Linux:** `FT-Assistant-setup.cmd`, a polyglot file
   that both Windows (`cmd`) and Linux (`bash`) can read. Each skips the other's part, installs a
   Python runtime, then both run the same shared Python setup program (which can be embedded in
   the same file). Windows: double-click. Linux: `bash FT-Assistant-setup.cmd`.
2. **The script stays small; everything else is downloaded.** No bundled "big package" option.
   The project can grow as large as it needs to; only the thing you hand out stays small.
3. **The setup script is the installer.** No separate installer.
4. **From zero** it installs whatever is missing: Python runtime, speech engine, GPU libraries if
   there's an NVIDIA card, the Whisper model, and the chosen harness's CLI (with consent).
5. **Hardware detection:** NVIDIA GPU → GPU path with large-v3-turbo; otherwise a CPU path with a
   smaller model.
6. **Clean install flow** (first install, or reinstall with no trace of the tool or its stack):
   1. The script's own console window says to **wait while requirements are checked** (OS, NVIDIA
      GPU or not, what's already installed, e.g. a harness CLI).
   2. It shows the **approximate total download size and disk space**, with a short breakdown, as
      **plain text before anything is downloaded, not even Python**, and waits for the user to
      continue (e.g. press Enter) or cancel.
   3. Only then it downloads and finishes setup; the setup window opens afterwards. If some
      components already exist, the summary lists only what's still missing.
   - Implementation: the requirement check runs in the script's Windows and Linux parts (before
     Python exists). Sizes come from a tiny manifest on the GitHub release, or built-in
     estimates if offline.

### Install, updates, uninstall

**Build status (phase 4, 2026-11-18):** `installer/setup-template.cmd` (Linux bash part, Windows
cmd + PowerShell part) and `installer/install.py` (shared install / update / uninstall, standard
library only); `python3 installer/build.py` writes `dist/FT-Assistant-setup.cmd` (~23 KB) with the
installer embedded at the end. The Python runtime is python-build-standalone 3.12 (68 MB Linux,
47 MB Windows), found through GitHub's API at install time. Packages are pinned to the versions
running today (faster-whisper 1.2.1, ctranslate2 4.9.0, cuBLAS/cuDNN cu12). On a computer without
an NVIDIA card the model is `small.en`. Linux needs `xdotool`, `notify-send` and `libportaudio2`
from the system; setup names the exact `apt install` command if one is missing. The app writes its
process id into its lock file so the installer can stop it before updating or uninstalling.
Windows part: written, not yet run (Bottles phase); the app itself has no Windows layer yet.
Live-tested on Linux (2026-11-18) in a throwaway folder (full GPU path; model copied from the
live install): setup file -> install -> the installed copy transcribed on the GPU -> first-run
setup, key change, dictation -> update (via `install.py update`) -> Uninstall from the setup
screen removed the install folder, settings and menu entries. Fixes from testing: GitHub writes
"+" as "%2B" in download names; user-site Python packages are kept out (`PYTHONNOUSERSITE`);
re-running setup skips a model that's already there; the setup screen uses pixel font sizes,
because the installed Python's Tk 9 draws with old X11 fonts (they also can't draw "…" or "–").
**Clear fonts on Linux (2026-11-18):** the setup window runs on the computer's own Python when its
Tk draws smooth (Xft) fonts (`ft_assistant/gui.py`; python-xlib and six are copied next to the
settings for it), else on the bundled Python with the pixel-size fallback. The setup file now
**offers to install missing system packages** with one `sudo` command (apt, dnf, pacman or zypper;
the user types their password): needed `xdotool`, `libnotify`, `portaudio` (setup stops if they're
still missing) and recommended `python3-tk` (setup continues without it, plainer font).
**Reuse before download (2026-11-18, user request: "anywhere possible, in Linux or Windows").**
Setup and installer reuse what's already on the computer:
- **Python:** the computer's own Python 3.9-3.13 with `venv` becomes the tool's private package
  folder (no 70 MB download; on Linux its Tk also gives smooth fonts). `python3-venv` is offered
  as a recommended package when only that is missing. If the speech engine has no build for that
  Python (installer exit code 3), setup falls back to the downloaded standalone Python. Windows:
  `py` launcher or a real `python` (not the Microsoft Store placeholder).
- **NVIDIA libraries:** used from the system when cuBLAS 12 and cuDNN 9 are installed there
  (Linux `ldconfig`, Windows `PATH`); otherwise pip copies.
- **Whisper model:** found in the Hugging Face cache (`HF_HUB_CACHE`, `HF_HOME`,
  `~/.cache/huggingface/hub`), and **hard-linked** (no extra
  disk; independent of the original). Newer caches keep big files in a shared blob store outside
  the model folder; those links are resolved to the real file.
- **pip's shared download cache**, Claude Code / OpenCode if installed, and the system tools.
- The size summary marks reused parts "already on this computer (reused)".
- **After a system upgrade** breaks a reused Python, the launcher shows a "needs a repair"
  notification; re-running setup rebuilds the package folder.
Live-tested on Linux: reused Python 3.12.3 and the live tool's model (download estimate 3.1 GB ->
1.45 GB), GPU transcription OK, first-run setup with smooth fonts, dictation, uninstall; the live
tool's model was untouched.

1. **Install location:** suggested, and changeable before installing. Per-user, no admin rights:
   Linux `~/.local/share/ft-assistant/`, Windows `%LOCALAPPDATA%\FT Assistant\`.
2. **Start at login:** Linux `~/.config/autostart/` entry; Windows a shortcut in the user's Startup
   folder.
3. **Settings file:** Linux `~/.config/ft-assistant/`, Windows `%APPDATA%\FT Assistant\`
   (chosen harness, Assistant key).
4. **Updates are never installed without asking.**
   - **Where:** the project's latest **GitHub Release** on the user's **`freethought78`** account
     (never `ftftft78`): public repo https://github.com/freethought78/ft-assistant. One request to GitHub's public "latest release" API,
     no account, no user data. This is the only thing that goes online outside setup.
   - **When:** about a minute after the tool starts, then at most once every 24 hours while
     running; **never during a dictation**; plus a **Check for updates** button. Offline or no
     answer → give up silently, retry next time.
   - **How the user is told:** a normal **system notification** (Linux bubble, Windows toast),
     e.g. "FT Assistant 1.3 is available". **No pop-up window and no focus stealing.** Clicking it,
     or saying "Assistant setup", opens the setup screen with what's new and **Update now** /
     **Not now**. "Not now" → quiet about that version for a few days, then one more reminder;
     a newer release resets this.
   - **Nothing is downloaded until "Update now".** Updating backs up the current version so it
     can be rolled back.
   - **Build status (phase 3, 2026-11-18):** built in `ft_assistant/updater.py` plus the app's
     schedule and the setup screen. Live-tested by the user against a pretend local release
     (notification with a Show button, setup screen with what's new, Not now, Check for
     updates). Until the installer exists, "Update now" opens the release page. The repo name is
     `freethought78/ft-assistant` (created 2026-11-18; no releases yet). Testing
     hooks: `FT_ASSISTANT_UPDATE_URL`, `FT_ASSISTANT_UPDATE_DELAY`, `FT_ASSISTANT_UPDATE_TICK`.
5. **Uninstall**, from the setup screen (both systems), Windows Settings → Apps (registered
   per-user), or an "Uninstall FT Assistant" entry in the Linux app menu. Removes the tool, its
   Python runtime, speech engine, GPU libraries, Whisper model, login and menu entries. Draft: a
   "keep my settings" checkbox; it **leaves the Claude Code and OpenCode CLIs installed** (separate
   programs the user may still want), and says so.

### Sizes (measured on this Linux machine, 2026-11-17)

- Tool's own code: 24 KB.
- Python packages without GPU libraries: ~350 MB on disk (~100–150 MB download, estimated).
- NVIDIA libraries (cuBLAS, cuDNN, NVRTC): 2.1 GB on disk (~1–1.5 GB download, estimated).
- Whisper large-v3-turbo: 1.6 GB. Smaller models: ~150–500 MB.
- Harness CLIs (npm installs): Claude Code 356 MB, OpenCode 412 MB on disk.
- Totals without a harness: ~3–3.5 GB download with an NVIDIA card, ~0.3–0.7 GB without.

## Decisions from the full review (2026-11-17)

1. **"Assistant setup" always opens the setup screen**, even inside a harness terminal; it's never
   sent to an agent as a message.
2. **The setup screen says plainly that Assistant commands go to an online AI** (Anthropic for
   Claude Code, OpenCode's model provider for OpenCode), while normal dictation stays entirely on
   the computer.
3. **Linux: X11 only for the first release.** Setup detects Wayland and explains it isn't
   supported. Wayland is not planned (see "Wayland is not planned" under "Planned", 2026-11-23).
4. **Windows testing happens in Bottles** (Wine), reusing the user's existing test bottle
   **`DannyRando-Test`** (Flatpak Bottles, win64, soda runner) instead of creating new ones.
   Never touch the user's other bottles (games and apps). Wine isn't real Windows, so some things can only
   be partly checked there: the NVIDIA/CUDA path, Windows Terminal, toast notifications, the
   Startup folder and "Settings → Apps" registration. Those need a real Windows machine before a
   public release.

## Planned (not started)

Documented only; no code yet. Sorted by branch (2026-11-21).

**Plan for the work:**
1. The user reviews these plans.
2. Everything under "On `next`" is built and tested on `next`, starting with FT Assistant's own
   Python, then released from `main` as usual.
3. The `conversation-management` branch is then made from `next`, so it has all of that,
   including the branch label and the switch for trying it as the live tool.
4. It stays separate until the user says to merge it.

**Keep it simple (the user, 2026-11-23):** FT Assistant is a one-button way to use the computer,
with little to read and nothing to set up. A new feature is only worth it if it adds no
complexity. Rules for every plan below:
- **No new settings:** it works with no setting, and nothing new goes on the setup screen.
- **Explanations are one sentence each,** in the voice commands window.
- **At most about 7 voice commands,** ever.
- **Something the user only notices when they need it** (a notice when something fails) is
  better than something they have to learn.

**Reviewed 2026-11-23:** the feature set is about right. Added: a notice when the assistant
window doesn't open, and "<word> undo". Dropped: the "possibly related note" hint (part 3 of
conversation management).

**Wayland is not planned (the user, 2026-11-23):** don't suggest Wayland support; the user will
bring it up if they ever want it. Linux stays X11 only.

## On `next`

Order: 1. FT Assistant's own Python (the user's first choice); 2. uninstall safety; 3. the folder
window; 4. trying a branch as the live tool (built first, at the user's request); 5. the voice
commands window. Added later (2026-11-21), after item 1: the installer's file name, and the
"FT Assistant" process name.

### FT Assistant always uses its own Python, and reuses it (added and built 2026-11-21)

**Built** (`installer/install.py`, `installer/setup-template.cmd`, `installer/build-smooth-tk.sh`):
- **The runtime is pinned** in install.py (`RUNTIME_RELEASE`, `RUNTIME_PYTHON`, SHA-256s). The
  setup script reads those lines from the copy of install.py embedded in it, so there's one
  source.
- **Downloads are checked** against the SHA-256 before use. The runtime folder gets a marker file
  (`FT-ASSISTANT-RUNTIME`).
- **Reuse:** setup reuses `<install dir>/python` when the marker matches, it isn't a venv, and it
  runs the pinned version.
- **Moving over:** an update moves any other install (a venv, or an older download):
  1. It builds `python.new` and installs the packages into it.
  2. Linux: it renames the folders. Windows: a helper window (`finish-update.cmd`) waits until
     the old Python has exited, then swaps them and runs `install.py finish-runtime`.
  3. `python.old` is deleted once FT Assistant logs `ready:` again; otherwise it's kept.
  4. A failure before the swap leaves everything as it was.
- **Smooth text:** setup swaps the smooth Tk into the runtime (`ensure_smooth_tk`) before
  anything opens a window. The setup window always uses FT Assistant's own Python (`gui.py`
  removed).
- **Tested 2026-11-21, all in throwaway folders:**
  - Linux fresh install with the real pinned download: 47 s with pip's cache. It transcribed on
    the GPU, and Tk drew smooth text.
  - Linux rerun: the Python was reused, nothing downloaded.
  - Linux update of a 0.2.8-style install on a system-Python venv (with the real 0.2.8
    installer): moved over, and the app imports under the new Python.
  - Windows (bottle) fresh install with the real download and Get-FileHash check, then a rerun:
    reused.
  - Windows update of a 0.2.8-style install: moved over through the helper window, leaving no
    `python.old` or `python.new` behind.
- **Still to do before release:**
  - Upload the smooth Tk as the pre-release `smooth-tk-9.0.4` (tests used the local file via
    `FT_SETUP_SMOOTH_TK`).
  - With a real 0.2.8 install on Windows, the old update window asks for Enter before it
    closes. The helper waits up to about 30 minutes and says so.

The plan as agreed:

**Decided by the user:** FT Assistant always runs on its own Python runtime, kept in
`<install dir>/python` and managed entirely by setup and the updater. It never uses or depends on
another Python on the computer, and never adds anything to one.

- **Today:** setup prefers the computer's own Python when it's a suitable version, and builds a
  private package folder (venv) from it in `<install dir>/python`.
  - The packages go into that folder, not into the user's Python, but the install still depends on
    that Python. Upgrading or removing it can break FT Assistant.
  - On Linux, setup may also offer to install the system package `python3-venv` "to reuse this
    computer's Python". That's a change to the system the user may not want to keep.
- **Change for new installs:**
  - Setup always uses the standalone runtime from python-build-standalone (Python 3.12).
  - Remove the system-Python path: `py_ok`/`py_venv`, the `python3-venv` offer and
    `PY_SOURCE=system` on Linux; `Find-SystemPython` and `$pySource = 'system'` on Windows; the
    "can't use this computer's Python, downloading one instead" fallback (exit code 3).
  - `install.py --python-source` keeps accepting `system` only so it can read old installs.
- **Reuse instead of downloading again** (seen on a Windows tester's PC): every run of
  `FT-Assistant-setup.cmd` over an existing install deleted `<install dir>/python` and downloaded
  the runtime again (about 50 MB on Windows, 70 MB on Linux). It did this even when a working
  copy was already there from earlier attempts. The Whisper model and NVIDIA libraries were
  correctly reused.
  - The cause is that `Get-StandalonePython` and `download_python` in `installer/setup-template.cmd`
    always delete the folder first.
  - New behaviour: if `<install dir>/python` is the standalone runtime (`install.json`
    `"python": "standalone"`) and its `python.exe` / `bin/python3` runs and reports 3.12, reuse it.
  - Download only when it's missing, broken, or the old system-based venv.
  - The "What setup needs" summary says "already in the install folder (reused)" when it will be
    reused.
  - Optionally keep the downloaded archive until setup succeeds, so a failed unpack doesn't
    download it again.
  - The built-in updater ("Update now" / `install.py update`) already keeps the existing Python;
    only running the setup file again re-downloaded it.
- **Moving existing installs over** (in the next release or one soon after):
  1. When an update sees `"python": "system"` in `install.json`, it downloads the standalone
     runtime into `python.new` and installs FT Assistant's packages into it. pip's download
     cache usually has them already, including the large NVIDIA libraries.
  2. Only once that works does it swap the folders: the old one becomes `python.old` for rollback,
     and `python.new` becomes `python`.
  3. It then updates `install.json` and restarts FT Assistant. `python.old` is deleted after a
     successful start, or by the next update.
  4. On Windows a running Python can't rename its own folder, so the swap has to happen from the new
     Python (or a small helper) after the old one has exited.
  5. Tell the user what happened in plain words, including the extra download size beforehand,
     and say that their own Python wasn't touched.
  6. The developer's own Linux install is one of these (system Python 3.12 venv). `run-dev.sh`
     borrows that Python, so it keeps working after the switch.
- **Test:**
  - Run setup twice over the same folder on Linux and in the Windows test bottle. The second run
    must not download Python.
  - With a deliberately broken `python` folder, setup must download a fresh copy.
  - Update an install made from a system Python (Linux venv, Windows venv): afterwards it runs on
    the standalone runtime, has no link to the system Python, and still dictates. Rolling back
    to `python.old` must work.

**Smooth text in the setup window on Linux (decided 2026-11-21).** The standalone Python's Tk
(9.0.4 in python-build-standalone 20261110) draws with old X11 fonts: rough, unsmoothed text. Until
now the setup window borrowed the system Python to draw smoothly (`gui.py`). The user's decision:
take whatever steps are needed so the setup window **never** shows rough text, even the first
time, and **no GitHub automation** (nothing that may cost money); we build and track it ourselves.

- **How:** Tk is a separate library inside the runtime (`python/lib/libtcl9tk9.0.so`), so it can
  be swapped for the same Tk version built with smooth fonts (Xft).
  - Built and checked locally 2026-11-21: it draws with the desktop's smooth fonts.
  - It needs only `libX11`, `libXft` and `libfontconfig`, which nearly every desktop has.
  - Its newest glibc symbol is 2.14, so it loads on Linux back to about 2011.
- **Build recipe** (to be written down as a script in the repo, run by hand):
  1. Get Tcl and Tk sources of the runtime's exact version (`info patchlevel`).
  2. Get the Xft, fontconfig and freetype header packages with `apt-get download`, unpacked into
     a scratch folder (nothing installed on the system).
  3. Build Tcl, then Tk with `--enable-xft --disable-xss --disable-zipfs`. Use a tiny
     `xft-config` that points at those headers. Force the old symbol versions of `pow`, `fmod`,
     `fmodf` and `hypot` with `.symver`, so the library doesn't need glibc 2.29-2.38.
  4. Check: `readelf -d` needs only the libraries above; `objdump -T` shows nothing newer than
     GLIBC_2.14; with the library swapped in, `::tk::pkgconfig get fontsystem` says `xft`.
- **In setup:**
  1. The Python runtime download is pinned to the matching python-build-standalone release
     (not "latest"), so the Tk version always matches.
  2. The smooth Tk (about 1.8 MB) is attached to our own GitHub release.
  3. After unpacking Python, and before anything opens a window, setup swaps it in, keeping the
     original as `libtcl9tk9.0.so.rough`.
  4. It checks that a Tk window opens. If it doesn't (e.g. `libXft` missing), it puts the
     original back, so the window opens with rough text rather than not at all.
- **Then** `gui.py`'s borrowing of the system Python and the `python3-tk` offer are removed.
- **Updating Python later** means rebuilding Tk with the recipe for the new Tk version.

### Setup window text size follows the desktop (built 2026-11-21)

- **The problem:** the setup window used fixed 15-pixel text. On the user's desktop (Ubuntu
  10 pt) that was too big. Worse, Tk converts sizes with the monitor's *physical* DPI: the
  user's wide monitor reports 54 DPI while the desktop draws text at 96 DPI. So with smooth fonts
  every size came out about 1.8 times too big.
- **Now** (`ft_assistant/look.py`, `setup_ui.py`):
  - **Linux:**
    - The desktop's interface font and size: Cinnamon, GNOME, MATE (gsettings), Xfce (xfconf),
      KDE (kreadconfig).
    - Times its text-scaling factor, at the desktop's font DPI (`Xft.dpi`).
    - Tk's scaling is set to that DPI.
  - **Windows:** Windows' interface font and size. The setup process is DPI-aware, so text stays
    sharp with display scaling.
  - **Kept between 9 and 18 pt.** Headings are 1.15× and the title 1.45× the body text.
  - **Spacing is in multiples of the text size:** line width 35 em, margins, button padding.
  - **Fitting the screen:** when the window is too tall, it first gets wider (up to 60 em), then
    the text shrinks (at most to 85 %, never below 9 pt), then the content scrolls. It stays
    inside the work area (taskbar and panels).
  - **Resizing re-wraps the text** to the new width.
- **Checked:**
  - The user approved it on their desktop.
  - Measured on simulated 2560×1400, 1366×728 (fits by widening), 1024×600 and 800×560
    (scrolls).
  - In the Windows test bottle: Windows' font at 9 pt; same fitting.
  - **Not yet on a real Windows PC with display scaling.**

### Uninstall deletes only what setup created (added and built 2026-11-21)

**Built:**
- **Uninstall:** `install.py` has `OWN_ITEMS`, one fixed list of everything setup and updates make
  in the install folder (a list, not `install.json`, so it also works for older installs). Plus
  temporary `ft-runtime-*` folders, and the old `ft-assistant-setup` launcher only when it's that
  small launcher.
  - Uninstall removes only those things, and only FT Assistant's model folders inside
    `models/`. Then it removes `models/` and the install folder if they're empty.
  - On Windows, the detached clean-up command deletes `python\` and then the folder with
    `rmdir` without `/s`, so only when it's empty.
- **Setup:** a chosen folder that holds anything else gets an "FT Assistant" subfolder (Linux and
  Windows). "Anything else" excludes FT Assistant's own leftovers (e.g. a failed earlier install),
  the setup file itself, and an existing install (`install.json`: updated in place).
  - If that subfolder also holds someone else's files, setup stops and asks for another folder.
  - The setup script reads `OWN_ITEMS` from the embedded installer, so there's one list.
- **Tested 2026-11-21:**
  - Unit tests for a shared folder, the user's own folder, the Windows clean-up command and the
    setup rule.
  - Real runs on Linux and in the Windows bottle: setup into a folder holding "My notes.txt" went
    into "FT Assistant" inside it, and uninstall left exactly "My notes.txt".

The plan as agreed:

- **A risk in the released versions:** uninstall deletes the whole install folder
  (`shutil.rmtree` in `install.py`).
  - Setup installs straight into whatever folder is typed. Typing an existing folder such as
    `E:\` or `Documents` puts FT Assistant's files among the user's own.
  - A later uninstall would then delete everything else in that folder too.
- **Fix, in two halves:**
  1. **Uninstall** removes only what setup created. `install.json` lists it: `app/`, `python/`,
     `models/`, the launchers, `install.py`, `install.json` and their `.old` rollback copies.
     The folder itself is removed only if it's empty afterwards.
  2. **Setup** installs into an "FT Assistant" subfolder of any chosen folder that isn't empty
     and isn't already an install (part of the folder-window plan below; can ship earlier on its
     own).
- **Test:** install into a folder that has other files in it, then uninstall. The other files are
  still there, and FT Assistant's are gone. That includes Windows, where the running Python is
  deleted a few seconds after uninstall exits.

### Choosing the install folder with a folder window, before anything is downloaded (added and built 2026-11-21)

**Built** (`installer/setup-template.cmd`):
- **The folder question comes first:**
  - Linux: right after the 64-bit and desktop checks, before the system packages step (which may
    use `sudo`).
  - Windows: before the summary.
- **Enter** keeps the default with no window. **C** opens the folder window at the default (or
  its nearest existing parent). **Cancel** asks again. Typing a path at the question still works.
  Updating an existing install says when another folder would make a second copy.
- **The windows:**
  - Linux: `zenity --file-selection --directory`, else `kdialog --getexistingdirectory`, else
    typing.
  - Windows: Explorer's "Select folder" window (`IFileOpenDialog` with FOS_PICKFOLDERS through
    `Add-Type` C#, kept to older C# for Windows PowerShell 5.1), else `FolderBrowserDialog`,
    else typing.
- **Then** the subfolder rule, the summary for the chosen folder, and "Press Enter to start". The
  folder is created only after that, so cancelling leaves nothing behind. The free-space check
  uses the nearest existing folder.
- **Tested 2026-11-21:**
  - Automated: pretend zenity and kdialog (choose, cancel, KDE, typed, updating), and the order
    of the steps.
  - The user, on their desktop with zenity: picked a folder holding a file, got the subfolder
    and the summary, cancelled.
  - kdialog in a temporary Ubuntu 24.04 container on the user's display: cancel and choose both
    worked.
  - Windows bottle: Explorer-style window (Wine's version) opened in the start folder; cancel
    and choose worked. A full setup into a new folder with a space in its name worked.
  - **Not yet on a real Windows 10/11 PC** (Windows PowerShell 5.1's C# compiler, the real
    Explorer look).

The plan as agreed:

**The problem:** setup asks for the install folder as typed text ("Press Enter, or type another
folder"). Typing a path is awkward, especially when dictating. On Linux the question also comes
after the system packages step, which may already download and install packages with `sudo`.

**Proposed flow** (the first question setup asks, before Step 1's package installs and before
Python or anything else is downloaded):

1. Setup explains the default location in plain words and asks one question in the terminal:
   - New install: "FT Assistant will be installed in <default> (your user folder, no admin rights
     needed). Press Enter to use this folder, or C to choose another folder."
   - Existing install found: "FT Assistant is installed in <folder>. Press Enter to update it
     there, or C to install somewhere else." (Choosing elsewhere warns that this makes a second
     copy.)
2. **Enter:** no folder window at all; the default is used.
3. **C:** a folder window opens, already showing the default location (or its nearest existing
   parent folder). The user can pick any existing folder or make a new one in the window.
4. **Cancel in the folder window** goes back to the question; it never ends setup.
5. Only then come the "What setup needs" summary and the downloads. The summary is worked out
   for the chosen folder: whether a speech model is already there, and the free-space check on
   that drive.

**The folder window, using only what's already on the computer** (Python isn't downloaded yet):
- **Windows:** the normal Explorer-style "Select folder" window (`IFileOpenDialog` with
  `FOS_PICKFOLDERS`), through a few lines of C# compiled by PowerShell's built-in `Add-Type`.
  - Fallback: .NET's `FolderBrowserDialog` (older tree-style window).
  - Needs PowerShell's STA mode (`powershell -STA`).
- **Linux:** kept deliberately simple. Setup tries these in order and uses the first one found:
  1. `zenity --file-selection --directory`: installed by default on Mint, Ubuntu, Fedora and
     most GNOME/GTK desktops;
  2. `kdialog --getexistingdirectory`: KDE;
  3. the typed path, as today, when neither is installed. This is common on XFCE and on minimal
     installs.

  No extra packages are installed for this, and no harder routes are attempted: for example the
  desktop portal over D-Bus works on more desktops but is much more complicated.
- **Linux without a desktop (terminal only):** FT Assistant can't work there at all, because it
  types into windows on an X11 desktop. Setup already stops right at the start with "No
  graphical desktop (X11) was found. Run setup from your desktop." So the folder question never
  comes up without a display. The typed path stays as the fallback when no window tool is
  installed, or the window fails to open.
- **Testing and unattended runs:** `FT_SETUP_DIR` / `FT_SETUP_YES` still skip every question.

**Where the files go in the chosen folder (a safety rule):**
- If the chosen folder is empty, or already an FT Assistant install (`install.json`), install
  right there.
- Otherwise, install into a new **"FT Assistant"** subfolder inside it, and say so: "FT Assistant
  will be installed in E:\Programs\FT Assistant".
- **Why:** see "Uninstall deletes only what setup created" above. The subfolder rule is the
  setup half of that fix.
- The chosen folder must be writable. Setup tests this before going on and asks again if it
  isn't.

**Test** (agreed with the user 2026-11-21: nothing extra is installed on the developer's Linux
system, and there's no second Linux install):
- **Cases on every path:**
  - default by Enter;
  - picking an empty folder, a non-empty folder (subfolder created) and an existing install
    (updates in place);
  - cancel, then choose again;
  - uninstall after installing into a non-empty folder leaves the other files there untouched.
- **Linux, zenity:** real test on the developer's desktop (Mint/Cinnamon has zenity).
- **Linux, typed path:** real test, running setup with a PATH that only has the tools it needs
  symlinked in, so zenity and kdialog aren't found. That's the same method as the GPU-check test
  in `tests/test_installer.py`. Nothing is uninstalled.
- **Linux, kdialog:**
  - **Automated:** a pretend `kdialog` script on that PATH that answers like the real one (prints
    the chosen folder and exits 0; exits 1 on cancel). This checks the call and the answers.
  - **Once before release, for real:** run KDE's `kdialog` in a temporary container (podman or
    docker) that shows its window on the developer's X11 desktop. It takes about 1 GB while it
    exists and is deleted completely afterwards.
  - Installing the real `kdialog` on the developer's system is avoided: it pulls in a large part
    of KDE's libraries.
- **Not tested, and not needed:** Wayland and terminal-only Linux. Setup stops at the start in
  both cases, before the folder question.
- **Windows, in the test bottle `DannyRando-Test`** (checked 2026-11-21, without showing a
  window):
  - The bottle runs **PowerShell 7.4 (Core)** in STA mode. Inline C# through `Add-Type` compiles.
  - The Explorer-style folder window (`IFileOpenDialog` + `FOS_PICKFOLDERS`) can be created and
    accepts the folder-picking option. .NET's `FolderBrowserDialog` loads too.
  - So the bottle tests the whole flow: the question, opening the window, picking, cancelling,
    the subfolder rule and uninstall. It shows Wine's version of the window.
- **What the bottle can't show:**
  - real Windows runs setup in **Windows PowerShell 5.1** (.NET Framework), not 7.4. Its
    `Add-Type` uses the older C# compiler, so the inline C# must stay in older C# (no newer
    syntax such as `out var`);
  - the real Explorer look of the window.
  - So one run on a real Windows 10/11 PC before release is required.
- **Never against the live install:** test runs use `FT_SETUP_DIR` with a throwaway folder, and
  `XDG_CONFIG_HOME` / `XDG_DATA_HOME` pointing to throwaway folders. That way no menu entries,
  login entry or settings of the real install are touched.

### Trying a branch as the live tool (added 2026-11-21, built 2026-11-21)

So the user can test ideas on branches without a release, and without two copies running at once.

**Built** as `run-branch.sh` and `ft_assistant/buildinfo.py`.
- **Commands:**
  - `./run-branch.sh <branch>` runs that branch's latest commit, from a detached snapshot in
    `.worktrees/<branch>`.
  - `./run-branch.sh .` runs the checkout as it is, with "with uncommitted changes" in the label.
  - `--back` returns to the installed copy, and `--status` says which copy is running.
- **How it works:**
  - It runs the code through `run-dev.sh`, with its own folders (`~/.config/ft-assistant-branch/`
    and `~/.local/share/ft-assistant-branch/`).
  - Processes are told apart by their `FT_ASSISTANT_CONFIG_DIR` / `FT_ASSISTANT_DATA_DIR`.
  - A small supervisor restarts the installed copy if the test build exits without `--back`.
- **Live-tested by the user (2026-11-21):**
  - switching to `.`: the setup screen showed "Version 0.3.0 release candidate (next, with
    uncommitted changes): not a public release";
  - dictation on button 12;
  - going back through the menu entry.
  - The crash fallback: the test build was killed abruptly (`kill -9`), and the installed copy
    was running again 2 s later, with the menu entry removed.
- **Found while building:** `run-dev.sh` used the installed copy's data folder, so its setup screen
  offered "Update now" and "Uninstall..." for the *installed* copy. It now uses its own data folder.

The plan as agreed:

- **One copy runs at a time.** "Run branch X" (done with Claude's help, or a script):
  1. warn that dictation drops out for a few seconds;
  2. stop the installed FT Assistant;
  3. start the code from branch X on the user's normal Assistant key;
  4. confirm the `ready:` line in that build's own log.

  "Back to the installed version" does the reverse.
- **Each branch runs from its own folder** (a `git worktree`), so a running build never has its
  files changed underneath it and the main checkout can stay on `next`. These folders hold only
  source code.
  - Everything heavy is borrowed from the install, as `run-dev.sh` does today: Python and its
    packages (including the NVIDIA libraries), the Whisper model, the word list, and the
    installed Claude Code / OpenCode.
  - If a branch needs an extra Python package, it goes in a small folder for that branch only.
    The install's Python is never changed.
- **Its own settings and log** (copied from the real settings at start), so a test can't change
  the installed version's settings.
- **The setup screen shows what's running.** The version line reads, e.g., "Version 0.3.0 test
  build (conversation-management): not a public release". The `ready:` log line names the branch
  too.
  - Only when running from a git checkout; installed copies show the plain version.
  - Wording: "release candidate" for `next`, "test build" for idea branches (seen and accepted by
    the user in the live test).
- **Safety nets:**
  - A menu entry for "Back to the installed version", because a broken build can't be
    dictated to.
  - If the test build crashes, the installed version starts again by itself.
  - Login always starts the installed version, so a restart of the computer always gets it back.
- **Replaces** the side-by-side `run-dev.sh` (Scroll Lock key). That can stay for quick checks
  that don't need the real key.

### Voice commands: a button on the setup screen, and a short list (added and built 2026-11-21)

**Built** (`ft_assistant/voice_commands.py`, `textproc.py`, `app.py`, `setup_ui.py`):
- **The list:** "<word>, ...", "<word>", "<word> stop", "<word> setup", "<word> help".
  - Shown by the "Voice commands..." button (next to the command word field), and by "<word>
    help" as its own process, in front.
  - In Dictation only it shows just setup and help, and "<word> stop" is typed as text.
  - The setup screen's explanation under the field is now one line pointing to the button.
- **Matching:** the whole rest of the dictation must be the command ("Assistant, stop the
  server" is a request). "help" and "stop" are Whisper hint words like "setup".
- **"<word> stop":**
  - It presses Escape in the assistant window being dictated to, or else brings forward the
    window FT Assistant opened and presses it there. With no such window, it shows a notice.
  - **OpenCode needs two presses:** one only shows "esc again to interrupt", which resets after a
    few seconds; two showed "interrupted" (tested in a throwaway folder 2026-11-21).
  - **Claude Code gets one:** a second Escape would open its "rewind" menu.
- **Tested:**
  - Unit tests: routing, the list (at most 7, each understood and hinted), stop per assistant,
    one help window at a time.
  - **The user, live, with the test build (2026-11-21):** "help", "stop" (Claude Code), and the
    setup button all worked.

The plan as agreed:

**Goal:** move the explanations of the spoken commands off the setup screen, so the screen doesn't
grow every time a command is added. The commands themselves must stay few and obvious: staying
simple and easy to use out of the box is one of the project's main goals.

**The button:**
- A **"Voice commands..."** button on the setup screen, e.g. next to the command word field.
- It opens a small window listing every command, one line each, with the user's own command word
  filled in.
- The setup screen keeps only one line: "Say "<word>, ..." to send a request to your assistant."
  The longer explanation under the command word field moves into the window.
- The window opens by voice too, with "<word> help", so it can be found without the setup screen.
- With "Dictation only", the window shows only the commands that still work ("<word> setup",
  "<word> help").

**Rules for the list:**
- **At most about 7 commands, ever.** A new command needs a strong reason, or it replaces one.
- **Each one is one or two everyday words** after the command word, and said naturally.
- **It must be useful to most users regularly**, not a power-user feature.
- **It must be unlikely as the start of a normal request.** "<word>, new topic: ..." is fine;
  "<word>, continue ..." isn't, because real requests start with "continue".
- **It must never approve anything.** Permission prompts stay keyboard-only (decision 7 under the
  "Assistant" keyword), so a misheard word can't authorize an action.
- **Whisper hint words:** every command is added to the hint list (`textproc`, today
  "<word>, <word> setup") so the speech engine catches it. Too many hints can make Whisper
  "hear" them in normal speech, which is one more reason to keep the list short.

**The list** (help, new topic and stop approved by the user, 2026-11-21):

| Say | What happens | Status |
|---|---|---|
| "<word>, <request>" | Sends the request to the assistant | exists |
| "<word>" | Opens the assistant (the current conversation) | exists |
| "<word> setup" | Opens the setup screen | exists |
| "<word> help" | Opens the voice commands window | new |
| "<word> new topic" (optionally followed by a request) | Starts a fresh conversation, then sends the request if there is one | new, conversation-management branch |
| "<word> stop" | Interrupts the assistant's current work (presses Escape in its window) | new |
| "<word> undo" | Removes the dictation just typed, if nothing was typed or clicked since (added 2026-11-23) | new |

**Candidates held back** (not approved; weigh against the 7-command limit before adding any):
- **"<word> scratch that":** approved 2026-11-23 as **"<word> undo"** (see its own plan under
  `next`).
- **"<word> remember this":** asks the agent to write a topic note now (conversation-management
  topic notes). It may not be needed if the agent writes notes by itself.
- **"<word> continue":** forces continuing the old conversation after a quiet gap. It clashes with
  real requests. It's unnecessary if "new topic" exists and the gap rule is off or long.

**How it fits the conversation-management plan:** "<word> new topic" answers the open question
about phrases. With it, the user decides when a topic starts, so the quiet-gap rule could be
optional (off by default) instead of the main mechanism. That's simpler to understand.

**Where it's built:**
- On `next`: the button, the window, "<word> help" and "<word> stop".
- On the `conversation-management` branch: "<word> new topic". The window gets that line from
  there, so the list on `next` shows only the commands that work there.

### The installer is called "FT Assistant Installer" (added and built 2026-11-21)

**Built:**
- `installer/build.py` writes `dist/FT-Assistant-Installer.cmd`, plus the same file under its old
  name (`LEGACY_NAMES`), to attach to a release or two. CLAUDE.md's release step uploads both.
- The installer prints "FT Assistant Installer" as its header. The README, the Linux repair
  notice and install.py's help text use the new name.
- A copy of the installer (either name) saved in the chosen folder doesn't count as "other
  files" for the subfolder rule.

The plan as agreed:

**Decided by the user:** the file people download is named for what it is. On the GitHub Releases
page, and everywhere in the project, it's **FT Assistant Installer**.

- **File name:** `FT-Assistant-Installer.cmd`. GitHub turns spaces in uploaded file names into
  dots ("FT.Assistant.Installer.cmd"), so hyphens keep it readable. Release titles and the README
  call it "FT Assistant Installer".
- **Why it helps:** "setup" currently means two things. `FT-Assistant-setup.cmd` is the
  installer, while "FT Assistant setup" (the menu entry, "Assistant setup") is the settings
  screen. After this, "setup" only means the settings screen.
- **What changes:**
  - `installer/build.py` (output name);
  - the README's download and run instructions;
  - text that names the file: the repair notice in the Linux launcher, install.py's help text, and
    the release notes;
  - the release steps in CLAUDE.md (`gh release create ... dist/FT-Assistant-Installer.cmd`).
- **Not affected:** the built-in updater, which downloads the release's source zip, not this file.
- **Moving over:** links to `releases/latest/download/FT-Assistant-setup.cmd` (e.g. in older
  messages to testers) would break. Attach the file under both names for one or two releases,
  then only the new one.
- **Check:** no name clash with the launchers in the install folder (`ft-assistant`,
  `ft-assistant-settings`, `ft-assistant-uninstall`). Windows ignores upper and lower case: that
  was the 0.2.5 bug.

### The running program is called "FT Assistant", not python or pythonw (added and built 2026-11-21)

**Built** (`ft_assistant/procname.py`; `NAMED_PROGRAMS`, `make_named_programs` in install.py):
- **Linux:** each process sets its name at start with prctl:
  - the app: `FT Assistant`;
  - the speech worker: `FT Asst speech`;
  - the setup window: `FT Asst setup`;
  - the voice commands window: `FT Asst help`.

  The full command line is unchanged, so older ways of finding it still work.
- **Windows:** the installer copies the runtime's `pythonw.exe` to `FT Assistant.exe`,
  `FT Assistant speech.exe`, `FT Assistant setup.exe` and `FT Assistant help.exe`. It does this
  at install and at every update.
  - Each copy's version resource is replaced (`UpdateResourceW`) so its description reads
    "FT Assistant ...".
  - The launchers, the engine, the setup window and "help" start these copies, falling back to
    pythonw/sys.executable if a copy is missing.
- **Tested 2026-11-21:**
  - Unit tests: names within Linux's 15-character limit, the same names in the app and the
    installer, the version resource read back, the copies, and the launcher choosing them.
  - Linux, real processes: `pgrep -x` found "FT Asst help", "FT Asst setup" and "FT Asst
    speech".
  - Windows bottle: the four copies exist and Windows reads back their descriptions ("FT
    Assistant", ...). The copy runs Python. The app ran as "FT Assistant.exe", and its setup
    window as "FT Assistant setup.exe" (tasklist).
  - **Not yet on a real Windows PC** (Task Manager's display of the description).
- **Not done (left for later if wanted):** setup's Stop-RunningApp and install.py's
  `is_ft_assistant` still find FT Assistant by path and command line, which keeps working.

The plan as agreed:

**Decided by the user:** in Task Manager, System Monitor, `ps` and similar, the running program shows
as **FT Assistant** instead of `python`, `python3` or `pythonw`. Users and FT Assistant itself (setup,
updates, run-branch.sh) can then find it and close it if needed.

- **Builds on FT Assistant's own Python** (item 1): the names are given to copies inside its own
  runtime folder, never to a Python the user has.
- **Windows:**
  - A program's name comes from its .exe file. Setup copies the runtime's `pythonw.exe` as
    `FT Assistant.exe` in the same folder (next to `python312.dll`, which it needs), and the
    launchers start that.
  - Task Manager's main list shows the file's *description* ("Python"), so the copy's version
    information is changed too (`UpdateResourceW` through ctypes; no extra tools).
  - The speech worker (started per dictation) and the setup window get their own names, e.g.
    `FT Assistant speech.exe` and `FT Assistant settings.exe`, so each one is clear.
  - Setup and the updater can then find FT Assistant by program name, instead of searching
    command lines for `-m ft_assistant` (slow through PowerShell).
- **Linux:**
  - The process name (what `top`, System Monitor, `pgrep` and `pkill` use; 15 characters at
    most) is set at start with `prctl(PR_SET_NAME)`, through ctypes. Names: `ft-assistant`, and
    e.g. `ft-asst-speech` / `ft-asst-setup` for the worker and the setup window.
  - Optionally the launcher also starts Python through a link named `ft-assistant` in the runtime
    folder, so the full command line (`ps -f`) starts with that name too.
- **Then update everything that finds the program:**
  - the restart command in CLAUDE.md (`pkill -f '... -m [f]t_assistant'`);
  - `run-branch.sh`'s process search;
  - setup's `Stop-RunningApp`;
  - `install.py`'s `is_ft_assistant`.

  Keep the old command-line match as a fallback for copies started by older versions.
- **Test:**
  - Linux: `pgrep -x ft-assistant` finds it, and System Monitor shows the name.
  - Windows (bottle, then a real PC): Task Manager shows "FT Assistant", and the speech worker
    and setup window show their own names.
  - Stopping by name stops only FT Assistant.

### Windows: real Start menu shortcuts (found and built 2026-11-21)

- **The problem:** setup put `.cmd` files into the Start menu folder, and a .cmd file in the
  Startup folder for login. The Start menu only lists shortcuts, so FT Assistant didn't show up
  there (a Windows tester couldn't find it).
- **Now:** `write_shortcuts` makes real `.lnk` shortcuts through WScript.Shell, in one PowerShell
  call (values passed as JSON in an environment variable).
  - **The entries:** "FT Assistant", "FT Assistant setup" and "Uninstall FT Assistant" in the
    Start menu, and "FT Assistant" in Startup (when starting at login is on).
  - **Windows:** the shortcuts start the launchers minimized, because the launchers set FT
    Assistant's settings and then start it without a window. Uninstall gets a normal window,
    because it asks a question.
  - **The icon** comes from "FT Assistant.exe".
- **Updates** replace the old .cmd entries (Start menu and Startup), and keep starting at login
  only if it was on (`autostart_enabled` also recognises the old .cmd).
- **If the shortcuts can't be made**, setup writes the old .cmd entries instead and warns.
- **Tested 2026-11-21:**
  - Unit tests: an update replaces the entries, the window styles, the fallback.
  - Windows bottle: a fresh install made all four shortcuts with the right targets and icon.
    Starting "FT Assistant" from its Start menu shortcut ran FT Assistant.exe. The .lnk files
    store "minimized" (7) and "normal" (1) correctly (Wine's own reader reports 1 for all).
  - **Not yet on a real Windows PC** (whether the Start menu lists them; it should, as they're
    standard shortcuts).

### Agent windows opened again after an update (found and fixed 2026-11-21, after 0.3.0)

- **The problem:** after the 0.3.0 update, "Assistant, ..." did nothing while a Claude Code
  window was open: no new window, nothing typed, nothing in the log.
- **Why:** the update restarts FT Assistant from the update window's terminal, so it inherited
  that window's address (`GNOME_TERMINAL_SCREEN`, `GNOME_TERMINAL_SERVICE`). gnome-terminal then
  tried to open each new window next to the closed update window. While any other gnome-terminal
  window was open, it printed "Failed to get screen from object path", opened nothing and still
  exited with 0. Setup's install, update and uninstall windows had the same problem.
- **Fix:** `harness.clean_env` (used for every window FT Assistant opens) also drops the
  variables terminals set for their own window or session (`TERMINAL_SESSION_VARS`: GNOME
  Terminal, Konsole, Tilix, Terminator, kitty, Alacritty, WezTerm, Windows Terminal).
- **Tested:** reproduced with throwaway windows (a terminal open, the stale variables set: no
  window); with the fix the window opens.

### The agent's window is remembered across FT Assistant's restarts (added and built 2026-11-21)

- **Before:** FT Assistant remembered the window it opened for the assistant only in memory. After
  a restart (an update, a crash), "Assistant, ..." opened a second window on the same
  conversation instead of sending to the open one.
- **Now** `agent_windows.py` keeps {assistant: window number} in a small file:
  - **What's in it:** only window numbers and which assistant, with an id for the login session.
    No text, no times.
  - **Where:** Linux: the login session's runtime folder (`/run/user/<uid>/ft-assistant-agent-windows.json`,
    emptied at logout); each build (installed, dev, branch test) has its own. Windows: FT
    Assistant's settings folder.
  - **Only in the same login session:** `login_session()` (Linux: boot id, login session and X
    display; Windows: the logon session's id with the hour the computer started). A file from
    another login is ignored. The file is removed when no window is left.
- **Window numbers get reused** (seen 2026-11-21: gnome-terminal gave a new plain terminal the
  number of the Claude Code window just closed). So a remembered window must still show its
  assistant's title (Claude Code "✳ ...", OpenCode "OC | ...") before anything is typed into it.
  The same now holds without a restart: once a window has shown its assistant's title, it must
  keep it (`App.titled`). Before, a closed window's number reused by a plain terminal would
  have got the request typed into the shell. A just-opened window still counts before its
  title is set.
- **Never a window FT Assistant didn't open:** a Claude Code window from another project has the
  same kind of title, so windows aren't picked by title alone.
- **Tested 2026-11-21:**
  - Unit tests: saving and loading, another login ignored, a damaged file, a reused number not
    typed into (sending and focus), a new window before its title.
  - Throwaway windows on Linux: found after a simulated restart. A plain terminal that got the
    closed window's number was not used, and the entry was forgotten.
  - **Not yet:** a real update with an open Claude Code window. Windows: whether Claude Code sets
    the console title there (if not, a restart opens a new window as before).

### Setup screen: less on it; explanations go to the voice commands window (added and built 2026-11-23)

**The user's direction (2026-11-23):** the setup screen should get shorter, not keep growing. New
features don't add settings or explanations to it. Descriptions go into the window that lists the
voice commands (opened by "<word> help" or the "Voice commands..." button).

**Built as proposed (the user approved it, 2026-11-23):**
- **Moves to the voice commands window**, as short notes under the list:
  - the privacy note (normal dictation stays on this computer; requests go to the assistant's
    online service);
  - "Say "<word>, ..." and a request..." under the command word;
  - "To open this screen again, hold <key> and say "<word> setup"" (the list already has it).
- **Shown only while choosing a key:** "Good choices" and "Best avoided" appear after "Change
  key" is pressed, and go away once a key is chosen.
- **Stays on the setup screen:** the assistant choice with Install..., the Assistant key, the
  command word (with its error or warning, when there is one), "Voice commands...", updates and
  uninstall, the version, Save and Cancel.
- **The voice commands window** keeps its short list (at most about 7 commands) and gets a "Good
  to know" part under it for these notes. Each note is one sentence (a test checks it).
- **Under the command word,** a line appears only for a problem with the word, or for the "try it
  a few times" tip once it's changed. The key and word messages take no space when empty.

**Text a little bigger, for poor eyesight (the user's request, 2026-11-23):**
- **A reading boost:** both windows' text is 20 % bigger than the desktop's normal text
  (`look.READING_BOOST`). On the user's desktop (Ubuntu 10): 12 pt.
- **Large-text settings are honoured further:** the limit went from 18 to 28 points, so a desktop
  set to large text isn't cut back.
- **Windows' "Text size" setting** (Settings > Accessibility) is followed, besides display
  scaling: `HKCU\Software\Microsoft\Accessibility\TextScaleFactor`. Windows may already have
  enlarged its interface font for it, so the larger of the two is used, never both.
- **Considered and set aside:** sizing by a share of the screen (unpredictable: huge on big
  monitors) and Ctrl +/- zoom (hidden, so those who need it wouldn't find it).
- **Small screens** still work as before: the text shrinks to at most 85 % before scrolling.
- **Not yet checked on a real Windows PC** (the bottle has no Text size setting).

### A notice when the assistant window doesn't open (added and built 2026-11-23)

- **The problem:** when the agent's window failed to open (the 0.3.0 bug, fixed in 0.3.1),
  nothing happened and nothing said why.
- **Now:** after "<word>, ..." opens a window, FT Assistant watches for it as before
  (`OPENED_WINDOW_WAIT`, 8 s). If nothing started, it shows "Couldn't open Claude Code's window."
  (or OpenCode's) and writes one error line to the log, with the assistant's name only, never
  the request.
- **"Nothing started" means all three** (`App._agent_started`), so there are no false alarms:
  - no new terminal window;
  - no new process in the sessions folder (Linux, `processes_in`): some terminals open the
    agent as a tab in a window that's already open;
  - the started process has exited (Windows: it's the agent itself; xterm and the like: the
    terminal, which stays running).
- **No setting, nothing to read:** the user only sees it when something is broken.
- **Tested 2026-11-23:** unit tests (nothing started; a new window; a new tab; still running;
  Windows without process info), and on Linux with throwaway terminals: the 0.3.0 bug recreated
  showed the notice; a normal launch didn't.
- **Not yet on a real Windows PC.**

### "<word> undo": remove what was just typed (added and built 2026-11-23)

- **What it does:** removes the dictation FT Assistant typed last, for when Whisper mishears. It
  was the "scratch that" candidate from the voice commands plan, under a shorter name. It works
  in "Dictation only" too.
- **Only when it's safe:** the same window still has focus, and the user hasn't pressed a key
  or clicked since (the wheel doesn't count). Otherwise nothing is deleted and a notice says
  why ("Nothing to undo." / "Nothing was undone: you've typed or clicked since."). It undoes
  once; any other voice command in between also cancels it.
- **Not in an assistant's window after "<word>, ...":** only plain dictation can be undone;
  a request has already been sent with Enter.
- **What's kept, in memory only:** the window, the length of the last dictation (never its
  text) and a count of the user's key presses and clicks (`plat.input_count()`, never which
  keys). Nothing is saved or logged.
- **How presses and clicks are counted:**
  - Linux: the Assistant key's XRecord listener now records every key and button. FT
    Assistant's own typing (xdotool) looks like the user's to X, so presses are ignored while
    it types and for 0.3 s after (`SYNTH_GRACE`).
  - Windows: both low-level hooks (keyboard and mouse) are installed; the one that isn't for
    the Assistant key only counts and never swallows anything. Injected input (FT Assistant's
    own typing) is ignored by its flag.
- **Removing:** Backspace as many times as characters were typed (`press_backspace`).
- **The voice commands list** has 6 commands now (still under 7).
- **Tested 2026-11-23:** unit tests (undo right after; not after a press or click; not in another
  window; only once; not after another command; nothing typed yet; only the length kept), and
  on Linux in a throwaway text window: FT Assistant's own typing and Backspace weren't counted,
  a key press after them was, and undo removed exactly the last dictation.
- **Not yet:** a live dictation test, and a real Windows PC (the second hook; if Windows ever
  dropped it, counting would stop, so this needs a check there).

## On the `conversation-management` branch

Built after the work on `next`, on a branch made from `next`; never merged until the user says so.

### Conversation management (added 2026-11-21)

**The problem:** "Assistant, ..." always continues the one ongoing conversation (decision 6 under
the "Assistant" keyword). That avoids a pile of one-request conversations, but unrelated topics mix
in one context. The agent can't tell which earlier parts matter. The conversation keeps growing,
so answers get slower and use more tokens.

**Considered and set aside: sorting conversations in the background.** The user's first idea was
this: after about 5 minutes of inactivity, split the running conversation by topic, move each part
into an existing conversation on that topic (or a new one), and then compress what's left. Not
recommended:

- **Writing into conversations isn't supported.** Claude Code's JSONL files and OpenCode's
  database are internal formats that change between versions.
  - The only safe way to add something to a conversation is to resume it and send a message.
    That costs a full round of tokens per topic and leaves injected text in it.
- **The sorting itself costs tokens every idle period**, which can cancel out the savings.
- **Mistakes would be silent.** A part filed under the wrong topic only shows up later as a
  strange answer.
- **It clashes with open windows.** A conversation may still be open, or the agent may still be
  working.
- **Compressing is already built in:** Claude Code's `/compact` and auto-compact, and OpenCode's
  compaction.

**Proposed instead (same goals, sturdier):**

0. **"<word> new topic"** (optionally followed by a request) starts a fresh conversation, then
   sends the request if there is one. It's one of the voice commands (see "Voice commands" under
   `next`), but built on this branch.

1. **A new conversation after a quiet gap.**
   - If the last activity in the ongoing conversation is older than the gap, "Assistant, ..."
     starts a new conversation instead of continuing it. Suggested default gap: 15 minutes; set
     on the setup screen (Off / 15 / 30 / 60 minutes).
   - "Last activity" is the newest write to the conversation: Claude Code's newest `.jsonl` file
     time; OpenCode's `session.time_updated`.
     - That includes the agent's own work, so a long-running task doesn't count as quiet.
     - Read with the code that already finds the last conversation
       (`harness.last_conversation`).
   - **Dictating inside an assistant's window always goes to that conversation**, as now. The gap
     only applies to "Assistant, ..." from elsewhere.
   - **If the old conversation's window is still open:** open a new window (old one stays), or
     start the new conversation in that window by sending `/clear` (Claude Code) or `/new`
     (OpenCode). Open question for the user.
   - **Overriding by voice:** "<word> new topic" starts fresh at any time (see "Voice
     commands" under `next`). A phrase to continue anyway after the gap is held back, because
     "Assistant, continue ..." clashes with requests that really start with "continue".
   - Small change; fixes the mixing and the growth at no extra cost. Could ship on its own.
2. **Topic notes with an index, kept by the agent.**
   - FT Assistant creates, in `~/FT Assistant sessions/`:
     - an instruction file, `CLAUDE.md` for Claude Code and `AGENTS.md` for OpenCode, with the
       same text. Both programs load it automatically at the start of every conversation.
     - a `notes/` folder with `notes/INDEX.md`.
   - Created only if missing; never overwrites the user's edits (e.g. a version marker in the
     file).
   - **The instruction file tells the agent to:**
     - read `notes/INDEX.md` at the start;
     - open a note when the request matches an index line;
     - write or update a short note when it finishes something worth keeping, with one
       descriptive index line per note ("Windows OpenCode launch: what broke and how it was
       fixed");
     - search old conversations only when the user clearly refers to earlier work ("what we did
       yesterday") and no note covers it.
   - **Sorting happens when a note is written**, while the agent already understands the topic,
     so there are no extra background AI calls.
   - **How a new conversation knows to look:** the index is in its context from the start (a few
     dozen lines, few tokens). Matching a request against it is ordinary AI judgment. Full notes
     are read only when something matches.
   - Same mechanism as Claude Code's own auto memory (a `MEMORY.md` index plus files). A shared
     notes folder works the same for both harnesses and survives switching between them.
   - **Where it can miss:**
     - Indirect connections, if an index line is worded too narrowly.
     - Work that never got a note.
     - Remedy: the user says "check your notes" or "look at earlier conversations".
3. **Dropped 2026-11-23 (keep it simple): a hint from FT Assistant, at no AI cost.** The agent
   already has the notes index in its context, so this would add code for little gain.
   - Before handing over the request, compare its words with the index titles.
   - On an obvious overlap, append "(possibly related note: <title>)".
   - A plain word match in memory; nothing is logged or stored.

**Privacy:** topic notes are a new store of what the user asks about (written by the agent in the
sessions folder, not FT Assistant's log). It must be clearly explained and kept in one folder the
user can see, edit and delete. The user chose on by default (2026-11-23, see below). The gap rule (1) stores nothing new.

**Testing:**
- Only with a throwaway sessions folder, never the user's real `~/FT Assistant sessions` or its
  conversations (`config.sessions_dir()` needs an override for this, like
  `FT_ASSISTANT_CONFIG_DIR`).
- Tested on Linux with both harnesses, then in the Windows test bottle.

**Decided by the user (2026-11-23):**
- **It works out of the box:** the quiet gap and topic notes are on by default.
- **No new settings on the setup screen.** How these work is explained in the voice commands
  window instead (see "Setup screen: less on it" under `next`). This replaces the setup-screen
  choices above (Off / 15 / 30 / 60 minutes, "Keep topic notes").

**Proposed defaults (the user didn't pick these; change if they say so):**
- **Gap: 15 minutes, fixed.** Kept in `settings.json` for testing, with no control on the setup
  screen.
- **If the old window is still open:** the new conversation starts in it (`/clear` for Claude
  Code, `/new` for OpenCode), so there's still one assistant window. The old conversation stays
  saved.
- **Release order:** "<word> new topic" and the quiet gap first (they store nothing new), topic
  notes in a later release.

**Still open:**
- **Turning topic notes off** without a setup-screen setting: deleting the notes folder, a
  voice command, or only `settings.json`.
- **The privacy explanation for topic notes,** since they're on by default: it goes in the voice
  commands window and the release notes. Existing users get a notice when they update.

## Open questions

- How setup installs the harness CLIs: the npm packages measured above need Node.js; the official
  standalone installers may avoid that. Technical, to settle while building.

## Technical notes for building

- **Keyword matching** (tested with synthetic speech through the real Whisper worker): Whisper
  writes "Assistant," / "Assistant" / "Assistant Setup" (capitalized, sometimes a comma) and
  leaves "The assistant said…" alone. Compare the first word case-insensitively and ignore
  punctuation right after it; match "assistant setup" the same way.
- **Starting the CLIs** (both live-tested in throwaway folders): `claude "<text>"` and
  `opencode <folder> --prompt "<text>"` open an interactive session and **send the message by
  themselves**. Launch with a **clean environment** (drop inherited `CLAUDE*`/`ANTHROPIC*`
  variables; inherited ones turned off Claude Code's transcript saving and terminal titles).
- **Claude Code first run** shows one-time screens (text style, security notes, folder trust) and
  needs sign-in with the user's Claude account; setup should tell users to expect this.
  **Auto mode** is its default permission mode.
- **Knowing you're "already in" a harness:** the tool remembers the terminal windows it opened;
  for ones the user opened by hand it falls back to titles: Claude Code `✳ <conversation name>`
  (seen when idle; may change while working), OpenCode `OC | <session title>`.
  Windows: use the focused window's program/title instead.
- **Caps Lock as the Assistant key:** it must never be left on. Preferably the key press is
  swallowed so caps never toggles; otherwise the tool resets it after each use. Ignore the key's
  auto-repeat while held. (The user's current trigger, mouse button 12, isn't available on
  Windows; they can capture it again in setup on Linux.)
- **Still unverified:** everything on Windows (needs a Windows machine).

## Windows (phase 5, 2026-11-18)

**Built:** `ft_assistant/platform_windows.py` (standard library only): the Assistant key through
low-level keyboard/mouse hooks that **swallow** the key (it never reaches other programs; Caps
Lock never toggles), typing with `SendInput` (Unicode, Enter for new lines), focused-window and
terminal detection (Windows Terminal, console), toasts through Windows PowerShell, key capture,
single-instance lock. `ft_assistant/plat.py` picks the Linux or Windows layer. Agents open in
a new console window (Windows Terminal when it's the default terminal); never through `wt.exe`,
which re-parses the command line and broke folder names with spaces (0.2.7). The installer registers FT Assistant under
Settings -> Apps and finishes deleting itself after uninstall exits.

**Decided by the user (2026-11-18):**
- **No recording cap.** Recordings last as long as the key is held; a stuck recording is a
  key-detection bug to fix, not something to cap.
- **Progress everywhere:** numbered setup steps ("Step 3 of 6"), progress bars for every download
  (the model is downloaded directly so its bar shows), a countdown while capturing a key; the user
  is never left looking at a blank window.

**Found and fixed in the Bottles bottle:**
- cuBLAS 12.9.3.13 has no Windows build; Windows uses 12.9.2.10.
- Wine breaks the model downloader's symlinks, so models are always stored as **plain files** in
  `models/<name>` (downloaded with `local_dir`, or hard-linked from an existing copy).
- The small model sometimes dropped a leading "Assistant"; the large one too (1 in 14). Whisper
  now always gets **"Assistant, Assistant setup"** as hint words before the user's vocabulary:
  14/14 on both.
- Wine sends its own Num Lock presses around every key (to sync lock states), so key capture saw
  "Num_Lock". Capture now skips those (first non-lock key wins; else the lock key pressed an odd
  number of times). Choosing Num Lock shows a warning.
- A "key still held?" check with `GetAsyncKeyState` was wrong: a swallowed key never updates that
  state. Removed; releases come only from the key-up messages (reliable in every clean test).
- Changing the Assistant key no longer restarts the app: the listener is stopped and a new one
  started in place (Linux and Windows).
- **Testing lesson:** each `bottles-cli run` is its own Wine session; several at once crashed the
  bottle and kept keys from reaching the app (rule added to CLAUDE.md).

**Verified in the bottle (one Wine session, user at the keyboard):** setup file (steps, progress
bars), first-run setup, key capture (Scroll Lock), in-place key switch, two dictations typed into
Notepad (~1.5 s on the CPU with small.en), "Assistant setup" reopening the screen.
**Linux recheck after phase 5 (2026-11-18):** fresh install into a throwaway folder: all six
steps shown, Python 3.12.3 and the existing model reused (plain hard-linked files, no extra disk),
GPU transcription kept "Assistant", the installed copy handled key presses (Pause) and released
everything, uninstall stopped it and removed it; the live tool's model was untouched.
**Not verifiable in Wine:** the NVIDIA/CUDA path, Windows toasts, Windows Terminal, the Startup
folder entry and Settings -> Apps; these need one pass on a real Windows PC before release.

## Why `.cmd` (format comparison, 2026-11-17)

No file type double-click-runs on both systems. On Linux a downloaded file is never executable
until allowed, so Linux always needs `bash <file>` or a "make executable" click. Windows decides:
- `.cmd`: double-click runs on every Windows, no settings. It hands off at once to PowerShell
  (built into Windows 10/11) for downloads. **Chosen.**
- `.bat`: same as `.cmd`, older name. `.ps1`: double-click opens Notepad and unsigned scripts are
  blocked. `.py`: no Python on a fresh Windows. `.sh`: Windows can't run it. A Cosmopolitan
  "actually portable" executable: exotic, larger, often flagged by antivirus.

## History: the desktop-app route (superseded 2026-11-17)

- **Claude desktop app:** `claude://code/new?q=<text>` opened a new no-folder Code session with
  the text filled in; pressing Enter sent it (live-tested). Not needed since the switch to CLIs.
- **OpenCode desktop app (1.19.6):** `opencode://new-session?directory=…&prompt=…` only works in
  the old layout; the new layout has no outside way to start a session in a chosen folder, its
  Ctrl+Shift+S shortcut uses the last-used project (rejected by the user: never send into an
  unrelated project), and its local server needs a per-launch password. A feature request is
  drafted in `docs/opencode-feature-request.md` for the user to post.
