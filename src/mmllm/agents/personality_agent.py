"""Personality agent that generates rich character descriptions from trait scores."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from mmllm.core.types import Controls, Role


@dataclass
class PersonalityProfile:
    """A generated personality profile with narrative description."""

    summary: str  # One-line character summary
    communication_style: str  # How they communicate
    decision_making: str  # How they make decisions
    social_approach: str  # How they interact with others
    under_pressure: str  # How they behave when stressed/accused


# Trait archetypes for combination
_ASSERTIVENESS_TRAITS = {
    "low": ["soft-spoken", "diplomatic", "avoids conflict", "peace-maker"],
    "mid": ["measured", "speaks up when needed", "picks battles carefully"],
    "high": ["outspoken", "confrontational", "dominant", "commanding presence"],
}

_SKEPTICISM_TRAITS = {
    "low": ["trusting", "gives benefit of doubt", "optimistic about others"],
    "mid": ["cautiously trusting", "needs some proof", "reserves judgment"],
    "high": ["deeply suspicious", "trusts no one easily", "paranoid", "watchful"],
}

_QUERY_RATE_TRAITS = {
    "low": ["declarative", "states opinions", "rarely asks", "tells rather than asks"],
    "mid": ["balanced communicator", "mixes questions with statements"],
    "high": ["inquisitive", "probing", "asks pointed questions", "interrogator"],
}

_RISK_TRAITS = {
    "low": ["cautious", "methodical", "needs evidence", "conservative"],
    "mid": ["calculated", "weighs options", "moderate risk-taker"],
    "high": ["bold", "impulsive", "gut-driven", "high-stakes player"],
}

_DECEPTION_TRAITS = {
    "low": ["honest", "transparent", "wears heart on sleeve", "straightforward"],
    "mid": ["strategically vague", "selective with truth", "plays cards close"],
    "high": ["manipulative", "skilled liar", "misdirector", "poker face"],
}

_VERBOSITY_TRAITS = {
    "low": ["terse", "economical with words", "brief", "laconic"],
    "mid": ["conversational", "explains when needed"],
    "high": ["verbose", "elaborate", "detailed explainer", "long-winded"],
}


def _tier(value: float) -> str:
    """Convert 0-1 value to low/mid/high tier."""
    if value < 0.35:
        return "low"
    elif value < 0.65:
        return "mid"
    return "high"


def _pick_traits(trait_dict: dict, tier: str, count: int = 1) -> List[str]:
    """Pick traits from a tier."""
    import random

    traits = trait_dict.get(tier, trait_dict["mid"])
    return random.sample(traits, min(count, len(traits)))


def _generate_summary(controls: Controls) -> str:
    """Generate a one-line character summary."""
    # Pick dominant traits
    traits = []

    # Most extreme trait becomes primary descriptor
    extremes = [
        (abs(controls.assertiveness - 0.5), "assertiveness", controls.assertiveness),
        (abs(controls.skepticism - 0.5), "skepticism", controls.skepticism),
        (abs(controls.deception - 0.5), "deception", controls.deception),
        (abs(controls.risk - 0.5), "risk", controls.risk),
    ]
    extremes.sort(reverse=True)

    # Top 2 most extreme traits
    for _, trait_name, value in extremes[:2]:
        tier = _tier(value)
        if trait_name == "assertiveness":
            traits.extend(_pick_traits(_ASSERTIVENESS_TRAITS, tier))
        elif trait_name == "skepticism":
            traits.extend(_pick_traits(_SKEPTICISM_TRAITS, tier))
        elif trait_name == "deception":
            traits.extend(_pick_traits(_DECEPTION_TRAITS, tier))
        elif trait_name == "risk":
            traits.extend(_pick_traits(_RISK_TRAITS, tier))

    # Add verbosity modifier
    verb_tier = _tier(controls.verbosity)
    if verb_tier == "low":
        traits.append("few words")
    elif verb_tier == "high":
        traits.append("talks at length")

    return f"A {', '.join(traits[:3])} type"


def _generate_communication_style(controls: Controls) -> str:
    """Describe how this person communicates."""
    parts = []

    # Verbosity
    if controls.verbosity < 0.35:
        parts.append("You speak in short, direct sentences. Get to the point quickly.")
    elif controls.verbosity > 0.65:
        parts.append(
            "You explain your reasoning thoroughly, often in multiple sentences."
        )
    else:
        parts.append("You communicate at a moderate pace, expanding when needed.")

    # Query rate
    if controls.query_rate < 0.35:
        parts.append("You prefer making statements over asking questions.")
    elif controls.query_rate > 0.65:
        parts.append("You frequently ask probing questions to gather information.")

    # Assertiveness in speech
    if controls.assertiveness > 0.7:
        parts.append("Your tone is confident and commanding.")
    elif controls.assertiveness < 0.3:
        parts.append("Your tone is gentle and non-threatening.")

    return " ".join(parts)


def _generate_decision_making(controls: Controls) -> str:
    """Describe how this person makes decisions."""
    parts = []

    # Risk tolerance
    if controls.risk < 0.35:
        parts.append("You need solid evidence before taking action.")
        parts.append("You avoid making accusations without proof.")
    elif controls.risk > 0.65:
        parts.append("You trust your instincts and act on hunches.")
        parts.append("You're willing to make bold moves with incomplete information.")
    else:
        parts.append("You balance gut feelings with available evidence.")

    # Skepticism affects evidence threshold
    if controls.skepticism > 0.65:
        parts.append("You question everything and look for hidden motives.")
    elif controls.skepticism < 0.35:
        parts.append("You tend to take people at their word initially.")

    return " ".join(parts)


def _generate_social_approach(controls: Controls) -> str:
    """Describe how this person interacts with others."""
    parts = []

    # Assertiveness + Skepticism combo
    if controls.assertiveness > 0.65 and controls.skepticism > 0.65:
        parts.append("You're not afraid to call out suspicious behavior directly.")
    elif controls.assertiveness < 0.35 and controls.skepticism > 0.65:
        parts.append(
            "You watch quietly and note inconsistencies without immediate confrontation."
        )
    elif controls.assertiveness > 0.65 and controls.skepticism < 0.35:
        parts.append(
            "You're vocal but generally assume good intent until proven otherwise."
        )
    else:
        parts.append(
            "You engage with others thoughtfully, neither too trusting nor too suspicious."
        )

    # Deception
    if controls.deception > 0.65:
        parts.append(
            "You're comfortable bending the truth or omitting details when strategic."
        )
    elif controls.deception < 0.35:
        parts.append("You value honesty and find it difficult to mislead others.")

    return " ".join(parts)


def _generate_under_pressure(controls: Controls) -> str:
    """Describe behavior when accused or under stress."""
    parts = []

    # High deception + high assertiveness = aggressive deflection
    if controls.deception > 0.6 and controls.assertiveness > 0.6:
        parts.append("When accused, you deflect aggressively and may counter-accuse.")
    # High deception + low assertiveness = quiet misdirection
    elif controls.deception > 0.6 and controls.assertiveness < 0.4:
        parts.append("When accused, you quietly redirect attention elsewhere.")
    # Low deception + high assertiveness = righteous defense
    elif controls.deception < 0.4 and controls.assertiveness > 0.6:
        parts.append("When accused, you defend yourself forcefully with facts.")
    # Low deception + low assertiveness = accepts scrutiny
    elif controls.deception < 0.4 and controls.assertiveness < 0.4:
        parts.append("When accused, you calmly explain yourself without escalating.")
    else:
        parts.append("When accused, you respond measured but firm.")

    # Risk affects how they handle pressure
    if controls.risk > 0.7:
        parts.append("You might make a bold counter-move under pressure.")
    elif controls.risk < 0.3:
        parts.append("You prefer to de-escalate and wait for more information.")

    return " ".join(parts)


def generate_personality_profile(controls: Controls) -> PersonalityProfile:
    """Generate a complete personality profile from control scores.

    Args:
        controls: The numeric personality controls

    Returns:
        A PersonalityProfile with narrative descriptions
    """
    return PersonalityProfile(
        summary=_generate_summary(controls),
        communication_style=_generate_communication_style(controls),
        decision_making=_generate_decision_making(controls),
        social_approach=_generate_social_approach(controls),
        under_pressure=_generate_under_pressure(controls),
    )


def format_personality_description(controls: Controls, role: Role | None = None) -> str:
    """Generate the full personality description for injection into prompts.

    This replaces numeric scores with a narrative description that feels
    more natural and immersive.

    Args:
        controls: The numeric personality controls
        role: Optional role for role-specific guidance

    Returns:
        A formatted string describing the personality
    """
    profile = generate_personality_profile(controls)

    lines = [
        "## Your Character",
        "",
        f"**{profile.summary}.**",
        "",
        "### How You Communicate",
        profile.communication_style,
        "",
        "### How You Make Decisions",
        profile.decision_making,
        "",
        "### How You Interact With Others",
        profile.social_approach,
        "",
        "### When You're Under Pressure",
        profile.under_pressure,
        "",
        "---",
        "**Stay in character.** Let these traits guide your words and actions naturally.",
    ]

    return "\n".join(lines)


class PersonalityAgent:
    """Agent responsible for generating personality descriptions.

    This agent takes raw personality scores and produces rich, narrative
    descriptions that can be injected into LLM prompts. The descriptions
    feel more natural than raw numbers and help the LLM embody the character.
    """

    def __init__(self) -> None:
        pass

    def describe(self, controls: Controls, role: Role | None = None) -> str:
        """Generate a personality description from controls.

        Args:
            controls: The numeric personality controls
            role: Optional role for role-specific guidance

        Returns:
            A formatted personality description string
        """
        return format_personality_description(controls, role)

    def get_profile(self, controls: Controls) -> PersonalityProfile:
        """Get the structured personality profile.

        Args:
            controls: The numeric personality controls

        Returns:
            A PersonalityProfile dataclass
        """
        return generate_personality_profile(controls)
