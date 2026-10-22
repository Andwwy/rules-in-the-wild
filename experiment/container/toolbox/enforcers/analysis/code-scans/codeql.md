# Analysis › Code scans › CodeQL
enforcer · A semantic code analyzer. It builds a database from the source code, then runs queries written in QL over it
(JavaScript/TypeScript, Python, Java, C/C++, C#, Go, Ruby, Swift).

- no recipe: the CodeQL bundle (large; a database is built from the code, per language)
- nearest: Semgrep (/opt/enforce-toolbox/enforcers/analysis/code-scans/semgrep.md)

From the leaf's note:

Install (pinned; the bundle holds the CLI and the standard query packs: 900 MB to download, more unpacked):
    wget -q https://github.com/github/codeql-action/releases/download/codeql-bundle-v2.19.3/codeql-bundle-linux64.tar.gz -O /tmp/codeql.tar.gz
    tar -xzf /tmp/codeql.tar.gz -C /opt/enforce && rm /tmp/codeql.tar.gz      # the CLI is /opt/enforce/codeql/codeql
Use:
    /opt/enforce/codeql/codeql database create /tmp/codeql-db --language=javascript --source-root=<folder> --overwrite
    /opt/enforce/codeql/codeql database analyze /tmp/codeql-db /opt/enforce/<query>.ql --format=sarif-latest --output=/tmp/out.sarif
A query (`.ql`) needs a `qlpack.yml` next to it that depends on the language's library pack (for JavaScript:
`codeql/javascript-all`, which the bundle includes). Creating a database takes from several seconds to minutes.
Query language: https://codeql.github.com/docs/writing-codeql-queries/

Query language: https://codeql.github.com/docs/writing-codeql-queries/
