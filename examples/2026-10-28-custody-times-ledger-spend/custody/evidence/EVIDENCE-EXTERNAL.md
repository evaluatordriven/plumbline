# Evidence held outside the working tree

The files below are the record's own evidence, kept out of git because of size. They are unchanged:
each one still has the sha256 the example record pins, so fetching it back makes the record verify
byte-for-byte.

| file | bytes | sha256 |
|---|---|---|
| `harness-maker-deepseek.log` | 7808305 | `882ee4e61a13fe614dfb4cbe12c3f6e228e1e8581dde23ca837471a062edc48a` |
| `harness-eval-glm-b1.log` | 1304887 | `63e756da6a52c5c7985862e61a2d164c1a7ac577dda5190b61e9e686a10055c6` |

Fetch them (from the repository root):

```
python3 tools/fetch_example_evidence.py            # writes each file to its recorded path
python3 tools/fetch_example_evidence.py --check    # or just report what is present
```

A download whose digest differs is refused rather than written, so a fetch can never quietly make
this record unverifiable. If the file is already present and correct the script says `OK` and does
nothing.
