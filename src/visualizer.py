import math
from typing import Any, Literal

from matplotlib.lines import Line2D

from .converter_anastruct import AnastructModel, to_anastruct
from .models import FtoolModel
from .stick_sizing import StickSizingReport


ResultPlot = Literal[
    "reactions",
    "axial",
    "shear",
    "moment",
    "displacement",
]
StickLabelDetail = Literal["compact", "detailed"]
LengthUnit = Literal["m", "cm", "mm"]


_STICK_MODE_STYLES = {
    "compression": ("#A64B00", "compressão"),
    "tension": ("#2563D9", "tração"),
    "minimum": ("#5F6B7A", "mínimo construtivo"),
    None: ("#777777", "sem compressão"),
}


def plot_ftool_model(
    model: FtoolModel,
    *,
    verbosity: int = 0,
    show_node_ids: bool = True,
    show_member_ids: bool = True,
    show_supports: bool = True,
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
        supports=show_supports,
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


def plot_stick_sizing(
    model: FtoolModel,
    report: StickSizingReport,
    *,
    show: bool = True,
    show_node_ids: bool = False,
    show_supports: bool = False,
    show_non_compression: bool = False,
    show_load_values: bool = False,
    label_detail: StickLabelDetail = "compact",
    show_legend: bool = True,
    length_unit: LengthUnit = "cm",
    scale: float = 1.0,
    offset: tuple[float, float] = (0.0, 0.0),
    figsize: tuple[float, float] = (10.0, 6.0),
) -> Any:
    """Mostra, por cor e espessura, a quantidade de palitos de cada membro.

    No modo ``compact`` cada rótulo mostra membro, palitos e camadas. O modo
    ``detailed`` acrescenta o esforço governante e os palitos por camada. Os
    eixos partem de ``(0, 0)`` no limite inferior esquerdo da estrutura.
    """

    if label_detail not in ("compact", "detailed"):
        raise ValueError("label_detail deve ser 'compact' ou 'detailed'")
    if length_unit not in ("m", "cm", "mm"):
        raise ValueError("length_unit deve ser 'm', 'cm' ou 'mm'")

    analysis, figure = plot_ftool_model(
        model,
        show=False,
        verbosity=0 if show_load_values else 1,
        show_node_ids=show_node_ids,
        show_member_ids=False,
        show_supports=show_supports,
        scale=scale,
        offset=offset,
        figsize=figsize,
    )
    axis = figure.axes[0]
    results = {item.ftool_id: item for item in report.members}
    x_values = [node.x for node in model.nodes]
    y_values = [node.y for node in model.nodes]
    span = max(max(x_values) - min(x_values), max(y_values) - min(y_values))
    label_offset = max(
        span * (0.022 if label_detail == "compact" else 0.055),
        1e-6,
    )
    center_x = (min(x_values) + max(x_values)) / 2
    center_y = (min(y_values) + max(y_values)) / 2
    visible_counts = [
        item.total_sticks
        for item in report.members
        if item.total_sticks is not None
    ]
    minimum_count = min(visible_counts, default=0)
    maximum_count = max(visible_counts, default=0)
    visible_modes = set()

    for member_index, member in enumerate(model.members):
        try:
            sizing = results[member.id]
        except KeyError as exc:
            raise ValueError(
                f"Barra FTool {member.id} não encontrada no relatório"
            ) from exc

        if sizing.required_layers is None and not show_non_compression:
            continue

        color, mode_label = _STICK_MODE_STYLES.get(
            sizing.governing_mode,
            ("#5F6B7A", "axial"),
        )
        visible_modes.add(sizing.governing_mode)
        if sizing.required_layers is None:
            label = (
                f"{sizing.id} · —"
                if label_detail == "compact"
                else f"{sizing.id}\nsem compressão"
            )
        else:
            if label_detail == "compact":
                label = (
                    f"{sizing.id} · {sizing.total_sticks}p · "
                    f"{sizing.required_layers}c"
                )
            else:
                stick_suffix = "palito" if sizing.total_sticks == 1 else "palitos"
                label = (
                    f"{sizing.id} · {mode_label}\n"
                    f"{sizing.required_layers} × {sizing.sticks_per_layer} = "
                    f"{sizing.total_sticks} {stick_suffix}"
                )

        dx = member.x2 - member.x1
        dy = member.y2 - member.y1
        middle_x = (member.x1 + member.x2) / 2
        middle_y = (member.y1 + member.y2) / 2
        normal_x = -dy / member.length
        normal_y = dx / member.length
        outward = (
            normal_x * (middle_x - center_x)
            + normal_y * (middle_y - center_y)
        )
        if abs(outward) <= span * 1e-6:
            direction = 1 if member_index % 2 == 0 else -1
        else:
            direction = 1 if outward > 0 else -1

        # Em treliças, diagonais curtas que chegam ao nó mais alto costumam
        # disputar espaço com as barras externas. Coloca seus rótulos no lado
        # interno para manter as duas quantidades legíveis.
        is_short_upper_member = (
            max(member.y1, member.y2) >= max(y_values) - span * 1e-6
            and min(member.y1, member.y2) >= center_y - span * 1e-6
            and member.length < span * 0.25
        )
        if is_short_upper_member:
            direction *= -1

        label_x = middle_x + direction * normal_x * label_offset
        label_y = middle_y + direction * normal_y * label_offset
        if is_short_upper_member:
            label_x += (-1 if middle_x < center_x else 1) * label_offset

        axis.plot(
            [member.x1, member.x2],
            [member.y1, member.y2],
            color=color,
            linewidth=_stick_line_width(
                sizing.total_sticks,
                minimum_count,
                maximum_count,
            ),
            alpha=0.78,
            solid_capstyle="round",
            zorder=7,
        )
        axis.text(
            label_x,
            label_y,
            label,
            color=color,
            fontsize=8,
            fontweight="bold",
            horizontalalignment="center",
            verticalalignment="center",
            zorder=13,
            bbox={
                "facecolor": "white",
                "edgecolor": color,
                "linewidth": 0.9,
                "alpha": 0.92,
                "pad": 1.3 if label_detail == "compact" else 1.6,
                "boxstyle": "round,pad=0.18",
            },
        )

    axis.set_title(
        "Quantidade de palitos por barra",
        loc="left",
        fontsize=14,
        fontweight="bold",
        pad=18,
    )
    axis.set_title(
        f"Total: {report.total_physical_sticks} palitos · "
        f"{report.total_required_layers} camadas",
        loc="right",
        fontsize=10,
        color="#30343B",
        pad=18,
    )
    axis.text(
        0.0,
        1.01,
        "Rótulo: membro (m) · palitos (p) / camadas (c)  |  "
        "Espessura da linha: quantidade relativa",
        transform=axis.transAxes,
        color="#5F6368",
        fontsize=8,
        horizontalalignment="left",
        verticalalignment="bottom",
    )
    _normalize_structure_axes(axis, x_values, y_values, length_unit)

    if show_legend and visible_modes:
        legend_handles = [
            Line2D(
                [0],
                [0],
                color=_STICK_MODE_STYLES[mode][0],
                linewidth=4,
                solid_capstyle="round",
                label=_STICK_MODE_STYLES[mode][1].capitalize(),
            )
            for mode in ("compression", "tension", "minimum", None)
            if mode in visible_modes
        ]
        axis.legend(
            handles=legend_handles,
            loc="upper center",
            bbox_to_anchor=(0.5, -0.13),
            ncol=len(legend_handles),
            frameon=False,
            fontsize=9,
            title="Esforço governante",
            title_fontsize=9,
        )
        figure.subplots_adjust(bottom=0.20, top=0.88)

    if show:
        analysis.system.plotter.plot()
    return figure


def _stick_line_width(
    count: int | None,
    minimum_count: int,
    maximum_count: int,
) -> float:
    """Converte a quantidade para uma espessura legível sem exagerar extremos."""

    if count is None or maximum_count <= minimum_count:
        return 3.0
    normalized = (
        math.sqrt(count) - math.sqrt(minimum_count)
    ) / (math.sqrt(maximum_count) - math.sqrt(minimum_count))
    return 2.4 + 3.6 * normalized


def _normalize_structure_axes(
    axis: Any,
    x_values: list[float],
    y_values: list[float],
    unit: LengthUnit,
) -> None:
    """Usa origem local e mantém a mesma escala geométrica nos dois eixos."""

    unit_factor = {"m": 1.0, "cm": 100.0, "mm": 1_000.0}[unit]
    x_min, x_max = min(x_values), max(x_values)
    y_min, y_max = min(y_values), max(y_values)
    width = x_max - x_min
    height = y_max - y_min
    span = max(width, height)

    axis.set_aspect("equal", adjustable="box")
    axis.set_xlim(x_min - span * 0.04, x_max + span * 0.04)
    axis.set_ylim(y_min - span * 0.06, y_max + span * 0.08)

    x_ticks, x_labels = _normalized_ticks(x_min, x_max, unit_factor)
    y_ticks, y_labels = _normalized_ticks(y_min, y_max, unit_factor)
    axis.set_xticks(x_ticks, labels=x_labels)
    axis.set_yticks(y_ticks, labels=y_labels)
    axis.set_xlabel(f"Comprimento ({unit})", color="#4B5563")
    axis.set_ylabel(f"Altura ({unit})", color="#4B5563")
    axis.grid(
        True,
        color="#D9DEE5",
        linewidth=0.6,
        alpha=0.65,
        linestyle="--",
        zorder=0,
    )


def _normalized_ticks(
    minimum: float,
    maximum: float,
    unit_factor: float,
) -> tuple[list[float], list[str]]:
    extent = (maximum - minimum) * unit_factor
    step = _nice_tick_step(extent)
    tick_count = int(math.floor(extent / step + 1e-9))
    values = [index * step for index in range(tick_count + 1)]
    if not math.isclose(values[-1], extent, rel_tol=0.0, abs_tol=step * 1e-6):
        values.append(extent)
    positions = [minimum + value / unit_factor for value in values]
    labels = [f"{value:g}" for value in values]
    return positions, labels


def _nice_tick_step(extent: float, target_ticks: int = 7) -> float:
    if extent <= 0:
        return 1.0
    rough_step = extent / target_ticks
    magnitude = 10 ** math.floor(math.log10(rough_step))
    normalized = rough_step / magnitude
    if normalized <= 1:
        nice = 1
    elif normalized <= 1.5:
        nice = 1.5
    elif normalized <= 2:
        nice = 2
    elif normalized <= 5:
        nice = 5
    else:
        nice = 10
    return nice * magnitude


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
