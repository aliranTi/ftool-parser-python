import styles from "./page.module.css";
import { FtlUpload } from "@/components/ftl-upload";

const steps = [
  { title: "Importar a estrutura", text: "Abrir um arquivo .ftl do FTool e conferir nós, barras, apoios e cargas." },
  { title: "Analisar os esforços", text: "Consultar os esforços axiais de tração e compressão em cada barra." },
  { title: "Dimensionar os palitos", text: "Verificar as camadas necessárias considerando a geometria e o material." },
];

export default function Home() {
  return (
    <main className={styles.main}>
      <header className={styles.header}>
        <span className={styles.brand}>FTool · Pontes</span>
        <span className={styles.badge}>Em desenvolvimento</span>
      </header>
      <section className={styles.hero} aria-labelledby="title">
        <p className={styles.eyebrow}>Análise de estruturas</p>
        <h1 id="title">Da estrutura ao dimensionamento.</h1>
        <p className={styles.intro}>Um espaço para analisar sua ponte e entender a quantidade de palitos necessária em cada barra.</p>
      </section>
      <FtlUpload />
      <section aria-labelledby="workflow-title">
        <h2 id="workflow-title" className={styles.sectionTitle}>O caminho da análise</h2>
        <ol className={styles.steps}>
          {steps.map((step, index) => (
            <li key={step.title} className={styles.card}>
              <span className={styles.number}>0{index + 1}</span>
              <h3>{step.title}</h3>
              <p>{step.text}</p>
            </li>
          ))}
        </ol>
      </section>
      <footer className={styles.footer}>
        <p>Desenvolvido para Trabalho de Conclusão de Curso.</p>
        <p>Autor: Antonio Joaquim de Lira Neto.</p>
        <p>Orientador: Dr. Matheus Fernandes de Araujo Silva.</p>
        <p>Projeto independente, sem vínculo com o FTool / PUC-Rio.</p>
      </footer>
    </main>
  );
}
