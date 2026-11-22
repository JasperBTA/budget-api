import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import ai_review
import httpx2
import pytest
from ai_review import Finding, Review, build_review_payload, collect_diff, commentable_lines
from google.genai import errors

PATCH = "\n".join(
    [
        "@@ -10,4 +10,5 @@ class Base(DeclarativeBase):",
        " context ten",
        "-removed eleven",
        "+added eleven",
        "++ b/evil.py",  # added line whose content looks like a file header
        " context thirteen",
        "\\ No newline at end of file",
        "@@ -40,2 +41,3 @@ class User(Base):",
        "-old",
        "+new forty-one \x0c with a form feed",  # splitlines() would cut this line in two
        "+new forty-two",
        " context forty-three",
    ]
)


def test_commentable_lines_follow_the_new_side_of_the_patch() -> None:
    assert commentable_lines(PATCH) == {10, 11, 12, 13, 41, 42, 43}


def test_collect_diff_skips_files_without_a_patch() -> None:
    files = [
        {"filename": "my file.py", "status": "added", "patch": "@@ -0,0 +1,2 @@\n+a\n+b"},
        {"filename": "logo.png", "status": "added"},
    ]

    diff, commentable = collect_diff(files)

    assert commentable == {("my file.py", 1), ("my file.py", 2)}
    assert "### logo.png (added, no textual diff)" in diff


def finding(path: str, line: int) -> Finding:
    return Finding(path=path, line=line, severity="bug", rule="Business rule 1", comment="float")


def test_payload_puts_diff_findings_inline_and_the_rest_in_the_summary() -> None:
    review = Review(summary="One issue.", findings=[finding("a.py", 3), finding("b.py", 99)])

    payload = build_review_payload(review, {("a.py", 3)}, "test-model")

    assert payload["event"] == "COMMENT"
    assert payload["comments"] == [
        {"path": "a.py", "line": 3, "side": "RIGHT", "body": "**bug** (Business rule 1): float"}
    ]
    assert "`b.py:99` **bug** (Business rule 1): float" in payload["body"]
    assert "`test-model`" in payload["body"]


def test_payload_without_findings_says_so() -> None:
    payload = build_review_payload(Review(summary="Looks fine.", findings=[]), set(), "m")
    assert payload["comments"] == []
    assert payload["body"].endswith("No findings.")


# --- main(): every failure must end in a skip with exit code 0 (the review is advisory) ---

FILES = json.dumps([[{"filename": "a.py", "status": "modified", "patch": "@@ -1 +1 @@\n+x"}]])
REVIEW = Review(summary="s", findings=[finding("a.py", 1)])
GhCall = tuple[tuple[str, ...], str | None]


def gh_error(stderr: str) -> subprocess.CalledProcessError:
    return subprocess.CalledProcessError(1, "gh", stderr=stderr)


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, value in {
        "GEMINI_API_KEY": "key",
        "REPO": "o/r",
        "PR_NUMBER": "7",
        "BASE_REF": "main",
        "HEAD_SHA": "abc123",
    }.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    monkeypatch.setenv("GEMINI_MODELS", "primary,fallback")  # tests never depend on the defaults


def fake_gh(monkeypatch: pytest.MonkeyPatch, *responses: str | Exception) -> list[GhCall]:
    calls: list[GhCall] = []
    queue = list(responses)

    def gh(*args: str, stdin: str | None = None) -> str:
        calls.append((args, stdin))
        response = queue.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(ai_review, "gh", gh)
    return calls


def gemini_returning(result: Review | Exception) -> Callable[..., Review]:
    def ask(*_: Any) -> Review:
        if isinstance(result, Exception):
            raise result
        return result

    return ask


