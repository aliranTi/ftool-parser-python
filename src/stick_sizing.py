import json
import math
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .converter_anastruct import AnastructModel
from .models import FtoolModel, Member, Section


class StickSizingError(ValueError):
    """Erro de entrada ou de convergência no dimensionamento de palitos."""


@dataclass(frozen=True)
class StickGeometry:
    """Dimensões nominais de um palito de madeira."""

    width_mm: float = 8.58
    thickness_mm: float = 1.94
    commercial_length_mm: float = 115.0

    def __post_init__(self) -> None:
        if (
            self.width_mm <= 0
            or self.thickness_mm <= 0
            or self.commercial_length_mm <= 0
        ):
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
class WoodTensionProperties:
    """Resistência média à tração paralela às fibras."""

    ft0m_mpa: float = 66.0

    def __post_init__(self) -> None:
        if self.ft0m_mpa <= 0:
            raise StickSizingError(
                "A resistência à tração paralela deve ser positiva"
            )


@dataclass(frozen=True)
class StickSizingConfig:
    """Hipóteses globais do dimensionamento."""

    stick: StickGeometry = field(default_factory=StickGeometry)
    wood: WoodCompressionProperties = field(
        default_factory=WoodCompressionProperties
    )
    tension: WoodTensionProperties = field(default_factory=WoodTensionProperties)
    effective_length_factor: float = 1.0
    design_force_factor: float = 1.0
    tension_force_factor: float = 1.0
    max_layers: int = 1_000
    minimum_member_layers: int = 1
    use_section_geometry: bool = True
    splice_overlap_mm: float = 0.0

    def __post_init__(self) -> None:
        if self.effective_length_factor <= 0:
            raise StickSizingError("O fator de comprimento efetivo deve ser positivo")
        if self.design_force_factor <= 0:
            raise StickSizingError("O fator do esforço de cálculo deve ser positivo")
        if self.tension_force_factor <= 0:
            raise StickSizingError("O fator do esforço de tração deve ser positivo")
        if self.max_layers < 1:
            raise StickSizingError("max_layers deve ser pelo menos 1")
        if self.minimum_member_layers < 1:
            raise StickSizingError("minimum_member_layers deve ser pelo menos 1")
        if self.minimum_member_layers > self.max_layers:
            raise StickSizingError(
                "minimum_member_layers não pode superar max_layers"
            )
        if self.splice_overlap_mm < 0:
            raise StickSizingError("A sobreposição não pode ser negativa")
        if self.splice_overlap_mm >= self.stick.commercial_length_mm:
            raise StickSizingError(
                "A sobreposição deve ser menor que o comprimento comercial"
            )


@dataclass(frozen=True)
class CompressionCheck:
    """Resultado completo para uma seção composta por camadas de palitos."""

    layer_count: int
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

    @property
    def stick_count(self) -> int:
        """Alias mantido para compatibilidade; representa camadas."""
        return self.layer_count

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TensionCheck:
    """Verificação da tração paralela às fibras."""

    layer_count: int
    tension_force_n: float
    design_force_n: float
    area_mm2: float
    stress_mpa: float
    ft0m_mpa: float
    resistance_n: float
    utilization: float
    passes: bool

    @property
    def governing_utilization(self) -> float:
        return self.utilization

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MemberStickSizing:
    """Camadas dimensionadas e quantidade física para uma barra do modelo."""

    id: str
    ftool_id: int
    anastruct_id: int
    start_node: str
    end_node: str
    member_length_m: float
    axial_min_n: float
    axial_max_n: float
    compression_demand_n: float
    tension_demand_n: float
    status: str
    governing_mode: Optional[str]
    required_layers: Optional[int]
    sticks_per_layer: Optional[int]
    total_sticks: Optional[int]
    section_width_mm: Optional[float]
    section_thickness_mm: Optional[float]
    geometry_section_name: Optional[str]
    compression_check: Optional[CompressionCheck]
    tension_check: Optional[TensionCheck]
    check: Optional[Union[CompressionCheck, TensionCheck]]

    @property
    def required_sticks(self) -> Optional[int]:
        """Alias compatível: agora representa palitos físicos, não camadas."""
        return self.total_sticks

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["required_sticks"] = self.total_sticks
        return data


