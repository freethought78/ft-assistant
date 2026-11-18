# FT Assistant

Push-to-talk voice dictation that runs on your own computer, with an optional voice shortcut to an
AI coding assistant.

- **Hold a key, speak, let go:** what you said is typed into whatever window you're using.
  Speech is turned into text locally with [Whisper](https://github.com/openai/whisper)
  (through [faster-whisper](https://github.com/SYSTRAN/faster-whisper)). Your voice never leaves
  your computer.
- **Say "Assistant" first** ("Assistant, fix the failing test") and the request goes to your
  chosen coding assistant instead: [Claude Code](https://claude.com/claude-code) or
  [OpenCode](https://opencode.ai). It opens in a normal terminal window, so you can always see what
  it's doing and keep talking to it. Nothing runs hidden in the background.

> **Status:** in development. There's no release yet; the first one is being prepared. The `main`
> branch holds the version in daily use today, and `next` holds the redesign described here.

## Features

- **Works with any program:** text is typed as if you'd typed it yourself.
- **The Assistant key** is any key or extra mouse button you choose (Caps Lock by default).
  Caps Lock is never left switched on.
- **Private by design:** audio stays in memory and is never saved; the speech model runs offline;
  what you say is never written to a log. Only requests that start with "Assistant" go online, to
  the assistant you picked.
- **Light on your computer:** the speech engine is loaded only while you dictate and released right
  after, so it doesn't hold memory or graphics memory in between.
- **Fast with an NVIDIA graphics card** (large-v3-turbo model); without one, a smaller model runs
  on the processor.
- **Small setup file** that downloads only what's missing, and reuses what's already on your
  computer (Python, NVIDIA libraries, an existing Whisper model) to save downloads and disk space.
- **Setup screen** (hold your key and say "Assistant setup") to pick the assistant, change the key,
  check for updates or uninstall. Updates are never installed without asking.

## Requirements

- **Linux** with an X11 desktop session (Wayland isn't supported yet), or **Windows 10/11**.
- A microphone.
- Optional: an NVIDIA graphics card for the fastest transcription.
- Optional: Claude Code (needs a Claude subscription) or OpenCode (free) for the Assistant keyword.

## Install

When the first release is out, download `FT-Assistant-setup.cmd` from the Releases page, then:

- **Windows:** double-click it.
- **Linux:** run `bash FT-Assistant-setup.cmd` in a terminal.

Setup checks your computer, shows exactly what it will download and how big it is, and waits for
you before downloading anything. On Linux it can install the few system packages it needs
(`xdotool`, `libnotify`, `portaudio`, and `python3-tk` for clear text) after asking for your
password.

## Using it

"Assistant" is the default **command word**; you can pick another one, or choose
**Dictation only** (no assistant, nothing leaves your computer), on the setup screen.

| You say (holding the Assistant key) | What happens |
|---|---|
| Anything | It's typed into the window you're using. |
| "Assistant, *request*" | The request goes to your assistant: into its window if you're already in it, otherwise it opens (continuing your last conversation). |
| "Assistant setup" | The setup screen opens. |

## Development

```bash
# run the tests
python3 -m unittest discover -s tests -t .

# build the setup file (written to dist/)
python3 installer/build.py
```

- `ft_assistant/`: the program (`platform_linux.py` and `platform_windows.py` hold the
  system-specific parts).
- `installer/`: the setup file template and the installer it embeds.
- `docs/design-notes.md`: the design, decisions and test results.

## License

Not chosen yet.
