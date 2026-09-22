"""Relatório gráfico web usando as mesmas funções do notebook."""

import base64
from io import BytesIO


def render_report(ftl_text: str, *, name: str | None = None) -> dict:
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import pyplot as plt

    from .pyodide_api import parse_ftl_text
    from .converter_anastruct import to_anastruct
    from .exporter import axial_analysis_to_dict
    from .stick_sizing import size_axial_members
    from .visualizer import plot_axial_forces, plot_displacements, plot_stick_sizing

    model = parse_ftl_text(ftl_text)
    analysis = to_anastruct(model, solve=True)
    sizing = size_axial_members(model, analysis)
    plots = [
        ("axial", "Diagrama axial", lambda: plot_axial_forces(
            model, analysis, show=False, force_unit="N", length_unit="cm", decimals=3,
        )),
        ("displacement", "Deformação", lambda: plot_displacements(
            analysis, show=False,
        )),
        ("sticks", "Quantidade de palitos", lambda: plot_stick_sizing(
            model, sizing, show=False, scale=0.6,
        )),
    ]
    charts = []
    initial_figures = set(plt.get_fignums())
    try:
        for chart_id, title, draw in plots:
            figure = draw()
            output = BytesIO()
            figure.savefig(output, format="svg", bbox_inches="tight")
            charts.append({
                "id": chart_id,
                "title": title,
                "image": "data:image/svg+xml;base64," + base64.b64encode(output.getvalue()).decode("ascii"),
            })
            plt.close(figure)
    finally:
        for figure_number in set(plt.get_fignums()) - initial_figures:
            plt.close(figure_number)
    return {
        "analysis": axial_analysis_to_dict(model, analysis, name=name),
        "stick_counts": sizing.counts_to_dict(),
        "charts": charts,
    }
