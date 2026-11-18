# Design notes: the redesign (`next` branch)

Living document. Decisions agreed with the user are recorded here as the design is refined.
Nothing in it is built yet. Implementation starts only when the user says the design is ready.

Last updated: 2026-11-17

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
   - Claude Code → `claude` (the Claude Code CLI) in a terminal window.
   - OpenCode → `opencode` (the OpenCode CLI) in a terminal window.

   Changed 2026-11-17 (was: desktop apps). Reasons: OpenCode's desktop app can't be pointed at a
   folder from outside, and the user prefers one consistent approach. Both CLIs are full agents
   that **can make changes on the host system** (edit files anywhere they're allowed, run shell
   commands), asking for permission as configured. No hidden or headless agent runs, ever.
5. **Routing depends on the focused window:**
   - **Already typing in a harness terminal** (Claude Code or OpenCode, **even if it's not the chosen one**)
     → strip "Assistant" from the start and type the rest into the current conversation.
     No new session.
   - **Anywhere else** → open a **new session** in the chosen harness's app and enter the
     rest of the dictation as the command.
6. **New sessions start in a neutral folder, not a project.** A CLI always runs in some folder,
   so both harnesses start in a dedicated `FT Assistant sessions` folder in the user's home
   (decided 2026-11-17). Agents can still reach the rest of the system when asked; it's only
   their starting point. Never an unrelated existing project. If the user wants it to become a project, they say so in that session;
   the tool needs no special handling for that.
   - **"Assistant" with nothing after it** → open the chosen harness in a new terminal window
     with an empty session, ready for the user. (If already in a harness terminal: nothing to
     type, so nothing happens.)
7. **"Assistant setup"** opens a small configuration screen:
   - It appears automatically the **first time the software is installed**, so a harness is
     always chosen before the keyword is used.
   - Saying "Assistant setup" reopens it any time.
   - **The screen itself tells the user how to get back to it,** using the key they actually
     have, e.g. "To open this screen again, hold Caps Lock and say 'Assistant setup'."
     That key is called the **Assistant key** in the UI and docs.
   - **Built with Tkinter:** it comes with Python (no extra download) and works the same on
     Windows and Linux. Plain but clean look.
   - The user picks **OpenCode** (free) or **Claude Code** (with a subscription, or by preference).
   - If the chosen harness isn't installed, the screen tells the user and helps them install it.
     **Nothing is downloaded automatically** outside this screen.
   - **Reassign the Assistant key:** a button on the screen starts capture; the next key press
     or mouse button press becomes the Assistant key. Easy to change again at any time.
     - **Default for a new install: Caps Lock** (every keyboard has it, on both systems).
     - **Any keyboard key** is allowed.
     - **Any extra mouse button** is allowed (side buttons, Fn buttons, etc.).
     - **Left, right and middle click are refused**, with a short message saying why.
     - **The scroll wheel is refused too** (wheel up/down and tilt left/right).
     - **The screen gives guidance** next to the capture button (draft wording, to refine):
       - *Good choices:* Caps Lock, Scroll Lock, Pause, Insert, the Menu key, F13–F24 if your
         keyboard has them, or a spare side button on your mouse. Pick one you can hold
         comfortably while speaking.
       - *Best avoided:* letters, numbers, Space, Enter, Tab, Backspace and arrows (you need them
         to type); Shift, Ctrl, Alt and the Windows/Super key (used in shortcuts); Esc and
         Print Screen (other programs use them).
       - Choosing a "best avoided" key shows a short warning and asks to confirm; it's still allowed.
8. **Only two harnesses for now: Claude Code and OpenCode.** OpenCode is the free option for users
   who can't or don't want to pay for Claude Code. Considered and set aside for now (2026-11-17):
   Google Antigravity (free plan with weekly limits) and Kilo Desktop (beta). Gemini CLI and
   Qwen Code no longer have free tiers. Adding more later should stay possible.

### Open questions

- **Already in a harness terminal, saying "Assistant, …":** type and also send (press Enter),
  or type only? (Asked 2026-11-17, not yet answered.)
- **Permission prompts by voice:** both CLIs ask before risky actions (a menu you answer with
  keys). Should the user be able to answer those by voice, or by keyboard only?
- **Which terminal window** to open on each system (Linux: the system's default terminal;
  Windows: Windows Terminal if present, else PowerShell's console).

### Technical findings (checked 2026-11-17 on Linux)

The desktop-app findings below are kept for the record; since the switch to CLIs (decision 4)
only the OpenCode CLI, focus detection and keyword results apply directly.

- **Claude desktop app (v45.2.1): works end to end (live-tested).**
  `claude-desktop "claude://code/new?q=<text>"` (`prompt=` also works; capped at 14,336
  characters) opens a new Claude Code session with the text **filled in but not sent**.
  The tool then presses **Enter** once the Claude window is in front (~4 s in the test), and the
  session runs with **no folder** (listed under "This computer"), matching decision 6.
  The app registers the `claude://` link type, so the same link should work on Windows.
- **OpenCode desktop app (1.18.x, and 1.19.6 after updating on 2026-11-17, live-retested):
  the link is ignored in its "New layout".** `opencode://new-session?directory=<folder>&prompt=<text>` reaches the app
  (its log says "deep link received"), but only the **old layout** acts on it. The user has
  OpenCode's **"New layout"** switched on (Settings → General), which OpenCode describes as
  switchable "for a limited time", so the old layout, and with it the link, will likely go away.
  The local server needs a login token (401), so that's no route either.
- **OpenCode keyboard route (live-tested):** with the OpenCode window in front, **Ctrl+Shift+S**
  opens a "New session" tab with the message box ready. Typing the command and pressing Enter
  would send it. Catch: the session goes to **OpenCode's last-used project** (in the test,
  "kit biz"), not the neutral `FT Assistant sessions` folder. **The user rejected this as is
  (2026-11-17): Assistant commands must never land in an unrelated project.** Only usable if the
  session can be pointed at the neutral folder first. In the test nothing was typed or sent;
  only an empty "New session" tab was opened.
- **Telling which app you're typing in** works via the focused window's `WM_CLASS`:
  Claude = `com.anthropic.Claude`, OpenCode desktop = `ai.opencode.desktop`. OpenCode in a
  terminal: the terminal's window title starts with `OC | `. (Windows: the focused
  window's program name instead.)
- **Keyword matching**, tested by feeding synthetic speech through the real Whisper worker:
  Whisper writes "Assistant," / "Assistant" / "Assistant Setup" (capitalized, sometimes a comma)
  and leaves "The assistant said…" alone. So: compare the first word case-insensitively, ignore
  punctuation right after it, and match "assistant setup" the same way.
- **Settings file location** (plan): `~/.config/ft-assistant/` on Linux,
  `%APPDATA%\FT Assistant\` on Windows (chosen harness, Assistant key).

### OpenCode route (settled 2026-11-17)

Code reading of OpenCode desktop 1.19.6:
- The **new layout has no outside way to start a session in a chosen folder**: no link
  handling, no "open project" command, and its new-session shortcut copies the folder of
  whatever tab is open (else the most recent project). Its local server uses a random
  password per launch that isn't stored anywhere readable.
- **Old layout + link** (`opencode://new-session?directory=…&prompt=…`) handles folder and text,
  but needs "New layout" switched off and will likely break when OpenCode retires the old
  layout. Not used.
- **Chosen: OpenCode's interface in a terminal window.** `opencode <folder> --prompt "<text>"`
  (CLI updated to 1.19.6). Live-tested in a throwaway folder: it opened in that folder and
  **sent the message by itself** (replied "OK"). The window title reads `OC | <session title>`.
- A feature request asking OpenCode to support the link in the new layout is drafted in
  `docs/opencode-feature-request.md` for the user to post. If OpenCode adds it, revisit.

### Verification status (after the switch to CLIs)

- **OpenCode CLI:** verified. `opencode <folder> --prompt "<text>"` opens visibly in that folder
  and sends the message. Installed size 412 MB (npm package `opencode-ai` 1.19.6, measured).
- **Claude Code CLI:** verified (installed 2026-11-17 with npm, `@anthropic-ai/claude-code`
  2.1.327, 356 MB; the user signed in with their Pro plan). `claude "<text>"` started in a
  throwaway folder opened an interactive session and **sent the message by itself** (replied "OK").
  Notes for building and setup:
  - **First run shows one-time setup screens** (text style, security notes, folder trust).
    The user must go through them once; setup should tell new users to expect this.
  - **Auto mode is now Claude Code's default permission mode:** it handles low-risk actions
    itself and only asks about risky ones, which keeps permission prompts rare.
  - Launch it with a clean environment: started from inside another Claude session it inherited
    a "child session" marker and turned off transcript saving.
  - Still to check: what the terminal title shows (for "already in Claude" detection).
- **Typing into an already-open conversation:** plain typing works in terminals today.
- **The Windows side:** needs a Windows machine.

## Feature: distribution as one small setup script

### Decided

1. **One setup script for both Windows and Linux.** A single file, not one per platform.
   Harder to build and test, but there's only one thing to distribute and maintain.
2. **The script stays small; everything else is downloaded.** No bundled "big package" option.
   The project itself can grow as large as it needs to; only the thing you hand out stays small.
3. **From zero:** on first run the script shows the setup screen (harness choice), then installs
   whatever is missing: Python runtime, speech engine, GPU libraries if there's an NVIDIA card,
   the Whisper model, and the chosen harness's CLI (with the user's consent).
