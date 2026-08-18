"""Gradio UI for the Text-to-Command Agent — compact chat-style layout.

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
    "list all python files modified in the last day",
    "מה כתובת ה-IP של המחשב שלי",
    "create a zip backup of the src folder",
    "delete everything on this computer",
    "asdkj qwoiu banana purple 42",
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

.gradio-container { max-width: 720px !important; margin: 0 auto !important; }

.agent-topbar {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 6px 2px 14px 2px;
}
.agent-topbar .agent-icon {
    font-size: 22px;
    filter: drop-shadow(0 0 8px rgba(61, 220, 132, 0.55));
}
.agent-topbar .agent-title {
    font-weight: 800;
    font-size: 15.5px;
    background: linear-gradient(90deg, #3ddc84, #5aa9ff 65%, #a78bfa);
    -webkit-background-clip: text; background-clip: text; color: transparent;
}
.agent-topbar .agent-sub { font-size: 12px; color: var(--agent-muted); }

.chat-row { display: flex; margin: 0 0 10px 0; }
.chat-row.user { justify-content: flex-end; }
.chat-row.agent { justify-content: flex-start; }

.bubble-user {
    background: linear-gradient(135deg, #2a3f5f, #1e2f4a);
    color: #eaf1ff;
    padding: 9px 14px;
    border-radius: 14px 14px 3px 14px;
    max-width: 85%;
    font-size: 13.5px;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    box-shadow: 0 1px 3px rgba(0,0,0,0.25);
}

.bubble-agent-wrap { max-width: 92%; }

.term-card {
    border-radius: 12px 12px 12px 3px;
    border: 1px solid var(--agent-border);
    background: var(--agent-panel);
    overflow: hidden;
    font-family: 'Consolas', 'SFMono-Regular', 'Menlo', monospace;
    box-shadow: 0 1px 3px rgba(0,0,0,0.25);
}
.term-titlebar {
    display: flex;
    align-items: center;
    gap: 7px;
    padding: 6px 10px;
    background: #0d1218;
    border-bottom: 1px solid var(--agent-border);
}
.term-dot { width: 9px; height: 9px; border-radius: 50%; }
.term-dot.red { background: #ff5f57; }
.term-dot.yellow { background: #febc2e; }
.term-dot.green { background: #28c840; }
.term-label { margin-left: 6px; color: var(--agent-muted); font-size: 11px; }

.term-body { padding: 12px 14px; }
.term-command {
    color: var(--agent-green);
    font-size: 14px;
    white-space: pre-wrap;
    word-break: break-word;
    margin: 0 0 8px 0;
}
.term-command::before { content: "$ "; color: var(--agent-muted); }
.term-explain {
    color: var(--agent-text);
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-size: 12.5px;
    margin-bottom: 10px;
}

.badge-row { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 5px; }
.badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 3px 8px;
    border-radius: 999px;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-size: 10.5px;
    font-weight: 600;
    border: 1px solid transparent;
}
.badge.ok { background: rgba(61, 220, 132, 0.12); color: var(--agent-green); border-color: rgba(61, 220, 132, 0.35); }
.badge.bad { background: rgba(255, 95, 109, 0.12); color: var(--agent-red); border-color: rgba(255, 95, 109, 0.35); }
.badge.warn { background: rgba(255, 200, 87, 0.12); color: var(--agent-amber); border-color: rgba(255, 200, 87, 0.35); }
.badge.info { background: rgba(90, 169, 255, 0.12); color: var(--agent-blue); border-color: rgba(90, 169, 255, 0.35); }

.verdict-banner {
    margin-top: 10px;
    padding: 7px 11px;
    border-radius: 8px;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-weight: 700;
    font-size: 11.5px;
}
.verdict-banner.safe { background: rgba(61, 220, 132, 0.10); color: var(--agent-green); border: 1px solid rgba(61, 220, 132, 0.35); }
.verdict-banner.unsafe { background: rgba(255, 95, 109, 0.10); color: var(--agent-red); border: 1px solid rgba(255, 95, 109, 0.35); }

.refuse-card {
    border-radius: 12px 12px 12px 3px;
    border: 1px solid rgba(255, 95, 109, 0.4);
    background: linear-gradient(135deg, rgba(255, 95, 109, 0.10), rgba(255, 200, 87, 0.06));
    padding: 12px 14px;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}
.refuse-card .refuse-title {
    font-size: 13px;
    font-weight: 800;
    color: var(--agent-red);
    margin-bottom: 4px;
    display: flex;
    align-items: center;
    gap: 6px;
}
.refuse-card .refuse-reason { color: var(--agent-text); font-size: 12.5px; line-height: 1.45; }

.warn-card {
    border-radius: 12px 12px 12px 3px;
    border: 1px solid rgba(255, 200, 87, 0.4);
    background: rgba(255, 200, 87, 0.08);
    padding: 10px 14px;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    color: var(--agent-amber);
    font-weight: 600;
    font-size: 12.5px;
    border-radius: 12px 12px 12px 3px;
}

.sandbox-card {
    border-radius: 12px 12px 12px 3px;
    border: 1px solid var(--agent-border);
    background: var(--agent-panel);
    padding: 12px 14px;
    font-family: 'Consolas', 'SFMono-Regular', 'Menlo', monospace;
    color: var(--agent-text);
    font-size: 12px;
    white-space: pre-wrap;
    word-break: break-word;
}

.empty-hint {
    text-align: center;
    color: var(--agent-muted);
    font-size: 12.5px;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    padding: 30px 10px;
}

#input_row { gap: 6px !important; }
#send_btn { min-width: 44px !important; max-width: 60px !important; }

footer { display: none !important; }
"""


