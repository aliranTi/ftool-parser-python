"""Fronteira JSON para executar o parser no Pyodide.

Este módulo evita imports de anaStruct, NumPy, SciPy e Matplotlib durante o
carregamento. Assim, a operação ``parse`` funciona apenas com a biblioteca
padrão; as operações de análise importam suas dependências sob demanda.
"""

import json
from collections.abc import Mapping
from typing import Any

from .models import FtoolModel
from .parser import FtlParseError, FtlParser


PYODIDE_API_SCHEMA = "ftool-parser-python.pyodide-response"
PYODIDE_API_VERSION = 1
PYODIDE_OPERATIONS = ("parse", "analyze_axial", "size_sticks", "render_report")


class PyodideRequestError(ValueError):
    """Erro no contrato da requisição recebida do JavaScript."""


def parse_ftl_text(ftl_text: str) -> FtoolModel:
    """Interpreta conteúdo FTL em memória, sem criar arquivo temporário."""

    return FtlParser.from_text(ftl_text).parse()


def analyze_ftl_text(
    ftl_text: str,
    *,
    name: str | None = None,
    include_samples: bool = False,
) -> dict[str, Any]:
    """Resolve o modelo e devolve a análise axial serializável."""

    from .converter_anastruct import to_anastruct
    from .exporter import axial_analysis_to_dict

    model = parse_ftl_text(ftl_text)
    analysis = to_anastruct(model, solve=True)
    return axial_analysis_to_dict(
        model,
        analysis,
        name=name,
        include_samples=include_samples,
    )


def size_ftl_sticks(
    ftl_text: str,
    *,
    name: str | None = None,
    include_samples: bool = False,
) -> dict[str, Any]:
    """Resolve, dimensiona os palitos e devolve apenas dados JSON nativos."""

    from .converter_anastruct import to_anastruct
    from .exporter import axial_analysis_to_dict
    from .stick_sizing import size_axial_members

    model = parse_ftl_text(ftl_text)
    analysis = to_anastruct(model, solve=True)
    report = size_axial_members(model, analysis)
    return {
        "analysis": axial_analysis_to_dict(
            model,
            analysis,
            name=name,
            include_samples=include_samples,
        ),
        "stick_sizing": report.to_dict(),
        "stick_counts": report.counts_to_dict(),
    }


def handle_request(request: Mapping[str, Any]) -> dict[str, Any]:
    """Executa uma requisição Python já convertida para um mapeamento."""

    operation: str | None = None
    try:
        if not isinstance(request, Mapping):
            raise PyodideRequestError("A requisição deve ser um objeto JSON")

        operation_value = request.get("operation", "parse")
        if not isinstance(operation_value, str):
            raise PyodideRequestError("operation deve ser uma string")
        operation = operation_value
        if operation not in PYODIDE_OPERATIONS:
            choices = ", ".join(PYODIDE_OPERATIONS)
            raise PyodideRequestError(
                f"Operação desconhecida: {operation!r}. Use uma de: {choices}"
            )

        ftl_text = request.get("ftl_text")
        if not isinstance(ftl_text, str) or not ftl_text.strip():
            raise PyodideRequestError("ftl_text deve ser uma string não vazia")

        name = request.get("name")
        if name is not None and not isinstance(name, str):
            raise PyodideRequestError("name deve ser uma string ou null")

        options = request.get("options", {})
        if not isinstance(options, Mapping):
            raise PyodideRequestError("options deve ser um objeto JSON")
        include_samples = _boolean_option(options, "include_samples", False)

        if operation == "parse":
            model = parse_ftl_text(ftl_text)
            result = {
                "summary": {
                    "node_count": len(model.nodes),
                    "member_count": len(model.members),
                    "material_count": len(model.materials),
                    "section_count": len(model.sections),
                },
                "model": model.to_dict(),
            }
        elif operation == "analyze_axial":
            result = {
                "analysis": analyze_ftl_text(
                    ftl_text,
                    name=name,
                    include_samples=include_samples,
                )
            }
        elif operation == "render_report":
            from .web_report import render_report

            result = render_report(ftl_text, name=name)
        else:
            result = size_ftl_sticks(
                ftl_text,
                name=name,
                include_samples=include_samples,
            )

        return _success_response(operation, result)
    except PyodideRequestError as exc:
        return _error_response(operation, "invalid_request", exc)
    except FtlParseError as exc:
        return _error_response(operation, "parse_error", exc)
    except (ModuleNotFoundError, ImportError) as exc:
        return _error_response(operation, "dependency_unavailable", exc)
    except Exception as exc:  # A fronteira JS deve sempre responder JSON.
        return _error_response(operation, "execution_error", exc)


def handle_request_json(request_json: str, *, indent: int | None = None) -> str:
    """Recebe e devolve JSON, evitando vazamento de ``PyProxy`` no JavaScript."""

    try:
        if not isinstance(request_json, str):
            raise PyodideRequestError("A requisição deve ser fornecida como JSON")
        request = json.loads(request_json, parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, PyodideRequestError, ValueError) as exc:
        response = _error_response(None, "invalid_json", exc)
    else:
        response = handle_request(request)

    return json.dumps(
        response,
        ensure_ascii=False,
        allow_nan=False,
        indent=indent,
    )


def _boolean_option(
    options: Mapping[str, Any],
    name: str,
    default: bool,
) -> bool:
    value = options.get(name, default)
    if not isinstance(value, bool):
        raise PyodideRequestError(f"options.{name} deve ser booleano")
    return value


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"Constante JSON inválida: {value}")


def _success_response(operation: str, result: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": PYODIDE_API_SCHEMA,
        "schema_version": PYODIDE_API_VERSION,
        "ok": True,
        "operation": operation,
        "result": result,
    }


def _error_response(
    operation: str | None,
    code: str,
    error: Exception,
) -> dict[str, Any]:
    return {
        "schema": PYODIDE_API_SCHEMA,
        "schema_version": PYODIDE_API_VERSION,
        "ok": False,
        "operation": operation,
        "error": {
            "code": code,
            "type": type(error).__name__,
            "message": str(error),
        },
    }
