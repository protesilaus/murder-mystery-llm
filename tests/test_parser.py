from mmllm.llm.output_parser import parse_action


def test_parse_action():
    assert parse_action('{"type": "vote"}') == {"type": "vote"}
