"""Pure text handling: cleaning Whisper output and recognising the "Assistant" keyword.

No I/O here, so everything in this module is unit-tested."""

import re
from dataclasses import dataclass

KEYWORD = "assistant"

# Phrases Whisper tends to invent on silence/noise; dropped if they are the whole result.
HALLUCINATIONS = {"thank you.", "thank you", "thanks for watching!", "thanks for watching.",
                  "you", "you.", "bye.", "bye!", "thank you very much.", ".", "okay."}

# Subtitle credits Whisper tacks onto the end of real speech (learned from video subtitles),
# e.g. "Closed Captioning by www.microsoft.com", "Subtitles by the Amara.org community".
# Only removed at the very end, and only when the credit word is capitalized, so a sentence
# like "the subtitles by default are off" is left alone.
CREDIT_RE = re.compile(
    r"[\s,]*\b(?:Closed [Cc]aption(?:ing|ed|s)?|Caption(?:ing|ed|s)?|Subtitles?|Subtitling"
    r"|Transcription|Transcribed)\b(?: [\w.'-]+){0,4}? by\b.{0,80}$")

# A word followed by any punctuation Whisper may attach ("Assistant," "Assistant." "Assistant:")
_FIRST_WORD_RE = re.compile(r"^\s*([A-Za-z]+)(?=$|[\s,.:;!?\-])[\s,.:;!?\-]*(.*)$", re.S)


def clean_text(text):
    """Drop subtitle credits from the end; return "" if nothing real is left."""
    text = (text or "").strip()
    prev = None
    while text and text != prev:
        prev = text
        text = CREDIT_RE.sub("", text).strip()
    if text.lower() in HALLUCINATIONS:
        return ""
    return text


@dataclass(frozen=True)
class Command:
    """What a dictation means.

    kind: "dictate" (type `text`), "assistant" (send `text` to the agent; may be ""),
          or "setup" (open the setup screen)."""
    kind: str
    text: str = ""


def _strip_leading_punct(s):
    return re.sub(r"^[\s,.:;!?\-]+", "", s).strip()


def parse_command(text):
    """Classify cleaned dictation text. Only the very first word can be the keyword."""
    text = (text or "").strip()
    m = _FIRST_WORD_RE.match(text)
    if not m or m.group(1).lower() != KEYWORD:
        return Command("dictate", text)
    rest = _strip_leading_punct(m.group(2))
    # "Assistant setup" / "Assistant, set up." / "Assistant set-up" (Whisper varies the spelling)
    if re.sub(r"[^a-z]+", " ", rest.lower()).strip() in ("setup", "set up"):
        return Command("setup")
    return Command("assistant", rest)
