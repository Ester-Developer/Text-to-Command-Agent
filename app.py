"""Gradio UI for the Text-to-Command Agent — light theme, persistent result panel.

Run with: python app.py
Requires GEMINI_API_KEY to be set (see .env.example) - free key from
https://aistudio.google.com/apikey
"""

import html

import gradio as gr

from src.converter import convert
from src.sandbox import run_in_sandbox, docker_available

OS_CHOICES = ["linux/macOS (bash)", "Windows (PowerShell)", "Windows (cmd.exe)"]

# The sandbox container (python:3.11-slim) is Linux-based, so it can only
# actually execute bash/POSIX commands - a Windows command like "ipconfig"
# would just fail inside it with "command not found", which would be
# misleading (looks like a sandbox failure, but is really just an OS
# mismatch). Only offer sandbox execution when the generated command
# targets this OS.
SANDBOX_COMPATIBLE_OS = "linux/macOS (bash)"

EXAMPLES = [
    "list all python files modified in the last day",
    "what is my computer's IP address",
    "create a zip backup of the src folder",
    "delete everything on this computer",
    "asdkj qwoiu banana purple 42",
]

LOGO_SVG = """
<svg width="52" height="52" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg" aria-label="Command Agent logo">
  <defs>
    <linearGradient id="agentBg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#132018"/>
      <stop offset="100%" stop-color="#0d1a2b"/>
    </linearGradient>
    <linearGradient id="agentGlow" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#3ddc84"/>
      <stop offset="100%" stop-color="#5aa9ff"/>
    </linearGradient>
  </defs>
  <rect x="2" y="2" width="60" height="60" rx="16" fill="url(#agentBg)" stroke="#1f2733" stroke-width="2"/>
  <path d="M18 22 L30 32 L18 42" fill="none" stroke="url(#agentGlow)" stroke-width="5.5" stroke-linecap="round" stroke-linejoin="round"/>
  <line x1="34" y1="42" x2="48" y2="42" stroke="url(#agentGlow)" stroke-width="5.5" stroke-linecap="round"/>
</svg>
"""

# Light palette applied to BOTH the light and dark theme token slots, so the
# UI stays light regardless of the visitor's OS/browser color-scheme setting.
# The Result panel's "term-card" is a deliberate exception: it keeps a dark,
# real-terminal look (see the .term-card variable overrides in CUSTOM_CSS)
# for visual contrast against the rest of the light page.
_BG = "#eef1f8"
_PANEL = "#ffffff"
_PANEL2 = "#f4f6fb"
_BORDER = "#dfe4ee"
_TEXT = "#1e2433"
_MUTED = "#697086"
_GREEN = "#17a865"

TERM_GREEN = "#4ade80"

LIGHT_THEME = gr.themes.Base(primary_hue="emerald", neutral_hue="slate").set(
    body_background_fill=_BG, body_background_fill_dark=_BG,
    body_text_color=_TEXT, body_text_color_dark=_TEXT,
    body_text_color_subdued=_MUTED, body_text_color_subdued_dark=_MUTED,
    background_fill_primary=_PANEL, background_fill_primary_dark=_PANEL,
    background_fill_secondary=_PANEL2, background_fill_secondary_dark=_PANEL2,
    border_color_primary=_BORDER, border_color_primary_dark=_BORDER,
    block_background_fill=_PANEL, block_background_fill_dark=_PANEL,
    block_border_color=_BORDER, block_border_color_dark=_BORDER,
    block_label_background_fill=_PANEL2, block_label_background_fill_dark=_PANEL2,
    block_label_text_color=_MUTED, block_label_text_color_dark=_MUTED,
    block_title_text_color=_TEXT, block_title_text_color_dark=_TEXT,
    panel_background_fill=_PANEL, panel_background_fill_dark=_PANEL,
    panel_border_color=_BORDER, panel_border_color_dark=_BORDER,
    input_background_fill=_PANEL2, input_background_fill_dark=_PANEL2,
    input_background_fill_hover=_PANEL2, input_background_fill_hover_dark=_PANEL2,
    input_background_fill_focus=_PANEL, input_background_fill_focus_dark=_PANEL,
    input_border_color=_BORDER, input_border_color_dark=_BORDER,
    input_border_color_hover=_GREEN, input_border_color_hover_dark=_GREEN,
    input_placeholder_color=_MUTED, input_placeholder_color_dark=_MUTED,
    button_primary_background_fill=_GREEN, button_primary_background_fill_dark=_GREEN,
    button_primary_background_fill_hover=_GREEN, button_primary_background_fill_hover_dark=_GREEN,
    button_primary_text_color="#ffffff", button_primary_text_color_dark="#ffffff",
    button_primary_text_color_hover="#ffffff", button_primary_text_color_hover_dark="#ffffff",
    button_secondary_background_fill=_PANEL, button_secondary_background_fill_dark=_PANEL,
    button_secondary_background_fill_hover=_PANEL2, button_secondary_background_fill_hover_dark=_PANEL2,
    button_secondary_text_color=_TEXT, button_secondary_text_color_dark=_TEXT,
    button_secondary_text_color_hover=_TEXT, button_secondary_text_color_hover_dark=_TEXT,
    button_secondary_border_color=_BORDER, button_secondary_border_color_dark=_BORDER,
    button_secondary_border_color_hover=_GREEN, button_secondary_border_color_hover_dark=_GREEN,
    checkbox_label_background_fill=_PANEL, checkbox_label_background_fill_dark=_PANEL,
    checkbox_label_background_fill_hover=_PANEL2, checkbox_label_background_fill_hover_dark=_PANEL2,
    checkbox_label_text_color=_TEXT, checkbox_label_text_color_dark=_TEXT,
    link_text_color=_GREEN, link_text_color_dark=_GREEN,
    link_text_color_hover=_GREEN, link_text_color_hover_dark=_GREEN,
)

