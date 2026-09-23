from dataclasses import dataclass
from typing import Dict

from anastruct import SystemElements

from .models import FtoolModel, Member, Node, Support


class AnastructConversionError(ValueError):
    """Erro ao representar um modelo FTool no anaStruct."""


@dataclass
class AnastructModel:
    """Sistema anaStruct e correspondência com os IDs do modelo FTool."""

    system: SystemElements
    node_ids: Dict[int, int]
    member_ids: Dict[int, int]
    solved: bool = False

    def solve(self, **kwargs):
        """Resolve o sistema e preserva o estado para os plots de resultados."""
        result = self.system.solve(**kwargs)
        self.solved = True
        return result

    def get_node_results(self, ftool_node_id: int):
        """Obtém resultados de um nó usando o ID derivado pelo parser."""
        self._require_solved()
        return self.system.get_node_results_system(self.node_ids[ftool_node_id])

    def get_member_results(self, ftool_member_id: int):
        """Obtém resultados de uma barra usando seu ID original do FTool."""
        self._require_solved()
        return self.system.get_element_results(self.member_ids[ftool_member_id])

    def get_reaction_results(self, ftool_node_id: int):
        """Obtém a reação de apoio na convenção cartesiana do FTool."""
        self._require_solved()
        ana_node_id = self.node_ids[ftool_node_id]
        try:
            reaction = self.system.reaction_forces[ana_node_id]
        except KeyError as exc:
            raise ValueError(
                f"Nó FTool {ftool_node_id} não possui reação de apoio"
            ) from exc
        return {
            "id": ftool_node_id,
            "Fx": reaction.Fx,
            "Fy": reaction.Fy * self.system.orientation_cs,
            "Tz": reaction.Tz,
        }

    def _require_solved(self) -> None:
        if not self.solved:
            raise RuntimeError("Execute solve() antes de consultar resultados")


