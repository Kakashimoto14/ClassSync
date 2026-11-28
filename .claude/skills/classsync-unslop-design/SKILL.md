---
name: classsync-unslop-design
description: Institutional UI/UX design system and anti-slop engineering standard for ClassSync (Colegio de Montalban). Apply whenever designing, refactoring, or styling pages, auth/onboarding flows, layouts, CSS, tables, or timetables in apps/web.
---

# ClassSync Institutional Design System (Anti-Slop Standard)

## Core Aesthetic Direction
Build a high-trust, calm, precision institutional SaaS interface (reference bar: Linear, Stripe Dashboard, Swiss editorial grids) tailored to Colegio de Montalban's ClassSync brand.

## Strict Visual Tokens (Pure CSS — 0 JS Overhead)
- **Surfaces (use tonal contrast, not heavy borders):**
  - `--surface-canvas: #F7F7F9` (page backdrop)
  - `--surface-primary: #FFFFFF` (cards, tables, sheets)
  - `--surface-subtle: #F1F3F6` (table headers, filter wells, inactive segmented controls)
  - `--border-subtle: #E5E7EB` · `--border-strong: #CBD5E1`
  - `--shadow-card: 0 1px 2px rgba(15, 23, 42, 0.05), 0 1px 1px rgba(15, 23, 42, 0.03)`
  - `--shadow-elevated: 0 8px 24px rgba(15, 23, 42, 0.08)`
- **Brand & Ink:**
  - `--brand-crimson: #991B2E` · `--brand-crimson-hover: #7F1525` · `--brand-crimson-soft: #FDF2F4`
  - `--ink-primary: #0F172A` · `--ink-secondary: #334155` · `--ink-muted: #64748B`
- **Semantic Session & Status Accents (3px left accent + soft tint):**
  - Lecture: `#334155` / `#F8FAFC`
  - Computer Lab: `#2563EB` / `#EFF6FF`
  - Science Lab: `#0D9488` / `#F0FDFA`
  - PE / Athletic: `#D97706` / `#FFFBEB`
  - Success/Ready: `#059669` / `#ECFDF5`
  - Danger/Conflict: `#DC2626` / `#FEF2F2`

## Mandatory Anti-Slop Rules
1. **Kill Card-in-Card Stacking:** Maximum one elevated surface layer. Put section headers, filters, and primary content cleanly inside a structured page rhythm instead of wrapping every sub-group in another bordered box.
2. **One Primary CTA Per Viewport:** Only the single most important next action gets solid `--brand-crimson`. All secondary actions use clean outlined or ghost styles. Destructive actions stay subtle/ghost until hover or confirmation.
3. **Tabular Precision:** Apply `font-variant-numeric: tabular-nums` to all times, IDs, percentages, counts, and metrics. Right-align numeric columns in tables. Prevent mid-word splits (`overflow-wrap: normal; white-space: nowrap` on IDs, times, status pills).
4. **Unified Control Geometry:** Every text input, `<select>`, search field, and toolbar button shares a unified `36px` height, `8px` radius, consistent `14px` font, custom chevron styling on selects, and accessible `:focus-visible` ring (`0 0 0 3px rgba(153, 27, 46, 0.16)`).
5. **De-Jargon Copy:** Remove repetitive engineering disclaimers from prime header real estate. Move revision numbers, UUIDs, and snapshot provenance into subtle metadata badges or collapsible details.
6. **Spatial Page Rhythm:** Every workspace page follows:
   - Compact **Page Header** (Eyebrow/Breadcrumb + Title + Inline Meta + Single Primary CTA)
   - Single-row **Filter / Command Bar** (Search + Chips/Selects)
   - High-signal **Primary View** (Time-Grid Matrix / Clean Hairline Table / Visual Metric Bars)
7. **Auth & Onboarding Excellence:** Split-screen editorial layout on desktop (`>= 960px`), clean focused card on mobile (`360px`), instant inline field validation, password visibility toggle, clear multi-step verification feedback, and calm branded loading states.
8. **Hard Engineering Constraints:**
   - **Zero new npm UI/icon/animation packages.**
   - **Strict bundle budget:** `apps/web` main entry MUST stay `<= 101,376` bytes (`node scripts/check_bundle_budget.mjs`). Keep page-specific CSS/components inside lazy chunks.
   - **Preserve all WCAG 2.1 AA contrast, keyboard navigation, `aria-label` accessible names, RBAC guards, and `NoDeadEnds` tests.**
   - **Verify visually at `1440px`, `1280px` (100% zoom), and `360px` mobile** with zero horizontal page overflow.