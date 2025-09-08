"""Pydantic models mirroring the Structured Outputs JSON Schema."""

from __future__ import annotations

from pydantic import BaseModel, Field


class VarModel(BaseModel):
    """Variable specification."""

    name: str
    type: str | None = None
    example: str | None = None
    description: str | None = None


class IOContract(BaseModel):
    """I/O contract."""

    inputs: str
    outputs: str


class AtomicPrompt(BaseModel):
    """Atomic prompt item."""

    title: str
    prompt_markdown: str
    variables: list[VarModel] = Field(default_factory=list)
    io_contract: IOContract
    citations: list[int] = Field(default_factory=list)


class WorkflowPrompt(BaseModel):
    """Workflow prompt aggregate."""

    title: str
    prompt_markdown: str
    variables: list[VarModel] = Field(default_factory=list)
    io_contract: IOContract
    citations: list[int] = Field(default_factory=list)


class SynthesisOutput(BaseModel):
    """Top-level structured output."""

    optimized_atomic_prompts: list[AtomicPrompt]
    optimized_workflow_prompt: WorkflowPrompt
    rationale: str


def schema_for_openai() -> dict:
    """Return JSON Schema for Structured Outputs `response_format`."""
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["optimized_atomic_prompts", "optimized_workflow_prompt", "rationale"],
        "properties": {
            "optimized_atomic_prompts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": [
                        "title",
                        "prompt_markdown",
                        "variables",
                        "io_contract",
                        "citations",
                    ],
                    "properties": {
                        "title": {"type": "string"},
                        "prompt_markdown": {"type": "string"},
                        "variables": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "required": ["name"],
                                "properties": {
                                    "name": {"type": "string"},
                                    "type": {"type": "string"},
                                    "example": {"type": "string"},
                                    "description": {"type": "string"},
                                },
                            },
                        },
                        "io_contract": {
                            "type": "object",
                            "required": ["inputs", "outputs"],
                            "properties": {
                                "inputs": {"type": "string"},
                                "outputs": {"type": "string"},
                            },
                        },
                        "citations": {"type": "array", "items": {"type": "integer"}},
                    },
                },
            },
            "optimized_workflow_prompt": {
                "type": "object",
                "required": ["title", "prompt_markdown", "variables", "io_contract", "citations"],
                "properties": {
                    "title": {"type": "string"},
                    "prompt_markdown": {"type": "string"},
                    "variables": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["name"],
                            "properties": {
                                "name": {"type": "string"},
                                "type": {"type": "string"},
                                "example": {"type": "string"},
                                "description": {"type": "string"},
                            },
                        },
                    },
                    "io_contract": {
                        "type": "object",
                        "required": ["inputs", "outputs"],
                        "properties": {
                            "inputs": {"type": "string"},
                            "outputs": {"type": "string"},
                        },
                    },
                    "citations": {"type": "array", "items": {"type": "integer"}},
                },
            },
            "rationale": {"type": "string"},
        },
    }