@dataclass(frozen=True)
class StickSizingReport:
    """Relatório de dimensionamento axial das barras."""

    config: StickSizingConfig
    members: List[MemberStickSizing]
    scope: str = "axial_force_members"

    @property
    def compression_members(self) -> int:
        return sum(item.compression_check is not None for item in self.members)

    @property
    def tension_members(self) -> int:
        return sum(item.tension_check is not None for item in self.members)

    @property
    def sized_members(self) -> int:
        return sum(item.required_layers is not None for item in self.members)

    @property
    def sum_of_member_section_counts(self) -> int:
        """Soma das camadas requeridas nas seções dos membros."""
        return sum(item.required_layers or 0 for item in self.members)

    @property
    def total_required_layers(self) -> int:
        return self.sum_of_member_section_counts

    @property
    def total_physical_sticks(self) -> int:
        return sum(item.total_sticks or 0 for item in self.members)

    @property
    def total_required_sticks(self) -> int:
        """Quantidade física total estimada de palitos comerciais."""
        return self.total_physical_sticks

    @property
    def compressed_lamination_length_m(self) -> float:
        return sum(
            (item.required_layers or 0) * item.member_length_m
            for item in self.members
            if item.compression_demand_n > 0
        )

    @property
    def total_lamination_length_m(self) -> float:
        return sum(
            (item.required_layers or 0) * item.member_length_m
            for item in self.members
        )

    @property
    def estimated_purchased_length_m(self) -> float:
        return (
            self.total_physical_sticks
            * self.config.stick.commercial_length_mm
            / 1_000.0
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema": "ftool-parser-python.stick-sizing",
            "schema_version": 3,
            "units": {
                "model_length": "m",
                "section_length": "mm",
                "force": "N",
                "stress": "MPa",
            },
            "scope": self.scope,
            "sign_convention": {
                "positive_axial_force": "tension",
                "negative_axial_force": "compression",
            },
            "config": asdict(self.config),
            "summary": {
                "member_count": len(self.members),
                "sized_member_count": self.sized_members,
                "compression_member_count": self.compression_members,
                "tension_member_count": self.tension_members,
                "total_required_sticks": self.total_required_sticks,
                "total_physical_sticks": self.total_physical_sticks,
                "total_required_layers": self.total_required_layers,
                "sum_of_member_section_counts": self.sum_of_member_section_counts,
                "compressed_lamination_length_m": self.compressed_lamination_length_m,
                "total_lamination_length_m": self.total_lamination_length_m,
                "estimated_purchased_length_m": self.estimated_purchased_length_m,
            },
            "members": [item.to_dict() for item in self.members],
        }

    def counts_to_dict(self) -> Dict[str, Any]:
        """Retorna uma visão compacta do total e da quantidade por membro."""
        return {
            "schema": "ftool-parser-python.stick-counts",
            "schema_version": 3,
            "scope": self.scope,
            "units": {
                "force": "N",
                "member_length": "m",
                "section_and_stick_length": "mm",
            },
            "total_required_sticks": self.total_required_sticks,
            "total_physical_sticks": self.total_physical_sticks,
            "total_required_layers": self.total_required_layers,
            "sized_member_count": self.sized_members,
            "compression_member_count": self.compression_members,
            "tension_member_count": self.tension_members,
            "compressed_lamination_length_m": self.compressed_lamination_length_m,
            "total_lamination_length_m": self.total_lamination_length_m,
            "commercial_stick_length_mm": self.config.stick.commercial_length_mm,
            "splice_overlap_mm": self.config.splice_overlap_mm,
            "members": [
                {
                    "id": item.id,
                    "ftool_id": item.ftool_id,
                    "start_node": item.start_node,
                    "end_node": item.end_node,
                    "length": item.member_length_m,
                    "compression_demand": item.compression_demand_n,
                    "tension_demand": item.tension_demand_n,
                    "governing_mode": item.governing_mode,
                    "required_layers": item.required_layers,
                    "sticks_per_layer": item.sticks_per_layer,
                    "total_sticks": item.total_sticks,
                    "required_sticks": item.total_sticks,
                    "section_width_mm": item.section_width_mm,
                    "section_thickness_mm": item.section_thickness_mm,
                    "geometry_section_name": item.geometry_section_name,
                    "status": item.status,
                    "governing_utilization": _check_utilization(item.check),
                }
                for item in self.members
            ],
        }


def check_compression_section(
    compression_force_n: float,
    member_length_m: float,
    layer_count: int,
    config: Optional[StickSizingConfig] = None,
) -> CompressionCheck:
    """Verifica uma quantidade definida de camadas em uma barra comprimida."""

    sizing = config or StickSizingConfig()
    if compression_force_n <= 0:
        raise StickSizingError("A força de compressão deve ser positiva")
    if member_length_m <= 0:
        raise StickSizingError("O comprimento da barra deve ser positivo")
    if (
        not isinstance(layer_count, int)
        or isinstance(layer_count, bool)
        or layer_count < 1
    ):
        raise StickSizingError("A quantidade de camadas deve ser um inteiro positivo")

    width = sizing.stick.width_mm
    height = sizing.stick.thickness_mm * layer_count
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
        layer_count=layer_count,
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


