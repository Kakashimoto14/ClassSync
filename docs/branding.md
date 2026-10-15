# ClassSync branding asset status

Package A uses `ClassSyncLogo` for every active application brand placement.

The visual authority is the supplied `C:/Users/lenovo/Downloads/ClassSync_Logo.png`:
an interlocking ribbon symbol, ClassSync wordmark, and **Smarter Classrooms Together**
tagline. The 1774 × 887 PNG is a composite presentation board with backgrounds and
mockup treatments, not an isolated production logo. The supplied HTML's hand-built
SVG is not a verified master. The inspected reference archive contains screenshots,
not isolated logo exports. The old `public/classsync-logo.png` is retained as an
existing file but is no longer displayed or used as the favicon.

## Current implementation

Until verified exports are supplied, the component displays ordinary product-name
text, not an official reconstructed wordmark. `horizontal`, `full`, and `symbol`
placements share this honest fallback; `full` may also display the tagline. No
substitute symbol, cropped board, filters, or fabricated favicon is supplied.
This is an asset limitation, not completed official ribbon integration.

## Required exports

- Horizontal ribbon + wordmark for light surfaces and an approved dark-surface version.
- Full horizontal lockup with readable tagline.
- Symbol-only SVG and transparent PNG; favicon 16/32, touch icon 180, application
  icons 192/512 derived from that same approved symbol when applicable.

Preserve navy #040B15, rouge #640000 / #420001, and rose #B67E7D artwork colors.
Do not replace them with application UI tokens. Preserve proportions and at least
one-quarter symbol-height clear space. No embossing, texture, or shadows baked
into production exports. Confirm fidelity against the authority before registering
paths in `approvedAssets` in `ClassSyncLogo.tsx` and adding the favicon to index.html.

## Placement

- Login: full lockup; mobile hides the tagline when space is limited.
- Expanded sidebar: horizontal dark-surface lockup, within the existing 256px shell.
- Mobile header: small horizontal lockup; no duplicate logos in content cards.
- Development preview: horizontal light-surface lockup.
- A future branded loading indicator may use `symbol`; announce loading separately.
- Favicon/app icon: approved symbol only. Missing assets must not revive the old mark.

Use `decorative` inside the already named ClassSync home link. Otherwise the product
name is accessible text or the image alternative. All images use intrinsic proportions.
