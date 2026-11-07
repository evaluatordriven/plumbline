"""Deliver one Architect escalation over a finished record; record the reply.

This is the script the escalation holder runs after ``loop()`` has returned.
``loop()`` does not call the Architect and does not import this module: the
rounds are over and what is missing is the analysis a human reads.

``deliver`` asks the Architect for its analysis, checks the optional proposed
packet, and hands the text to a transport that owns the address. Neither an
address nor a seat is named here: the plug supplies both, so the same script
serves any seat. A broken or incomplete Architect run -- a raise, no dict, no
text, blank text -- delivers nothing and writes nothing. It is not a send, so
a later finished run may still send once.

The facts that survive the process are on disk, under the record dir. The
delivery record is written before the transport is called, so a retry (even
after the module is reloaded) does not send twice, and a transport call that
raised still counts as made. What the transport returned is not copied into
the record: a send receipt is not a read-back. The record holds what was sent,
its sha256, and whether the call returned.

``decide`` records the Owner's reply beside the record and leaves
``terminal_state`` in ``summary.json`` and ``escalation.json`` alone. No state
name is introduced for an answered escalation, and no decision file is
implied: the shape of that act is still open.

Validation of ``proposed_packet`` is JSON Schema Draft 2020-12 against the
job-packet schema in this repo, read from the tree rather than restated. A
packet that validates but is ratified is not delivered; an invalid one is not
delivered; a valid unratified one rides along with the text and is never run.

Deliberately not settled here: option counts, clock arithmetic, the names of
the decision file and its fields, exit codes, held-out scanning, and the state
names an escalation passes through.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_PATH = os.path.join(_ROOT, "schemas", "job-packet.schema.json")

#: Written into the record dir. Its presence is the durable fact that the
#: transport has been called for this record.
DELIVERY_RECORD = "delivery.json"

#: Where ``decide`` puts the Owner's reply. Deliberately not a name the open
#: questions have settled.
REPLY_RECORD = "owner_reply.json"

_SCHEMAS: dict = {}


def deliver(record_dir, *, architect, transport):
    """Deliver the Architect's analysis once, and never twice.

    ``architect`` is a callable taking no arguments. A finished run returns a
    dict with a non-blank ``text``. ``proposed_packet`` is optional; a missing
    key and a null one mean the same thing, not present. Anything else, or a
    raise, is a broken or incomplete run: nothing is sent, nothing is written.

    ``transport`` is a callable that owns the address. It is called once, with
    the Architect's text unchanged as its first positional argument. Neither
    argument has a default; the caller supplies both.

    Returns a dict. On a send it has ``delivered`` True and ``sha256``, the
    digest of the text encoded as UTF-8, and that digest is also written into
    the record dir. On no send ``delivered`` is False and ``transport`` is not
    called. A transport that raises is not caught: the record already says the
    call was made, so a later attempt does not call it again.
    """
    os.makedirs(record_dir, exist_ok=True)
    earlier = _earlier_dispatch(record_dir)
    if earlier is not None:
        return {
            "delivered": bool(earlier.get("transport_returned")),
            "sha256": earlier.get("sha256"),
            "transport_called": False,
            "reason": "already dispatched; not sending again",
        }
    try:
        run = architect()
    except Exception as exc:
        return _not_delivered("the architect run raised: %s" % exc)
    text, refusal = _analysis(run)
    if refusal is not None:
        return _not_delivered(refusal)
    packet = run.get("proposed_packet")
    if packet is not None:
        accepted, why = _checked_packet(packet)
        if not accepted:
            return _not_delivered("the proposed packet does not validate: %s" % why)
        if packet.get("ratified") is True:
            return _not_delivered("the proposed packet is ratified; not delivered")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    record = {
        "architect_text": text,
        "sha256": digest,
        "transport_called": True,
        "transport_returned": False,
        "recorded_at": _stamp(),
        "recorded_by": "kit.escalate.deliver",
    }
    path = _delivery_path(record_dir)
    _write_json(path, record)
    transport(text)
    record["transport_returned"] = True
    record["returned_at"] = _stamp()
    _write_json(path, record)
    return {
        "delivered": True,
        "sha256": digest,
        "transport_called": True,
        "transport_returned": True,
        "recorded_at": record["recorded_at"],
    }


def decide(record_dir, reply):
    """Record the Owner's reply beside the record; touch nothing else.

    ``reply`` is the Owner's answer, passed positionally. Its exact text is
    written into the record dir. ``terminal_state`` in ``summary.json`` and
    ``escalation.json`` is not read, rewritten or moved: what an answered
    escalation becomes is not settled here.
    """
    if isinstance(reply, str):
        text = reply
    else:
        text = json.dumps(reply, ensure_ascii=False, sort_keys=True, default=str)
    os.makedirs(record_dir, exist_ok=True)
    record = {
        "reply": text,
        "recorded_at": _stamp(),
        "recorded_by": "kit.escalate.decide",
    }
    _write_json(os.path.join(record_dir, REPLY_RECORD), record)
    return record


def _not_delivered(reason):
    return {
        "delivered": False,
        "sha256": None,
        "transport_called": False,
        "reason": reason,
    }


def _analysis(run):
    """Split a finished Architect run into its text, or the reason it is not one."""
    if not isinstance(run, dict):
        return None, "the architect run returned %s, not a dict" % type(run).__name__
    text = run.get("text")
    if not isinstance(text, str) or not text.strip():
        return None, "the architect run returned no analysis text"
    return text, None


def _checked_packet(packet):
    try:
        schema = _job_packet_schema()
    except (OSError, ValueError) as exc:
        return False, "the packet schema could not be read: %s" % exc
    errors = _check(packet, schema, schema, "")
    if errors:
        return False, errors[0]
    return True, None


def _delivery_path(record_dir):
    return os.path.join(record_dir, DELIVERY_RECORD)


def _earlier_dispatch(record_dir):
    """The delivery record, or None when none was written.

    A record that exists but cannot be read is still a record: the call may
    have gone out, so the reading fails closed and nothing is sent again.
    """
    path = _delivery_path(record_dir)
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as handle:
            body = json.load(handle)
    except (OSError, ValueError):
        return {"transport_called": True, "transport_returned": False, "sha256": None}
    if not isinstance(body, dict):
        return {"transport_called": True, "transport_returned": False, "sha256": None}
    return body


def _write_json(path, body):
    """Write a record so a reader sees all of it or none of it."""
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    pending = path + ".pending"
    with open(pending, "w", encoding="utf-8") as handle:
        json.dump(body, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(pending, path)


def _stamp():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _job_packet_schema():
    schema = _SCHEMAS.get(SCHEMA_PATH)
    if schema is None:
        with open(SCHEMA_PATH, encoding="utf-8") as handle:
            schema = json.load(handle)
        _SCHEMAS[SCHEMA_PATH] = schema
    return schema


def _check(value, schema, root, where):
    """Errors for ``value`` against ``schema``; an empty list means it validates.

    Covers the Draft 2020-12 keywords the job-packet schema uses: local
    ``$ref``, ``type``, ``const``, ``enum``, ``required``, ``properties``,
    ``additionalProperties``, ``minProperties``, ``items``, ``minItems``,
    ``minLength``, ``pattern``, ``minimum``, ``allOf``, ``anyOf``, ``oneOf``,
    ``not`` and ``if``/``then``/``else``. A keyword it does not know is not
    silently satisfied by a guess elsewhere; it simply asserts nothing.
    """
    if schema is True:
        return []
    if schema is False:
        return [_at(where, "no value is allowed here")]
    if not isinstance(schema, dict):
        return [_at(where, "the schema is not an object")]
    errors = []
    reference = schema.get("$ref")
    if isinstance(reference, str):
        errors.extend(_check(value, _deref(root, reference), root, where))
    allowed = schema.get("type")
    if allowed is not None:
        names = allowed if isinstance(allowed, list) else [allowed]
        if not any(_of_type(value, name) for name in names):
            errors.append(
                _at(where, "%s is not of type %s" % (_shown(value), ", ".join(names)))
            )
            return errors
    if "const" in schema and value != schema["const"]:
        errors.append(_at(where, "%s is not %s" % (_shown(value), _shown(schema["const"]))))
    enumeration = schema.get("enum")
    if isinstance(enumeration, list) and value not in enumeration:
        errors.append(_at(where, "%s is not one of %s" % (_shown(value), _shown(enumeration))))
    if isinstance(value, dict):
        errors.extend(_check_object(value, schema, root, where))
    elif isinstance(value, list):
        errors.extend(_check_array(value, schema, root, where))
    elif isinstance(value, str):
        errors.extend(_check_string(value, schema, where))
    elif _is_number(value):
        errors.extend(_check_number(value, schema, where))
    errors.extend(_check_combinators(value, schema, root, where))
    return errors


def _check_object(value, schema, root, where):
    errors = []
    required = schema.get("required")
    if isinstance(required, list):
        for name in required:
            if name not in value:
                errors.append("'%s' is a required property" % name)
    properties = schema.get("properties")
    properties = properties if isinstance(properties, dict) else {}
    for name, subschema in properties.items():
        if name in value:
            errors.extend(_check(value[name], subschema, root, name))
    additional = schema.get("additionalProperties")
    if additional is False:
        for name in value:
            if name not in properties:
                errors.append(_at(where, "'%s' is not a declared property" % name))
    elif isinstance(additional, dict):
        for name in value:
            if name not in properties:
                errors.extend(_check(value[name], additional, root, name))
    least = schema.get("minProperties")
    if _is_number(least) and len(value) < least:
        errors.append(_at(where, "fewer than %s properties" % least))
    return errors


def _check_array(value, schema, root, where):
    errors = []
    least = schema.get("minItems")
    if _is_number(least) and len(value) < least:
        errors.append(_at(where, "fewer than %s items" % least))
    items = schema.get("items")
    if isinstance(items, dict):
        for index, item in enumerate(value):
            errors.extend(_check(item, items, root, "%s[%d]" % (where, index)))
    elif isinstance(items, list):
        for index, (item, subschema) in enumerate(zip(value, items)):
            errors.extend(_check(item, subschema, root, "%s[%d]" % (where, index)))
    return errors


def _check_string(value, schema, where):
    errors = []
    least = schema.get("minLength")
    if _is_number(least) and len(value) < least:
        errors.append(_at(where, "shorter than %s characters" % least))
    pattern = schema.get("pattern")
    if isinstance(pattern, str) and re.search(pattern, value) is None:
        errors.append(_at(where, "%s does not match %r" % (_shown(value), pattern)))
    return errors


def _check_number(value, schema, where):
    errors = []
    least = schema.get("minimum")
    if _is_number(least) and value < least:
        errors.append(_at(where, "%s is below %s" % (_shown(value), least)))
    return errors


def _check_combinators(value, schema, root, where):
    errors = []
    for subschema in schema.get("allOf") or []:
        errors.extend(_check(value, subschema, root, where))
    any_of = schema.get("anyOf")
    if isinstance(any_of, list) and any_of:
        if all(_check(value, subschema, root, where) for subschema in any_of):
            errors.append(_at(where, "matches none of the anyOf alternatives"))
    one_of = schema.get("oneOf")
    if isinstance(one_of, list):
        hits = sum(1 for subschema in one_of if not _check(value, subschema, root, where))
        if hits != 1:
            errors.append(_at(where, "matches %d of the oneOf alternatives" % hits))
    negated = schema.get("not")
    if isinstance(negated, (dict, bool)):
        if not _check(value, negated, root, where):
            errors.append(_at(where, "matches a 'not' schema that forbids it"))
    condition = schema.get("if")
    if isinstance(condition, (dict, bool)):
        if not _check(value, condition, root, where):
            if "then" in schema:
                errors.extend(_check(value, schema["then"], root, where))
        elif "else" in schema:
            errors.extend(_check(value, schema["else"], root, where))
    return errors


def _deref(root, reference):
    if not reference.startswith("#"):
        raise ValueError("only a local reference can be resolved: %s" % reference)
    node = root
    pointer = reference[1:]
    if pointer:
        for part in pointer.split("/"):
            part = part.replace("~1", "/").replace("~0", "~")
            if part:
                node = node[part]
    return node


def _of_type(value, name):
    if name == "object":
        return isinstance(value, dict)
    if name == "array":
        return isinstance(value, list)
    if name == "string":
        return isinstance(value, str)
    if name == "boolean":
        return isinstance(value, bool)
    if name == "null":
        return value is None
    if name == "integer":
        return _is_number(value) and float(value).is_integer()
    if name == "number":
        return _is_number(value)
    raise ValueError("unknown type name: %s" % name)


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _shown(value):
    try:
        return repr(value)
    except Exception:
        return "<unprintable>"


def _at(where, message):
    if where:
        return "%s: %s" % (where, message)
    return message
