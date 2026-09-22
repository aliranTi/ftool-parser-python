import type { BridgeModel } from "@/lib/bridge-preview";
import styles from "./ftl-upload.module.css";

export function BridgePreview({ model }: { model: BridgeModel }) {
  const xs = model.nodes.map((node) => node.x);
  const ys = model.nodes.map((node) => node.y);
  const minX = Math.min(...xs), maxX = Math.max(...xs);
  const minY = Math.min(...ys), maxY = Math.max(...ys);
  const width = maxX - minX, height = maxY - minY;
  const fit = Math.min(width > 0 ? 680 / width : Infinity, height > 0 ? 280 / height : Infinity);
  const scale = Number.isFinite(fit) ? fit : 1;
  const x = (value: number) => 400 + (value - (minX + maxX) / 2) * scale;
  const y = (value: number) => 180 - (value - (minY + maxY) / 2) * scale;
  const format = (value: number) => new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 3 }).format(value);

  return (
    <figure className={styles.preview}>
      <svg viewBox="0 0 800 360" role="img" aria-labelledby="bridge-title bridge-description">
        <title id="bridge-title">Prévia da geometria da ponte</title>
        <desc id="bridge-description">{model.nodes.length} nós e {model.members.length} barras. Largura {format(width)} metros e altura {format(height)} metros.</desc>
        {model.members.map((member) => (
          <line key={member.id} x1={x(member.x1)} y1={y(member.y1)} x2={x(member.x2)} y2={y(member.y2)} stroke="#356747" strokeWidth="3">
            <title>Barra {member.id}</title>
          </line>
        ))}
        {model.nodes.map((node) => (
          <g key={node.id}>
            <circle cx={x(node.x)} cy={y(node.y)} r="5" fill="#20382a"><title>Nó {node.id}: ({format(node.x)}, {format(node.y)}) m</title></circle>
            <text x={x(node.x) + 8} y={y(node.y) - 10} fontSize="13" fill="#20382a">{node.id}</text>
          </g>
        ))}
      </svg>
      <figcaption>{model.nodes.length} nós · {model.members.length} barras · Largura: {format(width)} m · Altura: {format(height)} m. Prévia geométrica, sem deformação ou resultados de cálculo.</figcaption>
    </figure>
  );
}
