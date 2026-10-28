from dataclasses import dataclass, field


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
    minimum_member_layers: int = 3
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
