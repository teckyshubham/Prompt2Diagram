"""AST and static code analysis engine to auto-generate architecture and logic-flow PlantUML diagrams."""

import ast
import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple

from app.models.schemas import CodeMetrics, DiagramType


@dataclass
class ParsedClass:
    name: str
    bases: List[str] = field(default_factory=list)
    methods: List[str] = field(default_factory=list)
    attributes: List[str] = field(default_factory=list)
    stereotype: str = "class"


@dataclass
class ParsedCodebase:
    classes: List[ParsedClass] = field(default_factory=list)
    functions: List[str] = field(default_factory=list)
    endpoints: List[str] = field(default_factory=list)
    imports: Set[str] = field(default_factory=set)
    call_edges: List[Tuple[str, str]] = field(default_factory=list)


class CodebaseAnalyzerService:
    """Static analyzer that inspects Python/Java/Go code to produce PlantUML diagrams."""

    def analyze_source(
        self, source_code: str, language: str, diagram_type: DiagramType
    ) -> Tuple[str, CodeMetrics]:
        lang = language.lower().strip()
        if lang == "python":
            parsed = self._parse_python_ast(source_code)
        else:
            parsed = self._parse_java_or_go(source_code, lang)

        metrics = CodeMetrics(
            classes_found=len(parsed.classes),
            functions_found=len(parsed.functions) + sum(len(c.methods) for c in parsed.classes),
            endpoints_found=len(parsed.endpoints),
            dependencies=sorted(parsed.imports)[:15],
            call_edges=[f"{src} -> {dst}" for src, dst in parsed.call_edges[:20]],
        )

        if diagram_type in (DiagramType.SEQUENCE, DiagramType.FLOWCHART):
            puml = self._render_call_flow_diagram(parsed, diagram_type)
        else:
            puml = self._render_architecture_diagram(parsed)

        return puml, metrics

    def analyze_directory(self, directory_path: str) -> Tuple[str, CodeMetrics]:
        """Scan a Python package directory and generate a module-level architecture diagram."""
        combined = ParsedCodebase()
        for root, _, files in os.walk(directory_path):
            if any(part.startswith(".") or part in ("venv", "__pycache__", "tests") for part in root.split(os.sep)):
                continue
            for file in sorted(files):
                if file.endswith(".py"):
                    full_path = os.path.join(root, file)
                    try:
                        with open(full_path, "r", encoding="utf-8") as fh:
                            sub = self._parse_python_ast(fh.read())
                            combined.classes.extend(sub.classes)
                            combined.functions.extend(sub.functions)
                            combined.endpoints.extend(sub.endpoints)
                            combined.imports.update(sub.imports)
                            combined.call_edges.extend(sub.call_edges)
                    except Exception:
                        continue

        metrics = CodeMetrics(
            classes_found=len(combined.classes),
            functions_found=len(combined.functions) + sum(len(c.methods) for c in combined.classes),
            endpoints_found=len(combined.endpoints),
            dependencies=sorted(combined.imports)[:15],
            call_edges=[f"{src} -> {dst}" for src, dst in combined.call_edges[:25]],
        )
        return self._render_architecture_diagram(combined), metrics

    def _parse_python_ast(self, source_code: str) -> ParsedCodebase:
        result = ParsedCodebase()
        try:
            tree = ast.parse(source_code)
        except SyntaxError:
            return self._parse_java_or_go(source_code, "python")

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    result.imports.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module:
                result.imports.add(node.module.split(".")[0])

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                bases = [self._expr_name(b) for b in node.bases if self._expr_name(b)]
                methods: List[str] = []
                attrs: Set[str] = set()
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        methods.append(item.name)
                        self._extract_calls_from_func(f"{node.name}.{item.name}", item, result)
                        for sub in ast.walk(item):
                            if (
                                isinstance(sub, ast.Attribute)
                                and isinstance(sub.value, ast.Name)
                                and sub.value.id == "self"
                            ):
                                attrs.add(sub.attr)
                stereotype = "service" if node.name.endswith("Service") else "class"
                result.classes.append(
                    ParsedClass(
                        name=node.name,
                        bases=bases,
                        methods=methods,
                        attributes=sorted(attrs - set(methods)),
                        stereotype=stereotype,
                    )
                )
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                result.functions.append(node.name)
                for dec in node.decorator_list:
                    dec_name = self._expr_name(dec)
                    if any(v in dec_name.lower() for v in ["get", "post", "put", "delete", "route"]):
                        result.endpoints.append(f"{dec_name}:{node.name}")
                self._extract_calls_from_func(node.name, node, result)

        return result

    def _extract_calls_from_func(
        self, caller_name: str, func_node: ast.AST, result: ParsedCodebase
    ) -> None:
        builtins_ignore = {
            "len", "str", "int", "float", "list", "dict", "set", "tuple",
            "print", "range", "enumerate", "isinstance", "getattr", "hasattr",
            "min", "max", "sum", "sorted", "any", "all", "super", "Field",
        }
        for sub in ast.walk(func_node):
            if isinstance(sub, ast.Call):
                callee = self._expr_name(sub.func)
                if callee and callee.split(".")[-1] not in builtins_ignore:
                    edge = (caller_name, callee)
                    if edge not in result.call_edges:
                        result.call_edges.append(edge)

    def _expr_name(self, expr: ast.AST) -> str:
        if isinstance(expr, ast.Name):
            return expr.id
        if isinstance(expr, ast.Attribute):
            prefix = self._expr_name(expr.value)
            if prefix == "self":
                return expr.attr
            return f"{prefix}.{expr.attr}" if prefix else expr.attr
        if isinstance(expr, ast.Call):
            return self._expr_name(expr.func)
        return ""

    def _parse_java_or_go(self, source_code: str, language: str) -> ParsedCodebase:
        result = ParsedCodebase()
        class_pattern = re.compile(
            r"(?:public\s+|private\s+|protected\s+)?(?:abstract\s+|final\s+)?"
            r"(class|interface|struct)\s+([A-Za-z_]\w*)"
            r"(?:\s+extends\s+([A-Za-z_]\w*))?"
            r"(?:\s+implements\s+([A-Za-z0-9_,\s]+))?"
        )
        method_pattern = re.compile(
            r"(?:public|private|protected|func)\s+(?:static\s+)?(?:[A-Za-z0-9_<>\[\]]+\s+)?([A-Za-z_]\w*)\s*\("
        )
        field_pattern = re.compile(
            r"private\s+(?:final\s+)?([A-Za-z_]\w*)\s+([a-z_]\w*)\s*;"
        )

        methods = [
            m.group(1)
            for m in method_pattern.finditer(source_code)
            if m.group(1) not in ("if", "for", "while", "switch", "catch")
        ]
        fields = [f"{m.group(2)}: {m.group(1)}" for m in field_pattern.finditer(source_code)]

        for match in class_pattern.finditer(source_code):
            kind, cname, ext, impl = match.groups()
            bases = []
            if ext:
                bases.append(ext.strip())
            if impl:
                bases.extend(i.strip() for i in impl.split(",") if i.strip())
            result.classes.append(
                ParsedClass(
                    name=cname,
                    bases=bases,
                    methods=methods[:8],
                    attributes=fields[:8],
                    stereotype=kind,
                )
            )
            for f in fields:
                dep_type = f.split(":")[-1].strip()
                result.call_edges.append((cname, dep_type))

        if not result.classes and methods:
            result.functions.extend(methods)
            for i in range(len(methods) - 1):
                result.call_edges.append((methods[i], methods[i + 1]))

        return result

    def _render_architecture_diagram(self, parsed: ParsedCodebase) -> str:
        lines = [
            "@startuml",
            "skinparam classAttributeIconSize 0",
            "skinparam Shadowing false",
            "skinparam PackageStyle rectangle",
        ]

        if parsed.endpoints:
            lines.append('package "API Layer (Endpoints)" {')
            for ep in parsed.endpoints[:10]:
                safe_ep = ep.replace('"', "'")
                lines.append(f'  class "{safe_ep}" <<endpoint>>')
            lines.append("}")

        if parsed.classes:
            lines.append('package "Domain & Service Classes" {')
            for cls in parsed.classes:
                lines.append(f'  class "{cls.name}" <<{cls.stereotype}>> {{')
                for attr in cls.attributes[:6]:
                    lines.append(f"    - {attr}")
                for method in cls.methods[:8]:
                    lines.append(f"    + {method}()")
                lines.append("  }")
            lines.append("}")

            known_classes = {c.name for c in parsed.classes}
            for cls in parsed.classes:
                for base in cls.bases:
                    lines.append(f'"{base}" <|-- "{cls.name}"')
                for attr in cls.attributes:
                    for target in known_classes:
                        if target != cls.name and target.lower() in attr.lower():
                            lines.append(f'"{cls.name}" --> "{target}" : uses')

        elif parsed.functions:
            lines.append('package "Module Functions" {')
            for fn in parsed.functions[:12]:
                lines.append(f'  component "{fn}()" as {fn}')
            lines.append("}")

        if parsed.call_edges and not parsed.classes:
            for caller, callee in parsed.call_edges[:12]:
                c1 = re.sub(r"[^A-Za-z0-9_]", "_", caller)
                c2 = re.sub(r"[^A-Za-z0-9_]", "_", callee)
                lines.append(f"{c1} --> {c2} : invokes")

        lines.append("@enduml")
        return "\n".join(lines)

    def _render_call_flow_diagram(
        self, parsed: ParsedCodebase, diagram_type: DiagramType
    ) -> str:
        if diagram_type == DiagramType.FLOWCHART:
            lines = [
                "@startuml",
                "start",
            ]
            if parsed.call_edges:
                for caller, callee in parsed.call_edges[:12]:
                    lines.append(f":{caller} invokes {callee}();")
            elif parsed.functions:
                for fn in parsed.functions[:10]:
                    lines.append(f":Execute {fn}();")
            else:
                lines.append(":Parse AST & Execute Module Entrypoint;")
            lines.append("stop")
            lines.append("@enduml")
            return "\n".join(lines)

        # Sequence call-flow diagram
        lines = [
            "@startuml",
            "autonumber",
            'actor "Caller / Client" as Caller',
        ]
        if parsed.call_edges:
            first_caller = parsed.call_edges[0][0].split(".")[0]
            lines.append(f'Caller -> "{first_caller}" : invoke()')
            for src, dst in parsed.call_edges[:14]:
                src_participant = src.split(".")[0]
                dst_participant = dst.split(".")[0]
                method_label = dst.split(".")[-1] + "()"
                lines.append(f'"{src_participant}" -> "{dst_participant}" : {method_label}')
        elif parsed.classes:
            for cls in parsed.classes[:5]:
                for m in cls.methods[:3]:
                    lines.append(f'Caller -> "{cls.name}" : {m}()')
        else:
            lines.append('Caller -> "Module" : execute()')

        lines.append("@enduml")
        return "\n".join(lines)


code_analyzer_service = CodebaseAnalyzerService()
