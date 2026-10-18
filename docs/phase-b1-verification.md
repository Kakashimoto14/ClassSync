# Phase B1 implementation and verification

18 October 2026. Local workspace is the source of truth. No commit, push, deployment,
backend change, authentication implementation, or S2C work was performed.

## Result and asset blocker

B1-B through B1-E are implemented and verified. B1-A asset investigation is complete,
but official artwork integration is **blocked**, not complete. The original geometric
ribbon requires an isolated SVG or sufficiently large transparent PNG master, with
horizontal/full/symbol and light/dark variants. Favicon and app icons depend on it.
See [branding audit](branding.md) for exact inspected sources and extraction assessment.
The supplied cap/calendar board and the old PNG were not substituted. No raster was
enlarged, reconstructed, generated, or misrepresented as an official vector.
`ClassSyncLogo` is reused unchanged with its honest pending text fallback.

The entrance now includes the requested headline and description, verified capability
labels, an explicitly illustrative timetable, and a focused access panel. Mobile places
the primary action before the illustration. Desktop uses a deliberate white/canvas
split. Self-hosted Inter and all Soft Rouge semantic colors are retained.

## Implementation map

- `apps/web/src/pages/AuthPage.tsx`: semantic welcome composition, illustrative content,
  immediate role-selection link, and session-aware Continue to workspace. Existing
  provider expiry and `demoDestination` enforce session lifetime and role-owned returns.
  University sign-in remains explicitly Not connected; its existing local validation
  never transmits credentials, and its action now says Check sign-in availability.
- `apps/web/src/components/brand/EntranceTimetable.tsx`: static example separate from
  scheduling/academic state, synthetic class and room labels, explicit sample caption,
  screen-reader description, and an example-only conflict-check label.
- `apps/web/src/entrance.css`: isolated responsive styles, safe-area spacing, `svh`,
  restrained 360–400ms brand/copy and two-item arrival, touch/hover/focus behavior,
  and reduced-motion overrides. No continuously running animation or navigation delay.
- `apps/web/src/pages/DevelopmentRolePreviewPage.tsx`: scoped role-card styling and
  Back to welcome label. Selection, destinations and persistence are unchanged.
- `apps/web/src/main.tsx`: imports entrance styles after existing workspace styles.
- `apps/web/index.html`: accurate title/description, Inter preload, explicit empty
  favicon reference preventing the browser's missing `/favicon.ico` request. This is
  deliberately **not** an official favicon integration.
- `apps/web/src/pages/AuthPage.test.tsx`: existing honest login tests retained;
  three new returning-role cases verify safe matching/cross-role return destinations.

No scheduling, persistent draft, academic-data, route registry, inventory, preview
provider, authorization, or backend implementation was changed.

## Motion decision

