"""Custom exception types for the game engine."""

from __future__ import annotations


class GameError(Exception):
    """Base exception for all game-related errors."""

    pass


class ActionError(GameError):
    """Error during action validation or execution."""

    def __init__(
        self,
        message: str,
        *,
        player_id: str | None = None,
        action_type: str | None = None,
        game_id: str | None = None,
    ) -> None:
        self.player_id = player_id
        self.action_type = action_type
        self.game_id = game_id
        details = []
        if game_id:
            details.append(f"game={game_id}")
        if player_id:
            details.append(f"player={player_id}")
        if action_type:
            details.append(f"action={action_type}")
        detail_str = f" [{', '.join(details)}]" if details else ""
        super().__init__(f"{message}{detail_str}")


class GameStateError(GameError):
    """Error related to game state inconsistency."""

    def __init__(
        self,
        message: str,
        *,
        expected: str | None = None,
        actual: str | None = None,
    ) -> None:
        self.expected = expected
        self.actual = actual
        details = []
        if expected:
            details.append(f"expected={expected}")
        if actual:
            details.append(f"actual={actual}")
        detail_str = f" ({', '.join(details)})" if details else ""
        super().__init__(f"{message}{detail_str}")


class InvalidTargetError(ActionError):
    """Error when an action targets an invalid player."""

    def __init__(
        self,
        message: str,
        *,
        target_id: str | None = None,
        **kwargs,
    ) -> None:
        self.target_id = target_id
        if target_id:
            message = f"{message} (target={target_id})"
        super().__init__(message, **kwargs)


class ConfigurationError(GameError):
    """Error in game configuration."""

    pass
