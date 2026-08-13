from __future__ import annotations


COMMANDS = "setup plan apply doctor catalog completion"


def completion_for(shell: str) -> str:
    if shell == "bash":
        return f"""_hermes_builder_complete() {{
  local cur
  cur="${{COMP_WORDS[COMP_CWORD]}}"
  COMPREPLY=( $(compgen -W "{COMMANDS}" -- "$cur") )
}}
complete -F _hermes_builder_complete hermes-builder
"""
    if shell == "zsh":
        return f"""#compdef hermes-builder
_arguments '1:command:({COMMANDS})'
"""
    if shell == "fish":
        return "\n".join(
            f"complete -c hermes-builder -f -a {command}"
            for command in COMMANDS.split()
        ) + "\n"
    raise ValueError(f"未対応のshellです: {shell}")
