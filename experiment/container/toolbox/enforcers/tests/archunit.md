# Tests › ArchUnit
enforcer · A Java library for tests that check the architecture: which packages may depend on which, layers, names.

- no recipe: Java 21 and Gradle
- check: `gradle -q test`, with ArchUnit rules in the tests

From the leaf's note:

Install: Java 21 and Gradle (see the Gradle note); the test build adds
`testImplementation("com.tngtech.archunit:archunit-junit5:1.5.1")`.
Use: a JUnit test with rules such as
`noClasses().that().resideInAPackage("..ui..").should().dependOnClassesThat().resideInAPackage("..db..")`, run by
`gradle test`.

Docs: https://www.archunit.org/userguide/html/000_Index.html
