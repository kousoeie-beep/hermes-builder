# Hermes Builder contributor instructions

- Python 3.11+ and standard library only for the bootstrap CLI.
- Use dataclasses for domain models.
- Never collect or persist API keys, tokens, passwords, cookies, or private keys.
- Run commands with argument arrays; never use `shell=True` with user input.
- Every mutating flow must support `--dry-run` or a plan-only equivalent.
- Interactive flows must have an answers-file path for CI and automation.
- Gateway defaults must be deny-by-default and least-privilege.
- Add tests for every planner policy or new answer field.
- Run `python3 -m unittest discover -s tests -v` and `bash -n install.sh` before handoff.
