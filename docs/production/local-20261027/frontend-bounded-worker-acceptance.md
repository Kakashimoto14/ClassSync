# Local regression runner throughput — acceptance before source change

27 October 2026. Current HEAD `39200a4f2ef3ec7557bc3c86127e674e260ca4fc`; scoped P2–P8 local source/test authority, cross-cutting reliability gate. No frontend product source or test assertions changed in the draft/restore slice.

Observed: the unchanged full frontend command timed out at its 300-second boundary, including a serial run completing 161 tests without an assertion failure. A diagnostic reporter confirms continued module collection/execution. Selected node and DOM suites pass. Independent review found the same patched tooling previously passed all 709 tests/40 files in 215.18 seconds. Older Node processes lack proven task ownership and must be preserved.

The app's Vitest configuration already permits at most two workers and default file isolation. The root wrapper overrides it to one. Before changing the wrapper, run the full suite with the existing configuration's two-worker bound, unchanged thread pool, default file isolation, all assertions and the existing 300-second process limit. No solver run may overlap this performance qualification.

Acceptance:

- All 40 files and 709 tests pass; no filters, retries within the command, skipped tests, fake time, disabled isolation, assertion changes or greater timeout.
- Honor the existing app configuration's bounded two-worker maximum; never use unbounded default CPU concurrency. No filesystem, listening server or shared persistent-data writes from discovered frontend tests.
- Preserve failure logs and independent review; treat this as throughput evidence, not proof of a resource-pressure root cause.
- If successful, remove only the redundant one-worker override from the wrapper. Verify the actual root command, security checks, static checks and independent diff review. If it fails, retain the failure and investigate rather than expanding time budgets.
- No cleanup of unclassified processes, original databases or user files. Product/browser acceptance remains separate; this runner change does not prove any institutional workflow.
