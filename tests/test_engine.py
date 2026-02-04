"""Tests for GameEngine."""

from mmllm.core.types import Phase
from mmllm.game.engine import GameEngine


def test_phase_advance():
    """Test that phases advance correctly."""
    engine = GameEngine(
        game_id="g1",
        player_ids=["p1", "p2", "p3"],
        murderer_id="p1",
    )
    # Start the engine
    engine.start()
    assert engine.current_phase() == Phase.night

    # Advance to day
    engine.advance_phase()
    assert engine.current_phase() == Phase.day

    # Advance to vote
    engine.advance_phase()
    assert engine.current_phase() == Phase.vote

    # Advance back to night (new round)
    engine.advance_phase()
    assert engine.current_phase() == Phase.night
    assert engine.runtime.public_state.round_num == 2


def test_engine_with_config():
    """Test that engine accepts game_config parameter."""
    from mmllm.core.game_config import GameTypeConfig

    config = GameTypeConfig.default_classic()
    engine = GameEngine(
        game_id="g2",
        player_ids=["p1", "p2", "p3"],
        murderer_id="p1",
        game_config=config,
    )
    assert engine.game_config == config
    assert engine.runtime.game_config == config
    assert engine.actions_per_player == 3


def test_engine_custom_actions_per_player():
    """Test custom actions_per_player from config."""
    from mmllm.core.game_config import GameTypeConfig, PlayerSettings

    config = GameTypeConfig.default_classic()
    config.player_settings.actions_per_player = 5

    engine = GameEngine(
        game_id="g3",
        player_ids=["p1", "p2", "p3"],
        murderer_id="p1",
        game_config=config,
    )
    assert engine.actions_per_player == 5
    # Check players have the right AP
    for player in engine.runtime.public_state.players:
        assert player.social_ap == 5
        assert player.social_ap_max == 5
