"""Syntactic validity check for a generated shell command.

This is deliberately lightweight (no full shell grammar parser): it uses
shlex to confirm the command tokenizes as a well-formed POSIX-ish shell
line (no dangling quotes, no trailing unescaped backslash, no empty
command), and a couple of structural sanity checks. It's the "syntactic
validity" metric referenced in the evaluation write-up.
"""

import shlex
from dataclasses import dataclass


@dataclass
class SyntaxResult:
    valid: bool
    reason: str = ""


def check_syntax(command: str) -> SyntaxResult:
    if command is None or command.strip() == "":
        return SyntaxResult(valid=False, reason="Empty command")

    stripped = command.strip()

    if stripped.count('"') % 2 != 0:
        return SyntaxResult(valid=False, reason="Unbalanced double quotes")
    if stripped.count("'") % 2 != 0:
        return SyntaxResult(valid=False, reason="Unbalanced single quotes")

    try:
        tokens = shlex.split(stripped, posix=True)
    except ValueError as e:
        return SyntaxResult(valid=False, reason=f"Shell tokenizer error: {e}")

    if not tokens:
        return SyntaxResult(valid=False, reason="No tokens after parsing")

    if stripped.endswith(("&&", "||", "|", ";")):
        return SyntaxResult(valid=False, reason="Command ends in a dangling operator")

    if stripped.startswith(("&&", "||", "|")):
        return SyntaxResult(valid=False, reason="Command starts with a dangling operator")

    return SyntaxResult(valid=True, reason="OK")
