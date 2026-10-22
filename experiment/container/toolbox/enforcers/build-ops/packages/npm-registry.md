# Build / ops › Packages › npm registry
enforcer · Checks against the public npm registry: does a package exist, what is its latest version, its license
(`npm view <package> version license --json`). It needs the internet.

- install: `node`
- check: `npm view <package> version license --json` (it needs the internet), from a check script (/opt/enforce-toolbox/skeletons/check.py) over package.json

- docs: https://docs.npmjs.com/cli/commands/npm-view
