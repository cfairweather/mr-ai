"""Tests for the AI pull-request reviewer.

Covers the parts that are wrong in ways a human reviewer would not notice: the
per-provider request shape, the response parsers, JSON recovery from a chatty
model, and the safety rules in `sanitize_review` that stop a compromised or
sloppy model response from producing an approval it did not earn.
"""

from __future__ import annotations

import os
import re
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".github", "scripts"))

import ai_review as air  # noqa: E402


class TestConfig(unittest.TestCase):
    def test_llm_api_key_wins_over_provider_variable(self):
        env = {"LLM_API_KEY": "primary", "ANTHROPIC_API_KEY": "fallback"}
        self.assertEqual(air.resolve_api_key("anthropic", env), "primary")

    def test_falls_back_to_provider_variable(self):
        self.assertEqual(air.resolve_api_key("openai", {"OPENAI_API_KEY": "sk-x"}), "sk-x")

    def test_gemini_accepts_either_conventional_name(self):
        self.assertEqual(air.resolve_api_key("gemini", {"GOOGLE_API_KEY": "g"}), "g")

    def test_missing_key_is_a_clear_error(self):
        with self.assertRaises(air.ReviewError) as ctx:
            air.resolve_api_key("anthropic", {})
        self.assertIn("LLM_API_KEY", str(ctx.exception))

    def test_anthropic_has_a_verified_default_model(self):
        self.assertEqual(air.resolve_model("anthropic", {}), "claude-opus-5")

    def test_other_providers_require_an_explicit_model(self):
        # Guessing an OpenAI/Gemini model ID would 404 at request time; failing
        # loudly at config time is the better trade.
        for provider in ("openai", "gemini"):
            with self.assertRaises(air.ReviewError):
                air.resolve_model(provider, {})

    def test_base_url_override_marks_endpoint_custom(self):
        url, custom = air.resolve_base_url("openai", {"LLM_BASE_URL": "http://vllm:8000/"})
        self.assertEqual(url, "http://vllm:8000")
        self.assertTrue(custom)
        url, custom = air.resolve_base_url("openai", {})
        self.assertEqual(url, "https://api.openai.com")
        self.assertFalse(custom)


class TestRequestShapes(unittest.TestCase):
    common = dict(model="m", api_key="k", system="sys", user="usr", max_tokens=99)

    def test_anthropic_shape(self):
        url, headers, payload = air.build_anthropic_request(
            base_url="https://api.anthropic.com", **self.common
        )
        self.assertEqual(url, "https://api.anthropic.com/v1/messages")
        self.assertEqual(headers["x-api-key"], "k")
        self.assertEqual(headers["anthropic-version"], "2023-06-01")
        self.assertEqual(payload["system"], "sys")
        self.assertEqual(payload["messages"], [{"role": "user", "content": "usr"}])

    def test_anthropic_omits_sampling_parameters(self):
        # temperature/top_p/top_k are rejected with a 400 on claude-opus-5.
        _, _, payload = air.build_anthropic_request(
            base_url="https://api.anthropic.com", **self.common
        )
        for banned in ("temperature", "top_p", "top_k"):
            self.assertNotIn(banned, payload)

    def test_anthropic_honours_self_hosted_base_url(self):
        url, _, _ = air.build_anthropic_request(base_url="http://proxy:9000", **self.common)
        self.assertEqual(url, "http://proxy:9000/v1/messages")

    def test_openai_shape_and_bearer_auth(self):
        url, headers, payload = air.build_openai_request(
            base_url="https://api.openai.com", custom_base=False, **self.common
        )
        self.assertEqual(url, "https://api.openai.com/v1/chat/completions")
        self.assertEqual(headers["authorization"], "Bearer k")
        self.assertEqual([m["role"] for m in payload["messages"]], ["system", "user"])

    def test_openai_token_field_depends_on_endpoint(self):
        _, _, hosted = air.build_openai_request(
            base_url="https://api.openai.com", custom_base=False, **self.common
        )
        self.assertIn("max_completion_tokens", hosted)
        _, _, selfhosted = air.build_openai_request(
            base_url="http://vllm:8000", custom_base=True, **self.common
        )
        self.assertIn("max_tokens", selfhosted)

    def test_openai_token_field_is_overridable(self):
        os.environ["OPENAI_MAX_TOKENS_FIELD"] = "max_tokens"
        try:
            _, _, payload = air.build_openai_request(
                base_url="https://api.openai.com", custom_base=False, **self.common
            )
            self.assertIn("max_tokens", payload)
            self.assertNotIn("max_completion_tokens", payload)
        finally:
            del os.environ["OPENAI_MAX_TOKENS_FIELD"]

    def test_gemini_keeps_the_key_out_of_the_url(self):
        url, headers, payload = air.build_gemini_request(
            base_url="https://generativelanguage.googleapis.com", **self.common
        )
        self.assertNotIn("k", url)
        self.assertNotIn("?", url)
        self.assertEqual(headers["x-goog-api-key"], "k")
        self.assertEqual(payload["systemInstruction"]["parts"][0]["text"], "sys")
        self.assertEqual(payload["generationConfig"]["maxOutputTokens"], 99)