def _badge(ok: bool, ok_text: str, bad_text: str) -> str:
    cls = "ok" if ok else "bad"
    icon = "✅" if ok else "❌"
    text = ok_text if ok else bad_text
    return f"<span class='badge {cls}'>{icon} {html.escape(text)}</span>"


def _risk_badge(risk_level: str) -> str:
    cls = {"low": "ok", "medium": "warn", "high": "bad"}.get(risk_level, "info")
    return f"<span class='badge {cls}'>⚡ {html.escape(risk_level)}</span>"


def _result_card(result) -> str:
    format_ok = result.parse_error is None
    badges = "".join([
        _badge(format_ok, "format ok", "format error"),
        _badge(result.syntax.valid, "syntax ok", "syntax error"),
        _risk_badge(result.llm_risk_level),
        _badge(not result.safety.blocked, "security clear", "BLOCKED"),
    ])

    safety_detail = ""
    if result.safety.blocked:
        reasons = "; ".join(f"{name}: {reason}" for name, reason in result.safety.matched_rules)
        safety_detail = f"<div class='badge-row'><span class='badge bad'>🛡️ {html.escape(reasons)}</span></div>"

    verdict_safe = result.final_safe_to_show_as_runnable
    verdict_cls = "safe" if verdict_safe else "unsafe"
    verdict_text = "✅ safe to run" if verdict_safe else "⛔ not safe to auto-run"

    return f"""<div class="term-card">
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
    </div>"""


def _refusal_card(reason: str, title: str = "🚫 Request refused") -> str:
    return (
        f"<div class='refuse-card'><div class='refuse-title'>{title}</div>"
        f"<div class='refuse-reason'>{html.escape(reason)}</div></div>"
    )


def _sandbox_card(sandbox_result) -> str:
    if not sandbox_result.ran:
        return _refusal_card(sandbox_result.error or "Unknown error", title="❌ Sandbox execution failed")
    out = f"exit code: {sandbox_result.exit_code}\n\n--- stdout ---\n{sandbox_result.stdout or '(empty)'}"
    if sandbox_result.stderr:
        out += f"\n\n--- stderr ---\n{sandbox_result.stderr}"
    return f"<div class='sandbox-card'>{html.escape(out)}</div>"


