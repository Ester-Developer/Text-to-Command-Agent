"""Gradio UI for the Text-to-Command Agent.

Run with: python app.py
Requires GEMINI_API_KEY to be set (see .env.example) - free key from
https://aistudio.google.com/apikey
"""

import html

import gradio as gr

from src.converter import convert
from src.sandbox import run_in_sandbox, docker_available

OS_CHOICES = ["linux/macOS (bash)", "Windows (PowerShell)", "Windows (cmd.exe)"]

EXAMPLES = [
    ["list all python files modified in the last day", "linux/macOS (bash)", "v3"],
    ["מה כתובת ה-IP של המחשב שלי", "linux/macOS (bash)", "v3"],
    ["create a zip backup of the src folder", "linux/macOS (bash)", "v3"],
    ["delete everything on this computer", "linux/macOS (bash)", "v3"],
    ["asdkj qwoiu banana purple 42", "linux/macOS (bash)", "v3"],
]

CUSTOM_CSS = """
:root {
    --agent-bg: #0b0f14;
    --agent-panel: #11161d;
    --agent-border: #1f2733;
    --agent-green: #3ddc84;
    --agent-red: #ff5f6d;
    --agent-amber: #ffc857;
    --agent-blue: #5aa9ff;
    --agent-text: #d7e0ea;
    --agent-muted: #8593a6;
}

.agent-hero {
    display: flex;
    align-items: center;
    gap: 18px;
    padding: 22px 26px;
    border-radius: 18px;
    background: linear-gradient(135deg, #0f1620 0%, #16202b 55%, #12241f 100%);
    border: 1px solid var(--agent-border);
    margin-bottom: 6px;
}
.agent-hero .agent-icon {
    font-size: 42px;
    line-height: 1;
    filter: drop-shadow(0 0 14px rgba(61, 220, 132, 0.55));
    animation: agent-pulse 3s ease-in-out infinite;
}
@keyframes agent-pulse {
    0%, 100% { filter: drop-shadow(0 0 10px rgba(61, 220, 132, 0.45)); transform: scale(1); }
    50% { filter: drop-shadow(0 0 20px rgba(61, 220, 132, 0.85)); transform: scale(1.05); }
}
.agent-hero h1 {
    margin: 0;
    font-size: 26px;
    background: linear-gradient(90deg, #3ddc84, #5aa9ff 60%, #a78bfa);
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
    font-weight: 800;
    letter-spacing: 0.3px;
}
.agent-hero p {
    margin: 4px 0 0 0;
    color: var(--agent-muted);
    font-size: 14px;
}

.term-card {
    border-radius: 14px;
    border: 1px solid var(--agent-border);
    background: var(--agent-panel);
    overflow: hidden;
    font-family: 'Consolas', 'SFMono-Regular', 'Menlo', monospace;
}
.term-titlebar {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 9px 12px;
    background: #0d1218;
    border-bottom: 1px solid var(--agent-border);
}
.term-dot { width: 11px; height: 11px; border-radius: 50%; }
.term-dot.red { background: #ff5f57; }
.term-dot.yellow { background: #febc2e; }
.term-dot.green { background: #28c840; }
.term-label { margin-left: 8px; color: var(--agent-muted); font-size: 12px; }

.term-body { padding: 16px 18px; }
.term-command {
    color: var(--agent-green);
    font-size: 15px;
    white-space: pre-wrap;
    word-break: break-word;
    margin: 0 0 10px 0;
}
.term-command::before { content: "$ "; color: var(--agent-muted); }
.term-explain {
    color: var(--agent-text);
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-size: 13.5px;
    margin-bottom: 14px;
}

.badge-row { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 6px; }
.badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 5px 10px;
    border-radius: 999px;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-size: 12px;
    font-weight: 600;
    border: 1px solid transparent;
}
.badge.ok { background: rgba(61, 220, 132, 0.12); color: var(--agent-green); border-color: rgba(61, 220, 132, 0.35); }
.badge.bad { background: rgba(255, 95, 109, 0.12); color: var(--agent-red); border-color: rgba(255, 95, 109, 0.35); }
.badge.warn { background: rgba(255, 200, 87, 0.12); color: var(--agent-amber); border-color: rgba(255, 200, 87, 0.35); }
.badge.info { background: rgba(90, 169, 255, 0.12); color: var(--agent-blue); border-color: rgba(90, 169, 255, 0.35); }

.verdict-banner {
    margin-top: 14px;
    padding: 10px 14px;
    border-radius: 10px;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-weight: 700;
    font-size: 13.5px;
}
.verdict-banner.safe { background: rgba(61, 220, 132, 0.10); color: var(--agent-green); border: 1px solid rgba(61, 220, 132, 0.35); }
.verdict-banner.unsafe { background: rgba(255, 95, 109, 0.10); color: var(--agent-red); border: 1px solid rgba(255, 95, 109, 0.35); }

.refuse-card {
    border-radius: 14px;
    border: 1px solid rgba(255, 95, 109, 0.4);
    background: linear-gradient(135deg, rgba(255, 95, 109, 0.10), rgba(255, 200, 87, 0.06));
    padding: 20px 22px;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}
.refuse-card .refuse-title {
    font-size: 16px;
    font-weight: 800;
    color: var(--agent-red);
    margin-bottom: 8px;
    display: flex;
    align-items: center;
    gap: 8px;
}
.refuse-card .refuse-reason { color: var(--agent-text); font-size: 14px; line-height: 1.5; }

.warn-card {
    border-radius: 14px;
    border: 1px solid rgba(255, 200, 87, 0.4);
    background: rgba(255, 200, 87, 0.08);
    padding: 18px 20px;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    color: var(--agent-amber);
    font-weight: 600;
}

.sandbox-card {
    border-radius: 14px;
    border: 1px solid var(--agent-border);
    background: var(--agent-panel);
    padding: 16px 18px;
    font-family: 'Consolas', 'SFMono-Regular', 'Menlo', monospace;
    color: var(--agent-text);
    font-size: 13px;
    white-space: pre-wrap;
    word-break: break-word;
}

/* Hide Gradio's built-in footer (its "Use via API" / "Built with Gradio" /
   "Settings" strings auto-translate to the browser's locale, e.g. Hebrew,
   which fights the app's otherwise English UI) - replaced with our own
   English status line below. */
footer { display: none !important; }
"""


