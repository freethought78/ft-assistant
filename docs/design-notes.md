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
