from mmllm.core.types import GameState
from mmllm.game.engine import GameEngine


def test_phase_advance():
    state = GameState(game_id="g1", phase="night", round=1, players=[])
    engine = GameEngine(state, ["night", "day", "vote"])
    assert engine.current_phase() == "night"
    assert engine.advance_phase() == "day"
