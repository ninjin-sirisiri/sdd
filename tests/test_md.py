from sddlib.md import extract_task, extract_task_heading, plan_task_numbers


FENCED_PLAN = """# Plan

## Task 1: Real one

alpha

~~~markdown
## Task 2: Fake tilde
~~~

````
## Task 9: Fake four backticks
````

   ```
## Task 8: Fake indented fence
   ```

still task one

## Task 2: Real two

beta
"""


def test_plan_task_numbers_skip_fenced_headings() -> None:
    assert plan_task_numbers(FENCED_PLAN) == [1, 2]


def test_extract_task_includes_fenced_fake_headings_in_body() -> None:
    text = extract_task(FENCED_PLAN, 1)
    assert text is not None
    assert text.startswith("## Task 1: Real one")
    assert "Fake tilde" in text
    assert "Fake four backticks" in text
    assert "Fake indented fence" in text
    assert "still task one" in text
    assert "## Task 2: Real two" not in text


def test_extract_task_heading_ignores_fences() -> None:
    assert extract_task_heading(FENCED_PLAN, 1) == "## Task 1: Real one"
    assert extract_task_heading(FENCED_PLAN, 2) == "## Task 2: Real two"
    assert extract_task_heading(FENCED_PLAN, 9) == ""


def test_inner_triple_backticks_do_not_close_longer_fence() -> None:
    plan = (
        "## Task 1: Outer\n"
        "````\n"
        "```\n"
        "## Task 2: Still fenced\n"
        "```\n"
        "````\n"
        "\n"
        "## Task 2: Real\n"
    )
    assert plan_task_numbers(plan) == [1, 2]
    body = extract_task(plan, 1)
    assert body is not None
    assert "## Task 2: Still fenced" in body
    assert extract_task_heading(plan, 2) == "## Task 2: Real"


def test_four_space_indent_is_not_a_fence() -> None:
    plan = (
        "## Task 1: First\n"
        "\n"
        "    ```\n"
        "## Task 2: Real because opener is indented code\n"
        "    ```\n"
    )
    assert plan_task_numbers(plan) == [1, 2]
    assert extract_task_heading(plan, 2) == (
        "## Task 2: Real because opener is indented code"
    )
