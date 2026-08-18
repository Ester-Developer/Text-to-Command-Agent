"""Gradio UI for the Text-to-Command Agent.

Run with: python app.py
Requires ANTHROPIC_API_KEY to be set (see .env.example).
"""

import gradio as gr

from src.converter import convert
from src.sandbox import run_in_sandbox, docker_available

OS_CHOICES = ["linux/macOS (bash)", "Windows (PowerShell)", "Windows (cmd.exe)"]


def format_report(result) -> str:
    lines = []

    if result.refused:
        lines.append("### 🚫 Request refused")
        lines.append(f"**Reason:** {result.refusal_reason}")
        return "\n\n".join(lines)

    lines.append(f"### Command\n```\n{result.command}\n```")
    lines.append(f"**Explanation:** {result.explanation}")
    lines.append(f"**Target OS:** {result.os}")

    lines.append("### Evaluation")
    lines.append(f"- **Output format:** {'✅ valid JSON parsed' if not result.parse_error else '❌ ' + result.parse_error}")
    lines.append(f"- **Syntactic validity:** {'✅ ' + result.syntax.reason if result.syntax.valid else '❌ ' + result.syntax.reason}")
    lines.append(f"- **Model self-reported risk:** {result.llm_risk_level} (model says safe={result.llm_safe})")

    if result.safety.blocked:
        reasons = "; ".join(f"{name}: {reason}" for name, reason in result.safety.matched_rules)
        lines.append(f"- **Independent safety check:** ❌ BLOCKED — {reasons}")
    else:
        lines.append("- **Independent safety check:** ✅ no dangerous patterns matched")

    verdict = "✅ Safe to run" if result.final_safe_to_show_as_runnable else "⛔ Not safe to auto-run"
    lines.append(f"\n**Overall verdict:** {verdict}")

    return "\n\n".join(lines)


def on_convert(instruction, os_choice, prompt_version):
    if not instruction or not instruction.strip():
        return "Please enter an instruction.", gr.update(interactive=False), None

    try:
        result = convert(instruction, os_name=os_choice, prompt_version=prompt_version)
    except RuntimeError as e:
        return f"⚠️ {e}", gr.update(interactive=False), None

    report = format_report(result)
    can_run = result.final_safe_to_show_as_runnable and docker_available()
    return report, gr.update(interactive=can_run), result.command if can_run else None


def on_run_sandbox(command):
    if not command:
        return "No safe command available to run."
    result = run_in_sandbox(command)
    if not result.ran:
        return f"❌ Sandbox execution failed: {result.error}"
    out = f"**Exit code:** {result.exit_code}\n\n**stdout:**\n```\n{result.stdout or '(empty)'}\n```"
    if result.stderr:
        out += f"\n\n**stderr:**\n```\n{result.stderr}\n```"
    return out


with gr.Blocks(title="Text to Command Agent") as demo:
    gr.Markdown("# 🖥️ Text to Command Agent")
    gr.Markdown(
        "Convert a free-text instruction into a runnable terminal command. "
        "Every suggestion passes through an independent syntax and security check "
        "before it is ever offered to run."
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
            convert_btn = gr.Button("Convert", variant="primary")

        with gr.Column(scale=3):
            output_md = gr.Markdown(label="Result")
            run_btn = gr.Button("▶️ Run in Docker sandbox (bonus)", interactive=False)
            sandbox_output = gr.Markdown()

    hidden_command_state = gr.State(None)

    convert_btn.click(
        on_convert,
        inputs=[instruction_box, os_dropdown, prompt_version_dropdown],
        outputs=[output_md, run_btn, hidden_command_state],
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
    demo.launch()
