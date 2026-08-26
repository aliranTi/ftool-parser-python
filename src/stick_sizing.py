import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .converter_anastruct import AnastructModel
from .models import FtoolModel, Member


class StickSizingError(ValueError):
    """Erro de entrada ou de convergência no dimensionamento de palitos."""


@dataclass(frozen=True)
class StickGeometry:
    """Dimensões nominais de um palito de madeira."""

    width_mm: float = 8.58
    thickness_mm: float = 1.94

    def __post_init__(self) -> None:
        if self.width_mm <= 0 or self.thickness_mm <= 0:
            raise StickSizingError("As dimensões do palito devem ser positivas")


@dataclass(frozen=True)
class WoodCompressionProperties:
    """Propriedades usadas na verificação de compressão e instabilidade."""

    strength_class: str = "C35"
    characteristic_strength_mpa: float = 25.0
    mean_elasticity_mpa: float = 13_000.0
    kmod1: float = 1.1
    kmod2: float = 0.9
    gamma_m: float = 1.0
    beta_c: float = 0.1

    def __post_init__(self) -> None:
        positive_values = (
            self.characteristic_strength_mpa,
            self.mean_elasticity_mpa,
            self.kmod1,
            self.kmod2,
            self.gamma_m,
        )
        if any(value <= 0 for value in positive_values):
            raise StickSizingError("As propriedades da madeira devem ser positivas")
        if self.beta_c < 0:
            raise StickSizingError("beta_c não pode ser negativo")

    @property
    def kmod(self) -> float:
        return self.kmod1 * self.kmod2

    @property
    def characteristic_elasticity_mpa(self) -> float:
        return 0.8 * self.mean_elasticity_mpa

    @property
    def design_strength_mpa(self) -> float:
        return self.kmod * self.characteristic_strength_mpa / self.gamma_m


@dataclass(frozen=True)
class StickSizingConfig:
    """Hipóteses globais do dimensionamento."""

    stick: StickGeometry = field(default_factory=StickGeometry)
    wood: WoodCompressionProperties = field(
        default_factory=WoodCompressionProperties
    )
    effective_length_factor: float = 1.0
    design_force_factor: float = 1.0
    max_sticks: int = 1_000

    def __post_init__(self) -> None:
        if self.effective_length_factor <= 0:
            raise StickSizingError("O fator de comprimento efetivo deve ser positivo")
        if self.design_force_factor <= 0:
            raise StickSizingError("O fator do esforço de cálculo deve ser positivo")
        if self.max_sticks < 1:
            raise StickSizingError("max_sticks deve ser pelo menos 1")


