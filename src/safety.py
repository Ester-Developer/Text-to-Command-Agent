"""
Independent, non-LLM safety gate.

This exists so a single bad "safe": true from the model can never be the
only thing standing between the user and a destructive command
(defense in depth, see prompts.py iteration v3 notes). Every command,
regardless of what the LLM says about it, is re-checked here with plain
pattern matching before it is shown as "safe to run" or handed to the
sandbox.
"""

import re
from dataclasses import dataclass, field


@dataclass
class SafetyResult:
    blocked: bool
    matched_rules: list = field(default_factory=list)

    @property
    def verdict(self) -> str:
        return "BLOCKED" if self.blocked else "ALLOWED"


# Each rule: (name, compiled regex, human-readable reason)
_DANGEROUS_PATTERNS = [
    ("rm_root_or_wildcard_recursive",
     re.compile(r"\brm\s+(-[a-zA-Z]*[rf][a-zA-Z]*\s+)+(/(\s|$)|~(\s|$)|\*|\.\.?/?\*?\s*$)"),
     "Recursive/forced delete targeting root, home, or a wildcard"),

    ("rm_rf_generic",
     re.compile(r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f[a-zA-Z]*\b|\brm\s+-[a-zA-Z]*f[a-zA-Z]*r[a-zA-Z]*\b"),
     "Forced recursive delete (rm -rf variants)"),

    ("dd_to_device",
     re.compile(r"\bdd\s+.*of=/dev/"),
     "Writing raw data directly to a block device (can destroy disks/partitions)"),

    ("mkfs",
     re.compile(r"\bmkfs(\.\w+)?\b"),
     "Formatting a filesystem"),

    ("fork_bomb",
     re.compile(r":\(\)\s*\{\s*:\|:&\s*\}\s*;\s*:"),
     "Fork bomb"),

    ("disk_partition_tools",
     re.compile(r"\b(fdisk|parted|gparted)\b.*\b/dev/"),
     "Direct disk partition manipulation"),

    ("chmod_777_root",
     re.compile(r"\bchmod\s+-R\s+777\s+/(\s|$)"),
     "Recursively opening permissions on the entire filesystem"),

    ("chown_root_recursive",
     re.compile(r"\bchown\s+-R\s+.*\s+/(\s|$)"),
     "Recursively changing ownership of the entire filesystem"),

    ("shutdown_reboot",
     re.compile(r"\b(shutdown|reboot|halt|poweroff)\b"),
     "Shutting down or rebooting the machine"),

    ("kill_all",
     re.compile(r"\bkill(all)?\s+(-9\s+)?-1\b|\bpkill\s+-9\s+-1\b"),
     "Killing all processes on the system"),

    ("curl_pipe_shell",
     re.compile(r"\b(curl|wget)\b[^|]*\|\s*(sudo\s+)?(bash|sh|zsh)\b"),
     "Piping a downloaded remote script directly into a shell"),

    ("overwrite_passwd_shadow",
     re.compile(r">\s*/etc/(passwd|shadow|sudoers)\b"),
     "Overwriting a critical system credentials/permissions file"),

    ("disable_firewall",
     re.compile(r"\b(ufw\s+disable|iptables\s+-F|systemctl\s+stop\s+firewalld)\b"),
     "Disabling the firewall"),

    ("wipe_env_var_secrets",
     re.compile(r"\bexport\s+HISTFILE=/dev/null\b|\bhistory\s+-c\b.*rm\b"),
     "Clearing shell history in combination with destructive actions (evasion pattern)"),

    ("del_windows_wide",
     re.compile(r"\b(del|erase)\s+/[sSqQ].*\*\.\*|\brmdir\s+/[sS]\s+/[qQ]\s+[a-zA-Z]:\\\\?\s*$", re.IGNORECASE),
     "Windows recursive/wildcard delete of a wide path"),

    ("format_windows_drive",
     re.compile(r"\bformat\s+[a-zA-Z]:", re.IGNORECASE),
     "Formatting a Windows drive"),

    ("diskpart",
     re.compile(r"\bdiskpart\b", re.IGNORECASE),
     "Invoking diskpart (can repartition/erase disks)"),

    ("reg_delete_wide",
     re.compile(r"\breg\s+delete\s+HK(LM|CU)\\\\?\s*/f", re.IGNORECASE),
     "Deleting a broad Windows registry hive"),
]


def check_command(command: str) -> SafetyResult:
    """Run the command text through every dangerous-pattern rule.

    Returns SafetyResult(blocked=True, matched_rules=[(name, reason), ...])
    if any rule matches; the command should never be auto-executed (sandbox
    included) when blocked=True, regardless of the model's own "safe" flag.
    """
    if not command or not command.strip():
        return SafetyResult(blocked=False, matched_rules=[])

    matched = []
    for name, pattern, reason in _DANGEROUS_PATTERNS:
        if pattern.search(command):
            matched.append((name, reason))

    return SafetyResult(blocked=len(matched) > 0, matched_rules=matched)
