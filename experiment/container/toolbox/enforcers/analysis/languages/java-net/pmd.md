# Analysis › Languages › Java / .NET › PMD
enforcer · A source code analyzer for Java (also Apex, Kotlin, JavaScript and others). Rules are in XML rulesets, written in
XPath or Java.

- no recipe: Java 21 and PMD
- check: `<pmd>/bin/pmd check -R <ruleset.xml> -d <file> --no-cache`

From the leaf's note:

Install: Java 21, then `wget -q https://github.com/pmd/pmd/releases/download/pmd_releases%2F7.28.0/pmd-dist-7.28.0-bin.zip -O /tmp/pmd.zip && python3 -m zipfile -e /tmp/pmd.zip /opt/enforce/`
(the image has no unzip).
Use: `JAVA_HOME=/opt/enforce/jdk-21.0.12.1+1 bash /opt/enforce/pmd-bin-7.28.0/bin/pmd check -R /opt/enforce/ruleset.xml -f json -d <file>`.

Docs: https://pmd.github.io/