# Belt-and-suspenders: also force the light (non-"dark") class state at
# load, so Gradio's own theme branch stays light even if the browser
# reports a dark color-scheme preference.
FORCE_LIGHT_JS = "() => { document.documentElement.classList.remove('dark'); }"

CUSTOM_CSS = f"""
:root {{
    --agent-bg: {_BG};
    --agent-panel: {_PANEL};
    --agent-panel2: {_PANEL2};
    --agent-border: {_BORDER};
    --agent-green: {_GREEN};
    --agent-red: #dc2626;
    --agent-amber: #c2760a;
    --agent-blue: #2563eb;
    --agent-text: {_TEXT};
    --agent-muted: {_MUTED};
}}

html, body {{
    background: radial-gradient(circle at 12% 0%, #e6f7ee 0%, transparent 42%),
                radial-gradient(circle at 88% 10%, #e8eefb 0%, transparent 38%),
                var(--agent-bg) !important;
}}
.gradio-container {{
    max-width: 1220px !important;
    width: 94% !important;
    margin: 0 auto !important;
    background: transparent !important;
}}

.agent-hero {{
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 20px 26px;
    margin: 8px 0 22px 0;
    border-radius: 18px;
    background: linear-gradient(135deg, #ffffff 0%, #f3fbf6 60%, #eef4fd 100%);
    border: 1px solid var(--agent-border);
    box-shadow: 0 1px 2px rgba(30, 41, 59, 0.04), 0 12px 28px rgba(30, 41, 59, 0.06);
}}
.agent-hero .agent-title {{
    font-weight: 800;
    font-size: 21px;
    background: linear-gradient(90deg, #17a865, #2563eb 65%, #8b5cf6);
    -webkit-background-clip: text; background-clip: text; color: transparent;
}}
.agent-hero .agent-sub {{ font-size: 13px; color: var(--agent-muted); margin-top: 3px; }}

.section-label {{
    font-size: 11.5px;
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    color: var(--agent-muted);
    margin: 0 0 10px 2px;
}}

/* --- Result card: kept as a real dark terminal window for contrast --- */
.term-card {{
    --agent-panel: #0f172a;
    --agent-panel2: #0b1220;
    --agent-border: #24314a;
    --agent-text: #e6edf7;
    --agent-muted: #93a1bd;
    --agent-green: {TERM_GREEN};
    --agent-red: #f87171;
    --agent-amber: #fbbf24;
    --agent-blue: #7dabff;
    border-radius: 14px;
    border: 1px solid var(--agent-border);
    background: var(--agent-panel);
    overflow: hidden;
    font-family: 'Consolas', 'SFMono-Regular', 'Menlo', monospace;
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.15), 0 16px 32px rgba(15, 23, 42, 0.18);
}}
.term-titlebar {{
    display: flex;
    align-items: center;
    gap: 7px;
    padding: 9px 14px;
    background: var(--agent-panel2);
    border-bottom: 1px solid var(--agent-border);
}}
.term-dot {{ width: 10px; height: 10px; border-radius: 50%; }}
.term-dot.red {{ background: #ff5f57; }}
.term-dot.yellow {{ background: #febc2e; }}
.term-dot.green {{ background: #28c840; }}
.term-label {{ margin-left: 6px; color: var(--agent-muted); font-size: 11.5px; }}

.term-body {{ padding: 18px 20px; }}
.term-command {{
    color: var(--agent-green);
    font-size: 15.5px;
    white-space: pre-wrap;
    word-break: break-word;
    margin: 0 0 10px 0;
}}
.term-command::before {{ content: "$ "; color: var(--agent-muted); }}
.term-explain {{
    color: var(--agent-text);
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-size: 13px;
    margin-bottom: 12px;
}}

.badge-row {{ display: flex; flex-wrap: wrap; gap: 7px; margin-bottom: 6px; }}
.badge {{
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 4px 9px;
    border-radius: 999px;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-size: 11px;
    font-weight: 600;
    border: 1px solid transparent;
}}
.badge.ok {{ background: rgba(74, 222, 128, 0.14); color: var(--agent-green); border-color: rgba(74, 222, 128, 0.35); }}
.badge.bad {{ background: rgba(248, 113, 113, 0.14); color: var(--agent-red); border-color: rgba(248, 113, 113, 0.35); }}
.badge.warn {{ background: rgba(251, 191, 36, 0.14); color: var(--agent-amber); border-color: rgba(251, 191, 36, 0.35); }}
.badge.info {{ background: rgba(125, 171, 255, 0.14); color: var(--agent-blue); border-color: rgba(125, 171, 255, 0.35); }}

.verdict-banner {{
    margin-top: 12px;
    padding: 9px 13px;
    border-radius: 8px;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-weight: 700;
    font-size: 12.5px;
}}
.verdict-banner.safe {{ background: rgba(74, 222, 128, 0.12); color: var(--agent-green); border: 1px solid rgba(74, 222, 128, 0.35); }}
.verdict-banner.unsafe {{ background: rgba(248, 113, 113, 0.12); color: var(--agent-red); border: 1px solid rgba(248, 113, 113, 0.35); }}

.refuse-card {{
    border-radius: 14px;
    border: 1px solid #fecaca;
    background: linear-gradient(135deg, #fef2f2 0%, #fffaf0 100%);
    padding: 16px 20px;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    box-shadow: 0 1px 2px rgba(30, 41, 59, 0.03), 0 10px 22px rgba(30, 41, 59, 0.05);
}}
.refuse-card .refuse-title {{
    font-size: 14.5px;
    font-weight: 800;
    color: var(--agent-red);
    margin-bottom: 6px;
    display: flex;
    align-items: center;
    gap: 6px;
}}
.refuse-card .refuse-reason {{ color: var(--agent-text); font-size: 13.5px; line-height: 1.55; }}

.warn-card {{
    border-radius: 14px;
    border: 1px solid #fde68a;
    background: #fffbeb;
    padding: 14px 18px;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    color: #92620a;
    font-weight: 600;
    font-size: 13.5px;
}}

.sandbox-card {{
    --agent-text: #e6edf7;
    border-radius: 14px;
    border: 1px solid #24314a;
    background: #0f172a;
    padding: 14px 18px;
    font-family: 'Consolas', 'SFMono-Regular', 'Menlo', monospace;
    color: var(--agent-text);
    font-size: 12.5px;
    white-space: pre-wrap;
    word-break: break-word;
    margin-top: 12px;
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.12), 0 12px 24px rgba(15, 23, 42, 0.14);
}}

.empty-hint {{
    text-align: center;
    color: var(--agent-muted);
    font-size: 13px;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    padding: 52px 16px;
    border: 1.5px dashed var(--agent-border);
    border-radius: 14px;
    background: var(--agent-panel);
}}

.settings-card {{
    border: 1px solid var(--agent-border);
    background: var(--agent-panel);
    border-radius: 14px;
    padding: 16px 18px 8px 18px;
    box-shadow: 0 1px 2px rgba(30, 41, 59, 0.03), 0 10px 22px rgba(30, 41, 59, 0.05);
}}

#input_row {{ gap: 8px !important; margin-bottom: 18px !important; }}
#send_btn {{ min-width: 48px !important; max-width: 64px !important; }}

footer {{ display: none !important; }}

/* Safety net: some Gradio-internal elements (dropdown option lists,
   table rows, etc.) don't fully follow the theme's hover tokens and can
   render illegible text on hover. Force our palette on every common
   interactive/hoverable element. */
button:hover, .dropdown-arrow:hover,
ul.options li:hover, ul.options li.selected,
.item:hover, .item.selected,
li.item:hover {{
    color: var(--agent-text) !important;
    background-color: var(--agent-panel2) !important;
}}
ul.options {{ background: var(--agent-panel) !important; border-color: var(--agent-border) !important; }}
ul.options li {{ color: var(--agent-text) !important; }}

@media (max-width: 900px) {{
    .gradio-container {{ width: 96% !important; }}
    #main_columns {{ flex-direction: column !important; }}
    #main_columns > * {{ width: 100% !important; flex: 1 1 100% !important; }}
    .agent-hero {{ padding: 16px 18px; }}
}}
"""


