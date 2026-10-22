# Analysis › Languages › Java / .NET › Checkstyle
enforcer · A Java style checker: names, layout, Javadoc, imports, sizes.

- no recipe: Java 21 and the Checkstyle jar
- check: `java -jar <checkstyle.jar> -c <checks.xml> <file>`

From the leaf's note:

Install: Java 21, then `wget -q https://github.com/checkstyle/checkstyle/releases/download/checkstyle-14.3.0/checkstyle-14.3.0-all.jar -O /opt/enforce/checkstyle.jar`.
Use: `/opt/enforce/jdk-21.0.12.1+1/bin/java -jar /opt/enforce/checkstyle.jar -c /opt/enforce/checkstyle.xml -f xml <file>`.

Docs: https://checkstyle.org/
