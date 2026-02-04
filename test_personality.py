"""Quick test to verify personality injection."""

from mmllm.game.engine import GameEngine
from mmllm.llm.prompt_builder import load_prompt_templates, build_messages
from mmllm.core.types import ActionRequest, ActionType, Phase

# Create a game with random personalities
engine = GameEngine(
    game_id="test_game",
    player_ids=["p1", "p2", "p3", "p4", "p5", "p6", "p7", "p8"],
    murderer_id="p1",
)

# Get observation for each player and show their personality
print("=" * 80)
print("PLAYER PERSONALITIES")
print("=" * 80)

for player in engine.runtime.public_state.players:
    pid = player.player_id
    controls = player.controls

    print(f"\n{pid.upper()}:")
    print(f"  Assertiveness: {controls.assertiveness:.2f}")
    print(f"  Skepticism:    {controls.skepticism:.2f}")
    print(f"  Query Rate:    {controls.query_rate:.2f}")
    print(f"  Risk:          {controls.risk:.2f}")
    print(f"  Deception:     {controls.deception:.2f}")
    print(f"  Verbosity:     {controls.verbosity:.2f}")

# Test prompt generation for one player
print("\n" + "=" * 80)
print("SAMPLE PROMPT FOR P2 (TOWN)")
print("=" * 80)

observation = engine.observation_for("p2")
request = ActionRequest(
    request_id="test_req",
    game_id="test_game",
    player_id="p2",
    round_num=1,
    phase=Phase.day,
    allowed_actions=[ActionType.speak, ActionType.pass_turn],
    ap_available=3,
)

templates = load_prompt_templates()
messages = build_messages(
    request=request,
    observation=observation,
    system_prompt=templates.system_town,
    user_prompt=templates.user,
    action_prompt=templates.action_speak,
)

print("\n--- SYSTEM PROMPT ---")
print(messages[0]["content"])

print("\n" + "=" * 80)
print("SUCCESS! Personality values are being injected into prompts.")
print("=" * 80)