@dataclass(frozen=True)
class CompressionCheck:
    """Resultado completo para uma seção composta por uma quantidade de palitos."""

    stick_count: int
    compression_force_n: float
    design_force_n: float
    member_length_m: float
    effective_length_mm: float
    area_mm2: float
    ix_mm4: float
    iy_mm4: float
    rx_mm: float
    ry_mm: float
    slenderness_x: float
    slenderness_y: float
    relative_slenderness_x: float
    relative_slenderness_y: float
    reduction_factor_x: float
    reduction_factor_y: float
    stress_mpa: float
    effective_strength_x_mpa: float
    effective_strength_y_mpa: float
    utilization_x: float
    utilization_y: float
    governing_axis: str
    governing_utilization: float
    passes: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MemberStickSizing:
    """Quantidade mínima de palitos para uma barra do modelo."""

    id: str
    ftool_id: int
    anastruct_id: int
    start_node: str
    end_node: str
    member_length_m: float
    axial_min_n: float
    axial_max_n: float
    compression_demand_n: float
    status: str
    required_sticks: Optional[int]
    check: Optional[CompressionCheck]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StickSizingReport:
    """Relatório de dimensionamento das barras comprimidas."""

    config: StickSizingConfig
    members: List[MemberStickSizing]

    @property
    def compression_members(self) -> int:
        return sum(item.compression_demand_n > 0 for item in self.members)

    @property
    def sum_of_member_section_counts(self) -> int:
        return sum(item.required_sticks or 0 for item in self.members)

    @property
    def total_required_sticks(self) -> int:
        """Soma das quantidades nas seções das barras comprimidas."""
        return self.sum_of_member_section_counts

    @property
    def compressed_lamination_length_m(self) -> float:
        return sum(
            (item.required_sticks or 0) * item.member_length_m
            for item in self.members
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema": "ftool-parser-python.stick-sizing",
            "schema_version": 1,
            "units": {
                "model_length": "m",
                "section_length": "mm",
                "force": "N",
                "stress": "MPa",
            },
            "scope": "compression_members",
            "sign_convention": {
                "positive_axial_force": "tension",
                "negative_axial_force": "compression",
            },
            "config": asdict(self.config),
            "summary": {
                "member_count": len(self.members),
                "compression_member_count": self.compression_members,
                "total_required_sticks": self.total_required_sticks,
                "sum_of_member_section_counts": self.sum_of_member_section_counts,
                "compressed_lamination_length_m": self.compressed_lamination_length_m,
            },
            "members": [item.to_dict() for item in self.members],
        }

    def counts_to_dict(self) -> Dict[str, Any]:
        """Retorna uma visão compacta do total e da quantidade por membro."""
        return {
            "schema": "ftool-parser-python.stick-counts",
            "schema_version": 1,
            "scope": "compression_members",
            "units": {"force": "N", "length": "m"},
            "total_required_sticks": self.total_required_sticks,
            "compression_member_count": self.compression_members,
            "compressed_lamination_length_m": self.compressed_lamination_length_m,
            "members": [
                {
                    "id": item.id,
                    "ftool_id": item.ftool_id,
                    "start_node": item.start_node,
                    "end_node": item.end_node,
                    "length": item.member_length_m,
                    "compression_demand": item.compression_demand_n,
                    "required_sticks": item.required_sticks,
                    "status": item.status,
                    "governing_utilization": (
                        item.check.governing_utilization if item.check else None
                    ),
                }
                for item in self.members
            ],
        }


def check_compression_section(
    compression_force_n: float,
    member_length_m: float,
    stick_count: int,
    config: Optional[StickSizingConfig] = None,
) -> CompressionCheck:
    """Verifica uma quantidade definida de palitos em uma barra comprimida."""

    sizing = config or StickSizingConfig()
    if compression_force_n <= 0:
        raise StickSizingError("A força de compressão deve ser positiva")
    if member_length_m <= 0:
        raise StickSizingError("O comprimento da barra deve ser positivo")
    if (
        not isinstance(stick_count, int)
        or isinstance(stick_count, bool)
        or stick_count < 1
    ):
        raise StickSizingError("A quantidade de palitos deve ser um inteiro positivo")

    width = sizing.stick.width_mm
    height = sizing.stick.thickness_mm * stick_count
    area = width * height
    ix = width * height**3 / 12.0
    iy = height * width**3 / 12.0
    rx = math.sqrt(ix / area)
    ry = math.sqrt(iy / area)
    effective_length = member_length_m * 1_000 * sizing.effective_length_factor
    slenderness_x = effective_length / rx
    slenderness_y = effective_length / ry

    wood = sizing.wood
    relative_factor = math.sqrt(
        wood.characteristic_strength_mpa
        / (math.pi**2 * wood.characteristic_elasticity_mpa)
    )
    relative_x = slenderness_x * relative_factor
    relative_y = slenderness_y * relative_factor
    reduction_x = _compression_reduction_factor(relative_x, wood.beta_c)
    reduction_y = _compression_reduction_factor(relative_y, wood.beta_c)

    design_force = compression_force_n * sizing.design_force_factor
    stress = design_force / area
    effective_strength_x = reduction_x * wood.design_strength_mpa
    effective_strength_y = reduction_y * wood.design_strength_mpa
    utilization_x = stress / effective_strength_x
    utilization_y = stress / effective_strength_y
    governing_axis = "x" if utilization_x >= utilization_y else "y"
    governing_utilization = max(utilization_x, utilization_y)

    return CompressionCheck(
        stick_count=stick_count,
        compression_force_n=float(compression_force_n),
        design_force_n=design_force,
        member_length_m=float(member_length_m),
        effective_length_mm=effective_length,
        area_mm2=area,
        ix_mm4=ix,
        iy_mm4=iy,
        rx_mm=rx,
        ry_mm=ry,
        slenderness_x=slenderness_x,
        slenderness_y=slenderness_y,
        relative_slenderness_x=relative_x,
        relative_slenderness_y=relative_y,
        reduction_factor_x=reduction_x,
        reduction_factor_y=reduction_y,
        stress_mpa=stress,
        effective_strength_x_mpa=effective_strength_x,
        effective_strength_y_mpa=effective_strength_y,
        utilization_x=utilization_x,
        utilization_y=utilization_y,
        governing_axis=governing_axis,
        governing_utilization=governing_utilization,
        passes=governing_utilization <= 1.0,
    )


