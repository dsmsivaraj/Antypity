"""Unit tests for the built-in agents."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from agents.agent_skills import common_skills
from agents.example_agent import GeneralistAgent, MathAgent, PlannerAgent, ReviewerAgent
from backend.llm_client import LLMResult


@pytest.fixture()
def mock_llm():
    client = MagicMock()
    client.enabled = False
    client.complete.return_value = LLMResult(
        content="LLM output for task.", used_llm=True, provider="mock"
    )
    return client


class TestMathAgent:
    def test_scores_high_for_add_keyword(self):
        agent = MathAgent(skills=common_skills)
        assert agent.can_handle("add 3 and 5") == 90

    def test_scores_high_for_sum_keyword(self):
        agent = MathAgent(skills=common_skills)
        assert agent.can_handle("sum of 1 2 3") == 90

    def test_scores_high_for_total_keyword(self):
        agent = MathAgent(skills=common_skills)
        assert agent.can_handle("total of 10 20") == 90

    def test_scores_medium_for_two_numbers(self):
        agent = MathAgent(skills=common_skills)
        score = agent.can_handle("combine 5 and 10 into something")
        assert score == 70

    def test_scores_zero_for_no_numbers(self):
        agent = MathAgent(skills=common_skills)
        assert agent.can_handle("explain the architecture") == 0

    def test_executes_sum_correctly(self):
        agent = MathAgent(skills=common_skills)
        result = agent.execute("add 3 and 7")
        assert "10" in result.output
        assert result.used_llm is False

    def test_executes_negative_numbers(self):
        agent = MathAgent(skills=common_skills)
        result = agent.execute("add -5 and 15")
        assert "10" in result.output

    def test_executes_float_numbers(self):
        agent = MathAgent(skills=common_skills)
        result = agent.execute("add 1.5 and 2.5")
        assert "4" in result.output

    def test_result_has_metadata(self):
        agent = MathAgent(skills=common_skills)
        result = agent.execute("add 2 and 3")
        assert "values" in result.metadata

    def test_empty_task_returns_zero_total(self):
        agent = MathAgent(skills=common_skills)
        result = agent.execute("no numbers here at all")
        assert "0" in result.output


class TestGeneralistAgent:
    def test_always_scores_40(self, mock_llm):
        agent = GeneralistAgent(llm_client=mock_llm, skills=common_skills)
        assert agent.can_handle("anything at all") == 40
        assert agent.can_handle("very specific numeric add 5 5") == 40

    def test_executes_and_returns_llm_result(self, mock_llm):
        mock_llm.enabled = True
        mock_llm.complete.return_value = LLMResult(
            content="Here is my analysis.", used_llm=True, provider="mock"
        )
        agent = GeneralistAgent(llm_client=mock_llm, skills=common_skills)
        result = agent.execute("explain the system design")
        assert result.output == "Here is my analysis."
        assert result.used_llm is True

    def test_returns_fallback_when_llm_disabled(self, mock_llm):
        mock_llm.enabled = False
        mock_llm.complete.return_value = LLMResult(
            content="Fallback text.", used_llm=False, provider="disabled"
        )
        agent = GeneralistAgent(llm_client=mock_llm, skills=common_skills)
        result = agent.execute("do something")
        assert result.used_llm is False
        assert result.output == "Fallback text."

    def test_uses_context_skill(self, mock_llm):
        agent = GeneralistAgent(llm_client=mock_llm, skills=common_skills)
        result = agent.execute("plan this task", context={"env": "production"})
        mock_llm.complete.assert_called_once()
        call_kwargs = mock_llm.complete.call_args
        assert call_kwargs is not None

    def test_metadata_contains_provider(self, mock_llm):
        agent = GeneralistAgent(llm_client=mock_llm, skills=common_skills)
        result = agent.execute("test")
        assert "provider" in result.metadata


class TestPlannerAgent:
    def test_scores_high_for_planning_keywords(self, mock_llm):
        agent = PlannerAgent(llm_client=mock_llm, skills=common_skills)
        assert agent.can_handle("plan the release steps") == 92

    def test_executes_with_llm(self, mock_llm):
        agent = PlannerAgent(llm_client=mock_llm, skills=common_skills)
        result = agent.execute("break down the implementation")
        assert result.output


class TestReviewerAgent:
    def test_scores_high_for_review_keywords(self, mock_llm):
        agent = ReviewerAgent(llm_client=mock_llm, skills=common_skills)
        assert agent.can_handle("review this bug fix for regressions") == 88

    def test_executes_with_llm(self, mock_llm):
        agent = ReviewerAgent(llm_client=mock_llm, skills=common_skills)
        result = agent.execute("review the code changes")
        assert result.output
