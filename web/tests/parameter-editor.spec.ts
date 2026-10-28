import { test, expect } from "@playwright/test";

test("edit, validate, calculate and restore parameters without external downloads", async ({ page }) => {
  await page.route("**/ftl-parser.worker.js", (route) => route.fulfill({
    contentType: "application/javascript",
    body: `self.onmessage = ({data}) => {
      const field = {key:'minimum_member_layers',label:'Mínimo construtivo de camadas',value:3,unit:'',group:'Dimensionamento',minimum:1,exclusive:false,integer:true};
      if(data.operation === 'parse') {
        self.postMessage({ok:true,result:{model:{nodes:[{id:1,x:0,y:0},{id:2,x:1,y:0}],members:[{id:1,x1:0,y1:0,x2:1,y2:0}]},parameters:[field]}});
      } else {
        const layers = data.parameters.minimum_member_layers ?? 3;
        self.postMessage({ok:true,result:{analysis:{members:[],reactions:[]},charts:[],parameters:[{...field,value:layers,edited:layers!==3}],stick_counts:{members:[],total_physical_sticks:layers*3,estimated_sticks_two_identical_faces:layers*6,total_required_layers:layers,commercial_stick_length_mm:115,splice_overlap_mm:0}}});
      }
    };`,
  }));
  await page.goto("/");
  const upload = async () => page.getByLabel("Arquivo da estrutura", { exact: true }).setInputFiles({
    name: "parameters.ftl", mimeType: "text/plain", buffer: Buffer.from("400 0\n"),
  });
  await upload();
  const field = page.getByLabel("Mínimo construtivo de camadas", { exact: true });
  const confirm = page.getByRole("button", { name: "Confirmar esta ponte", exact: true });
  await expect(field).toHaveValue("3");
  await field.fill("");
  await confirm.click();
  await expect(page.getByRole("heading", { name: "Dados avaliados", exact: true })).toHaveCount(0);
  await field.fill("4");
  await confirm.click();
  await expect(page.getByText("12 palitos", { exact: true })).toBeVisible();
  await expect(page.getByText("24 palitos", { exact: true })).toBeVisible();
  await expect(page.getByText("4 (editado)", { exact: true })).toBeVisible();
  await field.fill("5");
  await expect(page.getByRole("heading", { name: "Dados avaliados", exact: true })).toHaveCount(0);
  await confirm.click();
  await expect(page.getByText("15 palitos", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Restaurar parâmetros originais" }).click();
  await expect(field).toHaveValue("3");
  await expect(confirm).toBeEnabled();
  await field.fill("6");
  await upload();
  await expect(field).toHaveValue("3");
});
