# ClassSync branding asset status

## Current B1 logo integration

`ClassSyncLogo` now renders the owner-supplied provisional raster derivatives in
`apps/web/public/branding/classsync-logo-assets/`. These files were explicitly supplied
for this integration. They are derived from a brand concept, **not an official SVG
or independently verified original vector master**. Native colors, transparency,
padding and aspect ratios are preserved. No image was edited, cropped, recolored,
filtered or enlarged into a new asset.

| Placement | Asset and sizing |
| --- | --- |
| Welcome below 1024px | Horizontal lockup, 220px wide |
| Welcome 1024–1279px | Horizontal lockup, 320px wide |
| Welcome 1280px and above | Full horizontal lockup with embedded tagline, 480px wide |
| Expanded navigation and role selection | Horizontal lockup, up to 200px wide |
| Mobile workspace header | Compact horizontal lockup, up to 144px wide |
| Symbol-only component contexts | Ribbon mark, 32/44/96px according to component size |
| Favicon | Supplied ribbon icons, 32px and 48px |
| Touch icon and app manifest | Supplied ribbon icons, 192px and 512px |

The horizontal PNG is 1100×295; the full PNG is 1100×310; the transparent ribbon-only
PNG is 1024×1024. The supplied icon PNGs have an off-white square background; this
background is part of those assets and is retained. The full lockup contains the
wordmark and tagline, so the component adds neither as visible text while it loads
successfully. A responsive picture uses the horizontal image on smaller screens.

If an image fails to load, the component replaces the broken image with accessible
ordinary ClassSync text. Full placements also show the tagline in this failure state.
Decorative instances remain hidden from assistive technology inside already named
home links. Normal images have a ClassSync alternative.

There is no supplied dark master. A dark-surface component uses the same unmodified
light artwork on a neutral light backing. It does not invent a dark asset or use a CSS
filter. The current application has light logo surfaces and no new dark mode was added.

Assets use Vite's configured BASE_URL. Icon links use the same build base, and manifest
icon URLs resolve relative to the manifest. Public files are copied into the production
output by Vite. No runtime external image host or new dependency is involved.

## Provenance and historical B1 blocker

Before this follow-up, the asset registry was intentionally empty. The original
`C:/Users/lenovo/Downloads/ClassSync_Logo.png` was a 1774×887 presentation board with
shading, patterned backgrounds and mockups; no faithful isolated master could be
extracted without guessing colors/edges. The earlier reference archive contained
screenshots, while `ITADBMS_Final_Official_Logo_Package.zip` contained database
coursework and a CdM institutional logo. Neither supplied an isolated ribbon export.

The earlier cap/calendar attachment and old `public/classsync-logo.png` are different
artwork and remain unused. This follow-up changes the integration authority to the
new user-supplied provisional ribbon derivatives, without claiming that the missing
original vector master has been recovered. The full B1 verification report records
the historical state; this document supersedes its logo-integration blocker for the
provisional assets now supplied.

## Vercel verification

The user supplied `https://class-sync-bhiv.vercel.app` (project `class-sync-bhiv`).
Read-only browser verification found an older deployment: its root still renders
`data-logo-asset="pending"` and contains no logo images or favicon link. The new
horizontal/full/ribbon/icon PNG paths and app manifest return HTTP 404. Direct
`/auth/login`, `/dev/role-preview`, and all three dashboard URLs return Vercel 404
pages, indicating the deployed SPA history fallback is also absent. This pre-existing
deployment issue was reported without expanding the logo task into hosting changes.

The local production build renders the new assets correctly and serves all referenced
logo/icon/manifest paths with HTTP 200. Deployed success is not claimed. No commit,
push or deployment was performed; deployment requires the user's approval.
