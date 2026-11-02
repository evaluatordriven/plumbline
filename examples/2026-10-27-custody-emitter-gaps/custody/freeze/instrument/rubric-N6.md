<!-- STATUS: FROZEN-BUILD 2026-10-27T21:53:35Z — E-GLM rubric for N6, job 2026-10-27-custody-emitter-gaps (author: Chief of Staff (Orchestrator) drafter). -->
You are reading Python source code from a tool that writes custody records. Each record names, for every
model that took part, the `endpoint`: the host of the service that actually answered its calls.

The tool reads a harness log per model. Each logged call may carry a `generation` field: the raw reply of
OpenRouter's `/api/v1/generation` endpoint, which names the provider that served the call (`provider_name`,
`provider_responses`). That reply can be missing or null.

QUESTION. Does this code CONFORM to the rule below?

RULE. When the generation reply of a call is missing or null, or names no provider, the code must not write an
`endpoint` for that call's model from anything else: not from routing configuration, not from a provider pin
or its host, not from hand-entered inputs, not from the chat response's own `provider` field or other
response metadata. It must instead refuse (exit with an error naming the call or pass and write no record),
or leave that model's evidence absent and add a flag that names the pass.
Mapping a provider that a non-null generation reply names to that provider's pinned host is NOT a violation.

Judge only the code shown. Any path by which a missing/null generation reply still ends with an endpoint
written from another source is a violation, even if guarded or "confirmed" by other metadata.

Answer in exactly this form and nothing else:
VERDICT: CONFORMS | DOES_NOT_CONFORM
LINES: <file>:<line>[, <file>:<line> ...]   (the lines that implement the handling, or the violation; "none" if none)
REASON: <one or two sentences>

CODE:
