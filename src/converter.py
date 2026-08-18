"""Core text-to-command conversion pipeline.

Flow: instruction -> LLM (prompts.PROMPT_CURRENT) -> parsed JSON ->
independent syntax check -> independent safety check -> ConversionResult.

The independent checks always run and can only make the result *more*
restrictive than what the model claims (defense in depth) -- they never
relax a refusal the model already made.
"""

import json
import re
from dataclasses import dataclass, field
from typing import Optional

from . import prompts
from . import llm_client
from .safety import check_command, SafetyResult
from .syntax_validator import check_syntax, SyntaxResult
from .policy import check_prompt_leak, check_off_topic_shape, global_rate_limiter


@dataclass
class ConversionResult:
    instruction: str
    command: str
    explanation: str
    os: str
    llm_risk_level: str
    llm_safe: bool
    refused: bool
    refusal_reason: str
    syntax: SyntaxResult
    safety: SafetyResult
    final_safe_to_show_as_runnable: bool
    raw_model_output: str = ""
    parse_error: Optional[str] = None


def _friendly_api_error(e: Exception) -> str:
    text = str(e)
    if "429" in text or "RESOURCE_EXHAUSTED" in text:
        return (
            "The free Gemini API quota was hit (rate limit). Wait a bit and try again, "
            "or switch GEMINI_MODEL to a lighter model with a higher free quota "
            "(e.g. gemini-3.6-flash-lite) in your .env file."
        )
    return f"The model API request failed: {text[:200]}"


def _extract_json(text: str) -> dict:
    """The model is instructed to return raw JSON, but be tolerant of
    stray markdown fences some models occasionally add anyway."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("No JSON object found in model output")
    return json.loads(match.group(0))


def convert(instruction: str, os_name: str = "linux/macOS (bash)", prompt_version: str = "v3") -> ConversionResult:
    instruction = (instruction or "").strip()
    if not instruction:
        return ConversionResult(
            instruction=instruction, command="", explanation="", os=os_name,
            llm_risk_level="low", llm_safe=True, refused=True,
            refusal_reason="Empty instruction",
            syntax=SyntaxResult(valid=False, reason="Empty command"),
            safety=SafetyResult(blocked=False, matched_rules=[]),
            final_safe_to_show_as_runnable=False,
            raw_model_output="", parse_error=None,
        )

    if not global_rate_limiter.allow():
        wait_s = global_rate_limiter.seconds_until_available()
        return ConversionResult(
            instruction=instruction, command="", explanation="", os=os_name,
            llm_risk_level="low", llm_safe=False, refused=True,
            refusal_reason=f"Too many requests — please wait {wait_s:.0f}s and try again.",
            syntax=SyntaxResult(valid=False, reason="No command produced"),
            safety=SafetyResult(blocked=False, matched_rules=[]),
            final_safe_to_show_as_runnable=False,
            raw_model_output="", parse_error=None,
        )

    prompt = prompts.build_prompt(instruction, os_name=os_name, version=prompt_version)
    try:
        raw = llm_client.complete(prompt)
    except RuntimeError:
        raise
    except Exception as e:
        return ConversionResult(
            instruction=instruction, command="", explanation="", os=os_name,
            llm_risk_level="low", llm_safe=False, refused=True,
            refusal_reason=_friendly_api_error(e),
            syntax=SyntaxResult(valid=False, reason="No command produced"),
            safety=SafetyResult(blocked=False, matched_rules=[]),
            final_safe_to_show_as_runnable=False,
            raw_model_output="", parse_error=str(e),
        )

    try:
        data = _extract_json(raw)
        parse_error = None
    except (ValueError, json.JSONDecodeError) as e:
        data = {}
        parse_error = str(e)

    command = str(data.get("command", "") or "")
    explanation = str(data.get("explanation", "") or "")
    os_out = str(data.get("os", os_name) or os_name)
    llm_risk_level = str(data.get("risk_level", "high") or "high")
    llm_safe = bool(data.get("safe", False))
    refused = bool(data.get("refused", False))
    refusal_reason = str(data.get("refusal_reason", "") or "")

    if parse_error:
        refused = True
        refusal_reason = refusal_reason or f"Could not parse a valid response from the model ({parse_error})"
        llm_safe = False

    # Independent of anything the model claims about itself: does the raw
    # output or any field contain leaked fragments of our own system
    # prompt, or does the command/explanation not match the shape of "one
    # shell command + one sentence" (a poem, an essay, a code dump)? Either
    # one is a policy violation and forces a refusal, the same way a
    # dangerous-pattern match in safety.py does.
    policy_violation = check_prompt_leak(raw, command, explanation, refusal_reason) or check_off_topic_shape(
        command, explanation
    )
    if policy_violation:
        refused = True
        llm_safe = False
        refusal_reason = f"Blocked by an independent policy check: {policy_violation}"
        command = ""

    syntax_result = check_syntax(command) if command else SyntaxResult(valid=False, reason="No command produced")
    safety_result = check_command(command)

    # A "high" risk_level is never auto-runnable, even if the model also
    # claims safe=true. Without this, a self-contradictory response (e.g.
    # risk_level="high" + safe=true, observed live for a nonsense/gibberish
    # instruction that should have been refused) would still show a
    # green "safe to run" badge and offer one-click sandbox execution.
    final_safe = (
        not refused
        and llm_safe
        and llm_risk_level != "high"
        and syntax_result.valid
        and not safety_result.blocked
    )

    return ConversionResult(
        instruction=instruction,
        command=command,
        explanation=explanation,
        os=os_out,
        llm_risk_level=llm_risk_level,
        llm_safe=llm_safe,
        refused=refused,
        refusal_reason=refusal_reason,
        syntax=syntax_result,
        safety=safety_result,
        final_safe_to_show_as_runnable=final_safe,
        raw_model_output=raw,
        parse_error=parse_error,
    )
