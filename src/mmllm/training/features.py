"""Transcript/state featurization."""

from typing import Dict

from mmllm.core.types import PublicState


def featurize_state(state: PublicState) -> Dict[str, int]:
    return {
        "round": state.round_num,
        "alive": sum(1 for p in state.players if p.alive),
    }
