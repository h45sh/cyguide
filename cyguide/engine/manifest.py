"""Pydantic models for tool manifests."""

from typing import List, Dict, Optional
from pydantic import BaseModel, Field


class ToolMeta(BaseModel):
    name: str
    description: str
    one_line_summary: str = ""
    category: str = "Misc"
    categories: List[str]
    binary: str


class Recipe(BaseModel):
    name: str
    description: str
    flags: List[str] = Field(default_factory=list)


class Milestone(BaseModel):
    trigger: str
    prompt: str


class ExplainerConfig(BaseModel):
    tool_context: str
    milestones: List[Milestone]


class LearningConfig(BaseModel):
    enabled: bool = False
    flags: List[Dict[str, str]] = Field(default_factory=list)
    recipes: List[Recipe] = Field(default_factory=list)
    explainer: Optional[ExplainerConfig] = None


class PowerConfig(BaseModel):
    enabled: bool = False
    suggests: List[Dict[str, str]] = Field(default_factory=list)


class Manifest(BaseModel):
    """Structure of tools/<name>/manifest.toml."""
    meta: ToolMeta
    modes: Dict[str, bool]
    input: Dict[str, List[str]]
    output: Dict[str, List[str]]
    learning: Optional[LearningConfig] = None
    power: Optional[PowerConfig] = None
