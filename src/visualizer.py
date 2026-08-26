from typing import Any, Literal

from .converter_anastruct import AnastructModel, to_anastruct
from .models import FtoolModel


ResultPlot = Literal[
    "reactions",
    "axial",
    "shear",
    "moment",
    "displacement",
]


def plot_ftool_model(
    model: FtoolModel,
    *,
    verbosity: int = 0,
    show_node_ids: bool = True,
    show_member_ids: bool = True,
    scale: float = 1.0,
    offset: tuple[float, float] = (0.0, 0.0),
    figsize: tuple[float, float] = (10.0, 6.0),
    show: bool = True,
    annotations: bool = False,
) -> tuple[AnastructModel, Any]:
    """Converte o modelo e desenha estrutura, apoios e cargas com anaStruct.

    O primeiro item retornado contém o ``SystemElements`` e os mapas de IDs. A
    numeração nativa do anaStruct é substituída por ``n1``, ``n2``, ... para
    nós e ``m1``, ``m2``, ... para barras.
    """

    analysis = to_anastruct(model)
    # verbosity=0 é necessário para o anaStruct incluir as cargas. Os textos
    # numéricos nativos são removidos logo abaixo e substituídos pelos IDs FTool.
    figure = analysis.system.show_structure(
        verbosity=0,
        scale=scale,
        offset=offset,
        figsize=figsize,
        show=False,
        supports=True,
        annotations=annotations,
    )
    _customize_structure_labels(
        model,
        analysis,
        figure,
        show_node_ids=show_node_ids,
        show_member_ids=show_member_ids,
        show_load_values=verbosity == 0,
    )
    if show:
        analysis.system.plotter.plot()
    return analysis, figure


def _customize_structure_labels(
    model: FtoolModel,
    analysis: AnastructModel,
    figure: Any,
    *,
    show_node_ids: bool,
    show_member_ids: bool,
    show_load_values: bool,
) -> None:
    """Troca apenas as anotações; geometria, apoios e cargas são do anaStruct."""

    axis = figure.axes[0]
    for label in list(axis.texts):
        text = label.get_text().strip()
        if text.isdigit() or (not show_load_values and text.startswith("F=")):
            label.remove()

    x_values = [node.x for node in model.nodes]
    y_values = [node.y for node in model.nodes]
    span = max(max(x_values) - min(x_values), max(y_values) - min(y_values))
    label_offset = max(span * 0.018, 1e-6)
    colors = analysis.system.plotter.plot_colors
    label_box = {
        "facecolor": "white",
        "edgecolor": "none",
        "alpha": 0.7,
        "pad": 0.5,
    }

    if show_node_ids:
        for node in model.nodes:
            axis.text(
                node.x + label_offset,
                node.y + label_offset,
                f"n{node.id}",
                color=colors["node_number"],
                fontsize=9,
                fontweight="bold",
                zorder=12,
                bbox=label_box,
            )

    if show_member_ids:
        for member in model.members:
            dx = member.x2 - member.x1
            dy = member.y2 - member.y1
            length = member.length
            middle_x = (member.x1 + member.x2) / 2
            middle_y = (member.y1 + member.y2) / 2
            axis.text(
                middle_x - dy / length * label_offset,
                middle_y + dx / length * label_offset,
                f"m{analysis.member_ids[member.id]}",
                color=colors["element_number"],
                fontsize=9,
                fontweight="bold",
                horizontalalignment="center",
                verticalalignment="center",
                zorder=12,
                bbox=label_box,
            )


def plot_anastruct_result(
    analysis: AnastructModel,
    result: ResultPlot = "axial",
    *,
    show: bool = True,
    **plot_kwargs: Any,
) -> Any:
    """Desenha um resultado de um modelo já resolvido pelo anaStruct."""

    if not analysis.solved:
        raise RuntimeError("Execute analysis.solve() antes de plotar resultados")

    plotters = {
        "reactions": analysis.system.show_reaction_force,
        "axial": analysis.system.show_axial_force,
        "shear": analysis.system.show_shear_force,
        "moment": analysis.system.show_bending_moment,
        "displacement": analysis.system.show_displacement,
    }
    try:
        plotter = plotters[result]
    except KeyError as exc:
        choices = ", ".join(plotters)
        raise ValueError(
            f"Resultado desconhecido: {result!r}. Use um de: {choices}"
        ) from exc

    return plotter(show=show, **plot_kwargs)
