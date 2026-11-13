"""OpenAI ChatGPT integration and deterministic NLP fallback for Prompt-to-PlantUML generation."""

import re
from typing import List, Tuple
from openai import AsyncOpenAI

from app.config import settings
from app.models.schemas import DiagramType
from app.services.plantuml_service import sanitize_plantuml

SYSTEM_PROMPTS = {
    DiagramType.SEQUENCE: (
        "You are a Principal System Architect and PlantUML expert. "
        "Convert the user's natural language system workflow into a clean, valid PlantUML Sequence Diagram. "
        "Use `autonumber`, proper participant types (`actor`, `participant`, `database`, `queue`, `collections`), "
        "activation bars (`activate`/`deactivate`), and `alt`/`else`/`opt` blocks where appropriate. "
        "Return ONLY valid PlantUML code enclosed in `@startuml` and `@enduml`."
    ),
    DiagramType.FLOWCHART: (
        "You are a Principal System Architect and PlantUML expert. "
        "Convert the user's natural language process or logic flow into a modern PlantUML Activity Diagram (Flowchart). "
        "Use `start`, `stop`, `:Action;`, `if (...) then (yes) ... else (no) ... endif`, and swimlanes or partitions if applicable. "
        "Return ONLY valid PlantUML code enclosed in `@startuml` and `@enduml`."
    ),
    DiagramType.ARCHITECTURE: (
        "You are a Principal System Architect and PlantUML expert. "
        "Convert the user's natural language system description into a High-Level Design (HLD) PlantUML Component/Architecture Diagram. "
        "Group components into logical packages/clouds/nodes (`package`, `cloud`, `database`, `queue`, `component`) "
        "and label protocol arrows (e.g., `REST/HTTPS`, `gRPC`, `Kafka Event`, `Redis Cache`). "
        "Return ONLY valid PlantUML code enclosed in `@startuml` and `@enduml`."
    ),
    DiagramType.CLASS: (
        "You are a Principal Software Engineer and Low-Level Design (LLD) expert. "
        "Convert the user's description into a PlantUML Class Diagram with classes, interfaces, attributes, methods, "
        "and relationships (`<|--`, `*--`, `o--`, `-->`). "
        "Return ONLY valid PlantUML code enclosed in `@startuml` and `@enduml`."
    ),
    DiagramType.ER: (
        "You are a Database Architect and PlantUML expert. "
        "Convert the user's description into a PlantUML Entity-Relationship (ER) diagram using `entity`, primary keys (`*`), "
        "foreign keys, and crow's foot relationships (`||--o{`, `}o--||`). "
        "Return ONLY valid PlantUML code enclosed in `@startuml` and `@enduml`."
    ),
}


