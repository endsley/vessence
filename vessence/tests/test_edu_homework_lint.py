from agent_skills.edu_homework_lint import (
    lint_issue,
    lint_prompt,
    prompt_without_display_math,
    prompt_without_inline_or_environment_math,
    typo_lint_issues,
)


def kinds(issues):
    return [issue["kind"] for issue in issues]


def test_lint_helpers_preserve_issue_shape_typo_order_and_math_stripping():
    assert lint_issue("high", "kind", "message") == {
        "severity": "high",
        "kind": "kind",
        "message": "message",
    }
    assert typo_lint_issues("Please recieve thier file") == [
        {"severity": "med", "kind": "typo", "message": "Likely typo: 'recieve' -> 'receive'"},
        {"severity": "med", "kind": "typo", "message": "Likely typo: 'thier' -> 'their'"},
    ]
    assert prompt_without_display_math(r"before $$\frac{1}{2}$$ after") == "before  after"
    assert prompt_without_inline_or_environment_math(
        r"$\frac{1}{2}$ \begin{matrix}\sqrt{x}\end{matrix} \frac{1}{3}"
    ).strip() == r"\frac{1}{3}"


def test_lint_prompt_flags_template_math_typo_and_short_prompt_issues():
    issues = lint_prompt("{{ value }} $x TODO", "recieve")

    assert kinds(issues) == [
        "unrendered_jinja",
        "unbalanced_math",
        "typo",
        "short_prompt",
        "marker",
    ]
    assert issues[0]["severity"] == "high"
    assert issues[2]["message"] == "Likely typo: 'recieve' -> 'receive'"


def test_lint_prompt_flags_unwrapped_latex_and_fraction_repr():
    issues = lint_prompt(r"Use \frac{1}{2} and Fraction(1, 2)", "A long enough visible prompt")

    assert "unwrapped_latex" in kinds(issues)
    assert "fraction_repr_leak" in kinds(issues)


def test_lint_prompt_ignores_wrapped_math_and_display_environment():
    issues = lint_prompt(
        r"$\frac{1}{2}$ \begin{matrix}\frac{1}{2}\end{matrix}",
        "A sufficiently long prompt without typo",
    )

    assert kinds(issues) == []
