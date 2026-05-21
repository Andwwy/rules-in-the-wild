Classify the provided rule context.

Return plain text only: one line with six tab-separated fields:

```text
prerequisites	enforcement_mechanisms	triggers	ambiguity_level	ambiguity_notes	confidence
```

Use semicolon-space between multiple prerequisites, enforcement mechanisms, or
triggers.

Use an empty field when none are stated or implied.

Valid `ambiguity_level` values are:

- `none`
- `low`
- `medium`
- `high`

Do not include a header, markdown, numbering, bullets, or explanatory text.
