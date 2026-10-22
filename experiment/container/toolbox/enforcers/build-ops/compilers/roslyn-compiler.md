# Build / ops › Compilers › Roslyn compiler
enforcer · The C# compiler in the .NET SDK: compile errors and warnings are the check.

- no recipe: the .NET SDK
- check: `dotnet build -warnaserror`

From the leaf's note:

Install: the .NET SDK (see the Roslyn analyzer note).
Use: `/opt/enforce/dotnet/dotnet build <project> -warnaserror`.
- docs: https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/compiler-options/