def test_missing_key_skips(
    monkeypatch: pytest.MonkeyPatch, env: None, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("GEMINI_API_KEY")
    calls = fake_gh(monkeypatch)

    assert ai_review.main() == 0
    assert calls == []
    assert "skipped: GEMINI_API_KEY is not set" in capsys.readouterr().out


def test_github_failure_skips(
    monkeypatch: pytest.MonkeyPatch, env: None, capsys: pytest.CaptureFixture[str]
) -> None:
    fake_gh(monkeypatch, gh_error("HTTP 406: diff too large"))

    assert ai_review.main() == 0
    assert "GitHub API call failed: HTTP 406" in capsys.readouterr().out


def test_gemini_failure_skips_without_posting(
    monkeypatch: pytest.MonkeyPatch, env: None, capsys: pytest.CaptureFixture[str]
) -> None:
    calls = fake_gh(monkeypatch, FILES, "rules")
    monkeypatch.setattr(ai_review, "ask_gemini", gemini_returning(TimeoutError("read timed out")))

    assert ai_review.main() == 0
    assert len(calls) == 2  # files + rules, no review posted
    assert "Gemini call failed: primary: TimeoutError" in capsys.readouterr().out


def test_rejected_line_comment_retries_with_everything_in_the_body(
    monkeypatch: pytest.MonkeyPatch, env: None
) -> None:
    calls = fake_gh(monkeypatch, FILES, "rules", gh_error("HTTP 422"), "{}")
    monkeypatch.setattr(ai_review, "ask_gemini", gemini_returning(REVIEW))

    assert ai_review.main() == 0
    first, retry = (json.loads(stdin or "") for _, stdin in calls[2:])
    assert len(first["comments"]) == 1
    assert retry["comments"] == []
    assert "`a.py:1`" in retry["body"]
    assert retry["commit_id"] == "abc123"


def test_rules_come_from_the_base_branch(monkeypatch: pytest.MonkeyPatch, env: None) -> None:
    calls = fake_gh(monkeypatch, FILES, "rules", "{}")
    monkeypatch.setattr(ai_review, "ask_gemini", gemini_returning(REVIEW))

    ai_review.main()

    assert calls[1][0][-1] == "repos/o/r/contents/AGENTS.md?ref=main"


def test_posting_failure_skips(
    monkeypatch: pytest.MonkeyPatch, env: None, capsys: pytest.CaptureFixture[str]
) -> None:
    fake_gh(monkeypatch, FILES, "rules", gh_error("HTTP 422"), gh_error("HTTP 403"))
    monkeypatch.setattr(ai_review, "ask_gemini", gemini_returning(REVIEW))

    assert ai_review.main() == 0
    assert "posting the review failed: HTTP 403" in capsys.readouterr().out


# --- fallback model (docs/design/0001-gemini-fallback-model.md) ---


def api_error(code: int) -> errors.APIError:
    body = {"error": {"code": code, "message": "m", "status": "S"}}
    return errors.ServerError(code, body) if code >= 500 else errors.ClientError(code, body)


def gemini_by_model(
    results: dict[str, Review | Exception], calls: list[str]
) -> Callable[..., Review]:
    def ask(_key: str, model: str, _prompt: str) -> Review:
        calls.append(model)
        result = results[model]
        if isinstance(result, Exception):
            raise result
        return result

    return ask


REQUEST = httpx2.Request("POST", "https://generativelanguage.googleapis.com")
# What the SDK really raises on its httpx2 backend, not only builtin exceptions.
FALL_THROUGH = [
    api_error(503),
    api_error(504),
    api_error(429),
    api_error(408),
    api_error(404),
    httpx2.ReadTimeout("read timed out", request=REQUEST),
    httpx2.ConnectError("connection refused", request=REQUEST),
]


@pytest.mark.parametrize("first_error", FALL_THROUGH, ids=lambda e: type(e).__name__)
def test_transient_or_unknown_model_falls_back_to_the_next_model(
    monkeypatch: pytest.MonkeyPatch, env: None, tmp_path: Path, first_error: Exception
) -> None:
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    gh_calls = fake_gh(monkeypatch, FILES, "rules", "{}")
    calls: list[str] = []
    primary, fallback = "primary", "fallback"
    monkeypatch.setattr(
        ai_review, "ask_gemini", gemini_by_model({primary: first_error, fallback: REVIEW}, calls)
    )

    assert ai_review.main() == 0
    assert calls == [primary, fallback]
    posted = json.loads(gh_calls[2][1] or "")
    assert f"`{fallback}`" in posted["body"]  # the header names the model that answered
    line = summary.read_text().strip()
    assert line.startswith(f"{primary}: {type(first_error).__name__}")
    assert line.endswith(f"→ {fallback}: answered")


@pytest.mark.parametrize(
    "error",
    [api_error(401), api_error(403), api_error(400), ValueError("invalid JSON in the answer")],
)
def test_key_request_or_answer_problems_skip_without_a_second_model(
    monkeypatch: pytest.MonkeyPatch, env: None, capsys: pytest.CaptureFixture[str], error: Exception
) -> None:
    gh_calls = fake_gh(monkeypatch, FILES, "rules")
    calls: list[str] = []
    primary, fallback = "primary", "fallback"
    monkeypatch.setattr(
        ai_review, "ask_gemini", gemini_by_model({primary: error, fallback: REVIEW}, calls)
    )

    assert ai_review.main() == 0
    assert calls == [primary]
    assert len(gh_calls) == 2  # nothing posted
    assert "AI review skipped" in capsys.readouterr().out


def test_all_models_failing_skips_and_lists_each_error(
    monkeypatch: pytest.MonkeyPatch, env: None, capsys: pytest.CaptureFixture[str]
) -> None:
    fake_gh(monkeypatch, FILES, "rules")
    primary, fallback = "primary", "fallback"
    failures: dict[str, Review | Exception] = {primary: api_error(503), fallback: api_error(504)}
    monkeypatch.setattr(ai_review, "ask_gemini", gemini_by_model(failures, []))

    assert ai_review.main() == 0
    out = capsys.readouterr().out
    assert f"{primary}: ServerError: 503" in out and f"{fallback}: ServerError: 504" in out


def test_gemini_models_overrides_the_order(monkeypatch: pytest.MonkeyPatch, env: None) -> None:
    monkeypatch.setenv("GEMINI_MODELS", " b , a ")
    fake_gh(monkeypatch, FILES, "rules", "{}")
    calls: list[str] = []
    monkeypatch.setattr(
        ai_review, "ask_gemini", gemini_by_model({"b": api_error(503), "a": REVIEW}, calls)
    )

    assert ai_review.main() == 0
    assert calls == ["b", "a"]


def test_empty_override_falls_back_to_the_default_models(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_MODELS", " , ")
    assert ai_review.models() == list(ai_review.DEFAULT_MODELS)