def required_sticks_for_compression(
    compression_force_n: float,
    member_length_m: float,
    config: Optional[StickSizingConfig] = None,
) -> CompressionCheck:
    """Busca a menor quantidade inteira que atende à verificação completa."""

    sizing = config or StickSizingConfig()
    for stick_count in range(1, sizing.max_sticks + 1):
        check = check_compression_section(
            compression_force_n,
            member_length_m,
            stick_count,
            sizing,
        )
        if check.passes:
            return check
    raise StickSizingError(
        "Nenhuma seção atendeu até "
        f"{sizing.max_sticks} palitos para {compression_force_n:g} N e "
        f"{member_length_m:g} m"
    )


def size_compression_members(
    model: FtoolModel,
    analysis: AnastructModel,
    config: Optional[StickSizingConfig] = None,
) -> StickSizingReport:
    """Dimensiona todas as barras que possuem parcela de força de compressão."""

    if not analysis.solved:
        raise RuntimeError("Execute analysis.solve() antes de dimensionar palitos")
    sizing = config or StickSizingConfig()
    members = [_size_member(member, analysis, sizing) for member in model.members]
    return StickSizingReport(config=sizing, members=members)


def export_stick_sizing_report(
    report: StickSizingReport,
    destination: Union[str, Path],
    *,
    indent: int = 2,
) -> Path:
    """Grava o relatório de dimensionamento em JSON."""

    return _write_json(report.to_dict(), destination, indent)


def export_stick_counts(
    report: StickSizingReport,
    destination: Union[str, Path],
    *,
    indent: int = 2,
) -> Path:
    """Grava somente o total e a quantidade de palitos por membro."""

    return _write_json(report.counts_to_dict(), destination, indent)


def _size_member(
    member: Member,
    analysis: AnastructModel,
    config: StickSizingConfig,
) -> MemberStickSizing:
    try:
        ana_id = analysis.member_ids[member.id]
    except KeyError as exc:
        raise StickSizingError(
            f"Barra FTool {member.id} não pertence à análise informada"
        ) from exc

    result = analysis.system.get_element_results(ana_id)
    axial_min = float(result["Nmin"])
    axial_max = float(result["Nmax"])
    compression_demand = max(0.0, -axial_min)

    if compression_demand <= 1e-9:
        return MemberStickSizing(
            id=f"m{ana_id}",
            ftool_id=member.id,
            anastruct_id=ana_id,
            start_node=f"n{member.start_node_id}",
            end_node=f"n{member.end_node_id}",
            member_length_m=member.length,
            axial_min_n=axial_min,
            axial_max_n=axial_max,
            compression_demand_n=0.0,
            status="not_in_compression",
            required_sticks=None,
            check=None,
        )

    check = required_sticks_for_compression(
        compression_demand,
        member.length,
        config,
    )
    return MemberStickSizing(
        id=f"m{ana_id}",
        ftool_id=member.id,
        anastruct_id=ana_id,
        start_node=f"n{member.start_node_id}",
        end_node=f"n{member.end_node_id}",
        member_length_m=member.length,
        axial_min_n=axial_min,
        axial_max_n=axial_max,
        compression_demand_n=compression_demand,
        status="sized",
        required_sticks=check.stick_count,
        check=check,
    )


def _compression_reduction_factor(
    relative_slenderness: float,
    beta_c: float,
) -> float:
    curve_value = 0.5 * (
        1.0
        + beta_c * (relative_slenderness - 0.3)
        + relative_slenderness**2
    )
    discriminant = max(curve_value**2 - relative_slenderness**2, 0.0)
    reduction = 1.0 / (curve_value + math.sqrt(discriminant))
    return min(reduction, 1.0)


def _write_json(
    data: Dict[str, Any],
    destination: Union[str, Path],
    indent: int,
) -> Path:
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