def required_layers_for_compression(
    compression_force_n: float,
    member_length_m: float,
    config: Optional[StickSizingConfig] = None,
) -> CompressionCheck:
    """Busca a menor quantidade de camadas que atende à verificação."""

    sizing = config or StickSizingConfig()
    for layer_count in range(1, sizing.max_layers + 1):
        check = check_compression_section(
            compression_force_n,
            member_length_m,
            layer_count,
            sizing,
        )
        if check.passes:
            return check
    raise StickSizingError(
        "Nenhuma seção atendeu até "
        f"{sizing.max_layers} camadas para {compression_force_n:g} N e "
        f"{member_length_m:g} m"
    )


def required_sticks_for_compression(
    compression_force_n: float,
    member_length_m: float,
    config: Optional[StickSizingConfig] = None,
) -> CompressionCheck:
    """Alias compatível de :func:`required_layers_for_compression`."""
    return required_layers_for_compression(
        compression_force_n,
        member_length_m,
        config,
    )


def check_tension_section(
    tension_force_n: float,
    layer_count: int,
    config: Optional[StickSizingConfig] = None,
) -> TensionCheck:
    """Aplica ``sigma = Ft / (n * b * hp)`` em unidades N, mm e MPa."""

    sizing = config or StickSizingConfig()
    if tension_force_n <= 0:
        raise StickSizingError("A força de tração deve ser positiva")
    if (
        not isinstance(layer_count, int)
        or isinstance(layer_count, bool)
        or layer_count < 1
    ):
        raise StickSizingError("A quantidade de camadas deve ser um inteiro positivo")

    area = layer_count * sizing.stick.width_mm * sizing.stick.thickness_mm
    design_force = tension_force_n * sizing.tension_force_factor
    stress = design_force / area
    strength = sizing.tension.ft0m_mpa
    resistance = strength * area
    utilization = stress / strength
    return TensionCheck(
        layer_count=layer_count,
        tension_force_n=float(tension_force_n),
        design_force_n=design_force,
        area_mm2=area,
        stress_mpa=stress,
        ft0m_mpa=strength,
        resistance_n=resistance,
        utilization=utilization,
        passes=stress < strength,
    )


def required_layers_for_tension(
    tension_force_n: float,
    config: Optional[StickSizingConfig] = None,
) -> TensionCheck:
    """Busca o menor número de camadas que resiste à tração."""

    sizing = config or StickSizingConfig()
    for layer_count in range(1, sizing.max_layers + 1):
        check = check_tension_section(tension_force_n, layer_count, sizing)
        if check.passes:
            return check
    raise StickSizingError(
        "Nenhuma seção atendeu até "
        f"{sizing.max_layers} camadas para {tension_force_n:g} N"
    )


def size_compression_members(
    model: FtoolModel,
    analysis: AnastructModel,
    config: Optional[StickSizingConfig] = None,
) -> StickSizingReport:
    """Dimensiona todas as barras que possuem parcela de força de compressão."""

    return _size_members(model, analysis, config, include_tension=False)


def size_axial_members(
    model: FtoolModel,
    analysis: AnastructModel,
    config: Optional[StickSizingConfig] = None,
) -> StickSizingReport:
    """Dimensiona barras submetidas à compressão e/ou à tração."""

    return _size_members(model, analysis, config, include_tension=True)


