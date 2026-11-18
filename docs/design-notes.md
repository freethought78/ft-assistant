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
   - **Already typing in the chosen harness's app** → strip "Assistant" from the start and
     type the rest into the current conversation. No new session.
   - **Anywhere else** → open a **new session** in the chosen harness's app and enter the
     rest of the dictation as the command.
6. **New sessions have no project folder.** Same as starting a fresh Claude Code session
   with no folder. If the user wants it to become a project, they say so in that session;
   the tool needs no special handling for that.
7. **"Assistant setup"** opens a small configuration screen:
   - It appears automatically the **first time the software is installed**, so a harness is
     always chosen before the keyword is used.
   - Saying "Assistant setup" reopens it any time.
   - The user picks **OpenCode** (free) or **Claude Code** (with a subscription, or by preference).
   - If the chosen harness isn't installed, the screen tells the user and helps them install it.
     **Nothing is downloaded automatically** outside this screen.
8. **Only two harnesses for now: Claude Code and OpenCode.** OpenCode is the free option for users
   who can't or don't want to pay for Claude Code. Considered and set aside for now (2026-11-17):
   Google Antigravity (free plan with weekly limits) and Kilo Desktop (beta). Gemini CLI and
   Qwen Code no longer have free tiers. Adding more later should stay possible.

### Open questions

- **Chosen harness vs. other harness:** if Claude Code is chosen but the user says "Assistant …"
  while typing in the OpenCode app (or the reverse), should it type into the current window or
  open a new session in the chosen app?
- **"Assistant" with nothing after it:** ignore it, or just open/focus the app?
- **First install:** the tool currently has no installer. What does "installing the software"
  look like for a new user (and is that part of this redesign)?
- **Setup screen look and toolkit,** and where the chosen harness is saved
  (e.g. `~/.config/…`).

### To verify before building (technical, not user decisions)

- How to start a new session and enter a prompt in the **Claude desktop app** from outside it
  (launch or raise its window, new-session action, type the prompt).
- The same for the **OpenCode desktop app** (`ai.opencode.desktop` / `opencode-desktop`, both
  installed on this machine).
- How to tell which app has focus (X11 active window's `WM_CLASS`).
- Keyword matching: case and punctuation Whisper adds ("Assistant,", "Assistant.").

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

### Measured sizes (current Linux install, 2026-11-17)

- Tool's own code: 24 KB.
- Python packages without GPU libraries: ~350 MB on disk (~100–150 MB download, estimated).
- NVIDIA libraries (cuBLAS, cuDNN, NVRTC): 2.1 GB on disk (~1–1.5 GB download, estimated).
- Model large-v3-turbo: 1.6 GB. Smaller models: ~150–500 MB.
- Totals: ~3–3.5 GB download with an NVIDIA card, ~0.3–0.7 GB without one.

### Under discussion

- **How one file runs on both systems.** Leading idea: a "polyglot" file that both Windows
  (`cmd`) and Linux (`bash`) can read. Each OS skips the other's part, installs a Python
  runtime, then both run the same shared Python setup program. The Python could even be
  embedded in the same file, so it really is one file.
  - **Name: `FT-Assistant-setup.cmd`** (decided 2026-11-17; dashes so Linux terminal commands need no quotes).
  - **Format comparison (2026-11-17):** no file type double-click-runs on both systems. On Linux,
    a downloaded file is never executable until allowed, so Linux always needs
    `bash "<file>"` or a "make executable" click, whatever the extension. Windows decides:
    - `.cmd`: double-click runs on every Windows, no settings. Cmd is only the doorway:
      it hands off at once to PowerShell (built into Windows 10/11) for downloads. **Best fit.**
    - `.bat`: same as `.cmd`, older name.
    - `.ps1`: double-click opens Notepad; execution policy blocks unsigned scripts; not on Linux.
    - `.py`: Windows has no Python by default, so it fails "from zero".
    - `.sh`: Windows can't run it.
    - One "actually portable" executable (Cosmopolitan) that runs on both: exotic, larger,
      needs a `.exe` name on Windows, and antivirus tools tend to flag it.
- **Trigger key: maybe Caps Lock instead of mouse button 12.** (This reverses an earlier
  decision; mouse button 12 isn't usable on Windows.) If adopted: Caps Lock must never be left
  on after dictating. Preferably the key press is swallowed so caps never toggles; otherwise
  the tool resets it after each use. Hold-to-talk also has to ignore the key's auto-repeat.
