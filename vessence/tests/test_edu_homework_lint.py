from agent_skills.edu_homework_lint import lint_prompt


def kinds(issues):
    return [issue["kind"] for issue in issues]


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