Reviewed all five requested official pages: [overview](https://motion.dev/docs/react),
[installation](https://motion.dev/docs/react-installation),
[LazyMotion](https://motion.dev/docs/react-lazy-motion),
[AnimatePresence](https://motion.dev/docs/react-animate-presence), and
[accessibility](https://motion.dev/docs/react-accessibility).
The overview explicitly supports CSS for simple self-contained effects. CSS handles
this one-time sequence without component lifecycle orchestration or an exit state.
No `motion` dependency or lockfile change was needed. MotionConfig/AnimatePresence
would add complexity without useful behavior here. Animation uses opacity and transform;
text starts at readable opacity, controls accept input immediately, and reduced motion
disables animation and feedback transforms. No filters, looping effects or layout animation.

## Executed checks

| Check | Result |
| --- | --- |
| `npm run lint` | Pass, zero warnings |
| `npm run typecheck` | Pass |
| `npm run test:web` | Pass, 179 tests across 22 files |
| `npm run build` | Pass |
| `.venv/Scripts/python.exe -m pytest -q` | Pass, 65 tests; one upstream Starlette/httpx deprecation warning |
| `git diff --check` | Pass; Git only notes normal LF/CRLF conversion |

Browser plugin not available; used bundled Playwright with installed Chrome, without
installing a driver. Development URL: `http://127.0.0.1:5183`. Production Vite preview:
`http://127.0.0.1:5184`, with preview disabled by the normal production build.

Flow: welcome → Explore ClassSync → role selection → selected workspace. Checked all
three roles, refresh persistence, safe direct return links, cross-role returns, expired
and malformed sessions, role switching, Exit clearing storage, and normal production
gating including rejection of an injected preview session. Student entry was exercised
using only Tab and Enter through both welcome and role selection.

| Render/interaction check | Result |
| --- | --- |
| Page identity / meaningful content / no framework overlay | Pass |
| 360×800, 390×844, 768×1024, 1024×768, 1440×900 | Pass; no horizontal overflow |
| 390×568 short viewport | Pass; CTA bottom about 531px, naturally scrollable |
| Short viewport with expanded sign-in and focused email | Pass; field scrolls into view, no overflow |
| Primary CTA visible before scrolling | Pass at every requested width |
| Reduced-motion rendering | Pass; no animations; content remains present |
| Visible keyboard focus | Pass; 3px outline on primary action |
| Console/runtime errors | None in final flow run |
| Production preview gating | Pass; no role buttons or Explore action, guarded dashboard redirects |

Real mobile software keyboards and physical-device GPU/frame-rate behavior were not
tested; browser viewport and CPU emulation are not a claim of device certification.
No full screen-reader or WCAG conformance audit is claimed. Existing service and frontend
regressions passed; B1 did not repeat a live full-stack solver generation run.

## Performance

Same local build command before and after, Vite-reported decimal kB:

| Asset | Before | After | Delta |
| --- | ---: | ---: | ---: |
| JavaScript | 473.76 kB | 477.07 kB | +3.31 kB |
| JavaScript gzip | 140.54 kB | 141.15 kB | +0.61 kB |
| CSS | 61.97 kB | 68.94 kB | +6.97 kB |
| CSS gzip | 11.93 kB | 13.11 kB | +1.18 kB |

No new runtime dependency or raster download. Inter preload removed a measured font-swap
shift (about 0.002 CLS). Final 4× CPU-throttled local Chromium checks measured CLS 0
at 360, 390 and 1440px, no overflow, and zero running animations after settling.
DOMContentLoaded was approximately 1,089 / 392 / 459ms respectively on the development
server; these are local observations, not a production speed benchmark or before/after
latency comparison. Layout is reserved during opacity/transform motion.

## Visual evaluation and intentional deviations

Concept: `b1-concept.png` in the evidence directory below. Inspected with `view_image`
alongside actual desktop/mobile renders; also captured at the concept's native 1586×992.
The implementation was visually verified against that direction with these deliberate
changes, rather than treating generated copy as product authority:

| Comparison | Evaluation |
| --- | --- |
| Composition | White identity panel, pale access area, aligned desktop card and timetable retained; mobile moves the timetable after access |
| Typography | Inter retained; responsive headline sized to keep the requested wording readable at 360px |
| Palette | Exact Soft Rouge canvas/surface/ink/secondary/rouge; second headline line uses rouge intentionally |
| Capabilities | All three requested labels retained; icons and text are compact rather than large tinted pills |
| Timetable | Three readable synthetic examples, explicit illustration caption; reduced names and no fabricated institutional metrics |
| Access | Correct preview message retained; generated concept's misleading sign-in guidance replaced by the real Not connected disclosure |
| Brand | Ordinary text fallback retained explicitly; no generated symbol or logo integration claim |

Above-the-fold copy was checked against the request. Headline, supporting message,
capability labels and official tagline match. The access heading/helper, sample notice,
availability disclosure, illustrative caption and timetable heading are intentional
supporting copy. No operational AI/OCR/live-monitoring claims were introduced. No
material responsive clipping or layout defect remained in the inspected renders.

## Evidence

All captures/scripts/raw results are outside source at:

`C:/Users/lenovo/.codex/visualizations/2026/10/18/01a14e48-eb6b-7620-a8fa-0d5b6a108c65/`

- Before: `b1-before-390.png`, `b1-before-1440.png`.
- Final mobile/desktop: `b1-final-360.png`, `b1-final-390.png`, `b1-final-1440.png`.
- All requested widths and short viewport: `b1-after-{width}-{height}.png`.
- Role selection: `b1-roles-390.png`, `b1-roles-1440.png`.
- Reduced motion/focus: `b1-reduced-motion.png`.
- Production: `b1-production.png`; short expanded form: `b1-short-form.png`.
- Concept/native-size render: `b1-concept.png`, `b1-native-concept-size.png`.
- Executed scripts and results: `b1-qa.cjs`, `b1-browser-results.json`,
  `b1-production.cjs`, `b1-production-results.json`, `b1-performance.cjs`,
  `b1-performance.json`, `b1-additional.cjs`.

The official ribbon master remains the only B1 deliverable blocker. No approval was
requested for unavailable artwork and no substitute was manufactured.
