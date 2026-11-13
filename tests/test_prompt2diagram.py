"""Unit and integration test suite for Prompt2Diagram."""

from fastapi.testclient import TestClient

from app.main import app
from app.models.schemas import DiagramType
from app.services.code_analyzer import code_analyzer_service
from app.services.plantuml_service import encode_plantuml, sanitize_plantuml

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "healthy"
    assert payload["service"] == "Prompt2Diagram"


def test_plantuml_encoding_and_sanitization():
    raw = "```plantuml\nAlice -> Bob : Hello\n```"
    sanitized = sanitize_plantuml(raw)
    assert sanitized.startswith("@startuml")
    assert sanitized.endswith("@enduml")
    encoded = encode_plantuml(sanitized)
    assert isinstance(encoded, str) and len(encoded) > 5


def test_prompt_to_sequence_diagram():
    response = client.post(
        "/api/v1/diagrams/prompt",
        json={
            "prompt": (
                "Client requests Seat Map API; service checks Redis cache and Aerospike, "
                "queries MySQL on miss, and publishes seat lock event to Kafka."
            ),
            "diagram_type": "sequence",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "@startuml" in data["plantuml_code"]
    assert "Redis" in data["plantuml_code"] or "Cache" in data["plantuml_code"]
    assert "Kafka" in data["plantuml_code"]
    assert data["svg_url"].startswith("https://www.plantuml.com/plantuml/svg/")


def test_prompt_to_flowchart_diagram():
    response = client.post(
        "/api/v1/diagrams/prompt",
        json={
            "prompt": "Receive search request; check Redis cache hit; query Solr index; return ranked products.",
            "diagram_type": "flowchart",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "start" in data["plantuml_code"]
    assert "stop" in data["plantuml_code"]


def test_ast_codebase_analyzer_python():
    sample_python = """
import httpx

class CacheRepository:
    def get_item(self, key: str):
        return None

class SearchOrchestrator:
    def __init__(self, cache_repo: CacheRepository):
        self.cache_repo = cache_repo

    def execute_search(self, query: str):
        cached = self.cache_repo.get_item(query)
        return cached
"""
    response = client.post(
        "/api/v1/diagrams/analyze-code",
        json={
            "source_code": sample_python,
            "language": "python",
            "diagram_type": "architecture",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "SearchOrchestrator" in data["plantuml_code"]
    assert "CacheRepository" in data["plantuml_code"]
    assert data["metrics"]["classes_found"] == 2
    assert "httpx" in data["metrics"]["dependencies"]


def test_ast_codebase_analyzer_call_flow():
    sample_code = """
def handle_Order(order_id: str):
    validate_inventory(order_id)
    charge_payment(order_id)
    publish_kafka_event(order_id)
"""
    puml, metrics = code_analyzer_service.analyze_source(
        sample_code, "python", DiagramType.SEQUENCE
    )
    assert "validate_inventory()" in puml
    assert "charge_payment()" in puml
    assert "publish_kafka_event()" in puml
    assert metrics.functions_found == 1
