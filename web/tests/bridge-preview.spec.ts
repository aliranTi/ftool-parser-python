import { test, expect } from "@playwright/test";
import path from "node:path";
import { readFileSync } from "node:fs";

test("preview real FTL, confirm, replace and reject an invalid structure", async ({ page }) => {
  test.setTimeout(240_000);
  const scientific: string[] = [];
  page.on("request", (request) => { if (/numpy|scipy|anastruct-1/.test(request.url())) scientific.push(request.url()); });
  await page.goto("/");
  const picker = page.getByLabel("Arquivo da estrutura", { exact: true });
  await picker.setInputFiles(path.resolve("../inputs/ponte_3.ftl"));
  await expect(page.getByRole("img", { name: "Prévia da geometria da ponte" })).toBeVisible({ timeout: 90_000 });
  await expect(page.locator("svg line")).toHaveCount(19);
  await expect(page.locator("svg circle")).toHaveCount(10);
  expect(scientific).toHaveLength(0);
  await page.getByRole("button", { name: "Confirmar esta ponte", exact: true }).click();
  await expect(page.getByRole("button", { name: "Análise concluída", exact: true })).toBeDisabled({ timeout: 180_000 });
  await expect(page.getByRole("heading", { name: "Dados avaliados", exact: true })).toBeVisible();
  await expect(page.getByText("115 mm", { exact: true })).toBeVisible();
  await expect(page.getByText(/palito.*7,84 × 1,85 mm/)).toBeVisible();
  await page.getByText("Ver valores num\u00e9ricos e rea\u00e7\u00f5es", { exact: true }).click();
  await expect(page.getByRole("table", { name: "Esforços axiais por barra" }).locator("tbody tr")).toHaveCount(19);
  await expect(page.getByRole("row").filter({ has: page.getByRole("rowheader", { name: "m17", exact: true }) })).toContainText("-1.553,384");
  expect(scientific.length).toBeGreaterThan(0);
  await expect(page.locator("figure h4")).toHaveText(["Diagrama axial", "Deformação", "Quantidade de palitos"]);
  for (const title of ["Diagrama axial", "Deformação", "Quantidade de palitos"]) {
    const image = page.getByRole("img", { name: title, exact: true });
    await expect(image).toBeVisible();
    expect(await image.evaluate((element: HTMLImageElement) => element.complete && element.naturalWidth > 0)).toBe(true);
  }
  await expect(page.getByText(/Total: 408 palitos físicos/)).toBeVisible();
  const reactions = page.getByRole("table", { name: "Reações de apoio" });
  await expect(reactions.locator("tbody tr")).toHaveCount(2);
  for (const node of ["n7", "n8"]) {
    await expect(reactions.getByRole("row").filter({ has: page.getByRole("rowheader", { name: node, exact: true }) }).locator("td").nth(1)).toHaveText("1.000");
  }
  await page.getByRole("button", { name: "Abrir relatório completo", exact: true }).click();
  const report = page.getByRole("region", { name: "Relatório de análise estrutural" });
  await expect(report).toBeVisible();
  await expect(report.getByRole("heading", { name: "Dados avaliados", exact: true })).toBeVisible();
  await expect(page.locator("figure h3")).toHaveCount(3);
  await expect(page.locator("figure h4")).toHaveCount(0);
  await expect(report.locator("table").first().locator("tbody tr")).toHaveCount(19);
  await expect(report).toContainText("m17");
  await expect(report).toContainText("408");
  await expect(report.getByRole("columnheader", { name: "Comprimento (cm)", exact: true })).toBeVisible();
  await expect(report.getByRole("columnheader", { name: "Esforço médio (N)", exact: true })).toBeVisible();
  await expect(report.getByRole("button", { name: "Imprimir relatório", exact: true })).toBeVisible();
  await page.emulateMedia({ media: "print" });
  await expect(page.locator("main > header")).toHaveCSS("visibility", "hidden");
  await expect(report).toHaveCSS("visibility", "visible");
  await expect(report.locator("[data-print-hidden]")).toHaveCSS("display", "none");
  await page.emulateMedia({ media: "screen" });
  await report.getByRole("button", { name: "Voltar aos resultados", exact: true }).click();
  await expect(page.getByRole("button", { name: "Abrir relatório completo", exact: true })).toBeVisible();
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: "Escolher outro arquivo" }).click();
  await (await chooser).setFiles({ name: "invalido.ftl", mimeType: "text/plain", buffer: Buffer.from("400 0\ninvalid") });
  await expect(page.getByRole("img", { name: "Prévia da geometria da ponte" })).toHaveCount(0);
  await expect(page.locator("#upload-error")).toBeVisible({ timeout: 90_000 });
  await expect(page.getByRole("button", { name: "Ponte confirmada", exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Confirmar esta ponte", exact: true })).toHaveCount(0);
  await expect(page.getByRole("table")).toHaveCount(0);
});

test("analysis error preserves preview and can be retried", async ({ page }) => {
  test.setTimeout(240_000);
  const workerSource = readFileSync("public/ftl-parser.worker.js", "utf8");
  await page.route("**/ftl-parser.worker.js", (route) => route.fulfill({
    contentType: "application/javascript",
    body: `${workerSource}\nconst original = self.onmessage; self.onmessage = (event) => {
      if (event.data.operation === 'render_report') self.postMessage({ok:false,error:{message:'Falha simulada de análise'}});
      else original(event);
    };`,
  }));
  await page.goto("/");
  await page.getByLabel("Arquivo da estrutura", { exact: true }).setInputFiles(path.resolve("../inputs/ponte_3.ftl"));
  await page.getByRole("button", { name: "Confirmar esta ponte", exact: true }).click({ timeout: 90_000 });
  await expect(page.locator("#upload-error")).toBeVisible({ timeout: 180_000 });
  await expect(page.getByRole("img", { name: "Prévia da geometria da ponte" })).toBeVisible();
  await expect(page.getByRole("table")).toHaveCount(0);
  await page.unroute("**/ftl-parser.worker.js");
  await page.getByRole("button", { name: "Tentar cálculo novamente" }).click();
  await expect(page.getByRole("button", { name: "Análise concluída" })).toBeDisabled({ timeout: 180_000 });
  await expect(page.locator("#upload-error")).toHaveCount(0);
  await page.getByRole("button", { name: "Remover arquivo" }).click();
  await expect(page.getByRole("table")).toHaveCount(0);
});

test("failed runtime download shows an error without allowing confirmation", async ({ page }) => {
  await page.route("https://cdn.jsdelivr.net/**", (route) => route.abort());
  await page.goto("/");
  await page.getByLabel("Arquivo da estrutura", { exact: true }).setInputFiles(path.resolve("../inputs/ponte_3.ftl"));
  await expect(page.locator("#upload-error")).toBeVisible({ timeout: 90_000 });
  await expect(page.getByRole("button", { name: "Confirmar esta ponte", exact: true })).toHaveCount(0);
});
