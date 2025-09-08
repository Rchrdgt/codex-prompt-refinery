from pdr.schemas import SynthesisOutput, schema_for_openai


def test_schema_validation_roundtrip():
    """SynthesisOutput validates and schema contains required keys."""
    sample = {
        "optimized_atomic_prompts": [
            {
                "title": "T1",
                "prompt_markdown": "```markdown\nX\n```",
                "variables": [{"name": "x"}],
                "io_contract": {"inputs": "x", "outputs": "y"},
                "citations": [1, 2],
            }
        ],
        "optimized_workflow_prompt": {
            "title": "W1",
            "prompt_markdown": "```markdown\nY\n```",
            "variables": [{"name": "y"}],
            "io_contract": {"inputs": "x", "outputs": "z"},
            "citations": [3],
        },
        "rationale": "ok",
    }
    obj = SynthesisOutput.model_validate(sample)
    assert obj.optimized_atomic_prompts[0].title == "T1"
    schema = schema_for_openai()
    # spot-check required keys exist
    assert "optimized_atomic_prompts" in schema["required"]
