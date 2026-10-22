# Tests › UI › XCTest
enforcer · Apple's test framework for Swift and Objective-C. Its UI tests (XCUITest) need Xcode on macOS and cannot run here; on
Linux, the Swift toolchain has XCTest for unit tests.

- no recipe: Swift for Linux
- check: `swift test` in the package; Apple's UI tests do not run on Linux

From the leaf's note:

Install: `wget -qO- https://download.swift.org/swift-6.4.1-release/debian12/swift-6.4.1-RELEASE/swift-6.4.1-RELEASE-debian12.tar.gz | tar -xz -C /opt/enforce`,
and the Debian packages that https://www.swift.org/install/linux/ lists for Debian 12.
Use: `swift test` in a Swift package (`Package.swift`).

Docs: https://developer.apple.com/documentation/xctest
