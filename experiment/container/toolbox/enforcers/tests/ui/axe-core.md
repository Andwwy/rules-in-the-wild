# Tests › UI › axe-core
enforcer · The accessibility rules engine for web pages (WCAG checks).

- no recipe: Playwright and @axe-core/playwright
- check: a Playwright test that runs axe on each page

From the leaf's note:

Install: Playwright (see that note), then `npm install --prefix /opt/enforce/playwright @axe-core/playwright@4.14.0`.
Use: in a Playwright test, `const results = await new AxeBuilder({ page }).analyze();` each entry in
`results.violations` is a violation.

Docs: https://github.com/dequelabs/axe-core
