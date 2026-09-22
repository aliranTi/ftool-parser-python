import json
from pathlib import Path
from typing import Any, Dict, Optional, Union

from .converter_anastruct import AnastructModel
from .models import FtoolModel, Member, Node


AXIAL_EXPORT_SCHEMA = "ftool-parser-python.axial-analysis"
AXIAL_EXPORT_VERSION = 1


def axial_analysis_to_dict(
    model: FtoolModel,
    analysis: AnastructModel,
    *,
    name: Optional[str] = None,
    include_samples: bool = False,
) -> Dict[str, Any]:
    """Converte os resultados axiais resolvidos em dados serializáveis.

    Força axial positiva representa tração e força negativa representa
    compressão. Coordenadas e comprimentos são exportados em metros; forças,
    em newtons.
    """

    if not analysis.solved:
        raise RuntimeError("Execute analysis.solve() antes de exportar resultados")

    _validate_model_mapping(model, analysis)

    return {
        "schema": AXIAL_EXPORT_SCHEMA,
        "schema_version": AXIAL_EXPORT_VERSION,
        "name": name,
        "units": {
            "length": "m",
            "force": "N",
            "moment": "N.m",
            "angle": "rad",
        },
        "sign_convention": {
            "positive_axial_force": "tension",
            "negative_axial_force": "compression",
        },
        "summary": {
            "node_count": len(model.nodes),
            "member_count": len(model.members),
        },
        "nodes": [_node_to_dict(node) for node in model.nodes],
        "members": [
            _member_to_dict(member, analysis, include_samples)
            for member in model.members
        ],
        "reactions": _reactions_to_list(model, analysis),
    }


def export_axial_analysis(
    model: FtoolModel,
    analysis: AnastructModel,
    destination: Union[str, Path],
    *,
    name: Optional[str] = None,
    include_samples: bool = False,
    indent: int = 2,
) -> Path:
    """Grava uma análise axial em JSON e retorna o caminho criado."""

    data = axial_analysis_to_dict(
        model,
        analysis,
        name=name,
        include_samples=include_samples,
    )
    output_path = Path(destination)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as file:
        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=indent,
            allow_nan=False,
        )
        file.write("\n")
    return output_path


def _validate_model_mapping(
    model: FtoolModel,
    analysis: AnastructModel,
) -> None:
    missing_nodes = [node.id for node in model.nodes if node.id not in analysis.node_ids]
    missing_members = [
        member.id for member in model.members if member.id not in analysis.member_ids
    ]
    if missing_nodes or missing_members:
        raise ValueError(
            "O modelo não corresponde à análise convertida: "
            f"nós ausentes={missing_nodes}, barras ausentes={missing_members}"
        )


def _node_to_dict(node: Node) -> Dict[str, Any]:
    load = None
    if node.load is not None:
        load = {
            "name": node.load.name,
            "fx": float(node.load.fx),
            "fy": float(node.load.fy),
            "moment": float(node.load.moment),
        }

    return {
        "id": f"n{node.id}",
        "ftool_id": node.id,
        "coordinates": {"x": float(node.x), "y": float(node.y)},
        "support": {
            "ux": node.support.ux,
            "uy": node.support.uy,
            "rz": node.support.rz,
        },
        "load": load,
    }


def _member_to_dict(
    member: Member,
    analysis: AnastructModel,
    include_samples: bool,
) -> Dict[str, Any]:
    ana_id = analysis.member_ids[member.id]
    result = analysis.system.get_element_results(ana_id, verbose=True)
    axial_values = [float(value) for value in result["N"]]
    minimum = float(result["Nmin"])
    maximum = float(result["Nmax"])

    axial_result: Dict[str, Any] = {
        "start": axial_values[0],
        "end": axial_values[-1],
        "average": sum(axial_values) / len(axial_values),
        "minimum": minimum,
        "maximum": maximum,
        "state": _classify_axial_force(minimum, maximum),
    }
    if include_samples:
        length = float(result["length"])
        divisor = max(len(axial_values) - 1, 1)
        axial_result["samples"] = [
            {
                "position": length * index / divisor,
                "force": force,
            }
            for index, force in enumerate(axial_values)
        ]

    return {
        "id": f"m{ana_id}",
        "ftool_id": member.id,
        "anastruct_id": ana_id,
        "start_node": f"n{member.start_node_id}",
        "end_node": f"n{member.end_node_id}",
        "material": member.material_name,
        "section": member.section_name,
        "length": float(result["length"]),
        "angle": float(result["alpha"]),
        "axial_force": axial_result,
    }


def _classify_axial_force(minimum: float, maximum: float) -> str:
    tolerance = max(abs(minimum), abs(maximum), 1.0) * 1e-9
    if abs(minimum) <= tolerance and abs(maximum) <= tolerance:
        return "zero"
    if minimum >= -tolerance:
        return "tension"
    if maximum <= tolerance:
        return "compression"
    return "mixed"


def _reactions_to_list(
    model: FtoolModel,
    analysis: AnastructModel,
) -> list[Dict[str, Any]]:
    reactions = []
    for node in model.nodes:
        if node.support.is_free:
            continue
        result = analysis.get_reaction_results(node.id)
        reactions.append(
            {
                "node": f"n{node.id}",
                "fx": float(result["Fx"]),
                "fy": float(result["Fy"]),
                "moment": float(result["Tz"]),
            }
        )
    return reactions
