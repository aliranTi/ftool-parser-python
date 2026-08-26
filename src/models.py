import math
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any

@dataclass
class Material:
    """Propriedades mecânicas do material."""
    name: str
    elasticity: float          # E (N/m² ou Pa)
    poisson: float             # ν (coeficiente de Poisson)
    weight: float              # γ (peso específico em N/m³)
    thermal_expansion: float    # α (coeficiente de dilatação térmica 1/°C)

@dataclass
class Section:
    """Propriedades geométricas da seção transversal."""
    name: str
    area: float                # A (m²)
    inertia: float             # I (m⁴)
    height: float = 0.0        # h (m) - opcional para análise de temperatura

@dataclass
class PointLoad:
    """Carga pontual aplicada a nós."""
    name: str
    fx: float                  # Fx (N)
    fy: float                  # Fy (N)
    moment: float              # M (N·m)

@dataclass
class Support:
    """Condições de contorno de um nó.

    Estados usados pelo FTool: 0 = livre, 1 = restringido e 2 = mola.
    """
    ux: int = 0
    uy: int = 0
    rz: int = 0
    angle: float = 0.0         # graus
    kx: float = 0.0            # N/m
    ky: float = 0.0            # N/m
    kz: float = 0.0            # N·m/rad

    @property
    def is_free(self) -> bool:
        return self.ux == 0 and self.uy == 0 and self.rz == 0

    @property
    def is_fixed(self) -> bool:
        return self.ux == 1 and self.uy == 1 and self.rz == 1

    @property
    def is_pinned(self) -> bool:
        return self.ux == 1 and self.uy == 1 and self.rz == 0

    @property
    def is_roller_x(self) -> bool:
        return self.ux == 0 and self.uy == 1 and self.rz == 0

    @property
    def is_roller_y(self) -> bool:
        return self.ux == 1 and self.uy == 0 and self.rz == 0

    @property
    def has_spring(self) -> bool:
        return 2 in (self.ux, self.uy, self.rz)

@dataclass
class Node:
    """Nó da estrutura com coordenadas e apoios."""
    id: int
    x: float
    y: float
    support: Support = field(default_factory=Support)
    load: Optional[PointLoad] = None


@dataclass
class Member:
    """Barra/Elemento da estrutura conectando dois pontos."""
    id: int
    x1: float
    y1: float
    x2: float
    y2: float
    material_name: Optional[str] = None
    section_name: Optional[str] = None
    start_node_id: Optional[int] = None
    end_node_id: Optional[int] = None
    hinge_start: int = 0
    hinge_end: int = 0
    ignore_axial_deformation: int = 0
    ignore_shear_deformation: int = 0

    @property
    def length(self) -> float:
        """Calcula o comprimento da barra em metros."""
        return math.hypot(self.x2 - self.x1, self.y2 - self.y1)


@dataclass
class DimensionLine:
    """Cota com os pontos medidos e a linha exibida pelo FTool."""
    x1: float
    y1: float
    x2: float
    y2: float
    display_x1: Optional[float] = None
    display_y1: Optional[float] = None
    display_x2: Optional[float] = None
    display_y2: Optional[float] = None


@dataclass
class FtoolModel:
    """Estrutura extraída do FTool e normalizada para SI (N, m, Pa)."""
    materials: List[Material] = field(default_factory=list)
    sections: List[Section] = field(default_factory=list)
    point_loads: List[PointLoad] = field(default_factory=list)
    nodes: List[Node] = field(default_factory=list)
    members: List[Member] = field(default_factory=list)
    dimensions: List[DimensionLine] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Converte todo o modelo para um dicionário serializável em JSON."""
        return asdict(self)

@dataclass
class RawRecord:
    index: int
    lines: List[str]


@dataclass
class RawModel:
    lines: List[str]

    materials: List[Material] = field(default_factory=list)
    sections: List[Section] = field(default_factory=list)

    dimensions: List[DimensionLine] = field(default_factory=list)

    records: List[RawRecord] = field(default_factory=list)

