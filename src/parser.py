import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .ftl_reader import FtlReader
from .models import (
    DimensionLine,
    FtoolModel,
    Material,
    Member,
    Node,
    PointLoad,
    RawModel,
    RawRecord,
    Section,
    Support,
)
from .utils import parse_ints, parse_numbers, parse_quoted_record


class FtlParseError(ValueError):
    """Erro de estrutura em um arquivo FTL."""


class FtlParser:
    """Parser dos arquivos textuais do FTool 4.00/4.01.

    O FTool serializa barras, não nós independentes. Nós são derivados dos
    endpoints das barras e unificados geometricamente.
    """

    CREATOR_SIZE = 16
    CONNECTOR_SIZE = 12
    NODE_TOLERANCE = 1e-3
    SENTINEL_LIMIT = 1e29
    KILO_TO_BASE = 1_000.0

    def __init__(
        self,
        path: str | Path | None = None,
        *,
        text: str | None = None,
    ):
        if (path is None) == (text is None):
            raise ValueError("Informe exatamente um entre path e text")

        self.path = Path(path) if path is not None else None
        self._source_text = text
        self.lines: List[str] = []
        self.raw = RawModel(lines=[])
        self.model = FtoolModel()
        self.version = 0
        self.load_case_names: List[str] = []
        self._cursor = 0
        self._nodes: List[Node] = []
        self._materials_by_id: Dict[int, Material] = {}
        self._sections_by_id: Dict[int, Section] = {}
        self._point_loads_by_id: Dict[int, PointLoad] = {}

    @classmethod
    def from_text(cls, text: str) -> "FtlParser":
        """Cria um parser para conteúdo em memória, inclusive no Pyodide."""

        return cls(text=text)

    @classmethod
    def from_bytes(cls, raw: bytes) -> "FtlParser":
        """Cria um parser para bytes FTL codificados em latin-1."""

        return cls(text=raw.decode("latin-1"))

    def parse(self) -> FtoolModel:
        """Lê o arquivo e devolve um novo modelo a cada chamada."""
        self._reset()
        if self._source_text is None:
            if self.path is None:
                raise RuntimeError("Fonte FTL não configurada")
            self.lines = FtlReader(self.path).read()
        else:
            self.lines = FtlReader.from_text(self._source_text)
        self.raw.lines = self.lines

        self._parse_header()
        self._parse_loads_materials_and_sections()
        self._parse_dimensions()
        self._parse_root_node_data()
        self._parse_entities()
        self._validate_model()
        return self.model

    def _reset(self) -> None:
        self.raw = RawModel(lines=[])
        self.model = FtoolModel()
        self.version = 0
        self.load_case_names = []
        self._cursor = 0
        self._nodes = self.model.nodes
        self._materials_by_id = {}
        self._sections_by_id = {}
        self._point_loads_by_id = {}

    # ------------------------------------------------------------------
    # Cabeçalho e tabelas globais
    # ------------------------------------------------------------------

    def _parse_header(self) -> None:
        if len(self.lines) < 16:
            raise FtlParseError("Arquivo FTL menor que o cabeçalho de 16 linhas")

        signature = parse_ints(self.lines[0])
        if len(signature) != 2 or signature[0] not in (400, 401):
            raise FtlParseError(
                f"Versão FTL não suportada na linha 1: {self.lines[0]!r}"
            )

        self.version = signature[0]
        self._cursor = 16

    def _parse_loads_materials_and_sections(self) -> None:
        load_case_count = self._read_count("casos de carga")
        for _ in range(load_case_count):
            name, _ = self._read_quoted_record("caso de carga")
            self.load_case_names.append(name)

        self._read_int_line("campo reservado após casos de carga")

        point_load_count = self._read_count("cargas nodais")
        for load_id in range(1, point_load_count + 1):
            name, values = self._read_quoted_record("carga nodal")
            if len(values) != 3:
                self._fail("carga nodal deve conter Fx, Fy e Mz")
            load = PointLoad(
                name=name,
                fx=values[0] * self.KILO_TO_BASE,
                fy=values[1] * self.KILO_TO_BASE,
                moment=values[2] * self.KILO_TO_BASE,
            )
            self.model.point_loads.append(load)
            self._point_loads_by_id[load_id] = load

        # Tabelas globais de uma linha por definição. Esses tipos ainda não
        # são expostos pelo modelo, mas precisam ser consumidos corretamente.
        for label in (
            "cargas uniformes",
            "cargas lineares",
            "momentos de extremidade",
            "cargas térmicas",
        ):
            count = self._read_count(label)
            for _ in range(count):
                self._read_line(label)

        material_count = self._read_count("materiais")
        for material_id in range(1, material_count + 1):
            name, _ = self._read_quoted_record("material")
            values = parse_numbers(self._read_line("propriedades do material"))
            if len(values) < 4:
                self._fail("material deve conter E, ν, peso específico e α")
            material = Material(
                name=name,
                elasticity=values[0] * self.KILO_TO_BASE,
                poisson=values[1],
                weight=values[2] * self.KILO_TO_BASE,
                thermal_expansion=values[3],
            )
            self.model.materials.append(material)
            self._materials_by_id[material_id] = material

        section_count = self._read_count("seções")
        for section_id in range(1, section_count + 1):
            name, section_flags = self._read_quoted_record("seção")
            values = parse_numbers(self._read_line("propriedades da seção"))
            if len(values) < 2:
                self._fail("seção deve conter ao menos área e inércia")

            inertia_index = 2 if len(values) >= 3 else 1
            height = values[4] if len(values) >= 5 else 0.0
            is_rectangular = bool(section_flags and int(section_flags[0]) == 1)
            section = Section(
                name=name,
                area=values[0],
                inertia=values[inertia_index],
                height=height,
                width=values[0] if is_rectangular else 0.0,
                thickness=values[1] if is_rectangular else 0.0,
            )
            self.model.sections.append(section)
            self._sections_by_id[section_id] = section

        self._skip_load_trains()

    def _skip_load_trains(self) -> None:
        """Consome a tabela de trens de carga; ainda não a expõe no modelo."""
        train_count = self._read_count("trens de carga")
        for _ in range(train_count):
            self._read_line("nome do trem de carga")
            self._read_line("fator de impacto")

            concentrated_count = self._read_count("forças concentradas do trem")
            for _ in range(concentrated_count):
                self._read_line("força concentrada do trem")

            distributed_count = self._read_count("forças distribuídas do trem")
            for _ in range(distributed_count):
                self._read_line("força distribuída do trem")

            for label in (
                "carga viva exterior",
                "carga viva interior",
                "comprimento do trem",
                "modo cheio/vazio",
                "separador do trem",
            ):
                self._read_line(label)

    def _parse_dimensions(self) -> None:
        dimension_count = self._read_count("linhas de cota")
        for _ in range(dimension_count):
            values = parse_numbers(self._read_line("linha de cota"))
            if len(values) != 8:
                self._fail("linha de cota deve conter 8 coordenadas")
            self.model.dimensions.append(
                DimensionLine(
                    x1=values[0],
                    y1=values[1],
                    x2=values[2],
                    y2=values[3],
                    display_x1=values[4],
                    display_y1=values[5],
                    display_x2=values[6],
                    display_y2=values[7],
                )
            )

    # ------------------------------------------------------------------
    # Nó-base e entidades estruturais
    # ------------------------------------------------------------------

    def _parse_root_node_data(self) -> None:
        support_line = self._read_line("apoio do nó-base")
        spring_line = self._read_line("molas do nó-base")
        load_line = self._read_line("carga do nó-base")
        self._read_line("recalque do nó-base")

        anchor = parse_numbers(self.lines[4])
        if len(anchor) != 2 or self._has_sentinel(anchor):
            return

        node = self._get_or_create_node(anchor[0], anchor[1])
        node.support = self._parse_support(support_line, spring_line)
        self._assign_point_load(node, load_line)

    def _parse_entities(self) -> None:
        raw_index = 1

        while self._cursor < len(self.lines):
            if self.lines[self._cursor].strip() == "0":
                if all(not line.strip() or line.strip() == "0" for line in self.lines[self._cursor:]):
                    break
                self._fail("marcador de entidade esperado")

            if self.lines[self._cursor].strip() != "1":
                self._fail("marcador de entidade '1' esperado")

            if self._cursor + 1 >= len(self.lines):
                self._fail("header de entidade ausente")

            header = parse_ints(self.lines[self._cursor + 1])
            if len(header) != 11:
                self._fail("header de entidade deve conter 11 inteiros")

            entity_type = header[0]
            if entity_type == -1:
                block_size = 2
            elif entity_type == 2:
                block_size = self.CREATOR_SIZE
            elif entity_type == 4:
                block_size = self.CONNECTOR_SIZE
            else:
                self._fail(f"tipo de entidade desconhecido: {entity_type}")

            end = self._cursor + block_size
            if end > len(self.lines):
                self._fail(f"bloco tipo {entity_type} está truncado")

            block = self.lines[self._cursor:end]
            self.raw.records.append(RawRecord(index=raw_index, lines=block))
            raw_index += 1

            if entity_type == 2:
                self._parse_creator_member(header, block)
            elif entity_type == 4:
                self._parse_connector_member(header, block)

            self._cursor = end

    def _parse_creator_member(self, header: List[int], block: List[str]) -> None:
        endpoint = parse_numbers(block[2])
        bbox = parse_numbers(block[4])
        if len(endpoint) != 2 or len(bbox) != 4 or self._has_sentinel(endpoint + bbox):
            raise FtlParseError(f"Barra creator {header[-1]} possui geometria inválida")

        x_end, y_end = endpoint
        x_start = self._opposite_bbox_coordinate(x_end, bbox[0], bbox[1])
        y_start = self._opposite_bbox_coordinate(y_end, bbox[2], bbox[3])

        start_node = self._get_or_create_node(x_start, y_start)
        end_node = self._get_or_create_node(x_end, y_end)
        end_node.support = self._parse_support(block[12], block[13])
        self._assign_point_load(end_node, block[14])

        self._append_member(header, block, start_node, end_node)

    def _parse_connector_member(self, header: List[int], block: List[str]) -> None:
        global_bbox = parse_numbers(block[2])
        entity_bbox = parse_numbers(block[4])

        # Em barras resultantes de subdivisão, o bbox global pode vir com
        # sentinelas. A geometria física continua válida no bbox da entidade.
        if len(global_bbox) != 4:
            raise FtlParseError(f"Barra connector {header[-1]} possui bbox global inválido")
        if len(entity_bbox) != 4 or self._has_sentinel(entity_bbox):
            raise FtlParseError(f"Barra connector {header[-1]} possui bbox inválido")

        p1, p2 = self._connector_endpoints(entity_bbox)
        start_node = self._get_or_create_node(*p1)
        end_node = self._get_or_create_node(*p2)
        self._append_member(header, block, start_node, end_node)

    def _append_member(
        self,
        header: List[int],
        block: List[str],
        start_node: Node,
        end_node: Node,
    ) -> None:
        flags = parse_ints(block[5])
        if len(flags) != 6:
            raise FtlParseError(f"Barra {header[-1]} possui linha de flags inválida")

        material_id = self._single_int(block[6], "ID de material")
        section_id = self._single_int(block[7], "ID de seção")
        material = self._materials_by_id.get(material_id)
        section = self._sections_by_id.get(section_id)

        if material_id and material is None:
            raise FtlParseError(f"Barra {header[-1]} referencia material {material_id} inexistente")
        if section_id and section is None:
            raise FtlParseError(f"Barra {header[-1]} referencia seção {section_id} inexistente")

        self.model.members.append(
            Member(
                id=header[-1],
                x1=start_node.x,
                y1=start_node.y,
                x2=end_node.x,
                y2=end_node.y,
                material_name=material.name if material else None,
                section_name=section.name if section else None,
                start_node_id=start_node.id,
                end_node_id=end_node.id,
                hinge_start=flags[1],
                hinge_end=flags[2],
                ignore_axial_deformation=flags[3],
                ignore_shear_deformation=flags[4],
            )
        )

    # ------------------------------------------------------------------
    # Geometria, apoios e referências
    # ------------------------------------------------------------------

    def _get_or_create_node(self, x: float, y: float) -> Node:
        node = self._nearest_node(x, y)
        if node is not None and math.hypot(node.x - x, node.y - y) <= self.NODE_TOLERANCE:
            return node

        node = Node(id=len(self._nodes) + 1, x=x, y=y)
        self._nodes.append(node)
        return node

    def _nearest_node(self, x: float, y: float) -> Optional[Node]:
        if not self._nodes:
            return None
        return min(self._nodes, key=lambda node: math.hypot(node.x - x, node.y - y))

    def _connector_endpoints(
        self, bbox: List[float]
    ) -> Tuple[Tuple[float, float], Tuple[float, float]]:
        xmin, xmax, ymin, ymax = bbox
        positive = ((xmin, ymin), (xmax, ymax))
        negative = ((xmin, ymax), (xmax, ymin))

        def score(pair: Tuple[Tuple[float, float], Tuple[float, float]]) -> float:
            total = 0.0
            for x, y in pair:
                nearest = self._nearest_node(x, y)
                total += math.inf if nearest is None else math.hypot(nearest.x - x, nearest.y - y)
            return total

        return negative if score(negative) < score(positive) else positive

    def _opposite_bbox_coordinate(self, value: float, lower: float, upper: float) -> float:
        lower_distance = abs(value - lower)
        upper_distance = abs(value - upper)
        if lower_distance <= self.NODE_TOLERANCE and upper_distance <= self.NODE_TOLERANCE:
            return value
        return upper if lower_distance < upper_distance else lower

    def _parse_support(self, support_line: str, spring_line: str) -> Support:
        values = parse_numbers(support_line)
        springs = parse_numbers(spring_line)
        if len(values) != 5 or len(springs) != 3:
            raise FtlParseError("Bloco de apoio inválido")

        states = tuple(int(value) for value in values[1:4])
        if any(state not in (0, 1, 2) for state in states):
            raise FtlParseError(f"Estados de apoio inválidos: {states}")

        return Support(
            ux=states[0],
            uy=states[1],
            rz=states[2],
            angle=values[4],
            kx=springs[0] * self.KILO_TO_BASE,
            ky=springs[1] * self.KILO_TO_BASE,
            kz=springs[2] * self.KILO_TO_BASE,
        )

    def _assign_point_load(self, node: Node, line: str) -> None:
        load_id = self._single_int(line, "ID de carga nodal")
        if load_id == 0:
            return
        try:
            node.load = self._point_loads_by_id[load_id]
        except KeyError as exc:
            raise FtlParseError(f"Carga nodal {load_id} não foi definida") from exc

    # ------------------------------------------------------------------
    # Leitura e validação
    # ------------------------------------------------------------------

    def _read_line(self, label: str) -> str:
        if self._cursor >= len(self.lines):
            raise FtlParseError(f"Fim inesperado ao ler {label}")
        line = self.lines[self._cursor]
        self._cursor += 1
        return line

    def _read_int_line(self, label: str) -> List[int]:
        line = self._read_line(label)
        values = parse_ints(line)
        if not values:
            raise FtlParseError(f"Esperava inteiros em {label}: {line!r}")
        return values

    def _read_count(self, label: str) -> int:
        values = self._read_int_line(label)
        if len(values) != 1 or values[0] < 0:
            raise FtlParseError(f"Contagem inválida para {label}: {values}")
        return values[0]

    def _read_quoted_record(self, label: str) -> Tuple[str, List[float]]:
        line = self._read_line(label)
        record = parse_quoted_record(line)
        if record is None:
            raise FtlParseError(f"Registro de {label} sem nome entre aspas: {line!r}")
        return record

    def _single_int(self, line: str, label: str) -> int:
        values = parse_ints(line)
        if len(values) != 1:
            raise FtlParseError(f"{label} inválido: {line!r}")
        return values[0]

    def _has_sentinel(self, values: List[float]) -> bool:
        return any(abs(value) >= self.SENTINEL_LIMIT for value in values)

    def _fail(self, message: str) -> None:
        raise FtlParseError(f"Linha {self._cursor + 1}: {message}")

    def _validate_model(self) -> None:
        node_ids = {node.id for node in self.model.nodes}
        if len(node_ids) != len(self.model.nodes):
            raise FtlParseError("IDs de nós duplicados")

        for member in self.model.members:
            if member.length <= self.NODE_TOLERANCE:
                raise FtlParseError(f"Barra {member.id} possui comprimento nulo")
            if member.start_node_id not in node_ids or member.end_node_id not in node_ids:
                raise FtlParseError(f"Barra {member.id} referencia nó inexistente")

    def debug(self) -> None:
        print("=" * 60)
        source = self.path if self.path is not None else "<memória>"
        print(f"FTOOL {self.version / 100:.2f}: {source}")
        print("=" * 60)
        print(f"Materiais: {len(self.model.materials)}")
        print(f"Seções: {len(self.model.sections)}")
        print(f"Cargas nodais: {len(self.model.point_loads)}")
        print(f"Cotas: {len(self.model.dimensions)}")
        print(f"Nós derivados: {len(self.model.nodes)}")
        print(f"Barras físicas: {len(self.model.members)}")

        print("\nNÓS")
        for node in self.model.nodes:
            load = node.load.name if node.load else "-"
            print(
                f"  N{node.id}: ({node.x:g}, {node.y:g}) "
                f"apoio=({node.support.ux}, {node.support.uy}, {node.support.rz}) "
                f"carga={load}"
            )

        print("\nBARRAS")
        for member in self.model.members:
            print(
                f"  B{member.id}: N{member.start_node_id} -> N{member.end_node_id} "
                f"L={member.length:g} material={member.material_name!r} "
                f"seção={member.section_name!r}"
            )
