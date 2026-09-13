"""
A fake standing in for AIService in every test, via the same
app.dependency_overrides mechanism used for the database. Never makes a
real network call — that keeps tests fast, free, and independent of
Gemini's rate limit.

should_fail lets a test deterministically force the "AI call fails"
branch of the answer/retry state machine — see conftest.py for how a
single shared instance is wired up so a test can flip it mid-request.
"""

from app.services.ai import AIFeedbackOut, AIQuestionOut, AIServiceError


class FakeAIService:
    def __init__(self):
        self.opening_question = AIQuestionOut(question="Tell me about a project you're proud of.", question_type="intro")
        self.next_question = AIQuestionOut(question="Can you go deeper on the trade-offs there?", question_type="follow_up")
        self.feedback = AIFeedbackOut(
            rating=4,
            rating_explanation="Solid, specific answers throughout.",
            strengths=["Clear communication"],
            weaknesses=["Could go deeper on trade-offs"],
            suggestions=["Practice explaining trade-offs explicitly"],
        )
        self.should_fail = False

    def _maybe_fail(self):
        if self.should_fail:
            raise AIServiceError("simulated outage")

    async def generate_opening_question(self, config: dict) -> AIQuestionOut:
        self._maybe_fail()
        return self.opening_question

    async def generate_next_turn(self, transcript: str, is_last_question: bool) -> AIQuestionOut:
        self._maybe_fail()
        return self.next_question

    async def generate_feedback(self, transcript: str) -> AIFeedbackOut:
        self._maybe_fail()
        return self.feedback
