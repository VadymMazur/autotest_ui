# Public portfolio scope

This edition contains selected automation source files and synthetic harness tests. It is maintained independently for code review and local learning.

Included: Page Objects, a lead journey, generated synthetic data, API assertions, guarded cleanup, masked diagnostics, report generation and supporting tests.

Excluded: private Git history, actual environment files, credentials, real account/workspace identifiers, server domains/IPs, machine-specific paths, deployment or administration instructions, internal synchronization metadata, IDE settings and captured execution artifacts.

`.env.example` contains a loopback address, a reserved-domain example email and an empty password. Unit-test strings such as `synthetic-secret` are deliberately fake fixtures. Runtime account fields are hidden from configuration `repr`; report failures redact bound credentials and omit full page snapshots.

Generated reports, screenshots, recordings and authentication state are ignored. Do not infer that ignored or masked files are automatically safe to publish: inspect any future additions and artifacts explicitly.