class LLMDiagramService:
    """Transforms natural language prompts into PlantUML DSL using OpenAI API with heuristic fallback."""

    def __init__(self) -> None:
        self.api_key = settings.openai_api_key
        self.model = settings.openai_model
        self._client = (
            AsyncOpenAI(api_key=self.api_key)
            if self.api_key and not self.api_key.startswith("sk-your-")
            else None
        )

    async def generate_from_prompt(
        self, prompt: str, diagram_type: DiagramType, theme: str = "plain"
    ) -> Tuple[str, str]:
        """
        Generate PlantUML DSL from natural language prompt.
        Returns (plantuml_code, generation_mode).
        """
        if self._client is not None:
            try:
                system_prompt = SYSTEM_PROMPTS.get(
                    diagram_type, SYSTEM_PROMPTS[DiagramType.SEQUENCE]
                )
                response = await self._client.chat.completions.create(
                    model=self.model,
                    temperature=0.2,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {
                            "role": "user",
                            "content": f"Diagram Type: {diagram_type.value}\nTheme: {theme}\nPrompt:\n{prompt}",
                        },
                    ],
                )
                content = response.choices[0].message.content or ""
                return sanitize_plantuml(content), f"openai:{self.model}"
            except Exception:
                # Gracefully degrade to deterministic NLP synthesizer if API quota/network fails
                pass

        synthesized = self._heuristic_synthesize(prompt, diagram_type, theme)
        return sanitize_plantuml(synthesized), "heuristic-nlp-engine"

    def _extract_steps(self, prompt: str) -> List[str]:
        """Split a natural language prompt into ordered logical clauses."""
        parts = re.split(r"(?:[.;\n]+|\bthen\b|\band then\b|\bafterwards\b|->)", prompt, flags=re.IGNORECASE)
        steps = [p.strip(" ,:-") for p in parts if len(p.strip(" ,:-")) > 3]
        return steps if steps else [prompt.strip()]

    def _heuristic_synthesize(
        self, prompt: str, diagram_type: DiagramType, theme: str
    ) -> str:
        """Deterministic NLP-to-PlantUML synthesizer when OpenAI API key is not configured."""
        steps = self._extract_steps(prompt)
        theme_line = f"!theme {theme}\n" if theme and theme != "plain" else ""

        if diagram_type == DiagramType.FLOWCHART:
            lines = [
                "@startuml",
                theme_line.rstrip(),
                "skinparam conditionStyle inside",
                "skinparam ActivityBackgroundColor #F8FAFC",
                "skinparam ActivityBorderColor #334155",
                "start",
            ]
            for step in steps:
                lower = step.lower()
                if any(k in lower for k in ["if ", "check ", "cache hit", "valid", "whether"]):
                    lines.append(f"if ({step}?) then (yes)")
                    lines.append("  :Process primary path / fast return;")
                    lines.append("else (no / fallback)")
                    lines.append("  :Execute fallback / downstream handler;")
                    lines.append("endif")
                else:
                    lines.append(f":{step};")
            lines.append("stop")
            lines.append("@enduml")
            return "\n".join(line for line in lines if line)

        if diagram_type == DiagramType.ARCHITECTURE:
            return self._synthesize_architecture(prompt, steps, theme_line)

        if diagram_type == DiagramType.CLASS:
            return self._synthesize_class(prompt, theme_line)

        if diagram_type == DiagramType.ER:
            return self._synthesize_er(prompt, theme_line)

        # Default: Sequence Diagram
        return self._synthesize_sequence(prompt, steps, theme_line)

    def _synthesize_sequence(
        self, prompt: str, steps: List[str], theme_line: str
    ) -> str:
        lower_prompt = prompt.lower()
        lines = [
            "@startuml",
            theme_line.rstrip(),
            "autonumber",
            "skinparam BoxPadding 10",
            "skinparam ParticipantPadding 12",
            'actor "Client / User" as Client',
            'participant "API Gateway / Controller" as API',
            'participant "Core Domain Service" as Service',
        ]

        has_cache = any(k in lower_prompt for k in ["redis", "aerospike", "cache"])
        has_search = any(k in lower_prompt for k in ["solr", "lucene", "elastic", "search"])
        has_queue = any(k in lower_prompt for k in ["kafka", "queue", "event", "pubsub", "broker"])
        has_db = any(k in lower_prompt for k in ["db", "database", "mysql", "postgres", "mongo", "nosql", "opsdb", "store"])

        if has_cache:
            lines.append('database "Redis / Aerospike Cache" as Cache')
        if has_search:
            lines.append('collections "Search Engine (Solr/Lucene)" as Search')
        if has_db or not (has_cache or has_search):
            lines.append('database "Primary Datastore" as DB')
        if has_queue:
            lines.append('queue "Apache Kafka Broker" as Kafka')

        lines.append("")
        lines.append(f"Client -> API : Initiate request ({steps[0][:55]})")
        lines.append("activate API")
        lines.append("API -> Service : Route validated request")
        lines.append("activate Service")

        if has_cache:
            lines.append("Service -> Cache : Lookup key in distributed cache")
            lines.append("alt Cache Hit")
            lines.append("  Cache --> Service : Return cached payload (Low P99 latency)")
            lines.append("else Cache Miss")
            target = "Search" if has_search else "DB"
            lines.append(f"  Service -> {target} : Query underlying store")
            lines.append(f"  {target} --> Service : Return records")
            lines.append("  Service -> Cache : Populate cache asynchronously (TTL)")
            lines.append("end")
        elif has_search:
            lines.append("Service -> Search : Execute ranked query & boosting plugins")
            lines.append("Search --> Service : Return scored document hits")
        else:
            lines.append("Service -> DB : Execute transactional query")
            lines.append("DB --> Service : Return result set")

        for extra_step in steps[1:3]:
            lines.append(f"Service -> Service : {extra_step[:65]}")

        if has_queue:
            lines.append("Service -> Kafka : Publish asynchronous domain event")
            lines.append("Kafka --> Service : ACK offset")

        lines.append("Service --> API : Return serialized response DTO")
        lines.append("deactivate Service")
        lines.append("API --> Client : HTTP 200 OK (JSON)")
        lines.append("deactivate API")
        lines.append("@enduml")
        return "\n".join(line for line in lines if line is not None)

    def _synthesize_architecture(
        self, prompt: str, steps: List[str], theme_line: str
    ) -> str:
        lines = [
            "@startuml",
            theme_line.rstrip(),
            "skinparam componentStyle rectangle",
            'actor "Client Applications" as Client',
            'package "Edge & Gateway Layer" {',
            '  [API Gateway / Load Balancer] as Gateway',
            "}",
            'package "Microservices Layer (Spring Boot / FastAPI)" {',
            '  [Core Orchestrator Service] as CoreSvc',
            '  [Domain Worker Service] as WorkerSvc',
            "}",
            'package "Data & Messaging Infrastructure" {',
            '  database "Distributed Cache (Redis / Aerospike)" as Cache',
            '  database "Primary Database (SQL / NoSQL)" as DB',
            '  queue "Event Bus (Apache Kafka)" as Kafka',
            "}",
            "Client --> Gateway : HTTPS / REST",
            "Gateway --> CoreSvc : gRPC / REST",
            "CoreSvc --> Cache : Sub-ms Read/Write",
            "CoreSvc --> DB : Persistent Storage",
            "CoreSvc --> Kafka : Publish Domain Events",
            "Kafka --> WorkerSvc : Consume Async Stream",
            "WorkerSvc --> DB : Update Projection",
            f'note right of CoreSvc : "{steps[0][:70]}"',
            "@enduml",
        ]
        return "\n".join(line for line in lines if line)

    def _synthesize_class(self, prompt: str, theme_line: str) -> str:
        return "\n".join(
            line
            for line in [
                "@startuml",
                theme_line.rstrip(),
                "interface DiagramGenerator {",
                "  +generate(prompt: str): DiagramResult",
                "}",
                "class PromptService {",
                "  -llmClient: OpenAIClient",
                "  -plantumlEncoder: PlantUMLEncoder",
                "  +createFromPrompt(request: PromptRequest): DiagramResponse",
                "}",
                "class CodebaseAnalyzer {",
                "  +parseAST(sourceCode: str): ModuleGraph",
                "  +toPlantUML(graph: ModuleGraph): str",
                "}",
                "DiagramGenerator <|.. PromptService",
                "DiagramGenerator <|.. CodebaseAnalyzer",
                "@enduml",
            ]
            if line
        )

    def _synthesize_er(self, prompt: str, theme_line: str) -> str:
        return "\n".join(
            line
            for line in [
                "@startuml",
                theme_line.rstrip(),
                "entity \"User\" as users {",
                "  * id : UUID <<PK>>",
                "  --",
                "  email : VARCHAR(255)",
                "  created_at : TIMESTAMP",
                "}",
                "entity \"DiagramProject\" as projects {",
                "  * id : UUID <<PK>>",
                "  --",
                "  * user_id : UUID <<FK>>",
                "  diagram_type : VARCHAR(32)",
                "  plantuml_dsl : TEXT",
                "}",
                "users ||--o{ projects : owns",
                "@enduml",
            ]
            if line
        )


llm_service = LLMDiagramService()
