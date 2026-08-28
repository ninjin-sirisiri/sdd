# CONTEXT.md format

CONTEXT.md is a glossary and nothing else. No implementation details, specs, or scratch notes.

Template:

    # {Context Name}

    {One or two sentences: what this context is}

    ## Terms

    **{Term}**:
    {What it IS, one or two sentences}

    _Avoid_: {rejected synonyms}

Rules:
- Project-specific terms only. General programming concepts do not belong.
- One canonical term per concept. Put rivals under `_Avoid_`.
- Create the file lazily when the first term is resolved.
- In v1 write only a root CONTEXT.md. If CONTEXT-MAP.md exists, ask which single CONTEXT.md to use. Do not route terms automatically.
