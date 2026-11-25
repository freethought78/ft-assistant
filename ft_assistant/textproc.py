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
                   "undo": "undo", "send": "send", "close": "close"}
# What Whisper sometimes writes for a short command ("Assistant send" came back as "Assistant
# sent" in the user's tests, 2026-11-25). Only when it's the whole rest of the dictation, so
# "Assistant, sent items folder" stays a request.
SPOKEN_COMMANDS.update({"sent": "send", "cent": "send", "scent": "send", "sends": "send",
                        "closed": "close", "clothes": "close", "closes": "close",
                        "undue": "undo", "un do": "undo", "stopped": "stop", "stops": "stop",
                        "setups": "setup"})
# "<word> new topic" starts a new conversation, and may be followed by a request after a pause
# ("Assistant, new topic. Check the build."). The pause (punctuation from Whisper) is needed, so
# "Assistant, new topic ideas for the blog" stays an ordinary request.
_NEW_TOPIC_RE = re.compile(r"^new[\s-]+topic(?:\s*$|[.,:;!?]+\s*(.*)$)", re.I | re.S)
# Without an assistant ("Dictation only"), only these still mean something.
DICTATION_ONLY_COMMANDS = ("setup", "help", "undo", "send")


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
    rest = drop_echo(_strip_leading_punct(m.group(2)), keyword or DEFAULT_KEYWORD)
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


def drop_echo(rest, keyword):
    """What follows the command word, without the command word Whisper sometimes echoes from its
    hints on short commands: "Assistant, help, Assistant, help." or "Assistant send, Assistant"
    (found 2026-11-25: "Assistant" alone was typed into the assistant's window as a request). An
    echo is the word alone, or after a pause with nothing or the same words again after it."""
    words = re.findall(r"[^\W\d_]+", rest.lower())
    if words and all(w == keyword.casefold() for w in words):
        return ""
    m = re.search(rf"[,.;:!?]\s*{re.escape(keyword)}\b[\s,.;:!?]*(.*)$", rest, re.I | re.S)
    if m:
        first, after = rest[:m.start()], m.group(1)
        norm = lambda t: re.sub(r"[^a-z]+", " ", t.lower()).strip()   # noqa: E731
        if not norm(after) or norm(after) == norm(first):
            return first.strip()
    return rest


# Whisper is always given hint words: the command word, then each voice command's own words.
# Without them it sometimes drops a leading "Assistant" (tested 2026-11-18: 13/14 -> 14/14). The
# command word is in it once: phrases ("Assistant setup, Assistant help, ...") made Whisper echo
# them on short commands, and the word alone once made it repeat "Assistant" endlessly (tested
# 2026-11-25 on 18 synthetic clips: word once + bare words 18/18, 8 phrases 15/18, the 6 phrases of
# 0.5.0 17/18, the word alone 17/18).
def keyword_hints(keyword=DEFAULT_KEYWORD):
    k = keyword or DEFAULT_KEYWORD
    return (k, "setup", "help", "stop", "undo", "new topic", "send", "close")


def build_hotwords(vocabulary_words, keyword=DEFAULT_KEYWORD):
    """Whisper hotwords: the command-word hints first, then the user's vocabulary (no
    duplicates)."""
    seen, out = set(), []
    for w in list(keyword_hints(keyword)) + [v.strip() for v in vocabulary_words]:
        if w and w.lower() not in seen:
            seen.add(w.lower())
            out.append(w)
    return ", ".join(out)
