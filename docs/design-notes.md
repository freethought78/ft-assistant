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
   **desktop app** and types the command there, so the user can see the agent working:
   - Claude Code → the **Claude desktop app**.
   - OpenCode → the **OpenCode desktop app**.

   No hidden or headless agent runs, ever.
5. **Routing depends on the focused window:**
   - **Already typing in a harness app** (Claude or OpenCode, **even if it's not the chosen one**)
     → strip "Assistant" from the start and type the rest into the current conversation.
     No new session.
   - **Anywhere else** → open a **new session** in the chosen harness's app and enter the
     rest of the dictation as the command.
6. **New sessions have no project folder.** Same as starting a fresh Claude Code session
   with no folder. If the user wants it to become a project, they say so in that session;
   the tool needs no special handling for that.
   - **"Assistant" with nothing after it** → open the chosen harness's app with a new, empty
     session, ready for the user. (If already in a harness app: nothing to type, so nothing happens.)
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

None right now. (Install itself is covered by the setup script section below.)

### To verify before building (technical, not user decisions)

- How to start a new session and enter a prompt in the **Claude desktop app** from outside it
  (launch or raise its window, new-session action, type the prompt).
- The same for the **OpenCode desktop app** (`ai.opencode.desktop` / `opencode-desktop`, both
  installed on this machine).
- How to tell which app has focus (X11 active window's `WM_CLASS`).
- Keyword matching: case and punctuation Whisper adds ("Assistant,", "Assistant.").
- Settings file location. Plan: `~/.config/ft-assistant/` on Linux, `%APPDATA%\FT Assistant\`
  on Windows (chosen harness, Assistant key).

## Feature: distribution as one small setup script

### Decided

1. **One setup script for both Windows and Linux.** A single file, not one per platform.
   Harder to build and test, but there's only one thing to distribute and maintain.
2. **The script stays small; everything else is downloaded.** No bundled "big package" option.
   The project itself can grow as large as it needs to; only the thing you hand out stays small.
3. **From zero:** on first run the script shows the setup screen (harness choice), then installs
   whatever is missing: Python runtime, speech engine, GPU libraries if there's an NVIDIA card,
   the Whisper model, and the chosen harness's desktop app (with the user's consent).
4. **Hardware detection:** setup checks for an NVIDIA GPU and picks the GPU path with
   large-v3-turbo, or a CPU path with a smaller model.

5. **One polyglot file: `FT-Assistant-setup.cmd`.** Windows (`cmd`) and Linux (`bash`) can
   both read it; each skips the other's part, installs a Python runtime, then both run the
   same shared Python setup program, which can be embedded in the same file.
   Windows: double-click. Linux: `bash FT-Assistant-setup.cmd` (dashes, so no quotes needed).
6. **The setup script is the installer.** There's no separate installer for new users.
7. **Clean install flow** (first install, or reinstall with no trace of the tool or its stack):
   1. Tell the user to **wait a moment while requirements are checked** (OS, NVIDIA GPU or not,
      what's already installed, e.g. a harness app).
   2. **Show the approximate total download size** of the components still needed, with a short
      breakdown (Python runtime, speech engine, GPU libraries, Whisper model, harness app if chosen),
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

None right now.
