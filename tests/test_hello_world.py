"""
Tests for MAYA Hello World LangGraph
======================================
Run with:  pytest tests/
Run verbose: pytest tests/ -v

LEARNING NOTES for Srinivasan:
--------------------------------
Each test invokes the compiled graph with a specific input and
asserts something about the resulting state.

This tests:
  1. Language detection logic
  2. Intent detection logic
  3. End-to-end graph execution (all nodes run, state is complete)
  4. Conditional routing (correct branch is taken)
"""

import pytest
from src.maya.graph.hello_world_graph import maya_graph
from src.maya.models.state import MayaState


# ─── Helper ───────────────────────────────────────────────────────────────────

def invoke(user_input: str) -> MayaState:
    """Helper: build initial state and invoke the graph."""
    return maya_graph.invoke(
        {
            "user_input": user_input,
            "language": "",
            "intent": "",
            "response": "",
            "steps": [],
        }
    )


# ─── Language Detection ────────────────────────────────────────────────────────

class TestLanguageDetection:

    def test_pure_english_detected(self):
        result = invoke("Hello how are you today")
        assert result["language"] == "english"

    def test_pure_hindi_detected(self):
        # Two or more Hindi markers → hindi
        result = invoke("Namaste kya hal hai aap theek")
        assert result["language"] == "hindi"

    def test_hinglish_detected(self):
        # One Hindi marker → hinglish
        result = invoke("Hello namaste, nice to meet you")
        assert result["language"] == "hinglish"

    def test_english_with_no_hindi_words(self):
        result = invoke("What is photosynthesis?")
        assert result["language"] == "english"

    def test_multiple_hindi_markers_is_hindi(self):
        result = invoke("main aap se bahut accha seekhna chahte hain")
        assert result["language"] == "hindi"


# ─── Intent Detection ─────────────────────────────────────────────────────────

class TestIntentDetection:

    def test_english_greeting(self):
        result = invoke("Hello MAYA!")
        assert result["intent"] == "greeting"

    def test_hindi_greeting(self):
        result = invoke("Namaste!")
        assert result["intent"] == "greeting"

    def test_english_question(self):
        result = invoke("What is gravity?")
        assert result["intent"] == "question"

    def test_hindi_question(self):
        result = invoke("Gravity kya hoti hai")
        assert result["intent"] == "question"

    def test_math_intent_english(self):
        result = invoke("Calculate 25 times 4")
        assert result["intent"] == "math"

    def test_math_intent_symbol(self):
        result = invoke("What is 5 + 3")
        # "what" is a question word, but "+" is math - precedence: greeting > math > question
        # "+" matches math_words so intent should be "math"
        assert result["intent"] == "math"

    def test_general_intent_fallback(self):
        result = invoke("blah blah nonsense xyz")
        assert result["intent"] == "general"

    def test_greeting_takes_precedence_over_question(self):
        # "hello" + "what" in same sentence - greeting wins
        result = invoke("hello what is your name")
        assert result["intent"] == "greeting"


# ─── Conditional Routing ──────────────────────────────────────────────────────

class TestConditionalRouting:

    def test_greeting_routes_to_greet_response(self):
        """Greeting intent should take the greet_response branch."""
        result = invoke("Hello!")
        # greet_response node logs a specific step
        assert any("greet_response" in step for step in result["steps"])

    def test_question_routes_to_help_response(self):
        """Question intent should take the help_response branch."""
        result = invoke("What is the speed of light?")
        assert any("help_response" in step for step in result["steps"])

    def test_math_routes_to_help_response(self):
        """Math intent should take the help_response branch."""
        result = invoke("Calculate 10 + 5")
        assert any("help_response" in step for step in result["steps"])


# ─── End-to-End Graph Execution ───────────────────────────────────────────────

class TestEndToEnd:

    def test_all_state_fields_populated(self):
        """Every field in MayaState should be filled after graph runs."""
        result = invoke("Hello MAYA!")
        assert result["user_input"] == "Hello MAYA!"
        assert result["language"] in {"english", "hindi", "hinglish"}
        assert result["intent"] in {"greeting", "question", "math", "general"}
        assert len(result["response"]) > 0
        assert len(result["steps"]) >= 3   # At least 3 nodes must log

    def test_graph_always_produces_response(self):
        """Every input must produce a non-empty response - no crashes."""
        inputs = [
            "Hello!",
            "Namaste!",
            "What is the sun?",
            "5 + 3",
            "random text here",
            "",   # Edge case: empty string
        ]
        for text in inputs:
            result = invoke(text)
            assert isinstance(result["response"], str), f"No response for: '{text}'"
            assert len(result["response"]) > 0, f"Empty response for: '{text}'"

    def test_steps_show_correct_node_order(self):
        """Execution trace should always start with detect_language."""
        result = invoke("Hello!")
        assert result["steps"][0].startswith("[detect_language]")
        assert result["steps"][1].startswith("[understand_intent]")
        # Third step is whichever response node was chosen
        assert result["steps"][2].startswith("[greet_response]") or \
               result["steps"][2].startswith("[help_response]")

    def test_user_input_preserved_unchanged(self):
        """user_input must never be modified by any node."""
        original = "Hello MAYA, kya hal hai?"
        result = invoke(original)
        assert result["user_input"] == original

    def test_hindi_greeting_response_contains_hindi(self):
        """A Hindi greeting should get a Hindi response."""
        result = invoke("Namaste! Main Maya se milna chahta hun!")
        # Should be hindi or hinglish, and response should contain hindi text
        assert result["language"] in {"hindi", "hinglish"}
        # Check response has some Devanagari or common Hindi romanization
        hindi_indicators = ["hun", "main", "Namaste", "aap", "ho", "kya"]
        assert any(word in result["response"] for word in hindi_indicators)