class TestResponseParsers(unittest.TestCase):
    def test_anthropic_joins_text_blocks_and_skips_others(self):
        data = {"content": [
            {"type": "thinking", "thinking": ""},
            {"type": "text", "text": "a"},
            {"type": "text", "text": "b"},
        ]}
        self.assertEqual(air.parse_anthropic_response(data), "ab")

    def test_anthropic_refusal_raises_rather_than_returning_empty(self):
        data = {"stop_reason": "refusal", "stop_details": {"category": "cyber"}, "content": []}
        with self.assertRaises(air.ReviewError) as ctx:
            air.parse_anthropic_response(data)
        self.assertIn("refusal", str(ctx.exception))

    def test_openai_and_gemini_parsers(self):
        self.assertEqual(
            air.parse_openai_response({"choices": [{"message": {"content": " hi "}}]}), "hi"
        )
        self.assertEqual(
            air.parse_gemini_response(
                {"candidates": [{"content": {"parts": [{"text": "x"}, {"text": "y"}]}}]}
            ),
            "xy",
        )

    def test_empty_provider_responses_raise(self):
        with self.assertRaises(air.ReviewError):
            air.parse_openai_response({"choices": []})
        with self.assertRaises(air.ReviewError):
            air.parse_gemini_response({"candidates": []})


class TestExtractJson(unittest.TestCase):
    def test_bare_object(self):
        self.assertEqual(air.extract_json('{"verdict": "APPROVE"}')["verdict"], "APPROVE")

    def test_fenced_object(self):
        text = 'Sure!\n```json\n{"verdict": "COMMENT"}\n```\nHope that helps.'
        self.assertEqual(air.extract_json(text)["verdict"], "COMMENT")

    def test_object_embedded_in_prose(self):
        text = 'Here is my review: {"verdict": "COMMENT", "summary": "ok"} — done.'
        self.assertEqual(air.extract_json(text)["summary"], "ok")

    def test_braces_inside_strings_do_not_break_balancing(self):
        text = 'x {"summary": "use {this} and }that{", "verdict": "COMMENT"} y'
        self.assertEqual(air.extract_json(text)["summary"], "use {this} and }that{")

    def test_empty_and_unparseable_raise(self):
        for bad in ("", "   ", "no json here at all"):
            with self.assertRaises(air.ReviewError):
                air.extract_json(bad)


