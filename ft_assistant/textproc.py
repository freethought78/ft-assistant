"""Pure text handling: cleaning Whisper output and recognising the command word
("Assistant" unless the user picked another).

No I/O here, so everything in this module is unit-tested."""

import re
from dataclasses import dataclass

DEFAULT_KEYWORD = "Assistant"

# Words that often start ordinary sentences: as a command word they'd turn normal dictation into
# commands by accident, so choosing one shows a warning (it's still allowed).
COMMON_STARTERS = {
    "a", "about", "also", "an", "and", "are", "as", "at", "but", "can", "could", "did", "do",
    "does", "for", "hello", "hey", "hi", "how", "i", "if", "in", "is", "it", "just", "let",
    "lets", "my", "no", "now", "of", "oh", "ok", "okay", "on", "please", "right", "so", "sure",
    "that", "the", "then", "there", "this", "to", "uh", "um", "we", "well", "what", "when",
    "where", "why", "will", "with", "would", "yeah", "yes", "you",
}

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
_FIRST_WORD_RE = re.compile(r"^\s*([^\W\d_]+)(?=$|[\s,.:;!?\-])[\s,.:;!?\-]*(.*)$", re.S)


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
          "setup" (open the setup screen), "help" (show the voice commands), or "stop"
          (interrupt the assistant's current work)."""
    kind: str
    text: str = ""


def _strip_leading_punct(s):
    return re.sub(r"^[\s,.:;!?\-]+", "", s).strip()


def check_keyword(word):
    """Validate a command word chosen in setup.

    Returns (word, error, warning): the word tidied (first letter capitalized), an error message
    if it can't be used (then word is None), and a warning if it's allowed but risky."""
    w = (word or "").strip().strip(",.:;!?\"'")
    if not w:
        return None, "Type a word.", None
    if not re.fullmatch(r"[^\W\d_]+", w):
        return None, "Use a single word made of letters only (no spaces, numbers or symbols).", None
    if not 2 <= len(w) <= 20:
        return None, "Use a word of 2 to 20 letters.", None
    w = w[0].upper() + w[1:]
    if w.casefold() in COMMON_STARTERS:
        return w, None, (f"\"{w}\" often starts ordinary sentences, so normal dictation that "
                         "begins with it would be treated as a command.")
    return w, None, None


# The voice commands after the command word, besides "<word>, <request>" and "<word>" alone.
# Kept deliberately few (at most about 7 commands in all): see the voice commands plan in
# docs/design-notes.md. Each needs to be an everyday word, unlikely as the start of a request.
SPOKEN_COMMANDS = {"setup": "setup", "set up": "setup", "help": "help", "stop": "stop",
                   "undo": "undo"}
# "<word> new topic" starts a new conversation, and may be followed by a request after a pause
# ("Assistant, new topic. Check the build."). The pause (punctuation from Whisper) is needed, so
# "Assistant, new topic ideas for the blog" stays an ordinary request.
_NEW_TOPIC_RE = re.compile(r"^new[\s-]+topic(?:\s*$|[.,:;!?]+\s*(.*)$)", re.I | re.S)
# Without an assistant ("Dictation only"), only these still mean something.
DICTATION_ONLY_COMMANDS = ("setup", "help", "undo")


def route(text, dictation_only=False, keyword=DEFAULT_KEYWORD):
    """What to do with cleaned dictation text. In "Dictation only" there's no assistant, so the
    command word means nothing: "Assistant, ..." is typed like anything else. "Assistant setup"
    and "Assistant help" still work (otherwise there'd be no spoken way back to the settings)."""
    cmd = parse_command(text, keyword)
    if dictation_only and cmd.kind not in ("dictate",) + DICTATION_ONLY_COMMANDS:
        return Command("dictate", (text or "").strip())
    return cmd


def parse_command(text, keyword=DEFAULT_KEYWORD):
    """Classify cleaned dictation text. Only the very first word can be the command word."""
    text = (text or "").strip()
    m = _FIRST_WORD_RE.match(text)
    if not m or m.group(1).casefold() != (keyword or DEFAULT_KEYWORD).casefold():
        return Command("dictate", text)
    rest = _strip_leading_punct(m.group(2))
    # The whole rest must be the command: "Assistant setup" / "Assistant, set up." / "Assistant
    # set-up" (Whisper varies the spelling), "Assistant stop." But "Assistant, stop the server"
    # is a request.
    said = re.sub(r"[^a-z]+", " ", rest.lower()).strip()
    if said in SPOKEN_COMMANDS:
        return Command(SPOKEN_COMMANDS[said])
    m = _NEW_TOPIC_RE.match(rest)
    if m:
        return Command("new_topic", (m.group(1) or "").strip())
    return Command("assistant", rest)


# The command word is always given to Whisper as hint words, "<word>, <word> setup", ...: without
# them it sometimes drops a leading "Assistant" (tested 2026-11-18: 13/14 -> 14/14 on both
# large-v3-turbo and small.en). A list works better than the single word. Each voice command is
# a hint too, so it's caught reliably; too many hints could make Whisper "hear" them in normal
# speech, one more reason to keep the commands few.
def keyword_hints(keyword=DEFAULT_KEYWORD):
    k = keyword or DEFAULT_KEYWORD
    return (k, f"{k} setup", f"{k} help", f"{k} stop", f"{k} undo", f"{k} new topic")


def build_hotwords(vocabulary_words, keyword=DEFAULT_KEYWORD):
    """Whisper hotwords: the command-word hints first, then the user's vocabulary (no
    duplicates)."""
    seen, out = set(), []
    for w in list(keyword_hints(keyword)) + [v.strip() for v in vocabulary_words]:
        if w and w.lower() not in seen:
            seen.add(w.lower())
            out.append(w)
    return ", ".join(out)
