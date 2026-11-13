"""FastAPI router exposing Prompt-to-Diagram, Codebase Analysis, and PlantUML rendering endpoints."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from app.models.schemas import (
    CodeAnalysisRequest,
    DiagramResponse,
    DiagramType,
    PromptDiagramRequest,
    RenderPlantUMLRequest,
)
from app.services.code_analyzer import code_analyzer_service
from app.services.llm_service import llm_service
from app.services.plantuml_service import plantuml_service, sanitize_plantuml

router = APIRouter(prefix="/api/v1", tags=["diagrams"])


@router.get("/health")
async def health_check() -> dict:
    """Service health and capability readiness probe."""
    return {
        "status": "healthy",
        "service": "Prompt2Diagram",
        "openai_configured": bool(llm_service._client is not None),
        "plantuml_server": plantuml_service.server_url,
    }


@router.post("/diagrams/prompt", response_model=DiagramResponse)
async def generate_diagram_from_prompt(request: PromptDiagramRequest) -> DiagramResponse:
    """Transform a natural language prompt into PlantUML DSL and real-time SVG/PNG URLs."""
    plantuml_code, mode = await llm_service.generate_from_prompt(
        prompt=request.prompt,
        diagram_type=request.diagram_type,
        theme=request.theme or "plain",
    )
    encoded, svg_url, png_url = plantuml_service.build_render_urls(plantuml_code)
    return DiagramResponse(
        diagram_type=request.diagram_type,
        plantuml_code=plantuml_code,
        encoded_hash=encoded,
        svg_url=svg_url,
        png_url=png_url,
        generation_mode=mode,
        metadata={"theme": request.theme or "plain"},
    )


@router.post("/diagrams/analyze-code", response_model=DiagramResponse)
async def generate_diagram_from_code(request: CodeAnalysisRequest) -> DiagramResponse:
    """Analyze Python/Java/Go source code via AST/static parser to auto-generate architecture or call-flow diagrams."""
    plantuml_code, metrics = code_analyzer_service.analyze_source(
        source_code=request.source_code,
        language=request.language,
        diagram_type=request.diagram_type,
    )
    mode = f"ast-static-analyzer:{request.language}"

    if request.use_ai_enrichment:
        enrichment_prompt = (
            f"Refine and enrich this auto-generated PlantUML {request.diagram_type.value} diagram "
            f"extracted from {request.language} source code:\n{plantuml_code}"
        )
        plantuml_code, llm_mode = await llm_service.generate_from_prompt(
            prompt=enrichment_prompt,
            diagram_type=request.diagram_type,
        )
        mode = f"{mode}+{llm_mode}"

    encoded, svg_url, png_url = plantuml_service.build_render_urls(plantuml_code)
    return DiagramResponse(
        diagram_type=request.diagram_type,
        plantuml_code=plantuml_code,
        encoded_hash=encoded,
        svg_url=svg_url,
        png_url=png_url,
        generation_mode=mode,
        metrics=metrics,
        metadata={"language": request.language},
    )


@router.post("/diagrams/render", response_model=DiagramResponse)
async def render_raw_plantuml(request: RenderPlantUMLRequest) -> DiagramResponse:
    """Encode custom PlantUML DSL into live SVG and PNG rendering URLs."""
    normalized = sanitize_plantuml(request.plantuml_code)
    encoded, svg_url, png_url = plantuml_service.build_render_urls(normalized)
    return DiagramResponse(
        diagram_type=DiagramType.ARCHITECTURE,
        plantuml_code=normalized,
        encoded_hash=encoded,
        svg_url=svg_url,
        png_url=png_url,
        generation_mode="direct-plantuml-render",
    )


@router.post("/diagrams/svg")
async def proxy_svg_render(request: RenderPlantUMLRequest) -> Response:
    """Fetch and proxy rendered SVG markup directly from the PlantUML engine."""
    try:
        svg_content = await plantuml_service.fetch_svg(request.plantuml_code)
        return Response(content=svg_content, media_type="image/svg+xml")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"PlantUML render failed: {exc}") from exc
