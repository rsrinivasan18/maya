"""
Tests for MAYA Conversation Graph
====================================
Run with:  pytest tests/
Run verbose: pytest tests/ -v

Updated Session 2:
  - invoke() helper now includes message_history in initial state
  - Added tests for farewell intent + message_history accumulation
"""

import pytest
from src.maya.agents.memory_store import MemoryStore
from src.maya.graph.hello_world_graph import maya_graph


# ─── Helper ───────────────────────────────────────────────────────────────────

def invoke(user_input: str, history: list[dict] | None = None) -> dict:
    """Helper: build initial state and invoke the graph."""
    return maya_graph.invoke(
        {
            "user_input": user_input,
            "language": "",
            "intent": "",
            "response": "",
            "steps": [],
            "message_history": history or [],   # NEW - carry history between turns
        }
    )


# ─── Language Detection ────────────────────────────────────────────────────────

class TestLanguageDetection:

    def test_pure_english_detected(self):
        result = invoke("Hello how are you today")
        assert result["language"] == "english"

    def test_pure_hindi_detected(self):
        result = invoke("Namaste kya hal hai aap theek")
        assert result["language"] == "hindi"

    def test_hinglish_detected(self):
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

    def test_general_intent_fallback(self):
        result = invoke("blah blah nonsense xyz")
        assert result["intent"] == "general"

    def test_greeting_takes_precedence_over_question(self):
        result = invoke("hello what is your name")
        assert result["intent"] == "greeting"

    # ── NEW: Farewell intent ──────────────────────────────────────────────────

    def test_farewell_english(self):
        result = invoke("bye MAYA!")
        assert result["intent"] == "farewell"

    def test_farewell_hindi(self):
        result = invoke("alvida")
        assert result["intent"] == "farewell"

    def test_farewell_hinglish(self):
        result = invoke("goodbye MAYA phir milenge")
        assert result["intent"] == "farewell"

    def test_farewell_takes_highest_precedence(self):
        # Even if "hello" is in sentence, "bye" should win
        result = invoke("bye hello MAYA")
        assert result["intent"] == "farewell"

    def test_exit_triggers_farewell(self):
        result = invoke("exit")
        assert result["intent"] == "farewell"

    def test_quit_triggers_farewell(self):
        result = invoke("quit")
        assert result["intent"] == "farewell"


# ─── Conditional Routing ──────────────────────────────────────────────────────

class TestConditionalRouting:

    def test_greeting_routes_to_greet_response(self):
        result = invoke("Hello!")
        assert any("greet_response" in step for step in result["steps"])

    def test_farewell_routes_to_farewell_response(self):
        result = invoke("Goodbye!")
        assert any("farewell_response" in step for step in result["steps"])

    def test_question_routes_to_help_response(self):
        result = invoke("What is the speed of light?")
        assert any("help_response" in step for step in result["steps"])

    def test_math_routes_to_help_response(self):
        result = invoke("Calculate 10 + 5")
        assert any("help_response" in step for step in result["steps"])


# ─── Message History ──────────────────────────────────────────────────────────

class TestMessageHistory:

    def test_response_appended_to_history(self):
        """After one turn, history should contain the assistant response."""
        result = invoke("Hello!", history=[{"role": "user", "content": "Hello!"}])
        # message_history starts with user msg, graph appends assistant msg
        assert len(result["message_history"]) == 2
        assert result["message_history"][0]["role"] == "user"
        assert result["message_history"][1]["role"] == "assistant"

    def test_history_accumulates_across_turns(self):
        """Simulate 2-turn conversation - history should grow each turn."""
        # Turn 1
        history = [{"role": "user", "content": "Hello!"}]
        r1 = invoke("Hello!", history=history)
        history = r1["message_history"]    # now has [user, assistant]
        assert len(history) == 2

        # Turn 2 - add next user message
        history = history + [{"role": "user", "content": "What is gravity?"}]
        r2 = invoke("What is gravity?", history=history)
        history = r2["message_history"]    # now has [user, assistant, user, assistant]
        assert len(history) == 4

    def test_empty_history_on_first_turn(self):
        """First turn with no history - graph still works."""
        result = invoke("Hello!")
        # No user msg in initial state - only assistant response appended
        assert len(result["message_history"]) == 1
        assert result["message_history"][0]["role"] == "assistant"

    def test_farewell_shows_turn_count(self):
        """Farewell response should mention how many turns were had."""
        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"},
            {"role": "user", "content": "bye"},
        ]
        result = invoke("bye", history=history)
        # farewell_response counts user messages in history
        assert "2" in result["response"]   # 2 user turns


# ─── End-to-End ───────────────────────────────────────────────────────────────

class TestEndToEnd:

    def test_all_state_fields_populated(self):
        result = invoke("Hello MAYA!")
        assert result["user_input"] == "Hello MAYA!"
        assert result["language"] in {"english", "hindi", "hinglish"}
        assert result["intent"] in {"greeting", "question", "math", "general", "farewell"}
        assert len(result["response"]) > 0
        assert len(result["steps"]) >= 3

    def test_graph_always_produces_response(self):
        inputs = ["Hello!", "Namaste!", "What is the sun?", "5 + 3", "bye", ""]
        for text in inputs:
            result = invoke(text)
            assert len(result["response"]) > 0, f"Empty response for: '{text}'"

    def test_steps_show_correct_node_order(self):
        # Session 5: load_memory is now the first node, shifting all indices by 1
        result = invoke("Hello!")
        assert result["steps"][0].startswith("[load_memory]")
        assert result["steps"][1].startswith("[detect_language]")
        assert result["steps"][2].startswith("[understand_intent]")

    def test_user_input_preserved_unchanged(self):
        original = "Hello MAYA, kya hal hai?"
        result = invoke(original)
        assert result["user_input"] == original


# ─── Memory Nodes ─────────────────────────────────────────────────────────────

class TestMemoryNodes:
    """
    Tests for Session 5 SQLite memory: load_memory and save_memory nodes.

    All tests use a tmp_path DB (pytest fixture) so they never touch
    the real ~/.maya/memory.db.  The db path is injected via the
    memory_db_path state field.
    """

    def test_load_memory_returns_profile(self, tmp_path):
        """load_memory populates user_name and session_count from a seeded DB."""
        db = str(tmp_path / "test.db")

        # Seed the DB: one session already happened
        store = MemoryStore(db_path=db)
        store.start_session()  # session_count becomes 1

        result = maya_graph.invoke({
            "user_input": "Hello!",
            "language": "",
            "intent": "",
            "response": "",
            "steps": [],
            "message_history": [],
            "memory_db_path": db,
        })

        assert result["user_name"] == "Srinika"
        assert result["session_count"] == 1

    def test_save_memory_logs_turn(self, tmp_path):
        """save_memory logs the user's message to the topics table after each turn."""
        db = str(tmp_path / "test.db")

        maya_graph.invoke({
            "user_input": "What is photosynthesis?",
            "language": "",
            "intent": "",
            "response": "",
            "steps": [],
            "message_history": [],
            "memory_db_path": db,
        })

        store = MemoryStore(db_path=db)
        recent = store.get_recent_topics()
        assert "What is photosynthesis?" in recent

    def test_fresh_install_defaults(self, tmp_path):
        """MemoryStore returns safe defaults when the DB is brand new."""
        db = str(tmp_path / "fresh.db")
        store = MemoryStore(db_path=db)

        profile = store.get_profile()
        assert profile["user_name"] == "Srinika"
        assert profile["session_count"] == 0
        assert profile["total_turns"] == 0
        assert store.get_recent_topics() == []
