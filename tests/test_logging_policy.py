"""Privacy policy for the log file: errors and warnings only, plus one start-up line.
No record of activity (when or how much someone dictates) and never what was said."""
import ast
import unittest
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent / "ft_assistant"
ALLOWED_INFO = {("app.py", "ready: version %s, Assistant key %s, harness %s")}


def log_calls():
    for f in sorted(PKG.glob("*.py")):
        for node in ast.walk(ast.parse(f.read_text())):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name) and node.func.value.id == "log"):
                msg = node.args[0].value if node.args and isinstance(node.args[0], ast.Constant) else None
                yield f.name, node.func.attr, msg, node


class LogPolicy(unittest.TestCase):
    def test_only_the_start_up_line_is_info(self):
        info = {(f, m) for f, level, m, _ in log_calls() if level == "info"}
        self.assertEqual(info, ALLOWED_INFO)

    def test_no_transcript_text_in_any_log_call(self):
        # The cleaned text and the command text must never be passed to the logger.
        for f, level, m, node in log_calls():
            names = {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
            attrs = {n.attr for n in ast.walk(node) if isinstance(n, ast.Attribute)}
            self.assertFalse({"text", "raw", "prompt"} & names, (f, m))
            self.assertNotIn("text", attrs - {"len"}, (f, m)) if "len" not in names else None

    def test_log_file_is_size_capped(self):
        src = (PKG / "app.py").read_text()
        self.assertIn("RotatingFileHandler", src)
        self.assertIn("maxBytes=200_000", src)


if __name__ == "__main__":
    unittest.main()
