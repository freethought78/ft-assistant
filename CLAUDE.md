# FT Assistant

This project is for **maintaining, updating and adding features to the user's push-to-talk voice dictation tool**:
hold a mouse button, speak, release, and local Whisper types what was said into whichever window has focus.

The user relies on it every day and dictates nearly everything they send (including messages to
Claude) through this tool. Treat it as production software: a broken build means the user can't
type comfortably.

## Where the live tool is

**This repo is the source; the live install is a deployed copy** at `~/.local/share/voice-dictation/`
(the user chose this on 2026-11-17). Edit files here, then deploy with `./deploy.sh` (see below).
The repo holds `dictate.py`, `whisper_worker.py`, `run.sh`, `vocabulary.txt` and `autostart/voice-dictation.desktop`.
`venv/`, `models/`, `dictation.log` and `.lock` exist only in the install and stay out of git.

Live install layout:

| File | Role |
|---|---|
| `dictate.py` | Main process. Watches X11 mouse button events (XRecord via python-xlib), records the mic while button 12 is held, sends audio to the worker, types the result with `xdotool type`. Single-instance via `fcntl` lock on `.lock`. |
| `whisper_worker.py` | Speech engine subprocess: faster-whisper `large-v3-turbo`, CUDA float16, English, beam 5, VAD filter, `hotwords` from `vocabulary.txt`. Protocol on stdin/stdout: prints `READY`, then per request reads a 4-byte LE length + float32 16 kHz mono audio and replies with one JSON line `{"text": ...}` or `{"error": ...}`. |
| `run.sh` | Launcher: sets `LD_LIBRARY_PATH` to the venv's nvidia cublas/cudnn libs, `HF_HUB_OFFLINE=1`, runs `dictate.py` with the venv's Python. |
| `vocabulary.txt` | Words/names Whisper should spell a certain way, one per line (`#` comments). Read on every transcription, so edits apply without a restart. |
| `dictation.log` | Log of events only: engine load/unload, mic open/close, audio length, transcription time and character count per dictation, errors. **Never the transcribed text.** |
| `venv/` | Python 3.12 venv: faster-whisper 1.2.1, ctranslate2 4.9, numpy, sounddevice, python-xlib, nvidia libs. |
| `models/` | Downloaded HF cache for `mobiuslabsgmbh/faster-whisper-large-v3-turbo`. |

It starts at login from `~/.config/autostart/voice-dictation.desktop` (runs `run.sh`, 5 s delay).

`~/bin/start-whisper-stt` is an **older, unrelated** script (a whisper-fastapi server). It isn't part of this tool.

### Deploying

- `./deploy.sh` — dry run: prints a diff of every file where repo and live differ. Changes nothing.
- `./deploy.sh --yes` — syntax-checks the Python and `run.sh`, backs up the live files to
  `~/.local/share/voice-dictation/backups/<timestamp>/`, then copies the changed files over.
- `./deploy.sh --rollback` — restores the most recent backup.
- The script never restarts the tool. Code changes need a restart (see "Working on it safely");
  `vocabulary.txt` changes apply on the next dictation.
- Always dry-run first. If the dry run shows a live file differing in a way the repo doesn't explain
  (e.g. the user edited `vocabulary.txt` in the install), pull that change into the repo before deploying.
- Don't deploy or commit without the user's go-ahead.

## System

- Linux Mint (Cinnamon), **X11** session. The tool is X11-only (XRecord and xdotool), and Wayland would need a different input/typing path.
- NVIDIA RTX 4070 (12 GB). The engine loads in about 1 s and transcribes about 20 s of speech in about 0.5 s.
- Trigger: X11 **mouse button 12**, a spare Fn button on an ELECOM DEFT Pro trackball, forwarded through input-remapper.
  Override with `DICTATE_BUTTON`. Other env settings: `DICTATE_IDLE_SEC`, `DICTATE_MODEL`.

## Design decisions the user made (keep them unless they ask otherwise)

- **A mouse button, not a keyboard key** (they turned down Caps Lock).
- **Free all resources when idle.** The worker subprocess and the mic stream start on the first press and are released
  **right after each dictation** (`IDLE_SEC = 0`). The user tried a 5-minute delay first and then asked for an immediate
  unload, because the roughly 1 s cold start is fine. Killing the subprocess is what guarantees GPU memory is returned.
- **Never mute, disable or reconfigure the system microphone.** Releasing only closes the tool's own input stream.
  The user specifically asked about this, so say "closes its mic stream", never "turns off the mic".
- **Privacy:** audio is kept only in memory and never written to disk, and transcript text is never logged. The model runs offline (`HF_HUB_OFFLINE=1`).
- **It works with background audio playing** (tested), and short taps or near-silent clips are ignored (`MIN_SEC`, `MIN_RMS`).
- Whisper's typical made-up phrases on silence ("Thank you.", "Thanks for watching!") are dropped when they are the whole result (`HALLUCINATIONS`).
- A start beep (880 Hz) means the mic is live, and a stop beep (587 Hz) means release was registered.

## Working on it safely

- **Restarting the tool cuts off the user's typing** until it's back, and they may be dictating to you through it.
  Say so before restarting, keep the downtime short, and confirm it's back (`ready:` line in `dictation.log`).
  Restart: `pkill -f '[v]oice-dictation/dictate.py'; sleep 1; setsid ~/.local/share/voice-dictation/run.sh >/dev/null 2>&1 < /dev/null &`
  (the `[v]` stops `pkill` from matching, and killing, the shell running the command itself).
- Test changes before deploying them over the working version, and keep a way to roll back.
- **Never log what the user says.** On 2026-11-17 they had transcript logging turned off and the old log deleted.
  Don't add any log line, debug print or file that records transcript text. If debugging needs the text, ask first and remove it afterwards.

## Working with the user

- They dictate, so prefer one-click choices (buttons or options) over questions that need typed answers.
- They like concise reports.
- Never launch games or emulators: they steal focus while the user is playing.
