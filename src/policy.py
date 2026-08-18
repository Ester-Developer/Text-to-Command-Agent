"""Independent, non-LLM guards against prompt leakage, off-topic misuse,
and request flooding.

These exist for the same reason safety.py does: relying only on the
model's willingness to follow instructions is a *soft* guarantee (it held
up in live testing against several prompt-injection attempts, but nothing
stops a more creative attacker from eventually getting past it). Every
check here is plain Python — deterministic, not "persuadable", and runs
whether or not the model behaved.
"""

import threading
import time
from collections import deque
from dataclasses import dataclass, field


# --- 1. System prompt leakage ------------------------------------------
#
# Short phrases that only ever appear inside our own system prompt
# (src/prompts.py) - a legitimate one-line command explanation or a short
# refusal reason would never need to contain them verbatim. If any show
# up in the raw model output or in a parsed field, the model has leaked
# (some of) its instructions, regardless of *why* it did so.
_PROMPT_LEAK_SENTINELS = [
    "OUTPUT CONTRACT",
    "RISK CLASSIFICATION RULES",
    "REFUSAL RULES",
    "FEW-SHOT EXAMPLES",
    "Text-to-Command agent. You translate",
]


def check_prompt_leak(raw_text: str, *fields: str) -> str:
    """Returns a non-empty reason string if the system prompt appears to
    have leaked into the output; empty string otherwise."""
    haystacks = [raw_text or ""] + [f or "" for f in fields]
    for text in haystacks:
        for sentinel in _PROMPT_LEAK_SENTINELS:
            if sentinel in text:
                return f"Response appears to contain internal system-prompt text (matched: \"{sentinel}\")"
    return ""


# --- 2. Off-topic / non-command output ----------------------------------
#
# The contract is "one runnable shell command" + "one concise sentence".
# A poem, an essay, or a code dump doesn't fit that shape structurally,
# independent of whether the model *labeled* itself as refusing.
_MAX_COMMAND_LEN = 300
_MAX_EXPLANATION_LEN = 400


def check_off_topic_shape(command: str, explanation: str) -> str:
    """Returns a non-empty reason string if command/explanation don't
    match the expected shape of a single shell command + one sentence;
    empty string otherwise."""
    if "\n" in command:
        return "Command contains multiple lines, which doesn't match a single runnable shell command"
    if len(command) > _MAX_COMMAND_LEN:
        return f"Command is unexpectedly long ({len(command)} chars) for a single shell command"
    if len(explanation) > _MAX_EXPLANATION_LEN:
        return f"Explanation is unexpectedly long ({len(explanation)} chars) for a one-sentence description"
    return ""


# --- 3. Rate limiting -----------------------------------------------------
#
# No authentication exists in this app, so anyone with access to the
# Gradio URL could otherwise call convert() in a tight loop and burn
# through the (small, free-tier) API quota. This is a simple in-process
# sliding-window limiter shared by every caller of converter.convert().
@dataclass
class RateLimiter:
    max_requests: int
    window_seconds: float
    _timestamps: deque = field(default_factory=deque, init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def allow(self) -> bool:
        now = time.monotonic()
        with self._lock:
            while self._timestamps and now - self._timestamps[0] > self.window_seconds:
                self._timestamps.popleft()
            if len(self._timestamps) >= self.max_requests:
                return False
            self._timestamps.append(now)
            return True

    def seconds_until_available(self) -> float:
        with self._lock:
            if len(self._timestamps) < self.max_requests:
                return 0.0
            return max(0.0, self.window_seconds - (time.monotonic() - self._timestamps[0]))


# Shared instance: at most 15 conversions per rolling 60-second window,
# process-wide. Generous enough for normal interactive use, tight enough
# to stop a runaway loop from exhausting the free API quota in seconds.
global_rate_limiter = RateLimiter(max_requests=15, window_seconds=60)
