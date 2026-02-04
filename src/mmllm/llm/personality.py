"""Personality descriptor generation for LLM prompts."""

from __future__ import annotations

from mmllm.core.types import Controls


def get_personality_descriptors(controls: Controls) -> dict[str, str]:
    """Convert numeric personality controls into natural language descriptions.

    Args:
        controls: The Controls object with personality parameters

    Returns:
        Dictionary with description keys (e.g., 'assertiveness_desc')
    """
    descriptors = {}

    # Assertiveness
    agg = controls.assertiveness
    if agg < 0.3:
        descriptors['assertiveness_desc'] = "Diplomatic and non-confrontational"
    elif agg < 0.7:
        descriptors['assertiveness_desc'] = "Assertive when needed"
    else:
        descriptors['assertiveness_desc'] = "Highly confrontational and direct"

    # Skepticism
    skep = controls.skepticism
    if skep < 0.3:
        descriptors['skepticism_desc'] = "Trusting until given reason not to be"
    elif skep < 0.7:
        descriptors['skepticism_desc'] = "Neutral stance, prove yourself trustworthy"
    else:
        descriptors['skepticism_desc'] = "Highly suspicious of everyone initially"

    # Query Rate (how much they ask questions)
    query = controls.query_rate
    if query < 0.3:
        descriptors['query_rate_desc'] = "Rarely asks questions, makes statements"
    elif query < 0.7:
        descriptors['query_rate_desc'] = "Balances questions and statements"
    else:
        descriptors['query_rate_desc'] = "Frequently asks questions to probe others"

    # Risk Tolerance
    risk = controls.risk
    if risk < 0.3:
        descriptors['risk_desc'] = "Very cautious and evidence-driven"
    elif risk < 0.7:
        descriptors['risk_desc'] = "Balanced risk assessment"
    else:
        descriptors['risk_desc'] = "Bold and willing to make risky plays"

    # Deception (willingness to lie/mislead)
    dec = controls.deception
    if dec < 0.3:
        descriptors['deception_desc'] = "Honest and straightforward"
    elif dec < 0.7:
        descriptors['deception_desc'] = "Strategic with information"
    else:
        descriptors['deception_desc'] = "Comfortable with misdirection and bluffing"

    # Verbosity
    verb = controls.verbosity
    if verb < 0.3:
        descriptors['verbosity_desc'] = "Concise communicator (1-2 sentences typical)"
    elif verb < 0.7:
        descriptors['verbosity_desc'] = "Moderate speaker (2-3 sentences typical)"
    else:
        descriptors['verbosity_desc'] = "Verbose explainer (3-5 sentences typical)"

    return descriptors


def format_personality_for_prompt(controls: Controls) -> str:
    """Format personality into a multi-line string for prompt injection.

    Args:
        controls: The Controls object with personality parameters

    Returns:
        Formatted string describing the personality
    """
    descriptors = get_personality_descriptors(controls)

    lines = [
        "## Your Personality Profile",
        "You have the following behavioral tendencies (scale 0.0-1.0):",
        f"- **Assertiveness**: {controls.assertiveness:.2f} - {descriptors['assertiveness_desc']}",
        f"- **Skepticism**: {controls.skepticism:.2f} - {descriptors['skepticism_desc']}",
        f"- **Query Rate**: {controls.query_rate:.2f} - {descriptors['query_rate_desc']}",
        f"- **Risk Tolerance**: {controls.risk:.2f} - {descriptors['risk_desc']}",
        f"- **Deception**: {controls.deception:.2f} - {descriptors['deception_desc']}",
        f"- **Verbosity**: {controls.verbosity:.2f} - {descriptors['verbosity_desc']}",
        "",
        "**Play according to this personality.** These traits should influence:",
        "- How quickly you accuse others",
        "- Whether you bluff or withhold information",
        "- How much evidence you need before voting",
        "- The length and frequency of your messages",
        "- Whether you rely on data or gut feelings",
        "- How skeptical you are of others' claims",
    ]

    return "\n".join(lines)
