# Visual system

Use these tokens unless the project already has a type/spacing scale. Prefer existing tokens when they already encode rank.

## Tokens

```css
:root {
  color-scheme: light dark;
  --text: CanvasText;
  --bg: Canvas;
  --muted: color-mix(in oklab, CanvasText 62%, Canvas);
  --line: color-mix(in oklab, CanvasText 18%, Canvas);
  --surface: color-mix(in oklab, CanvasText 6%, Canvas);
  --accent: LinkText;
  --space-1: 0.25rem;
  --space-2: 0.5rem;
  --space-3: 1rem;
  --space-4: 1.5rem;
  --space-5: 2.5rem;
  --measure: 68ch;
  --step-0: 1rem;
  --step-1: 1.125rem;
  --step-2: 1.375rem;
  --step-3: 1.75rem;
  --step-4: 2.25rem;
  --leading-body: 1.55;
  --leading-head: 1.2;
}
```

## Type scale

| Role | Size | Weight | Notes |
|---|---|---|---|
| `h1` | `var(--step-4)` | 700 | Page title; one per page |
| `h2` | `var(--step-3)` | 650 | Section |
| `h3` | `var(--step-2)` | 600 | Subsection |
| `h4`–`h6` | `var(--step-1)` → `var(--step-0)` | 600 | Never larger than the rank above |
| body | `var(--step-0)` | 400 | Line-height 1.5–1.6 |
| caption / meta | `0.875rem` | 400 | `color: var(--muted)` |

Heading block spacing:

```css
:is(h1, h2, h3, h4, h5, h6) {
  line-height: var(--leading-head);
  text-wrap: balance;
  margin-block: 1.25em 0.4em;
}
h1 { margin-block-start: 0; }
:is(h1, h2, h3, h4, h5, h6) + * { margin-block-start: 0; }
```

## Region recipes

**Header** — bottom rule or distinct surface; not the same as `main`.

```css
body > header {
  border-bottom: 1px solid var(--line);
  padding-block: var(--space-3);
  margin-bottom: var(--space-5);
}
```

**Nav** — row with gap; links look like controls.

```css
nav {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2) var(--space-4);
}
nav a { text-decoration: none; }
nav a[aria-current="page"] { font-weight: 650; }
```

**Main** — limited measure, centered for documents.

```css
main {
  max-width: var(--measure);
  margin-inline: auto;
}
```

**Section siblings** — gap, not cards by default.

```css
main > section + section {
  margin-top: var(--space-5);
  padding-top: var(--space-4);
  border-top: 1px solid var(--line);
}
```

**Aside** — muted, narrower, smaller type.

```css
aside {
  background: var(--surface);
  color: var(--muted);
  padding: var(--space-3);
  font-size: 0.9375rem;
}
```

**Footer** — top rule, smaller type.

```css
body > footer {
  margin-top: var(--space-5);
  padding-top: var(--space-3);
  border-top: 1px solid var(--line);
  color: var(--muted);
  font-size: 0.875rem;
}
```

## Lists, tables, forms

```css
:is(ul, ol) { padding-inline-start: 1.25em; }
li + li { margin-top: 0.25em; }

th {
  text-align: start;
  background: var(--surface);
  border-bottom: 1px solid var(--line);
}
td { border-bottom: 1px solid var(--line); }
td:is([data-numeric], .numeric) { text-align: end; font-variant-numeric: tabular-nums; }

label { display: block; font-weight: 600; margin-bottom: var(--space-1); }
fieldset {
  border: 1px solid var(--line);
  padding: var(--space-3);
  min-inline-size: 0;
}
legend { font-weight: 650; }
```

## Document vs app

| | Document | App |
|---|---|---|
| Measure | `60–75ch` | Full region width |
| Section gap | Large, optional rule | Tight; use layout grid |
| Cards | Rare | For objects, not headings |
| Nav | Simple list | Persistent chrome |
| Density | Comfortable reading | Compact controls, 44px targets |

## Overlay

For reviews, add `class="debug-structure"` to `html` and include `overlay.css`. Labels use element names (`header`, `h2`, …). Remove before shipping unless asked to keep it.
