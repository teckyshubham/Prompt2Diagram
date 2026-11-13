"""Pydantic request and response schemas for Prompt2Diagram."""

from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class DiagramType(str, Enum):
    SEQUENCE = "sequence"
    FLOWCHART = "flowchart"
    ARCHITECTURE = "architecture"
    CLASS = "class"
    ER = "er"


class PromptDiagramRequest(BaseModel):
    prompt: str = Field(
        ...,
        min_length=5,
        max_length=4000,
        description="Natural language description of the system design or workflow.",
        examples=[
            "User requests seat map in airline check-in service; API checks Redis L1 cache, falls back to Aerospike L2 cache, and publishes seat-lock event to Kafka."
        ],
    )
    diagram_type: DiagramType = Field(
        default=DiagramType.SEQUENCE,
        description="Target technical diagram type to generate.",
    )
    theme: Optional[str] = Field(
        default="plain",
        description="Optional PlantUML theme name.",
    )


class CodeAnalysisRequest(BaseModel):
    source_code: str = Field(
        ...,
        min_length=10,
        description="Source code snippet (Python, Java, or Go) to analyze.",
    )
    language: str = Field(
        default="python",
        pattern="^(python|java|go)$",
        description="Programming language of the source code.",
    )
    diagram_type: DiagramType = Field(
        default=DiagramType.ARCHITECTURE,
        description="Whether to generate an architecture/class view or call-flow diagram.",
    )
    use_ai_enrichment: bool = Field(
        default=False,
        description="Optionally enrich AST analysis with OpenAI semantic labels.",
    )


class RenderPlantUMLRequest(BaseModel):
    plantuml_code: str = Field(
        ...,
        min_length=10,
        description="Raw PlantUML DSL (@startuml ... @enduml) to encode and render.",
    )


class CodeMetrics(BaseModel):
    classes_found: int = 0
    functions_found: int = 0
    endpoints_found: int = 0
    dependencies: List[str] = Field(default_factory=list)
    call_edges: List[str] = Field(default_factory=list)


class DiagramResponse(BaseModel):
    diagram_type: DiagramType
    plantuml_code: str
    encoded_hash: str
    svg_url: str
    png_url: str
    generation_mode: str = Field(
        description="Indicates whether OpenAI API, AST Engine, or Template Engine generated the DSL."
    )
    metrics: Optional[CodeMetrics] = None
    metadata: Dict[str, str] = Field(default_factory=dict)