def _render_transcript(history) -> str:
    if not history:
        return "<div class='empty-hint'>⚡ Ask for a command, e.g. “list files changed in the last day”</div>"

    parts = []
    for turn in history:
        parts.append(
            f"<div class='chat-row user'><div class='bubble-user'>{html.escape(turn['instruction'])}</div></div>"
        )
        parts.append(
            f"<div class='chat-row agent'><div class='bubble-agent-wrap'>{turn['agent_html']}</div></div>"
        )
        if turn.get("sandbox_html"):
            parts.append(
                f"<div class='chat-row agent'><div class='bubble-agent-wrap'>{turn['sandbox_html']}</div></div>"
            )
    return "".join(parts)


def on_send(instruction, os_choice, prompt_version, history):
    history = list(history or [])
    can_run = False

    if not instruction or not instruction.strip():
        return _render_transcript(history), history, "", gr.update(interactive=False)

    try:
        result = convert(instruction, os_name=os_choice, prompt_version=prompt_version)
    except RuntimeError as e:
        agent_html = _refusal_card(str(e), title="⚠️ Configuration error")
        history.append({"instruction": instruction, "agent_html": agent_html, "command": None})
        return _render_transcript(history), history, "", gr.update(interactive=False)

    if result.refused:
        agent_html = _refusal_card(result.refusal_reason)
        command = None
    else:
        agent_html = _result_card(result)
        can_run = result.final_safe_to_show_as_runnable and docker_available()
        command = result.command if can_run else None

    history.append({"instruction": instruction, "agent_html": agent_html, "command": command})
    return _render_transcript(history), history, "", gr.update(interactive=can_run)


def on_run_sandbox(history):
    history = list(history or [])
    if not history or not history[-1].get("command"):
        return _render_transcript(history), history

    sandbox_result = run_in_sandbox(history[-1]["command"])
    history[-1]["sandbox_html"] = _sandbox_card(sandbox_result)
    return _render_transcript(history), history


with gr.Blocks(title="Text to Command Agent") as demo:
    gr.HTML(
        """
        <div class="agent-topbar">
            <span class="agent-icon">⚡</span>
            <div>
                <div class="agent-title">Command Agent</div>
                <div class="agent-sub">text &rarr; terminal command, checked for syntax &amp; safety</div>
            </div>
        </div>
        """
    )

    transcript = gr.HTML(_render_transcript([]))
    history_state = gr.State([])

    with gr.Row(elem_id="input_row"):
        instruction_box = gr.Textbox(
            show_label=False,
            placeholder="Ask for a command…",
            scale=8,
            container=False,
        )
        send_btn = gr.Button("➤", variant="primary", scale=1, elem_id="send_btn")

    with gr.Accordion("⚙️ Settings", open=False):
        with gr.Row():
            os_dropdown = gr.Dropdown(OS_CHOICES, value=OS_CHOICES[0], label="Target OS/shell", scale=2)
            prompt_version_dropdown = gr.Dropdown(
                ["v1", "v2", "v3"], value="v3", label="Prompt version", scale=1,
            )
        run_btn = gr.Button("▶️ Run last command in Docker sandbox (bonus)", interactive=False, size="sm")
        gr.Markdown(f"Docker sandbox: **{'available' if docker_available() else 'unavailable — start Docker to enable'}**")
        gr.Examples(examples=[[e] for e in EXAMPLES], inputs=[instruction_box], label="Examples")

    send_btn.click(
        on_send,
        inputs=[instruction_box, os_dropdown, prompt_version_dropdown, history_state],
        outputs=[transcript, history_state, instruction_box, run_btn],
    )
    instruction_box.submit(
        on_send,
        inputs=[instruction_box, os_dropdown, prompt_version_dropdown, history_state],
        outputs=[transcript, history_state, instruction_box, run_btn],
    )
    run_btn.click(
        on_run_sandbox,
        inputs=[history_state],
        outputs=[transcript, history_state],
    )

if __name__ == "__main__":
    demo.launch(css=CUSTOM_CSS, theme=gr.themes.Soft(primary_hue="emerald", neutral_hue="slate"))