class TestSanitizeReview(unittest.TestCase):
    files = {"src/app.py", "README.md"}

    def test_failing_gate_cannot_be_approved(self):
        raw = {
            "verdict": "APPROVE",
            "gates": [{"gate": "Security", "result": "FAIL", "evidence": "hardcoded key"}],
        }
        out = air.sanitize_review(raw, self.files)
        self.assertEqual(out["verdict"], "REQUEST_CHANGES")
        self.assertEqual(out["failed_gates"], ["Security"])

    def test_blocking_comment_cannot_be_approved(self):
        raw = {
            "verdict": "APPROVE",
            "comments": [
                {"path": "src/app.py", "line": 3, "severity": "blocking", "body": "sql injection"}
            ],
        }
        self.assertEqual(air.sanitize_review(raw, self.files)["verdict"], "REQUEST_CHANGES")

    def test_clean_review_keeps_its_approval(self):
        raw = {
            "verdict": "APPROVE",
            "gates": [{"gate": "Code checks", "result": "PASS", "evidence": "tests added"}],
            "comments": [
                {"path": "src/app.py", "line": 3, "severity": "praise", "body": "nice"}
            ],
        }
        self.assertEqual(air.sanitize_review(raw, self.files)["verdict"], "APPROVE")

    def test_unknown_verdict_degrades_to_comment(self):
        for bad in ("LGTM", "", "MERGE_IT", None):
            self.assertEqual(air.sanitize_review({"verdict": bad}, self.files)["verdict"], "COMMENT")

    def test_unknown_gate_result_is_treated_as_failure(self):
        # An unparseable result is unknown, and unknown is not success.
        raw = {"verdict": "APPROVE", "gates": [{"gate": "X", "result": "probably fine"}]}
        out = air.sanitize_review(raw, self.files)
        self.assertEqual(out["gates"][0]["result"], "FAIL")
        self.assertEqual(out["verdict"], "REQUEST_CHANGES")

    def test_comment_outside_the_diff_is_demoted_not_dropped(self):
        raw = {
            "verdict": "COMMENT",
            "comments": [
                {"path": "not/in/diff.py", "line": 9, "severity": "suggestion", "body": "hmm"},
                {"path": "src/app.py", "line": 4, "severity": "suggestion", "body": "ok"},
            ],
        }
        out = air.sanitize_review(raw, self.files)
        self.assertEqual([c["path"] for c in out["comments"]], ["src/app.py"])
        self.assertEqual(len(out["unanchored"]), 1)
        self.assertIn("hmm", out["unanchored"][0]["body"])

    def test_missing_or_bogus_line_is_demoted(self):
        raw = {"comments": [
            {"path": "src/app.py", "severity": "suggestion", "body": "no line"},
            {"path": "src/app.py", "line": "abc", "severity": "suggestion", "body": "bad line"},
        ]}
        out = air.sanitize_review(raw, self.files)
        self.assertEqual(out["comments"], [])
        self.assertEqual(len(out["unanchored"]), 2)

    def test_comment_count_is_capped(self):
        raw = {"comments": [
            {"path": "src/app.py", "line": i, "severity": "suggestion", "body": f"n{i}"}
            for i in range(1, 40)
        ]}
        self.assertEqual(len(air.sanitize_review(raw, self.files, max_comments=5)["comments"]), 5)

    def test_unknown_severity_becomes_suggestion(self):
        raw = {"comments": [
            {"path": "src/app.py", "line": 1, "severity": "CATASTROPHIC", "body": "x"}
        ]}
        self.assertEqual(air.sanitize_review(raw, self.files)["comments"][0]["severity"], "suggestion")

    def test_junk_entries_are_ignored(self):
        raw = {"gates": ["not a dict", None], "comments": ["nope", {"body": "   "}]}
        out = air.sanitize_review(raw, self.files)
        self.assertEqual(out["gates"], [])
        self.assertEqual(out["comments"], [])


class TestRenderBody(unittest.TestCase):
    def test_body_contains_verdict_gates_and_attribution(self):
        review = air.sanitize_review(
            {
                "summary": "Adds a reviewer.",
                "repo_fit": "Fits the repo's gate model.",
                "verdict": "COMMENT",
                "gates": [{"gate": "Documentation", "result": "PASS", "evidence": "docs/ai-review.md"}],
            },
            set(),
        )
        body = air.render_body(review, "anthropic", "claude-opus-5")
        self.assertIn("**Verdict: COMMENT**", body)
        self.assertIn("Documentation", body)
        self.assertIn("Fit for this repository", body)
        self.assertIn("Generated by [Claude Code]", body)
        self.assertIn("anthropic/claude-opus-5", body)

    def test_pipes_in_evidence_do_not_break_the_table(self):
        review = air.sanitize_review(
            {"gates": [{"gate": "G", "result": "PASS", "evidence": "a | b\nc"}]}, set()
        )
        row = [ln for ln in air.render_body(review, "p", "m").splitlines() if ln.startswith("| G ")][0]
        # Count only unescaped pipes: 4 delimiters => 3 cells. The pipe inside
        # the evidence is escaped, so it must not add a cell.
        delimiters = len(re.findall(r"(?<!\\)\|", row))
        self.assertEqual(delimiters, 4)
        self.assertIn(r"a \| b", row)
        self.assertNotIn("\n", row)  # the newline in evidence was flattened


class TestScrub(unittest.TestCase):
    def test_query_string_is_stripped_from_logged_urls(self):
        self.assertEqual(air._scrub("https://x/v1?key=secret123"), "https://x/v1")
        self.assertNotIn("secret123", air._scrub("https://x/v1?key=secret123"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