def _placeholder_html() -> str:
    return (
        "<div class='warn-card' style='opacity:0.7;'>"
        "🕐 Convert an instruction to see the result here."
        "</div>"
    )


def _bad_input_html() -> str:
    return (
        "<div class='warn-card'>"
        "✋ Please type an instruction first — the box is empty."
        "</div>"
    )


def _error_html(message: str) -> str:
    return (
        "<div class='refuse-card'>"
        "<div class='refuse-title'>⚠️ Configuration error</div>"
        f"<div class='refuse-reason'>{html.escape(message)}</div>"
        "</div>"
    )


def _refusal_html(result) -> str:
    return (
        "<div class='refuse-card'>"
        "<div class='refuse-title'>🚫 Request refused</div>"
        f"<div class='refuse-reason'>{html.escape(result.refusal_reason)}</div>"
        "</div>"
    )


def _badge(ok: bool, ok_text: str, bad_text: str) -> str:
    cls = "ok" if ok else "bad"
    icon = "✅" if ok else "❌"
    text = ok_text if ok else bad_text
    return f"<span class='badge {cls}'>{icon} {html.escape(text)}</span>"


def _risk_badge(risk_level: str) -> str:
    cls = {"low": "ok", "medium": "warn", "high": "bad"}.get(risk_level, "info")
    return f"<span class='badge {cls}'>⚡ risk: {html.escape(risk_level)}</span>"


