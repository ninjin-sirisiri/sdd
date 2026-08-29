# Examples

## Document page

**Before** — landmarks missing, headings do not create a visual outline:

```html
<body>
  <div>Example Implementation Plan</div>
  <div>Goal: Build the example.</div>
  <div>Global Constraints</div>
  <div>Do not leak tokens into a task brief.</div>
  <div>Task 1: First thing</div>
  <p>First body.</p>
</body>
```

**After** — outline in the markup, regions and rank in the CSS:

```html
<body>
  <header>
    <p>Project docs</p>
    <nav aria-label="Doc sections">
      <a href="#goal">Goal</a>
      <a href="#constraints">Constraints</a>
      <a href="#tasks">Tasks</a>
    </nav>
  </header>
  <main>
    <h1>Example Implementation Plan</h1>
    <section id="goal">
      <h2>Goal</h2>
      <p>Build the example.</p>
    </section>
    <section id="constraints">
      <h2>Global Constraints</h2>
      <p>Do not leak tokens into a task brief.</p>
    </section>
    <section id="tasks">
      <h2>Tasks</h2>
      <h3>Task 1: First thing</h3>
      <p>First body.</p>
    </section>
  </main>
</body>
```

Squint result: title largest, sections separated by gap + rule, tasks nested under Tasks.

## App chrome

**Before** — one column of identical blocks; nav looks like body text.

**After** — `header`/`nav`/`main`/`aside` with region recipes from `reference.md`. Object cards stay on list items, not on every heading.

## Overlay

```html
<html lang="ja" class="debug-structure">
```

Include `overlay.css` during review. Labels must match the real elements. If a box says `section` but reads like the page title, the HTML outline is wrong.
