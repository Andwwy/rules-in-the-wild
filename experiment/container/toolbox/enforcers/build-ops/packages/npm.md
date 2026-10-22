# Build / ops › Packages › npm
enforcer · Node's package manager, for checks on `package.json` and the dependencies: `npm ls`, `npm audit --json`,
`npm pkg get <field>`. It comes with Node.js 22.

- install: `node` (it has npm)
- check: `npm ls --prefix <project>` (the dependencies resolve), or a check script (/opt/enforce-toolbox/skeletons/check.py) on package.json

- docs: https://docs.npmjs.com/cli/commands/npm-ls