def _size_members(
    model: FtoolModel,
    analysis: AnastructModel,
    config: Optional[StickSizingConfig],
    *,
    include_tension: bool,
) -> StickSizingReport:
    if not analysis.solved:
        raise RuntimeError("Execute analysis.solve() antes de dimensionar palitos")
    sizing = config or StickSizingConfig()
    members = [
        _size_member(
            member,
            analysis,
            sizing,
            model.sections,
            include_tension=include_tension,
        )
        for member in model.members
    ]
    scope = "axial_force_members" if include_tension else "compression_members"
    return StickSizingReport(config=sizing, members=members, scope=scope)


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
    sections: List[Section],
    *,
    include_tension: bool,
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
    tension_demand = max(0.0, axial_max)

    has_compression = compression_demand > 1e-9
    has_tension = include_tension and tension_demand > 1e-9
    if not has_compression and not has_tension:
        if include_tension:
            member_config, geometry_section_name = _config_for_member(
                member,
                sections,
                config,
            )
            required_layers = config.minimum_member_layers
            sticks_per_layer = _sticks_along_member(member.length, member_config)
            total_sticks = required_layers * sticks_per_layer
        else:
            geometry_section_name = None
            required_layers = None
            sticks_per_layer = None
            total_sticks = None
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
            tension_demand_n=tension_demand,
            status="minimum_layers" if include_tension else "not_in_compression",
            governing_mode="minimum" if include_tension else None,
            required_layers=required_layers,
            sticks_per_layer=sticks_per_layer,
            total_sticks=total_sticks,
            section_width_mm=(
                member_config.stick.width_mm if include_tension else None
            ),
            section_thickness_mm=(
                member_config.stick.thickness_mm if include_tension else None
            ),
            geometry_section_name=geometry_section_name,
            compression_check=None,
            tension_check=None,
            check=None,
        )

    member_config, geometry_section_name = _config_for_member(
        member,
        sections,
        config,
    )
    minimum_compression_check = (
        required_layers_for_compression(
            compression_demand,
            member.length,
            member_config,
        )
        if has_compression
        else None
    )
    minimum_tension_check = (
        required_layers_for_tension(tension_demand, member_config)
        if has_tension
        else None
    )
    required_layers = max(
        config.minimum_member_layers,
        minimum_compression_check.layer_count if minimum_compression_check else 0,
        minimum_tension_check.layer_count if minimum_tension_check else 0,
    )
    compression_check = (
        check_compression_section(
            compression_demand,
            member.length,
            required_layers,
            member_config,
        )
        if has_compression
        else None
    )
    tension_check = (
        check_tension_section(tension_demand, required_layers, member_config)
        if has_tension
        else None
    )
    governing_mode, check = _governing_check(compression_check, tension_check)
    sticks_per_layer = _sticks_along_member(member.length, member_config)
    total_sticks = required_layers * sticks_per_layer
    if has_compression and has_tension:
        status = "sized_mixed"
    elif has_compression:
        status = "sized_compression"
    else:
        status = "sized_tension"
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
        tension_demand_n=tension_demand,
        status=status,
        governing_mode=governing_mode,
        required_layers=required_layers,
        sticks_per_layer=sticks_per_layer,
        total_sticks=total_sticks,
        section_width_mm=member_config.stick.width_mm,
        section_thickness_mm=member_config.stick.thickness_mm,
        geometry_section_name=geometry_section_name,
        compression_check=compression_check,
        tension_check=tension_check,
        check=check,
    )


def _config_for_member(
    member: Member,
    sections: List[Section],
    config: StickSizingConfig,
) -> tuple[StickSizingConfig, Optional[str]]:
    if not config.use_section_geometry:
        return config, None

    if not member.section_name:
        raise StickSizingError(
            f"Barra FTool {member.id} não possui seção para obter as dimensões"
        )

    matching = [
        section for section in sections if section.name == member.section_name
    ]
    valid = [section for section in matching if _has_stick_dimensions(section)]

    # Alguns arquivos possuem nomes que diferem apenas em maiúsculas e uma
    # definição incompleta. Nesse caso, usa a definição válida equivalente.
    if not valid:
        valid = [
            section
            for section in sections
            if section.name.casefold() == member.section_name.casefold()
            and _has_stick_dimensions(section)
        ]

    if not valid:
        raise StickSizingError(
            f"Seção {member.section_name!r} da barra FTool {member.id} "
            "não possui largura e espessura retangulares positivas"
        )

    section = valid[0]
    stick = replace(
        config.stick,
        width_mm=section.width * 1_000.0,
        thickness_mm=section.thickness * 1_000.0,
    )
    return replace(config, stick=stick), section.name


def _governing_check(
    compression: Optional[CompressionCheck],
    tension: Optional[TensionCheck],
) -> tuple[str, Union[CompressionCheck, TensionCheck]]:
    if compression is None and tension is None:
        raise StickSizingError("Nenhuma solicitação axial para dimensionar")
    if compression is None:
        assert tension is not None
        return "tension", tension
    if tension is None:
        return "compression", compression
    if compression.layer_count > tension.layer_count:
        return "compression", compression
    if tension.layer_count > compression.layer_count:
        return "tension", tension
    if compression.governing_utilization >= tension.utilization:
        return "compression", compression
    return "tension", tension


def _check_utilization(
    check: Optional[Union[CompressionCheck, TensionCheck]],
) -> Optional[float]:
    if isinstance(check, CompressionCheck):
        return check.governing_utilization
    if isinstance(check, TensionCheck):
        return check.utilization
    return None


def _has_stick_dimensions(section: Section) -> bool:
    return section.width > 0 and section.thickness > 0


def _sticks_along_member(
    member_length_m: float,
    config: StickSizingConfig,
) -> int:
    member_length_mm = member_length_m * 1_000.0
    commercial_length = config.stick.commercial_length_mm
    overlap = config.splice_overlap_mm
    if member_length_mm <= commercial_length:
        return 1
    effective_increment = commercial_length - overlap
    remaining_length = member_length_mm - commercial_length
    tolerance_mm = 1e-9
    extra_sticks = math.ceil(
        max(0.0, remaining_length - tolerance_mm) / effective_increment
    )
    return 1 + extra_sticks


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
