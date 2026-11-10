# Evidence held outside the working tree

The files below are the record's own evidence, kept out of git because of size. They are unchanged:
each one still has the sha256 the example record pins, so fetching it back makes the record verify
byte-for-byte.

| file | bytes | sha256 |
|---|---|---|
| `llm` | 3754111 | `0487cb13d7cf9218951cd2724c92af736561bf81d8beb5b970e37f1c2f20b3a1` |

Fetch them (from the repository root):

```
python3 tools/fetch_example_evidence.py            # writes each file to its recorded path
python3 tools/fetch_example_evidence.py --check    # or just report what is present
```

A download whose digest differs is refused rather than written, so a fetch can never quietly make
this record unverifiable. If the file is already present and correct the script says `OK` and does
nothing.
