# Design notes: the redesign (`next` branch)

Living document. Decisions agreed with the user are recorded here as the design is refined.
Nothing in it is built yet. Implementation starts only when the user says the design is ready.

Last updated: 2026-11-17 (full review and cleanup)

## Releases

- **v0.1.0** (2026-11-18): first release; the user switched their daily tool to it the same day
  (installed from the release's setup file, reusing Python and the model; Assistant key mouse
  button 12). The old tool is kept for rollback.
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
  `~/.cache/huggingface/hub`) or the earlier voice-dictation tool, and **hard-linked** (no extra
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
   supported yet. Wayland can come later (it needs a different key-capture and typing method).
4. **Windows testing happens in Bottles** (Wine), reusing the user's existing test bottle
   **`DannyRando-Test`** (Flatpak Bottles, win64, soda runner) instead of creating new ones.
   Never touch the user's other bottles (games and apps). Wine isn't real Windows, so some things can only
   be partly checked there: the NVIDIA/CUDA path, Windows Terminal, toast notifications, the
   Startup folder and "Settings → Apps" registration. Those need a real Windows machine before a
   public release.

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
Windows Terminal (`wt`), else a new console. The installer registers FT Assistant under
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
