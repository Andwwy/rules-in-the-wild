Extract every rule from the provided document context.

Return plain text only.

Use one line per rule and exactly three tab-separated fields per line:

```text
rule_text	start_line	end_line
```

The `start_line` and `end_line` values must be line numbers in the provided
document text.

A rule is a statement about what an agent, system, organization, user, or
regulated party must do, must not do, should do, may do, or is conditionally
allowed to do.

Do not classify the rule. Do not infer actor, modality, type, evidence,
confidence, prerequisites, triggers, enforcement, or ambiguity.

Do not include a header, markdown, numbering, bullets, or explanatory text.

Return an empty string if there are no rules.
