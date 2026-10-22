# Tests › UI › Playwright
enforcer · Browser automation and end-to-end tests: open the app in a real browser, act on it, check the page.

- no recipe: Node.js, @playwright/test and its browsers (large)
- check: `npx playwright test` in the project

From the leaf's note:

Install: Node.js 22, then `npm install --prefix /opt/enforce/playwright @playwright/test@1.64.1` and
`/opt/enforce/playwright/node_modules/.bin/playwright install --with-deps chromium` (it downloads Chromium and installs
its system libraries with apt).
Use: tests in `*.spec.ts` files, run with `/opt/enforce/playwright/node_modules/.bin/playwright test --config /opt/enforce/playwright.config.ts --reporter json`;
the config can start the project's server (`webServer`).

Docs: https://playwright.dev/docs/intro
