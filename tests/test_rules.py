"""Tests for game rules."""

from mmllm.core.types import Phase, Role
from mmllm.game.engine import GameEngine
from mmllm.game.rules import winner, legal_actions, is_game_over


def test_winner_town():
    """Test that town wins when murderer is eliminated."""
    engine = GameEngine(
        game_id="g1",
        player_ids=["p1", "p2", "p3"],
        murderer_id="p1",
    )
    engine.start()

    # Eliminate the murderer
    murderer = engine.runtime.get_player("p1")
    murderer.alive = False

    assert winner(engine.runtime) == "town"
    assert is_game_over(engine.runtime)


def test_winner_murderer():
    """Test that murderer wins when town is reduced to <= 1."""
    engine = GameEngine(
        game_id="g2",
        player_ids=["p1", "p2", "p3"],
        murderer_id="p1",
    )
    engine.start()

    # Kill all but one town member
    engine.runtime.get_player("p2").alive = False

    # Now only p1 (murderer) and p3 (town) are alive - murderer wins
    assert winner(engine.runtime) == "murderer"
    assert is_game_over(engine.runtime)


def test_game_continues():
    """Test that game continues when neither win condition is met."""
    engine = GameEngine(
        game_id="g3",
        player_ids=["p1", "p2", "p3", "p4"],
        murderer_id="p1",
    )
    engine.start()

    # All alive, game should continue
    assert winner(engine.runtime) is None
    assert not is_game_over(engine.runtime)


def test_legal_actions_night_murderer():
    """Test that murderer can kill at night."""
    engine = GameEngine(
        game_id="g4",
        player_ids=["p1", "p2", "p3"],
        murderer_id="p1",
    )
    engine.start()

    from mmllm.core.types import ActionType

    actions = legal_actions(engine.runtime, "p1")
    assert ActionType.kill in actions
    assert ActionType.pass_turn in actions


def test_legal_actions_night_detective():
    """Test that detective can investigate at night."""
    engine = GameEngine(
        game_id="g5",
        player_ids=["p1", "p2", "p3"],
        murderer_id="p1",
    )
    engine.start()

    from mmllm.core.types import ActionType

    # p2 should be the detective
    actions = legal_actions(engine.runtime, "p2")
    assert ActionType.investigate in actions
    assert ActionType.pass_turn in actions


def test_legal_actions_day():
    """Test day phase actions based on AP."""
    engine = GameEngine(
        game_id="g6",
        player_ids=["p1", "p2", "p3"],
        murderer_id="p1",
    )
    engine.start()
    engine.advance_phase()  # Move to day

    from mmllm.core.types import ActionType

    # With 3 AP, should have access to all day actions
    actions = legal_actions(engine.runtime, "p1")
    assert ActionType.speak in actions
    assert ActionType.question in actions
    assert ActionType.poll in actions
    assert ActionType.pass_turn in actions

    # Reduce AP to 1
    engine.runtime.get_player("p1").social_ap = 1
    actions = legal_actions(engine.runtime, "p1")
    assert ActionType.speak in actions
    assert ActionType.question not in actions
    assert ActionType.poll not in actions


def test_legal_actions_vote():
    """Test vote phase actions."""
    engine = GameEngine(
        game_id="g7",
        player_ids=["p1", "p2", "p3"],
        murderer_id="p1",
    )
    engine.start()
    engine.advance_phase()  # day
    engine.advance_phase()  # vote

    from mmllm.core.types import ActionType

    actions = legal_actions(engine.runtime, "p1")
    assert ActionType.vote in actions
    assert ActionType.pass_turn in actions
