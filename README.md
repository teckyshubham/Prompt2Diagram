# Prompt2Diagram — AI-Powered Technical Diagram Generator & Codebase Analyzer

**Prompt2Diagram** is an AI-powered developer productivity tool built with **Python**, **FastAPI**, **OpenAI ChatGPT API**, and **PlantUML**. It transforms natural language prompts and raw source code (Python, Java/Spring Boot, Go) into real-time **Sequence Diagrams**, **Flowcharts**, **High-Level Architecture (HLD)**, and **Low-Level Class (LLD)** diagrams.

---

## Key Features

1. **Natural Language Prompt-to-Diagram Synthesis:**
   - Converts plain-English system workflows into valid PlantUML DSL for **Sequence**, **Flowchart (Activity)**, **Architecture (Component)**, **Class**, and **ER** diagrams.
   - Integrates **OpenAI ChatGPT API (`gpt-4o-mini` / `gpt-4o`)** with automatic PlantUML syntax sanitization (`@startuml ... @enduml`) and a deterministic **NLP heuristic engine fallback** for offline/zero-key execution.
2. **AST-Based Codebase Analysis Engine:**
   - Parses Python Abstract Syntax Trees (`ast`) and Java/Go source files to extract classes, inheritance hierarchies, service dependencies, REST endpoints, and method call graphs.
   - Auto-generates architecture and execution call-flow diagrams directly from source code, eliminating manual documentation drift.
3. **Real-Time PlantUML Deflate + 6-Bit Base64 Rendering:**
   - Implements PlantUML's native raw-Deflate and custom 64-character encoding pipeline to stream instant **SVG** and **PNG** renders alongside an interactive split-pane web studio.

---

## System Architecture

```
+------------------------+       REST / JSON       +-------------------------------+
|  Interactive Web UI    | ----------------------> |     FastAPI Backend Server    |
|  (Split-Pane Studio)   |                         |   (/api/v1/diagrams/*)        |
+------------------------+                         +---------------+---------------+
                                                                   |
                                      +----------------------------+----------------------------+
                                      |                                                         |
                                      v                                                         v
                     +--------------------------------+                        +--------------------------------+
                     |    LLM Diagram Synthesizer     |                        |  AST & Static Code Analyzer    |
                     | (OpenAI API + Heuristic Engine)|                        | (Python AST / Java / Go Regex) |
                     +----------------+---------------+                        +----------------+---------------+
                                      |                                                         |
                                      +----------------------------+----------------------------+
                                                                   |
                                                                   v
                                                   +-------------------------------+
                                                   |  PlantUML Deflate Encoder &   |
                                                   |   Real-Time SVG/PNG Renderer  |
                                                   +-------------------------------+
```

---

## Tech Stack

- **Backend Framework:** Python 3.10+, FastAPI, Pydantic v2, Uvicorn
- **AI / LLM Integration:** OpenAI Python SDK (`AsyncOpenAI`, `gpt-4o-mini`)
- **Static Code Analysis:** Python `ast` module, Multi-language Regex Call-Graph Extractor
- **Diagram Rendering:** PlantUML Deflate + Custom 6-Bit Base64 Encoder (`httpx`, `zlib`)
- **Testing & Containerization:** Pytest, Docker

---

## Quick Start

### 1. Clone & Install Dependencies

```bash
git clone https://github.com/teckyshubham/Prompt2Diagram.git
cd Prompt2Diagram
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment Variables (Optional)

```bash
cp .env.example .env
# Edit .env and set OPENAI_API_KEY=sk-...
# Note: If OPENAI_API_KEY is omitted, the built-in heuristic NLP & AST engines work out of the box!
```

### 3. Run the FastAPI Server

```bash
uvicorn app.main:app --reload --port 8000
```

- **Interactive Web Studio:** Open `http://localhost:8000`
- **Swagger / OpenAPI Docs:** Open `http://localhost:8000/docs`

---

## API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/v1/health` | Health check and OpenAI/PlantUML readiness status |
| `POST` | `/api/v1/diagrams/prompt` | Generate Sequence, Flowchart, HLD, LLD, or ER diagram from text prompt |
| `POST` | `/api/v1/diagrams/analyze-code` | Analyze Python/Java/Go code to auto-generate architecture or call-flow diagrams |
| `POST` | `/api/v1/diagrams/render` | Encode raw PlantUML DSL into live SVG and PNG URLs |

### Example Request (`POST /api/v1/diagrams/prompt`)

```bash
curl -X POST "http://localhost:8000/api/v1/diagrams/prompt" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Client requests Seat Map API; service checks Redis L1 cache and Aerospike L2 cache, queries MySQL on miss, and publishes seat lock event to Kafka.",
    "diagram_type": "sequence"
  }'
```

---

## Running Tests

```bash
pytest -v
```