4. **Hardware detection:** setup checks for an NVIDIA GPU and picks the GPU path with
   large-v3-turbo, or a CPU path with a smaller model.

5. **One polyglot file: `FT-Assistant-setup.cmd`.** Windows (`cmd`) and Linux (`bash`) can
   both read it; each skips the other's part, installs a Python runtime, then both run the
   same shared Python setup program, which can be embedded in the same file.
   Windows: double-click. Linux: `bash FT-Assistant-setup.cmd` (dashes, so no quotes needed).
6. **The setup script is the installer.** There's no separate installer for new users.
7. **Clean install flow** (first install, or reinstall with no trace of the tool or its stack):
   1. Tell the user to **wait a moment while requirements are checked** (OS, NVIDIA GPU or not,
      what's already installed, e.g. a harness CLI).
   2. **Show the approximate total download size** of the components still needed, with a short
      breakdown (Python runtime, speech engine, GPU libraries, Whisper model, harness CLI if needed),
      and the disk space needed, **before anything big is downloaded**.
   3. Only then download and finish setup. When some components already exist, the summary
      shows only what's still missing.

### Measured sizes (current Linux install, 2026-11-17)

- Tool's own code: 24 KB.
- Python packages without GPU libraries: ~350 MB on disk (~100–150 MB download, estimated).
- NVIDIA libraries (cuBLAS, cuDNN, NVRTC): 2.1 GB on disk (~1–1.5 GB download, estimated).
- Model large-v3-turbo: 1.6 GB. Smaller models: ~150–500 MB.
- Totals: ~3–3.5 GB download with an NVIDIA card, ~0.3–0.7 GB without one.

### Format comparison (2026-11-17, why `.cmd`)

No file type double-click-runs on both systems. On Linux, a downloaded file is never
executable until allowed, so Linux always needs `bash <file>` or a "make executable" click,
whatever the extension. Windows decides:
- `.cmd`: double-click runs on every Windows, no settings. Cmd is only the doorway:
  it hands off at once to PowerShell (built into Windows 10/11) for downloads. **Chosen.**
- `.bat`: same as `.cmd`, older name.
- `.ps1`: double-click opens Notepad; execution policy blocks unsigned scripts; not on Linux.
- `.py`: Windows has no Python by default, so it fails "from zero".
- `.sh`: Windows can't run it.
- One "actually portable" executable (Cosmopolitan) that runs on both: exotic, larger,
  needs a `.exe` name on Windows, and antivirus tools tend to flag it.

### Caps Lock as the Assistant key (implementation notes)

Caps Lock is the default (mouse button 12, the user's current trigger, isn't usable on Windows;
the user can reassign theirs). Caps Lock must never be left on after dictating: preferably the
key press is swallowed so caps never toggles; otherwise the tool resets it after each use.
Hold-to-talk also has to ignore the key's auto-repeat.

### Install, updates, uninstall (decided 2026-11-17)

1. **Install location:** the installer suggests one and the user can change it before
   installing. Suggested defaults are per-user, so no admin rights are needed:
   - Linux: `~/.local/share/ft-assistant/`
   - Windows: `%LOCALAPPDATA%\FT Assistant\`
2. **Start at login** (plan): Linux `~/.config/autostart/` entry; Windows a shortcut in the
   user's Startup folder.
3. **Built-in update check** against the project's latest **GitHub Release** (the project will
   live on GitHub; no repo there yet). This is the only thing that goes online outside setup;
   it sends no user data.
4. **Uninstall**, reachable from:
   - the **setup screen** ("Uninstall" button), on both systems;
   - **Windows:** Settings → Apps (registered per-user, so no admin needed);
   - **Linux:** an "Uninstall FT Assistant" entry in the app menu.

   It removes the tool, its Python runtime, the speech engine, GPU libraries, the Whisper model,
   the login entry and app-menu entries. Draft details: a "keep my settings" checkbox, and it
   **leaves the Claude and OpenCode apps installed** (they're separate programs the user may still
   want), saying so.

5. **Updates are never installed without asking.** (Detailed 2026-11-17.)
   - **How:** one request to GitHub's public "latest release" API for the project's repo (no
     account, no user data). Compare its version with the installed one; if newer, read that
     release's notes for "what's new". Offline or no answer → give up silently, retry next time.
   - **When:** about a minute after the tool starts (normally just after login), then at most once
     every 24 hours while running. **Never during a dictation** (waits until the Assistant key is
     released). Also on demand via a **"Check for updates"** button on the setup screen.
   - **How the user is told:** a normal **system notification** (Linux notification bubble,
     Windows toast), e.g. "FT Assistant 1.3 is available". **No pop-up window and no focus
     stealing** (the user may be typing or playing a game).
     - Clicking the notification, or saying "Assistant setup", opens the setup screen showing the
       new version, what's new, and **Update now** / **Not now**.
     - **Not now** → quiet about that version for a few days, then one more reminder.
       A newer release resets this.
   - **Nothing is downloaded until "Update now".** Updating backs up the current version so it
     can be rolled back.

8. **On a clean machine the size summary is plain text, before any download** (decided
   2026-11-17). The setup script's own console window shows "checking requirements", then the
   size summary, and waits for the user to continue (e.g. press Enter) or cancel. Nothing is
   downloaded until they continue, not even Python. The setup window opens afterwards.
   - Implementation notes: the requirement check (OS, NVIDIA GPU, what's installed) runs in the
     script's Windows and Linux parts, before Python exists. Sizes come from a tiny manifest on
     the GitHub release (a few KB), or built-in estimates if offline.

### Open questions

- **Already in a harness terminal, saying "Assistant, …":** type and also send (press Enter),
  or type only? (Asked 2026-11-17, not yet answered.)
- **Permission prompts by voice:** both CLIs ask before risky actions (a menu you answer with
  keys). Should the user be able to answer those by voice, or by keyboard only?
- **Which terminal window** to open on each system (Linux: the system's default terminal;
  Windows: Windows Terminal if present, else PowerShell's console).
