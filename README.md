# FT Assistant

Push-to-talk voice dictation that runs on your own computer, with a voice shortcut to an AI
assistant.

- **Hold a key, speak, let go:** what you said is typed into whatever window you're using.
  Speech is turned into text on your computer with [Whisper](https://github.com/openai/whisper)
  (through [faster-whisper](https://github.com/SYSTRAN/faster-whisper)). Your voice never leaves
  your computer.
- **Say "Assistant" first** ("Assistant, what's using all my disk space?") and the request goes to
  your AI assistant instead: [Claude Code](https://claude.com/claude-code) or
  [OpenCode](https://opencode.ai). It opens in a normal terminal window, so you can always see
  what it's doing and keep talking to it. Nothing runs hidden in the background.

This page is the complete manual. The **Manual** button on the setup screen opens it.

> **Status:** early releases, in daily use and being tested by a few people.

## Contents

- [What it's for](#what-its-for)
- [Requirements](#requirements)
- [Install](#install)
- [Dictating](#dictating)
- [Voice commands](#voice-commands)
- [Talking to your assistant](#talking-to-your-assistant)
- [The setup screen](#the-setup-screen)
- [Privacy](#privacy)
- [Updating](#updating)
- [Troubleshooting](#troubleshooting)
- [Uninstalling](#uninstalling)
- [Files and settings](#files-and-settings)
- [Development](#development)

## What it's for

FT Assistant is a **one-button way to use your computer by voice**: dictation everywhere, and an
assistant you can hand a quick task or question to without typing.

- **Good for:** dictating anything, and **one-off requests** to the assistant: a question, a quick
  fix on your computer, finding something, a short task.
- **For bigger projects** (writing or building something over many sessions, with a long history),
  use the assistant's **full desktop app or terminal in that project's own folder**. FT Assistant
  still helps there: dictate into it like into any other window.

A conversation with the assistant lasts as long as its window is open (see
[Conversations](#conversations)): close the window when you're done, and the next request starts
fresh, which suits quick requests and keeps answers fast.

## Requirements

- **Linux** with an X11 desktop session (Wayland isn't supported), or **Windows 10/11**.
- A microphone.
- **English speech.** The speech models are set to English, so other languages aren't supported.
- Optional: an NVIDIA graphics card for the fastest transcription.
- Optional, for the assistant: **Claude Code** (needs a Claude subscription) or **OpenCode** (free).
  The setup screen can install either one.

## Install

Download **FT Assistant Installer** (`FT-Assistant-Installer.cmd`) from the
[latest release](https://github.com/freethought78/ft-assistant/releases/latest), then:

- **Windows:** double-click it.
- **Linux:** run `bash FT-Assistant-Installer.cmd` in a terminal.

What happens:

1. **Where to install:** press Enter for the usual place in your user folder, or C to pick another
   folder in a folder window. If that folder already has other files in it, FT Assistant goes into
   an "FT Assistant" folder of its own there.
2. **What it will download** is shown, with sizes, and nothing is downloaded until you press Enter.
   Setup only downloads what's missing and reuses what's already on your computer (NVIDIA
   libraries, an existing Whisper model).
3. **On Linux** it can install the few system packages it needs (`xdotool`, `libnotify`,
   `portaudio`) after asking for your password.
4. **The first time FT Assistant starts,** the setup screen opens: choose your assistant (or
   Dictation only) and your Assistant key.

FT Assistant uses **its own copy of Python**, kept in its install folder. It never uses or changes
any Python already on your computer. It starts by itself when you log in, and it's in your Start
menu or app menu as **FT Assistant**, **FT Assistant setup** and **Uninstall FT Assistant**.

## Dictating

1. **Hold your Assistant key** (Caps Lock unless you chose another). A high beep means the
   microphone is listening.
2. **Speak.**
3. **Let go.** A lower beep means it heard you let go. A moment later the text is typed where your
   cursor is.

- **Works in any program:** the text is typed as if you'd typed it yourself.
- **Your Assistant key is FT Assistant's alone:** whether it's a key or a mouse button, other
  programs never receive it, so pressing it over another window doesn't click or activate that
  window. Caps Lock is never left switched on when it's your Assistant key.
- **Short taps and silence are ignored,** and so are the stock phrases Whisper sometimes makes up
  on silence (such as "Thank you.").
- **Background audio** (music, a video) is fine.
- **Mistakes:** say "Assistant undo" right away to remove what was just typed (see below).
- **Names and unusual words:** add them to your [word list](#files-and-settings) to get them
  spelled your way.

## Voice commands

Hold your Assistant key and say the command word ("Assistant" unless you chose another) followed
by:

| You say | What happens |
|---|---|
| "Assistant, *request*" | The request goes to your assistant (see [Talking to your assistant](#talking-to-your-assistant)). |
| "Assistant" | Your assistant's window comes to the front, or a new one opens. |
| "Assistant new topic, *request*" | A new conversation starts, with the request if you add one after a short pause. |
| "Assistant close" | Your assistant's window closes, which ends the conversation. |
| "Assistant send" | Presses Enter, to send what you've dictated (in any program). |
| "Assistant stop" | Your assistant stops what it's doing right now, like pressing Esc in its window. |
| "Assistant undo" | Removes what FT Assistant just typed, if you haven't typed or clicked since. |
| "Assistant setup" | The setup screen opens. |
| "Assistant help" | A short list of these commands opens. |

Anything you say without the command word first is typed where your cursor is.

- **"Assistant undo"** only works right after a dictation, in the same window, and only if you
  haven't pressed a key or clicked since. Otherwise it does nothing, so it can never delete
  anything else. It removes only the last dictation, once.
- **"Assistant new topic"** needs a short pause after "new topic" if you add a request ("Assistant,
  new topic. Check the build."). Without the pause, "Assistant, new topic ideas for my blog" is an
  ordinary request.
- **"Assistant send"** is handy after dictating a message or a prompt: it sends it without
  reaching for the keyboard.
- **"Assistant close"** only closes the window FT Assistant opened for your assistant, never any
  other window. It stops any work in progress first.
- **Dictation only** (no assistant): only "send", "undo", "setup" and "help" work; anything else is
  typed.

## Talking to your assistant

### Where requests go

- **From any other window,** "Assistant, ..." brings your assistant's window to the front and sends
  the request there. If the window isn't open, a new one opens.
- **Inside the assistant's window,** "Assistant, ..." types the request there and sends it. Plain
  dictation (without the command word) is typed into its input like anywhere else, so you can
  check it and press Enter yourself.
- **When it asks to approve something,** answer with the keyboard. Voice never approves anything,
  so a misheard word can't allow an action.

### Conversations

**A conversation lasts as long as its window.** What you see is what the assistant knows:

- **While the window is open,** every request continues that conversation, however long it's been
  and however long the assistant has been working.
- **Close the window** (or say "Assistant close") when you're done. The next request opens a new
  window with a fresh conversation.
- **"Assistant new topic"** starts a fresh conversation without closing the window (FT Assistant
  types `/clear` for Claude Code or `/new` for OpenCode).
- **Earlier conversations are kept** and can be reopened inside the assistant (`/resume` in Claude
  Code, the session list in OpenCode).
- **Remembering earlier work:** Claude Code keeps its own memory of what you've worked on and
  brings it into new conversations. OpenCode doesn't, so tell it what it needs to know, or reopen
  the earlier conversation.

Conversations start in a neutral folder of FT Assistant's own, "FT Assistant sessions" in your user
folder, never in one of your projects.

## The setup screen

Open it by saying **"Assistant setup"**, or from your Start menu or app menu (**FT Assistant
setup**). Your Assistant key keeps working while it's open.

- **Assistant:** Dictation only, OpenCode or Claude Code. If one isn't installed yet, its
  **Install...** button gets the latest version from its official source, and the screen notices
  when it's done.
- **Assistant key:** click **Change key**, then press the key or mouse button you want. Tips on good
  choices show while you choose. The new key works right away, so you can try it before saving:
  **Save** keeps it, **Cancel** goes back to your old one.
- **Command word:** "Assistant" by default. Any single word works; a less common word is caught more
  reliably and won't clash with ordinary sentences. **Voice commands...** shows the list of
  commands with your word, and a few things good to know.
- **Help and updates:** **Check for updates**, **Uninstall...**, and **Manual** (this page).

The text follows your desktop's text size and font, a little bigger for easy reading. If you've
made text larger in your system's settings (including Windows' **Text size**), these windows follow
it.

## Privacy

- **Your voice stays on your computer.** Audio is kept only in memory while you dictate and is never
  saved. The speech model runs offline.
- **What you say is never written to a log.** The log only records errors and one line when
  FT Assistant starts.
- **Only requests that start with "Assistant" go online,** to the assistant you chose (Anthropic for
  Claude Code, your OpenCode model provider for OpenCode). With **Dictation only**, nothing you say
  leaves your computer.
- **Apart from that,** FT Assistant connects only to GitHub, about once a day, to see whether a new
  version is out. Nothing about you or what you say is sent.
- **"Assistant undo"** remembers only how many characters were typed last and a count of key presses
  and clicks, in memory, never the text or which keys.
- **Light on your computer:** the speech engine is loaded only while you dictate and released right
  after, so it doesn't hold memory or graphics memory in between. FT Assistant closes its own
  microphone stream after each dictation; it never mutes or changes your system microphone.

## Updating

- **FT Assistant checks for a new version about once a day** and shows a notification when there is
  one. Updates are never installed without asking: click the notification, or open the setup screen
  and click **Update now**.
- **Check now:** **Check for updates** on the setup screen.
- **Updating keeps** your settings, your word list, the speech model and anything already
  downloaded.
- **Repairing:** run the newest installer again. It finds your existing install and offers to
  update it in the same folder.

## Troubleshooting

FT Assistant only shows a notification when something's wrong or an update is out, never during
normal use.

- **Nothing is typed:** make sure the window you want to type into has the cursor. On Linux, FT
  Assistant needs an X11 session (not Wayland) and `xdotool`.
- **"Microphone error":** check that a microphone is connected and chosen as the input in your
  system's sound settings.
- **"Couldn't open Claude Code's window"** (or OpenCode's): the assistant's window didn't start. Check
  that the assistant is installed (setup screen), then try again.
- **"No assistant chosen yet":** open the setup screen and choose one (or Dictation only).
- **Slow transcription and a note about your graphics card:** FT Assistant is using the processor
  because the NVIDIA card couldn't be used (often an old driver). Update the NVIDIA driver and
  restart the computer.
- **"Assistant undo" did nothing:** you typed or clicked after the dictation, or switched windows.
  That's on purpose: it only removes text when it's sure it's the last thing typed there.
- **A word is often misheard:** add it to your word list, or for the command word, choose a less
  common one.
- **Is it running?** Look for **FT Assistant** in Task Manager (Windows) or System Monitor (Linux).
  Start it from the Start menu or app menu if it isn't.
- **The log** (errors only): `ft-assistant.log` in the settings folder (see below).

## Uninstalling

Use **Uninstall FT Assistant** in the Start menu or app menu, or **Uninstall...** on the setup
screen. It removes only FT Assistant's own files; anything else in the same folder is left alone.

## Files and settings

| What | Linux | Windows |
|---|---|---|
| Settings, word list, log | `~/.config/ft-assistant/` | `%APPDATA%\FT Assistant\` |
| The program (default place) | `~/.local/share/ft-assistant/` | `%LOCALAPPDATA%\FT Assistant\` |
| Assistant conversations start in | `~/FT Assistant sessions/` | `%USERPROFILE%\FT Assistant sessions\` |

- **Word list:** `vocabulary.txt` in the settings folder, one word or name per line (lines starting
  with `#` are comments). Changes count from your next dictation.
- **Settings:** `settings.json`, written by the setup screen.

## Development

```bash
# run the tests
python3 -m unittest discover -s tests -t .

# build the installer (written to dist/)
python3 installer/build.py
```

- `ft_assistant/`: the program (`platform_linux.py` and `platform_windows.py` hold the
  system-specific parts).
- `installer/`: the installer template and the setup program it carries.
- `docs/design-notes.md`: the design, decisions and test results.
- `tests/`: the unit tests.
- **Branches:** `main` holds the released version, `next` the work for the next release.

## License

Not chosen yet.
