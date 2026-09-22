"use client";

import { useEffect, useRef, useState } from "react";
import { analyzeBridge, parseBridge, type AxialAnalysis, type BridgeModel } from "@/lib/bridge-preview";
import { AxialResults } from "./axial-results";
import { ReportView } from "./report-view";
import { BridgePreview } from "./bridge-preview";
import { readFtlFile, type ImportedFtl } from "@/lib/ftl-file";
import styles from "./ftl-upload.module.css";

export function FtlUpload() {
  const [file, setFile] = useState<ImportedFtl | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const request = useRef(0);
  const active = useRef<AbortController | null>(null);
  const [model, setModel] = useState<BridgeModel | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [calculating, setCalculating] = useState(false);
  const [analysis, setAnalysis] = useState<AxialAnalysis | null>(null);
  const [reportOpen, setReportOpen] = useState(false);

  useEffect(() => () => { active.current?.abort(); }, []);

  async function selectFiles(files: File[]) {
    if (files.length === 0) return;
    const current = ++request.current;
    active.current?.abort();
    const controller = new AbortController();
    active.current = controller;
    setModel(null);
    setConfirmed(false);
    setCalculating(false);
    setAnalysis(null);
    setReportOpen(false);
    setFile(null);
    setError("");
    setLoading(false);
    if (files.length !== 1) {
      setError("Selecione apenas um arquivo por vez.");
      return;
    }
    setLoading(true);
    try {
      const imported = await readFtlFile(files[0]);
      if (current !== request.current || controller.signal.aborted) return;
      const preview = await parseBridge(imported.text, controller.signal);
      if (current === request.current && !controller.signal.aborted) {
        setFile(imported);
        setModel(preview);
      }
    } catch (cause) {
      if (current === request.current) {
        setError(cause instanceof Error ? cause.message : "Não foi possível ler o arquivo. Tente novamente.");
      }
    } finally {
      if (current === request.current) setLoading(false);
    }
  }

  function removeFile() {
    request.current++;
    active.current?.abort();
    setModel(null);
    setConfirmed(false);
    setCalculating(false);
    setAnalysis(null);
    setReportOpen(false);
    setFile(null);
    setError("");
    setLoading(false);
    if (input.current) input.current.value = "";
    input.current?.focus();
  }

  async function confirmBridge() {
    if (!file || calculating || analysis) return;
    const current = ++request.current;
    active.current?.abort();
    const controller = new AbortController();
    active.current = controller;
    setConfirmed(true);
    setCalculating(true);
    setError("");
    try {
      const result = await analyzeBridge(file.text, controller.signal);
      if (current === request.current && !controller.signal.aborted) setAnalysis(result);
    } catch (cause) {
      if (current === request.current && !controller.signal.aborted) {
        setError(cause instanceof Error ? cause.message : "Não foi possível calcular a estrutura.");
      }
    } finally {
      if (current === request.current) setCalculating(false);
    }
  }

  return (
    <section className={styles.section} aria-labelledby="upload-title">
      <h2 id="upload-title">Importar arquivo FTool</h2>
      <p className={styles.help} id="upload-help">Selecione ou arraste um arquivo .ftl, versão 4.00 ou 4.01, de até 10 MB. O arquivo fica somente neste navegador.</p>
      <div
        className={styles.dropzone}
        onDragOver={(event) => event.preventDefault()}
        onDrop={(event) => {
          event.preventDefault();
          void selectFiles(Array.from(event.dataTransfer.files));
        }}
      >
        <label htmlFor="ftl-file" className={styles.label}>Arquivo da estrutura</label>
        <input
          ref={input}
          id="ftl-file"
          type="file"
          accept=".ftl"
          aria-describedby={`upload-help${error ? " upload-error" : ""}`}
          aria-invalid={!!error}
          onChange={(event) => {
            void selectFiles(Array.from(event.currentTarget.files ?? []));
            event.currentTarget.value = "";
          }}
        />
        <p className={styles.help}>Você também pode soltar o arquivo nesta área.</p>
      </div>
      <div role="status" aria-live="polite" aria-busy={loading}>
        {loading && <p className={styles.help}>Preparando a prévia da ponte… Na primeira leitura, isso pode levar alguns instantes.</p>}
        {file && (
          <div className={styles.result}>
            <p className={styles.filename}><strong>{file.name}</strong></p>
            <p>{new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 }).format(file.size / 1024)} KB · FTool {file.version === "400" ? "4.00" : "4.01"}</p>
            <p>{confirmed ? "Ponte confirmada." : "Confira se a geometria abaixo corresponde à ponte que você deseja analisar."}</p>
            {calculating && <p>Calculando a estrutura… O primeiro cálculo pode levar alguns instantes para carregar os recursos necessários.</p>}
            {model && <BridgePreview model={model} />}
            <div className={styles.actions}>
              <button type="button" disabled={calculating || !!analysis} onClick={() => void confirmBridge()}>{calculating ? "Calculando…" : analysis ? "Análise concluída" : confirmed ? "Tentar cálculo novamente" : "Confirmar esta ponte"}</button>
              <button type="button" onClick={() => input.current?.click()}>Escolher outro arquivo</button>
            <button type="button" onClick={removeFile}>Remover arquivo</button>
            </div>
            {analysis && !reportOpen && <AxialResults analysis={analysis} />}
            {analysis && !reportOpen && <button type="button" onClick={() => setReportOpen(true)}>Abrir relatório completo</button>}
            {analysis && reportOpen && <ReportView analysis={analysis} fileName={file.name} onBack={() => setReportOpen(false)} />}
          </div>
        )}
      </div>
      {error && <p id="upload-error" role="alert" className={styles.error}>{error}</p>}
    </section>
  );
}
