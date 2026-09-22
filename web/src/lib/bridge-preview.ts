export type BridgeModel = {
  nodes: { id: number; x: number; y: number }[];
  members: { id: number; x1: number; y1: number; x2: number; y2: number }[];
};

export type AxialAnalysis = {
  charts: { id: string; title: string; image: string }[];
  stick_counts: { total_required_layers: number; total_physical_sticks: number };
  members: { id: string; ftool_id: number; length: number; axial_force: { minimum: number; maximum: number; state: "tension" | "compression" | "zero" | "mixed" } }[];
  reactions: { node: string; fx: number; fy: number; moment: number }[];
};

export function parseBridge(text: string, signal: AbortSignal): Promise<BridgeModel> {
  return runBridge(text, signal, "parse") as Promise<BridgeModel>;
}

export function analyzeBridge(text: string, signal: AbortSignal): Promise<AxialAnalysis> {
  return runBridge(text, signal, "render_report") as Promise<AxialAnalysis>;
}

function runBridge(text: string, signal: AbortSignal, operation: "parse" | "render_report"): Promise<BridgeModel | AxialAnalysis> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) { reject(new Error("Leitura cancelada.")); return; }
    const worker = new Worker("/ftl-parser.worker.js");
    const finish = () => {
      clearTimeout(timeout);
      worker.terminate();
      signal.removeEventListener("abort", abort);
    };
    const abort = () => { finish(); reject(new Error("Leitura cancelada.")); };
    const timeout = setTimeout(() => {
      finish();
      reject(new Error("A operação demorou demais. Verifique sua conexão e tente novamente."));
    }, operation === "parse" ? 90_000 : 180_000);
    signal.addEventListener("abort", abort, { once: true });
    worker.onerror = () => {
      finish();
      reject(new Error("Não foi possível carregar a prévia. Tente novamente."));
    };
    worker.onmessage = ({ data }) => {
      finish();
      if (!data.ok) { reject(new Error(data.error?.message ?? "Arquivo FTL inválido.")); return; }
      if (operation === "render_report") {
        resolve({ ...data.result.analysis, charts: data.result.charts, stick_counts: data.result.stick_counts } as AxialAnalysis);
        return;
      }
      const model = data.result.model as BridgeModel;
      if (!model.nodes.length || !model.members.length) {
        reject(new Error("O arquivo não contém uma estrutura com nós e barras."));
        return;
      }
      if (model.nodes.some((n) => !Number.isFinite(n.x) || !Number.isFinite(n.y)) ||
          model.members.some((m) => ![m.x1, m.y1, m.x2, m.y2].every(Number.isFinite))) {
        reject(new Error("A estrutura contém coordenadas inválidas."));
        return;
      }
      resolve(model);
    };
    worker.postMessage({ text, operation });
  });
}
