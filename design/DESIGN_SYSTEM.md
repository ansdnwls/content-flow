# ContentFlow Design System

## Core Idea

ContentFlow should read as a signal engine: one input enters, many outputs radiate outward. Every major screen should reinforce that model through burst compositions, directional gradients, and bright operational status cues.

## Color Rules

Primary `--color-primary`

- Main CTA fills
- Headline accents
- Active navigation
- High-priority chart highlights

Secondary `--color-secondary`

- Support gradients
- Badge fills
- Hover bloom and ambient lighting

Accent `--color-accent`

- Success-like operational cues
- Selected chips and enabled states
- Fine-detail glow, sparkline emphasis, and scan lines

Surface colors

- `--color-bg`: app and page background
- `--color-bg-elevated`: cards and panels
- `--color-bg-panel`: denser glass surfaces
- `--color-bg-soft`: muted table rows, toggles, and chips

Text colors

- `--color-text`: primary content
- `--color-text-muted`: metadata and supporting copy
- `--color-text-soft`: tertiary labels and dividers

Status colors

- Success: operational completion
- Warning: scheduled, pending, or rate-limited
- Danger: failed publish or invalid auth

## Typography Scale

- Display XL: `96 / 0.9 / -0.06em`
- Display L: `64 / 0.92 / -0.05em`
- Display M: `48 / 0.95 / -0.04em`
- Heading L: `32 / 1.0 / -0.04em`
- Heading M: `24 / 1.1 / -0.03em`
- Body L: `20 / 1.5 / -0.01em`
- Body M: `16 / 1.6 / normal`
- Body S: `14 / 1.55 / normal`
- Meta: `12 / 1.4 / 0.12em`

## Component Patterns

Buttons

- Primary: gradient fill, inset highlight, strong shadow, slight lift on hover
- Secondary: dark panel, tinted border, sharper text contrast
- Ghost: transparent until hover, for navigation and low-emphasis actions

Cards

- Use soft glass surfaces with a top edge highlight
- Keep radius generous but not bubble-like
- Cards should carry layered backgrounds, not flat fills

Forms

- Floating labels when the field is a primary interaction
- Focus should use ring + glow, not only border color
- Error feedback should include icon or copy, never color alone

Tables

- Dense but breathable
- Header text in uppercase meta style
- Row hover should feel illuminated, not simply darker

Navigation

- Active state should look locked-in and energized
- Sidebar should feel like a control rail, not a plain drawer

## Motion Rules

- Default easing: `cubic-bezier(0.34, 1.56, 0.64, 1)`
- Page entry: fade + slight vertical shift
- Card groups: stagger from top to bottom
- Numbers and charts: reveal from low opacity to full signal state
- Hover states: use lift, glow, and border emphasis in combination
- Respect `prefers-reduced-motion` by removing non-essential loops

## Do

- Use oversized headlines with short copy
- Build atmospheric backgrounds with radial light and subtle grid texture
- Let operational data feel cinematic
- Keep accent colors concentrated around key interactions

## Don't

- Do not use purple-first gradients
- Do not default to flat gray cards on a black background
- Do not scatter equal visual weight across every section
- Do not hide status meaning behind color only

## Illustration Style

Chosen direction: geometric editorial systems art

- Use simple vector geometry
- Combine burst rays, nodes, and modular panels
- Keep illustration palettes consistent with the core token set
- Prefer SVG for crisp scaling and repository portability
