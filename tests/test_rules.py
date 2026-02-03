from mmllm.core.types import GameState, PlayerState
from mmllm.game.rules import winner


def test_winner_town():
    state = GameState(
        game_id="g1",
        phase="day",
        round=1,
        players=[
            PlayerState("p1", "town", True),
            PlayerState("p2", "town", True),
        ],
    )
    assert winner(state) == "town"
