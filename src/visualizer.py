# src/visualizer.py
import matplotlib.pyplot as plt
from .models import FtoolModel


def plot_ftool_model(
    model: FtoolModel,
    show_node_ids: bool = True,
    show_member_ids: bool = False,
    scale_arrows: float = 0.25,
    show_dimensions: bool = False,
    show: bool = True,
):
    """
    Desenha a geometria da estrutura (barras, nós, apoios) e vetores de força
    para conferência visual dos dados importados do Ftool.
    """
    fig, ax = plt.subplots(figsize=(10, 6))

    if show_dimensions:
        for dimension in model.dimensions:
            if dimension.display_x1 is None or dimension.display_x2 is None:
                continue
            ax.plot(
                [dimension.display_x1, dimension.display_x2],
                [dimension.display_y1, dimension.display_y2],
                color='gray', linestyle='--', linewidth=0.8, alpha=0.6,
                zorder=0,
            )

    # 1. Desenha as Barras
    for member in model.members:
        ax.plot([member.x1, member.x2], [member.y1, member.y2], 'b-', linewidth=2, zorder=1)
        if show_member_ids:
            mid_x = (member.x1 + member.x2) / 2
            mid_y = (member.y1 + member.y2) / 2
            ax.text(mid_x, mid_y, f"B{member.id}", color='darkblue', fontsize=8, ha='center', va='bottom')

    # 2. Desenha os Nós e Identifica Apoios
    for node in model.nodes:
        if not node.support.is_free:
            if node.support.has_spring:
                ax.plot(node.x, node.y, 'D', color='purple', markersize=8, zorder=3)
            elif node.support.is_fixed:
                ax.plot(node.x, node.y, 's', color='black', markersize=8, label='Engaste', zorder=3)
            elif node.support.is_pinned:
                ax.plot(node.x, node.y, '^', color='green', markersize=9, label='Apoio Fixo', zorder=3)
            else:
                ax.plot(node.x, node.y, 'o', color='orange', markersize=8, label='Apoio Móvel', zorder=3)
        else:
            ax.plot(node.x, node.y, 'o', color='red', markersize=4, zorder=2)

        if show_node_ids:
            ax.text(node.x, node.y + 0.02, f"N{node.id}", fontsize=8, color='gray', ha='center', va='bottom')

        # 3. Desenha os Vetores de Carga Pontual
        if node.load:
            load = node.load

            # Vetor em Y (Fy)
            if load.fy != 0:
                dy = -scale_arrows if load.fy < 0 else scale_arrows
                ax.annotate(
                    f"{load.name}\n({load.fy:g} N)",
                    xy=(node.x, node.y),
                    xytext=(node.x, node.y - dy),
                    arrowprops=dict(facecolor='red', edgecolor='darkred', width=2, headwidth=7, shrink=0.05),
                    ha='center', va='center', color='darkred', fontweight='bold', fontsize=8
                )

            # Vetor em X (Fx)
            if load.fx != 0:
                dx = scale_arrows if load.fx > 0 else -scale_arrows
                ax.annotate(
                    f"{load.name}\n({load.fx:g} N)",
                    xy=(node.x, node.y),
                    xytext=(node.x - dx, node.y),
                    arrowprops=dict(facecolor='red', edgecolor='darkred', width=2, headwidth=7, shrink=0.05),
                    ha='center', va='center', color='darkred', fontweight='bold', fontsize=8
                )

    # Ajustes de exibição para manter proporção real (1:1 no espaço)
    ax.set_aspect('equal', adjustable='datalim')
    ax.set_title("Validação Visual da Geometria e Cargas (Ftool)", fontsize=12, fontweight='bold')
    ax.set_xlabel("X (m)")
    ax.set_ylabel("Y (m)")
    ax.grid(True, linestyle='--', alpha=0.5)

    plt.tight_layout()
    if show:
        plt.show()

    return fig, ax
