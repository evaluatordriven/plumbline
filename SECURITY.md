# Security

**Reporting a problem.** If you find a way to make the emitter write a record that misstates a job's
history, or to make `kit/plumbline_verify.py` accept a record it should reject, please report it privately
through GitHub's "Report a vulnerability" button on this repository's Security tab. Please do not open a
public issue for it first.

**What counts.** A record that verifies but breaks a custody/v1 requirement or an `x-plumbline` rule; a
digest, ledger or evidence check that can be bypassed; a hand-entered time that reaches a record unflagged;
or tooling that writes something into a record that its inputs did not say.

**What to expect.** An acknowledgement within a week. A fix is released as a new version, and CHANGELOG.md
says what changed and why, crediting the reporter unless they ask otherwise.

**Secrets.** No tool here reads a key from a fixed path: model keys come from the environment or a key file
you name. Never commit a key, a model log containing one, or held-out evaluation material.
