# Build / ops › Builds › Gradle
enforcer · The build tool for Java and Kotlin: `gradle build`, `gradle test`, `gradle check`.

- no recipe: Java 21 and Gradle
- check: `gradle -q build`

From the leaf's note:

Install: Java 21, then `wget -q https://services.gradle.org/distributions/gradle-9.8.1-bin.zip -O /tmp/gradle.zip && python3 -m zipfile -e /tmp/gradle.zip /opt/enforce/ && chmod +x /opt/enforce/gradle-9.8.1/bin/gradle`.
Use: `JAVA_HOME=/opt/enforce/jdk-21.0.12.1+1 /opt/enforce/gradle-9.8.1/bin/gradle -p <project> check`.

Docs: https://docs.gradle.org/current/userguide/userguide.html
