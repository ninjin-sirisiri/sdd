---
name: html-visual-clarity
description: Makes HTML visually scannable by aligning type, spacing, and color with document structure (headings, landmarks, sections). Use when writing, editing, reviewing, or rendering HTML, CSS, JSX, or page layouts; when a page looks flat or hard to scan; or when the user mentions visual hierarchy, landmarks, document outline, 視覚的, わかりやすく, or 見やすく.
---

# HTML Visual Clarity

Goal: a reader should grasp the page outline in about 3 seconds without reading every word. Visual design exists to show structure, not to decorate.

Do not load `ui-ux-pro-max` or `frontend-design` for this. Those optimize aesthetics or a design system. This skill optimizes **scanability**.

## When to apply

- New or edited `.html` / JSX that produces a page
- CSS for documents, dashboards, settings, or marketing pages
- Reviews where the page looks like a wall of text or a pile of identical cards
- Rendered Markdown/docs HTML that needs a readable outline

Skip for non-visual backend work.

## Workflow

Copy this checklist and track it:

```
Scanability:
- [ ] Document outline extracted (landmarks + h1–h6)
- [ ] Each outline node has a distinct visual treatment
- [ ] Landmarks are distinguishable without reading labels
- [ ] Measure, type scale, and spacing use tokens
- [ ] Squint / overlay check passed
```

### 1. Extract the outline

From the markup, list in order:

1. Landmarks: `header`, `nav`, `main`, `aside`, `footer`
2. Headings: `h1`–`h6` (one `h1`, no skipped levels)
3. Clusters: `section`, `article`, `form`, `table`, `ul`/`ol`, `figure`

If the outline is unclear in the HTML, fix the HTML first. Do not fake structure with `div` + CSS.

### 2. Map structure to visuals

Every semantic node must have a visual counterpart. Defaults:

| Markup | Visual job |
|---|---|
| `header` | Chrome, separated from the reading column |
| `nav` | Compact control row/list, not body paragraphs |
| `main` | Primary column, limited measure (`60–75ch`) |
| `section` | Block with a heading; sibling sections have a gap |
| `article` | Self-contained unit; optional card, not every block |
| `aside` | Secondary: quieter type or muted surface |
| `footer` | Recessed, smaller type, top rule |
| `h1`–`h6` | Strict type scale; size never contradicts rank |
| `ul`/`ol` | Indent + markers; hanging rhythm |
| `table` | Header contrast, row rhythm, aligned numbers |
| `form` / `fieldset` | Grouped fields; labels above or beside, never placeholder-only |
| `figure` | Caption quieter than the figure |

**Document pages** (specs, plans, articles): prioritize measure, type scale, section rhythm.

**App chrome** (dashboards, settings): prioritize region identity (nav vs main vs aside) and density. Still keep heading rank visible.

### 3. Apply the visual system

Use the token set in [reference.md](reference.md). Copy `starter.css` when the project has no existing type/spacing scale.

Non-negotiables:

- Type scale follows heading rank (`h1` largest … `h6` smallest, above body)
- Spacing comes from a scale, not one-off `px`
- Color supports structure (muted secondary, stronger primary) and is never the only signal
- Contrast stays at least 4.5:1 for text, 3:1 for UI boundaries
- `color-scheme` supports light and dark unless the project forbids it

### 4. Verify scanability

1. **Squint test**: blur or zoom out. `h1` / `h2` / body / chrome must still separate.
2. **3-second test**: name the regions (nav, main, aside, footer) without reading.
3. **Structure overlay**: temporarily include [overlay.css](overlay.css) or add `class="debug-structure"` on `html`. Confirm landmarks and heading levels. Remove the overlay before shipping unless the user asked to keep it.
4. If the page is user-visible UI, check it in the browser, not only in source.

## Anti-patterns

- All headings the same size or weight
- `div` soup instead of landmarks and headings
- Every block wrapped in a card
- Gradients, hero chrome, or shadows that hide rank
- Color as the only structure cue
- Full-bleed paragraphs with no measure
- Skipping heading levels to get a size
- Placeholder-only labels, gray-on-gray secondary text

## Related files

- Token scale, starter rules, document vs app: [reference.md](reference.md)
- Copy-paste base stylesheet: [starter.css](starter.css)
- Debug overlay for landmarks and headings: [overlay.css](overlay.css)
- Before/after markup: [examples.md](examples.md)
