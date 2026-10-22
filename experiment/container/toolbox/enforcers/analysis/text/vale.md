# Analysis › Text › Vale
enforcer · A prose linter: style rules in YAML files (words to use or not, terms, sentence length, capitals).

- install: `vale`
- check: `vale --config <.vale.ini> --output=line <file>` (exit 1 on an error-level alert)
- config: `[*.md]` then `BasedOnStyles = Vale`, or a style folder with your own rules (`StylesPath`)

Docs: https://vale.sh/docs/
