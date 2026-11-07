# Defense-in-Depth Validation

## Overview

When you fix a bug caused by invalid data, one validation point can look sufficient. Different code paths, refactoring, or mocks can still let the bad data through.

**Core principle:** Place validation at the trust boundaries the data actually crosses, and on the bypass paths that matter. Each check should cover a distinct way the failure can reach production, and you should be able to say what it covers.

## Why Multiple Checks

Single check: "We fixed this path"
Several checks: "We covered the distinct paths we found"

Different checks catch different cases:
- Entry validation catches bad input at the API boundary
- Business logic rejects values that are invalid for the operation
- Environment guards prevent context-specific dangers
- Diagnostics capture evidence when another check fails

These are candidate locations, not a fixed set. A small, local defect may need
only one check. A value that crosses several trust boundaries may need one at
each boundary it actually crosses.

## Candidate Checks

### 1. Entry Point Validation
**Purpose:** Reject obviously invalid input at API boundary

```typescript
function createProject(name: string, workingDirectory: string) {
  if (!workingDirectory || workingDirectory.trim() === '') {
    throw new Error('workingDirectory cannot be empty');
  }
  if (!existsSync(workingDirectory)) {
    throw new Error(`workingDirectory does not exist: ${workingDirectory}`);
  }
  if (!statSync(workingDirectory).isDirectory()) {
    throw new Error(`workingDirectory is not a directory: ${workingDirectory}`);
  }
  // ... proceed
}
```

### 2. Business Logic Validation
**Purpose:** Ensure data makes sense for this operation

```typescript
function initializeWorkspace(projectDir: string, sessionId: string) {
  if (!projectDir) {
    throw new Error('projectDir required for workspace initialization');
  }
  // ... proceed
}
```

### 3. Environment Guards
**Purpose:** Prevent dangerous operations in specific contexts

```typescript
async function gitInit(directory: string) {
  // In tests, refuse git init outside temp directories
  if (process.env.NODE_ENV === 'test') {
    const normalized = normalize(resolve(directory));
    const tmpDir = normalize(resolve(tmpdir()));

    if (!normalized.startsWith(tmpDir)) {
      throw new Error(
        `Refusing git init outside temp dir during tests: ${directory}`
      );
    }
  }
  // ... proceed
}
```

### 4. Diagnostics
**Purpose:** Capture context for forensics

```typescript
async function gitInit(directory: string) {
  const stack = new Error().stack;
  logger.debug('About to git init', {
    directory,
    cwd: process.cwd(),
    stack,
  });
  // ... proceed
}
```

Diagnostics are not validation. Add them when they answer a question you
actually have. Log paths, cwd, timestamps, and non-sensitive metadata; never log
secret values or full environment dumps.

## Applying the Pattern

When you find a bug:

1. **Trace the data flow** - Where does the bad value originate? Where is it used?
2. **Map trust boundaries and bypass paths** - Which code paths can carry the bad value into the dangerous operation? Which are public, internal, test-only, or privileged?
3. **Add checks where they cover a distinct path** - Prefer the narrowest check that catches the path. Do not add a check whose only justification is "more layers".
4. **Test each check against the path it claims** - Try to bypass the earlier check and verify the later check catches it. Do not require every layer to have the same test.
5. **State the residual risk** - Say which paths are covered, which are not, and why the uncovered ones are acceptable.

## Example from Session

Bug: Empty `projectDir` caused `git init` in source code

**Data flow:**
1. Test setup → empty string
2. `Project.create(name, '')`
3. `WorkspaceManager.createWorkspace('')`
4. `git init` runs in `process.cwd()`

**Checks and diagnostics added at the boundaries the value crossed:**
- Layer 1: `Project.create()` validates not empty/exists/writable
- Layer 2: `WorkspaceManager` validates projectDir not empty
- Layer 3: `WorktreeManager` refuses git init outside tmpdir in tests
- Layer 4: Stack trace logging before git init

**Result:** All 1847 tests passed; the reproduction no longer occurred.
Those checks covered distinct paths in that codebase. They do not prove that
the bug can never recur through a new path.

## Key Insight

In that session, each check or diagnostic covered a different bypass path or question:
- Different code paths bypassed entry validation
- Mocks bypassed business logic checks
- Edge cases on different platforms needed environment guards
- Diagnostics identified structural misuse

**Don't stop at one check when a real second path exists.** Equally, don't add
checks that repeat the same coverage. Choose by trust boundary and bypass path,
and say what each check covers.