class AnastructConverter:
    """Converte :class:`FtoolModel` em :class:`anastruct.SystemElements`.

    O modelo de entrada já deve estar normalizado em SI: N, m e Pa.
    """

    ZERO_TOLERANCE = 1e-12

    def __init__(self, model: FtoolModel):
        self.model = model
        self.materials = {material.name: material for material in model.materials}
        self.sections = {section.name: section for section in model.sections}

    def convert(self, solve: bool = False, **solve_kwargs) -> AnastructModel:
        if not self.model.members:
            raise AnastructConversionError("O modelo não possui barras")

        # O anaStruct usa internamente o eixo vertical invertido para que as
        # cargas e os diagramas sejam desenhados na orientação cartesiana.
        system = SystemElements(invert_y_loads=True)
        member_ids: Dict[int, int] = {}

        for member in self.model.members:
            if member.id in member_ids:
                raise AnastructConversionError(f"ID de barra duplicado: {member.id}")
            member_ids[member.id] = self._add_member(system, member)

        node_ids = self._map_nodes(system)
        for node in self.model.nodes:
            ana_node_id = node_ids[node.id]
            self._add_support(system, ana_node_id, node.support)
            self._add_load(system, ana_node_id, node)

        converted = AnastructModel(
            system=system,
            node_ids=node_ids,
            member_ids=member_ids,
        )
        if solve:
            converted.solve(**solve_kwargs)
        return converted

    def _add_member(self, system: SystemElements, member: Member) -> int:
        if member.ignore_axial_deformation:
            raise AnastructConversionError(
                f"Barra {member.id}: restrição de deformação axial não suportada"
            )

        material = self.materials.get(member.material_name or "")
        section = self.sections.get(member.section_name or "")
        if material is None:
            raise AnastructConversionError(
                f"Barra {member.id}: material {member.material_name!r} não encontrado"
            )
        if section is None:
            raise AnastructConversionError(
                f"Barra {member.id}: seção {member.section_name!r} não encontrada"
            )

        # Mesma compatibilidade do dimensionamento: arquivos antigos podem
        # conter uma definição incompleta e outra válida com nome equivalente.
        if section.area <= 0:
            alternatives = [
                candidate for candidate in self.model.sections
                if candidate.name.casefold() == section.name.casefold()
                and candidate.area > 0
            ]
            if len(alternatives) == 1:
                section = alternatives[0]

        ea = material.elasticity * section.area
        ei = material.elasticity * section.inertia
        if ea <= self.ZERO_TOLERANCE:
            raise AnastructConversionError(f"Barra {member.id}: EA deve ser positivo")

        location = [[member.x1, member.y1], [member.x2, member.y2]]
        is_truss = section.inertia <= 0.0 or (
            member.hinge_start == 1 and member.hinge_end == 1
        )

        if is_truss:
            element_id = system.add_truss_element(location=location, EA=ea)
        else:
            springs = {}
            if member.hinge_start:
                springs[1] = 0.0
            if member.hinge_end:
                springs[2] = 0.0
            element_id = system.add_element(
                location=location,
                EA=ea,
                EI=ei,
                spring=springs or None,
            )

        system.element_map[element_id].section_name = section.name
        return element_id

    def _map_nodes(self, system: SystemElements) -> Dict[int, int]:
        result: Dict[int, int] = {}
        for node in self.model.nodes:
            ana_node_id = system.find_node_id([node.x, node.y], tolerance=1e-6)
            if ana_node_id is None:
                raise AnastructConversionError(
                    f"Nó {node.id} ({node.x}, {node.y}) não criado no anaStruct"
                )
            result[node.id] = ana_node_id
        return result

    def _add_support(
        self,
        system: SystemElements,
        node_id: int,
        support: Support,
    ) -> None:
        states = (support.ux, support.uy, support.rz)
        fixed = tuple(1 if state == 1 else 0 for state in states)

        if fixed == (1, 1, 1):
            system.add_support_fixed(node_id)
        elif fixed == (1, 1, 0):
            system.add_support_hinged(node_id)
        elif fixed == (0, 1, 0):
            system.add_support_roll(
                node_id, direction="x", angle=support.angle or None
            )
        elif fixed == (1, 0, 0):
            system.add_support_roll(
                node_id, direction="y", angle=support.angle or None
            )
        elif fixed == (0, 1, 1):
            system.add_support_roll(
                node_id,
                direction="x",
                angle=support.angle or None,
                rotate=False,
            )
        elif fixed == (1, 0, 1):
            system.add_support_roll(
                node_id,
                direction="y",
                angle=support.angle or None,
                rotate=False,
            )
        elif fixed == (0, 0, 1):
            system.add_support_rotational(node_id)
        elif fixed != (0, 0, 0):
            raise AnastructConversionError(
                f"Combinação de apoio não suportada no nó anaStruct {node_id}: {states}"
            )

        for axis, (state, stiffness) in enumerate(
            zip(states, (support.kx, support.ky, support.kz)), start=1
        ):
            if state != 2:
                continue
            if stiffness <= 0:
                raise AnastructConversionError(
                    f"Mola no eixo {axis} do nó anaStruct {node_id} sem rigidez positiva"
                )
            system.add_support_spring(
                node_id=node_id,
                translation=axis,
                k=stiffness,
                roll=True,
            )

    @staticmethod
    def _add_load(system: SystemElements, node_id: int, node: Node) -> None:
        if node.load is None:
            return
        if node.load.fx or node.load.fy:
            system.point_load(node_id=node_id, Fx=node.load.fx, Fy=node.load.fy)
        if node.load.moment:
            system.moment_load(node_id=node_id, Tz=node.load.moment)


def to_anastruct(
    model: FtoolModel,
    solve: bool = False,
    **solve_kwargs,
) -> AnastructModel:
    """Converte um modelo FTool para anaStruct."""

    return AnastructConverter(model).convert(solve=solve, **solve_kwargs)
