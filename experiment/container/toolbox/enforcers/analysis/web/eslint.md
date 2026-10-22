# Analysis › Web › ESLint
enforcer · The standard linter for JavaScript and TypeScript: rules on code patterns, names and style, many with an autofix.

- install: `eslint`
- check: `eslint --config <eslint.config.mjs> <file>`; text not yet on disk: `--stdin --stdin-filename <path in the project>`; a report: `--format json`
- config: `export default [{ files: ["**/*.js"], rules: { "<rule>": "error" } }];` (TypeScript also needs typescript-eslint)

Docs: https://eslint.org/docs/latest/
