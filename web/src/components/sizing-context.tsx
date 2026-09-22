import type { AxialAnalysis } from "@/lib/bridge-preview";
import styles from "./sizing-context.module.css";

const number = (value: number) => new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 3 }).format(value);

export function SizingContext({ analysis }: { analysis: AxialAnalysis }) {
  const sections = Array.from(new Map(
    analysis.stick_counts.members
      .filter((member) => member.section_width_mm !== null && member.section_thickness_mm !== null)
      .map((member) => [
        `${member.geometry_section_name}|${member.section_width_mm}|${member.section_thickness_mm}`,
        {
          name: member.geometry_section_name ?? "Seção sem nome",
          width: member.section_width_mm as number,
          thickness: member.section_thickness_mm as number,
        },
      ]),
  ).values());

  return (
    <section className={styles.context} aria-labelledby="sizing-context-title">
      <h4 id="sizing-context-title">Dados avaliados</h4>
      <dl className={styles.grid}>
        <div><dt>Comprimento comercial do palito</dt><dd>{number(analysis.stick_counts.commercial_stick_length_mm)} mm</dd></div>
        <div><dt>Sobreposição nas emendas</dt><dd>{number(analysis.stick_counts.splice_overlap_mm)} mm</dd></div>
        <div><dt>Seções utilizadas</dt><dd>{sections.length}</dd></div>
      </dl>
      <ul className={styles.sections}>
        {sections.map((section) => (
          <li key={`${section.name}-${section.width}-${section.thickness}`}>
            <strong>{section.name}</strong>: {number(section.width)} × {number(section.thickness)} mm
            <span> (largura × espessura)</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
