/* global importScripts, loadPyodide */
// Scientific packages are loaded only after explicit confirmation.
self.onmessage = async ({ data }) => {
  try {
    if (!["parse", "render_report"].includes(data.operation)) throw new Error("Operação inválida.");
    const indexURL = "https://cdn.jsdelivr.net/pyodide/v0.28.0/full/";
    importScripts(`${indexURL}pyodide.js`);
    const pyodide = await loadPyodide({ indexURL });
    if (data.operation === "render_report") {
      await pyodide.loadPackage(["numpy", "scipy", "matplotlib"]);
      pyodide.runPython("import matplotlib\nmatplotlib.use('Agg')");
      const archive = await fetch("https://files.pythonhosted.org/packages/3a/a5/c8056f62118c8779fee38d0efc47a25dacae681b9fb2c27db62639308a92/anastruct-1.7.0.tar.gz");
      if (!archive.ok) throw new Error("Download do anaStruct indisponível.");
      const bytes = await archive.arrayBuffer();
      const digest = Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)), (b) => b.toString(16).padStart(2, "0")).join("");
      if (digest !== "34fcba6e3fbc6ba290b9e79c22dd5253f89a3f19530da285d33cbcf06e1b8f86") throw new Error("Pacote anaStruct inválido.");
      // Use the upstream pure-Python fallback instead of native Cython binaries.
      pyodide.unpackArchive(bytes, "gztar", { extractDir: "/vendor" });
      pyodide.runPython("import sys\nsys.path.insert(0, '/vendor/anastruct-1.7.0')");
    }
    const response = await fetch(new URL("./python/parser.json", self.location.href));
    if (!response.ok) throw new Error("Não foi possível carregar o parser.");
    const files = await response.json();
    pyodide.FS.mkdirTree("/app/src");
    for (const [name, content] of Object.entries(files)) {
      pyodide.FS.writeFile(`/app/src/${name}`, content);
    }
    pyodide.runPython("import sys\nsys.path.insert(0, '/app')\nfrom src.pyodide_api import handle_request_json");
    pyodide.globals.set("request_json", JSON.stringify({ operation: data.operation, ftl_text: data.text }));
    const result = JSON.parse(pyodide.runPython("handle_request_json(request_json)"));
    self.postMessage(result);
  } catch {
    self.postMessage({ ok: false, error: { message: "Não foi possível carregar os recursos necessários. Confira a conexão e tente novamente." } });
  }
};