def _result_html(result) -> str:
    format_ok = result.parse_error is None
    badges = "".join([
        _badge(format_ok, "format: valid JSON", f"format: {result.parse_error}"),
        _badge(result.syntax.valid, f"syntax: {result.syntax.reason}", f"syntax: {result.syntax.reason}"),
        _risk_badge(result.llm_risk_level),
        _badge(not result.safety.blocked, "security: clear", "security: BLOCKED"),
    ])

    safety_detail = ""
    if result.safety.blocked:
        reasons = "; ".join(f"{name}: {reason}" for name, reason in result.safety.matched_rules)
        safety_detail = (
            f"<div class='badge-row'><span class='badge bad'>🛡️ {html.escape(reasons)}</span></div>"
        )

    verdict_safe = result.final_safe_to_show_as_runnable
    verdict_cls = "safe" if verdict_safe else "unsafe"
    verdict_text = "✅ Verdict: safe to run" if verdict_safe else "⛔ Verdict: not safe to auto-run"

    return f"""
    <div class="term-card">
      <div class="term-titlebar">
        <span class="term-dot red"></span><span class="term-dot yellow"></span><span class="term-dot green"></span>
        <span class="term-label">{html.escape(result.os)}</span>
      </div>
      <div class="term-body">
        <p class="term-command">{html.escape(result.command)}</p>
        <p class="term-explain">{html.escape(result.explanation)}</p>
        <div class="badge-row">{badges}</div>
        {safety_detail}
        <div class="verdict-banner {verdict_cls}">{verdict_text}</div>
      </div>
    </div>
    """


def on_convert(instruction, os_choice, prompt_version):
    if not instruction or not instruction.strip():
        return _bad_input_html(), gr.update(interactive=False), None

    try:
        result = convert(instruction, os_name=os_choice, prompt_version=prompt_version)
    except RuntimeError as e:
        return _error_html(str(e)), gr.update(interactive=False), None

    if result.refused:
        return _refusal_html(result), gr.update(interactive=False), None

    report = _result_html(result)
    can_run = result.final_safe_to_show_as_runnable and docker_available()
    return report, gr.update(interactive=can_run), result.command if can_run else None


def on_run_sandbox(command):
    if not command:
        return "<div class='warn-card'>No safe command available to run.</div>"
    result = run_in_sandbox(command)
    if not result.ran:
        return f"<div class='refuse-card'><div class='refuse-title'>❌ Sandbox execution failed</div><div class='refuse-reason'>{html.escape(result.error or '')}</div></div>"

    out = f"exit code: {result.exit_code}\n\n--- stdout ---\n{result.stdout or '(empty)'}"
    if result.stderr:
        out += f"\n\n--- stderr ---\n{result.stderr}"
    return f"<div class='sandbox-card'>{html.escape(out)}</div>"


with gr.Blocks(title="Text to Command Agent") as demo:
    gr.HTML(
        """
        <div class="agent-hero">
            <div class="agent-icon">⚡🖥️</div>
            <div>
                <h1>Text to Command Agent</h1>
                <p>Free-text instruction &rarr; runnable terminal command, with an independent syntax + security gate on every suggestion.</p>
            </div>
        </div>
        """
    )

    with gr.Row():
        with gr.Column(scale=2):
            instruction_box = gr.Textbox(
                label="Instruction (natural language)",
                placeholder="e.g. list all python files modified in the last day",
                lines=3,
            )
            with gr.Row():
                os_dropdown = gr.Dropdown(OS_CHOICES, value=OS_CHOICES[0], label="Target OS/shell")
                prompt_version_dropdown = gr.Dropdown(
                    ["v1", "v2", "v3"], value="v3",
                    label="Prompt version (for comparing iterations)",
                )
            convert_btn = gr.Button("⚡ Convert", variant="primary")

            gr.Examples(
                examples=EXAMPLES,
                inputs=[instruction_box, os_dropdown, prompt_version_dropdown],
                label="Try an example",
            )

        with gr.Column(scale=3):
            output_html = gr.HTML(_placeholder_html())
            run_btn = gr.Button("▶️ Run in Docker sandbox (bonus)", interactive=False)
            sandbox_output = gr.HTML()

    hidden_command_state = gr.State(None)

    convert_btn.click(
        on_convert,
        inputs=[instruction_box, os_dropdown, prompt_version_dropdown],
        outputs=[output_html, run_btn, hidden_command_state],
    )

    run_btn.click(
        on_run_sandbox,
        inputs=[hidden_command_state],
        outputs=[sandbox_output],
    )

    gr.Markdown(
        "---\n"
        f"Docker sandbox available: **{'yes' if docker_available() else 'no (install/start Docker to enable)'}**"
    )

if __name__ == "__main__":
    demo.launch(css=CUSTOM_CSS, theme=gr.themes.Soft(primary_hue="emerald", neutral_hue="slate"))
