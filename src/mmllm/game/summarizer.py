"""Template-based day summarizer with interaction ranking."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

from mmllm.core.types import (
    EventType,
    GameEvent,
    Phase,
    PublicMemory,
    PublicState,
    TranscriptEntry,
)


@dataclass
class RankedInteraction:
    """A transcript entry with a computed relevance score."""

    entry: TranscriptEntry
    score: float
    reason: str


# Generic phrases that indicate low-quality interactions
GENERIC_PATTERNS = [
    r"has anyone noticed",
    r"what do you all think",
    r"i agree with",
    r"that's a good point",
    r"interesting observation",
    r"let's discuss",
    r"we should consider",
    r"i'm not sure",
    r"hard to say",
    r"could be anyone",
]

# High-value interaction patterns
ACCUSATION_PATTERNS = [
    r"i think .+ is the murderer",
    r"i suspect .+",
    r"(?:seems?|looks?) suspicious",
    r"i vote (?:for|to eliminate)",
    r"we should (?:vote|eliminate)",
    r"(?:acting|behaving) strange",
]

DEFENSE_PATTERNS = [
    r"i am not the murderer",
    r"i'm innocent",
    r"i can prove",
    r"that's not true",
    r"why would i",
    r"i was (?:trying|just)",
]

EVIDENCE_PATTERNS = [
    r"yesterday .+ said",
    r"last (?:night|round)",
    r"remember when",
    r"noticed that",
    r"contradicts what",
    r"earlier .+ claimed",
]


def _is_generic(text: str) -> bool:
    """Check if text contains generic/low-value phrases."""
    text_lower = text.lower()
    return any(re.search(pattern, text_lower) for pattern in GENERIC_PATTERNS)


def _has_accusation(text: str) -> bool:
    """Check if text contains accusation language."""
    text_lower = text.lower()
    return any(re.search(pattern, text_lower) for pattern in ACCUSATION_PATTERNS)


def _has_defense(text: str) -> bool:
    """Check if text contains defense language."""
    text_lower = text.lower()
    return any(re.search(pattern, text_lower) for pattern in DEFENSE_PATTERNS)


def _has_evidence(text: str) -> bool:
    """Check if text contains evidence/reference language."""
    text_lower = text.lower()
    return any(re.search(pattern, text_lower) for pattern in EVIDENCE_PATTERNS)


def _mentions_player(text: str, player_ids: List[str]) -> Optional[str]:
    """Return the first player ID mentioned in text, or None."""
    text_lower = text.lower()
    for pid in player_ids:
        if pid.lower() in text_lower:
            return pid
    return None


def rank_interactions(
    entries: List[TranscriptEntry],
    player_ids: List[str],
) -> List[RankedInteraction]:
    """
    Rank transcript entries by relevance/interest.

    Scoring:
    - Base score: 1.0
    - Mentions another player: +2.0
    - Accusation language: +3.0
    - Defense language: +2.0
    - Evidence/reference: +2.0
    - Question action type: +1.5 (involves 2 players)
    - Generic phrase: -2.0
    - Short message (<30 chars): -1.0
    """
    ranked: List[RankedInteraction] = []

    for entry in entries:
        score = 1.0
        reasons: List[str] = []

        body = entry.body

        # Check for player mentions
        mentioned = _mentions_player(body, player_ids)
        if mentioned:
            score += 2.0
            reasons.append(f"mentions {mentioned}")

        # Check for accusation
        if _has_accusation(body):
            score += 3.0
            reasons.append("accusation")

        # Check for defense
        if _has_defense(body):
            score += 2.0
            reasons.append("defense")

        # Check for evidence
        if _has_evidence(body):
            score += 2.0
            reasons.append("evidence")

        # Question actions naturally involve 2 players
        # (The speaker and target are both engaged)
        if "?" in body and mentioned:
            score += 1.5
            reasons.append("direct question")

        # Penalize generic content
        if _is_generic(body):
            score -= 2.0
            reasons.append("generic")

        # Penalize very short messages
        if len(body) < 30:
            score -= 1.0
            reasons.append("short")

        ranked.append(
            RankedInteraction(
                entry=entry,
                score=score,
                reason=", ".join(reasons) if reasons else "baseline",
            )
        )

    # Sort by score descending
    ranked.sort(key=lambda x: x.score, reverse=True)
    return ranked


def generate_state_summary(
    public_state: PublicState,
    events: List[GameEvent],
) -> str:
    """
    Generate a deterministic summary of the current game state.

    This replaces LLM-generated summaries for factual game state info.
    """
    parts: List[str] = []

    round_num = public_state.round_num
    alive = [p for p in public_state.players if p.alive]

    # Round info
    day_word = "first" if round_num == 1 else f"day {round_num}"
    parts.append(f"It is the {day_word}.")

    # Deaths from events
    for evt in events:
        if evt.event_type == EventType.night_kill:
            victim = evt.payload.get("target") or evt.payload.get("victim")
            if victim:
                parts.append(f"{victim.title()} was killed during the night.")
        elif evt.event_type == EventType.player_eliminated:
            victim = evt.payload.get("eliminated") or evt.payload.get("player_id")
            if victim:
                parts.append(f"{victim.title()} was eliminated by vote.")

    # Alive count
    parts.append(
        f"{len(alive)} players remain: {', '.join(p.player_id.title() for p in alive)}."
    )

    # If anyone died recently
    if public_state.last_night_kill:
        parts.append(f"Last night's victim: {public_state.last_night_kill.title()}.")
    if public_state.last_day_eliminated:
        parts.append(
            f"Yesterday's vote: {public_state.last_day_eliminated.title()} was eliminated."
        )

    return " ".join(parts)


def generate_interaction_summary(
    ranked: List[RankedInteraction],
    max_highlights: int = 3,
) -> str:
    """
    Generate a summary highlighting the most interesting interactions.

    Takes pre-ranked interactions and formats the top ones.
    """
    if not ranked:
        return ""

    # Take top interactions above threshold
    threshold = 2.0
    highlights = [r for r in ranked[: max_highlights * 2] if r.score >= threshold][
        :max_highlights
    ]

    if not highlights:
        return ""

    lines: List[str] = ["Key moments:"]
    for rank in highlights:
        speaker = rank.entry.speaker_id.title()
        # Truncate long messages
        body = rank.entry.body
        if len(body) > 100:
            body = body[:97] + "..."
        lines.append(f'• {speaker}: "{body}"')

    return "\n".join(lines)


def generate_day_summary(
    public_state: PublicState,
    public_memory: PublicMemory,
    events: List[GameEvent],
    max_highlights: int = 3,
) -> str:
    """
    Generate a complete day summary using templates + interaction ranking.

    This is the main entry point that replaces the LLM-based summarizer.
    """
    # Get transcript entries for the current round
    current_round = public_state.round_num
    round_entries = [
        e
        for e in public_memory.transcript
        if e.round_num == current_round and e.phase == Phase.day
    ]

    # Get player IDs for interaction analysis
    player_ids = [p.player_id for p in public_state.players]

    # Generate state summary (factual, deterministic)
    state_summary = generate_state_summary(public_state, events)

    # Rank and summarize interactions
    ranked = rank_interactions(round_entries, player_ids)
    interaction_summary = generate_interaction_summary(ranked, max_highlights)

    # Combine
    parts = [state_summary]
    if interaction_summary:
        parts.append("")
        parts.append(interaction_summary)

    return "\n".join(parts)


class TemplateSummarizer:
    """
    Template-based summarizer that replaces LLM calls for day summaries.

    Uses deterministic templates for game state and interaction ranking
    to select the most interesting moments.
    """

    def __init__(self, max_highlights: int = 3) -> None:
        self.max_highlights = max_highlights

    def summarize(
        self,
        public_state: PublicState,
        public_memory: PublicMemory,
        events: List[GameEvent],
    ) -> str:
        """Generate a day summary without LLM calls."""
        return generate_day_summary(
            public_state,
            public_memory,
            events,
            max_highlights=self.max_highlights,
        )
