# Analysis › Languages › Dart › custom_lint
enforcer · A Dart package for writing your own lint rules in Dart, run as an analyzer plugin.

- no recipe: the Dart SDK
- check: `dart run custom_lint` in the project

From the leaf's note:

Install: the Dart SDK, `wget -q https://storage.googleapis.com/dart-archive/channels/stable/release/3.13.5/sdk/dartsdk-linux-x64-release.zip -O /tmp/dart.zip && python3 -m zipfile -e /tmp/dart.zip /opt/enforce/ && chmod -R +x /opt/enforce/dart-sdk/bin`.
Use: a lint package that depends on `custom_lint_builder`; the checked project adds `custom_lint: 0.8.1` and that
package as dev dependencies, then `dart run custom_lint`. It runs inside a Dart project (its `pubspec.yaml`), so it
needs a change to the project; outside the project, use the Dart analyzer or a script.

Docs: https://pub.dev/packages/custom_lint
