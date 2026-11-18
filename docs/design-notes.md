# Design notes: the redesign (`next` branch)

Living document. Decisions agreed with the user are recorded here as the design is refined.
Nothing in it is built yet. Implementation starts only when the user says the design is ready.

Last updated: 2026-11-17 (full review and cleanup)

## Carried over from the current tool (unchanged)

- **Push-to-talk:** hold the Assistant key, speak, release; local Whisper transcribes.
- **Free all resources when idle:** the speech engine and the tool's own mic stream are released
  right after each dictation (~1 s cold start is fine).
- **Never mute, disable or reconfigure the system microphone;** only the tool's own input stream
  is opened and closed.
- **Privacy:** audio stays in memory only, never on disk. The Whisper model runs offline.
  **Transcribed text is never logged.**
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

1. **Install location:** suggested, and changeable before installing. Per-user, no admin rights:
   Linux `~/.local/share/ft-assistant/`, Windows `%LOCALAPPDATA%\FT Assistant\`.
2. **Start at login:** Linux `~/.config/autostart/` entry; Windows a shortcut in the user's Startup
   folder.
3. **Settings file:** Linux `~/.config/ft-assistant/`, Windows `%APPDATA%\FT Assistant\`
   (chosen harness, Assistant key).
4. **Updates are never installed without asking.**
   - **Where:** the project's latest **GitHub Release** on the user's **`freethought78`** account
     (never `ftftft78`; no repo there yet). One request to GitHub's public "latest release" API,
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