def _badge(ok: bool, ok_text: str, bad_text: str) -> str:
    cls = "ok" if ok else "bad"
    icon = "✅" if ok else "❌"
    text = ok_text if ok else bad_text
    return f"<span class='badge {cls}'>{icon} {html.escape(text)}</span>"


def _risk_badge(risk_level: str) -> str:
    cls = {"low": "ok", "medium": "warn", "high": "bad"}.get(risk_level, "info")
    return f"<span class='badge {cls}'>⚡ {html.escape(risk_level)}</span>"


def _placeholder_html() -> str:
    return "<div class='empty-hint'>⚡ Ask for a command, e.g. “list files changed in the last day”</div>"


def _bad_input_html() -> str:
    return "<div class='warn-card'>✋ Type an instruction first — the box is empty.</div>"


def _result_card(result, os_choice: str) -> str:
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

    sandbox_note = ""
    if verdict_safe and os_choice != SANDBOX_COMPATIBLE_OS:
        sandbox_note = (
            "<p class='term-explain' style='margin-top:8px;'>"
            "🐳 Docker sandbox validation only supports linux/macOS (bash) commands "
            "— the container itself is Linux-based, so a Windows command would just "
            f"fail there with \"not found\" (switch Target OS to run it in the sandbox)."
            "</p>"
        )

    return f"""<div class="term-card">
      <div class="term-titlebar">
        <span class="term-dot red"></span><span class="term-dot yellow"></span><span class="term-dot green"></span>
        <span class="term-label">{html.escape(result.os)}</span>
      </div>
      <div class="term-body">
        <p class="term-command">{html.escape(result.command)}</p>
        <p class="term-explain">{html.escape(result.explanation)}</p>
        <div class="badge-row">{badges}</div>
        {sandbox_note}
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


def on_convert(instruction, os_choice, prompt_version):
    if not instruction or not instruction.strip():
        return _bad_input_html(), gr.update(visible=False), None, ""

    try:
        result = convert(instruction, os_name=os_choice, prompt_version=prompt_version)
    except RuntimeError as e:
        return _refusal_card(str(e), title="⚠️ Configuration error"), gr.update(visible=False), None, ""

    if result.refused:
        return _refusal_card(result.refusal_reason), gr.update(visible=False), None, ""

    can_run = (
        result.final_safe_to_show_as_runnable
        and docker_available()
        and os_choice == SANDBOX_COMPATIBLE_OS
    )
    return (
        _result_card(result, os_choice),
        gr.update(visible=can_run, interactive=can_run),
        (result.command if can_run else None),
        "",
    )


def on_run_sandbox(command):
    if not command:
        return ""
    return _sandbox_card(run_in_sandbox(command))


with gr.Blocks(title="Text to Command Agent") as demo:
    gr.HTML(f"""
        <div class="agent-hero">
            {LOGO_SVG}
            <div>
                <div class="agent-title">Command Agent</div>
                <div class="agent-sub">text &rarr; terminal command, checked for syntax &amp; safety</div>
            </div>
        </div>
    """)

    with gr.Row(elem_id="input_row"):
        instruction_box = gr.Textbox(
            show_label=False,
            placeholder="Ask for a command…",
            scale=8,
            container=False,
        )
        convert_btn = gr.Button("➤", variant="primary", scale=1, elem_id="send_btn")

    with gr.Row(elem_id="main_columns"):
        with gr.Column(scale=3, min_width=340):
            gr.HTML("<div class='section-label'>Result</div>")
            output_html = gr.HTML(_placeholder_html())
            run_btn = gr.Button("▶️ Run this command in Docker sandbox", visible=False, size="sm")
            sandbox_output = gr.HTML("")

        with gr.Column(scale=2, min_width=280):
            gr.HTML("<div class='section-label'>Settings</div>")
            with gr.Group(elem_classes=["settings-card"]):
                os_dropdown = gr.Dropdown(OS_CHOICES, value=OS_CHOICES[0], label="Target OS / shell")
                prompt_version_dropdown = gr.Dropdown(
                    ["v1", "v2", "v3"], value="v3", label="Prompt version",
                )

            with gr.Accordion("💡 Examples", open=False):
                for example in EXAMPLES:
                    ex_btn = gr.Button(example, size="sm", variant="secondary")
                    ex_btn.click(lambda e=example: e, outputs=instruction_box)

    hidden_command_state = gr.State(None)

    convert_btn.click(
        on_convert,
        inputs=[instruction_box, os_dropdown, prompt_version_dropdown],
        outputs=[output_html, run_btn, hidden_command_state, sandbox_output],
    )
    instruction_box.submit(
        on_convert,
        inputs=[instruction_box, os_dropdown, prompt_version_dropdown],
        outputs=[output_html, run_btn, hidden_command_state, sandbox_output],
    )
    run_btn.click(
        on_run_sandbox,
        inputs=[hidden_command_state],
        outputs=[sandbox_output],
    )

if __name__ == "__main__":
    demo.launch(css=CUSTOM_CSS, theme=LIGHT_THEME, js=FORCE_LIGHT_JS)
