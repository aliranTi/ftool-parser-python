"use client";

import type { AxialAnalysis } from "@/lib/bridge-preview";
import styles from "./report-view.module.css";
import { SizingContext } from "./sizing-context";

const states = { tension: "Tração", compression: "Compressão", zero: "Nulo", mixed: "Misto" } as const;
const modes = { tension: "Tração", compression: "Compressão", minimum: "Mínimo" } as const;
const number = (value: number) => new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 3 }).format(value);

function stateLabel(
  state: keyof typeof states,
  mode: keyof typeof modes | null | undefined,
) {
  if (!mode || mode === state) return states[state];
  return `${states[state]} · ${modes[mode]}`;
}

export function ReportView({ analysis, fileName, onBack }: { analysis: AxialAnalysis; fileName: string; onBack: () => void }) {
  const stickById = new Map(analysis.stick_counts.members.map((member) => [member.id, member]));

  return (
    <section className={styles.report} aria-labelledby="report-title">
      <div className={styles.toolbar} data-print-hidden>
        <button type="button" onClick={onBack}>Voltar aos resultados</button>
        <button type="button" onClick={() => window.print()}>Imprimir relatório</button>
      </div>
      <header className={styles.heading}>
        <p className={styles.kicker}>Relatório de análise estrutural</p>
        <h2 id="report-title">Relatório de análise estrutural · {fileName}</h2>
        <p>Resultados gerados pelo parser FTool, anaStruct e dimensionamento de palitos.</p>
      </header>
      <SizingContext analysis={analysis} />
      <div className={styles.charts}>
        {analysis.charts.map((chart) => (
          <figure key={chart.id} className={styles.chart}>
            <h3>{chart.title}</h3>
            {/* SVG gerado pelas mesmas funções usadas no notebook. */}
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={chart.image} alt={chart.title} />
            <figcaption>
              {chart.id === "axial" && "Forças em N e coordenadas em cm."}
              {chart.id === "displacement" && "Estrutura original e deformada, com escala visual informada no gráfico."}
              {chart.id === "sticks" && `${analysis.stick_counts.total_physical_sticks} palitos físicos · ${analysis.stick_counts.total_required_layers} camadas.`}
            </figcaption>
          </figure>
        ))}
      </div>
      <div className={styles.summary}>
        <div><span>Palitos físicos</span><strong>{analysis.stick_counts.total_physical_sticks}</strong></div>
        <div><span>Camadas somadas</span><strong>{analysis.stick_counts.total_required_layers}</strong></div>
        <div><span>Membros analisados</span><strong>{analysis.members.length}</strong></div>
      </div>
      <div className={styles.tableWrap}>
        <table>
          <caption>Dimensionamento e esforços por membro</caption>
          <thead><tr><th>Membro</th><th>Comprimento (cm)</th><th>Palitos</th><th>Camadas</th><th>Esforço médio (N)</th><th>Estado</th></tr></thead>
          <tbody>{analysis.members.map((member) => {
            const sticks = stickById.get(member.id);
            return <tr key={member.id}>
              <th scope="row">{member.id}</th>
              <td>{number(member.length * 100)}</td>
              <td>{sticks?.total_sticks ?? "—"}</td>
              <td>{sticks?.required_layers ?? "—"}</td>
              <td>{number(member.axial_force.average)}</td>
              <td>{stateLabel(member.axial_force.state, sticks?.governing_mode)}</td>
            </tr>;
          })}</tbody>
        </table>
      </div>
      <div className={styles.reactions}>
        <h3>Reações de apoio</h3>
        <table><thead><tr><th>Nó</th><th>Fx (N)</th><th>Fy (N)</th><th>Momento (N·m)</th></tr></thead>
          <tbody>{analysis.reactions.map((reaction) => <tr key={reaction.node}><th scope="row">{reaction.node}</th><td>{number(reaction.fx)}</td><td>{number(reaction.fy)}</td><td>{number(reaction.moment)}</td></tr>)}</tbody>
        </table>
      </div>
      <footer className={styles.academicFooter}>
        <p>Desenvolvido para Trabalho de Conclusão de Curso.</p>
        <p>Autor: Antonio Joaquim de Lira Neto</p>
        <p>Orientador: Dr. Matheus Fernandes de Araujo Silva.</p>
      </footer>
    </section>
  );
}
