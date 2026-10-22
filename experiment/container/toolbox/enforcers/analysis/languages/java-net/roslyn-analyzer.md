# Analysis › Languages › Java / .NET › Roslyn analyzer
enforcer · The .NET compiler's code analyzers (rules CAxxxx and IDExxxx, and analyzer packages). They run during the build.

- no recipe: the .NET SDK
- check: `dotnet build -warnaserror` in the project
- nearest: Semgrep (/opt/enforce-toolbox/enforcers/analysis/code-scans/semgrep.md) (Java and C# rules)

From the leaf's note:

Install: `wget -q https://dot.net/v1/dotnet-install.sh -O /tmp/dotnet-install.sh && bash /tmp/dotnet-install.sh --version 10.0.402 --install-dir /opt/enforce/dotnet`
(the .NET 10 SDK; set `DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1`, because the image has no ICU library).
Use: `/opt/enforce/dotnet/dotnet build <project> -warnaserror`. Set each rule's severity in a global analyzer config
file (`is_global = true`, `dotnet_diagnostic.CA1822.severity = error`). MSBuild reads the nearest `Directory.Build.props`
above a project, so one outside the project (for example `/Directory.Build.props`) can add the file:
`<ItemGroup><GlobalAnalyzerConfigFiles Include="/opt/enforce/rules.globalconfig" /></ItemGroup>`.

Docs: https://learn.microsoft.com/dotnet/fundamentals/code-analysis/overview
