"""Conversation notes: short notes the assistant keeps in the sessions folder, so a new
conversation (after "<word> new topic" or a quiet gap) can pick up earlier work.

FT Assistant doesn't write notes itself. It writes a short block of instructions into the files
each assistant reads at the start of every conversation in the sessions folder: CLAUDE.md
(Claude Code) and AGENTS.md (OpenCode). The notes are in notes/, with one line per note in
notes/INDEX.md.

On or off is a checkbox on the setup screen (the user's decision, 2026-11-23). Turning it off
never deletes notes: the block is swapped for one line telling the assistant to leave the notes
alone, so turning it back on brings the old notes back. Only the part between the markers is
FT Assistant's; anything else the user writes in those files is kept."""

import re
from pathlib import Path

FILES = ("CLAUDE.md", "AGENTS.md")
NOTES_DIR = "notes"
INDEX = "INDEX.md"
START = "<!-- FT Assistant conversation notes: start (FT Assistant updates this part) -->"
END = "<!-- FT Assistant conversation notes: end -->"

ON = """## Conversation notes

FT Assistant (voice dictation) starts conversations in this folder. They're often short and start
fresh, so keep short notes to carry what matters from one conversation to the next:

- At the start of a conversation, read notes/INDEX.md (one line per note).
- When a request matches a line there, read that note before answering.
- When you finish something worth keeping (a decision, a fix, how something works, something the
  user wants done a certain way), write or update a short note in notes/ and keep its line in
  notes/INDEX.md descriptive, for example:
  `- [Windows OpenCode launch](windows-opencode-launch.md): what broke and how it was fixed`
- Look through earlier conversations only when the user clearly refers to earlier work and no
  note covers it.
- Never put passwords, keys or other secrets in notes. The user can read, edit or delete them."""

OFF = """## Conversation notes

Conversation notes are turned off in FT Assistant: don't read or write the notes/ folder unless
the user asks."""

INDEX_TEXT = """# Conversation notes

One line per note: `- [Title](file.md): what it covers`

"""

_BLOCK = re.compile(re.escape(START) + r".*?" + re.escape(END), re.S)


def block(on):
    return f"{START}\n{ON if on else OFF}\n{END}"


def with_block(text, on):
    """`text` (an instructions file's content) with FT Assistant's part set to on or off."""
    new = block(on)
    if _BLOCK.search(text):
        return _BLOCK.sub(lambda m: new, text, count=1)
    if not text.strip():
        return new + "\n"
    return text.rstrip("\n") + "\n\n" + new + "\n"


def apply(folder, on):
    """Make the instructions in `folder` say on or off. Turning off keeps every note. Nothing is
    created to say "off" in a folder that never had notes."""
    folder = Path(folder)
    notes = folder / NOTES_DIR
    if not on and not notes.exists() and not any((folder / f).exists() for f in FILES):
        return
    folder.mkdir(parents=True, exist_ok=True)
    if on:
        notes.mkdir(exist_ok=True)
        index = notes / INDEX
        if not index.exists():
            index.write_text(INDEX_TEXT, encoding="utf-8")
    for name in FILES:
        path = folder / name
        old = path.read_text(encoding="utf-8") if path.exists() else ""
        new = with_block(old, on)
        if new != old:
            path.write_text(new, encoding="utf-8")
