import type { ParameterField } from "@/lib/bridge-preview";
import styles from "./parameter-editor.module.css";

export function readParameters(fields: ParameterField[], edits: Record<string, string>) {
  const values: Record<string, number> = {};
  for (const field of fields) {
    if (!(field.key in edits)) continue;
    const text = edits[field.key].trim();
    const value = Number(text);
    if (text && value === field.value) continue;
    if (!text || !Number.isFinite(value) || value < field.minimum ||
        (field.exclusive && value === field.minimum) || (field.integer && !Number.isInteger(value))) {
      throw new Error(`${field.group} — ${field.label}: informe um valor ${field.integer ? "inteiro " : ""}válido em ${field.unit || "unidades"}.`);
    }
    values[field.key] = value;
  }
  return values;
}

export function ParameterEditor({ fields, edits, disabled, onChange, onReset }: {
  fields: ParameterField[]; edits: Record<string, string>; disabled: boolean;
  onChange: (key: string, value: string) => void; onReset: () => void;
}) {
  const groups = [...new Set(fields.map((field) => field.group))];
  return <section className={styles.editor} aria-labelledby="parameters-title">
    <h3 id="parameters-title">Parâmetros antes do cálculo</h3>
    <p>Os valores iniciais vêm do arquivo e dos padrões de dimensionamento. As edições valem apenas para esta análise; o arquivo original não é alterado.</p>
    <p>Alterar b ou h recalcula área e inércia. Se você também editar área ou inércia, o valor manual prevalece na análise. A contagem usa as dimensões do palito, com camadas coladas pelas faces largas.</p>
    <p>O módulo E da análise e o E médio usado na flambagem são independentes. Campos zerados de seções incompletas podem permanecer sem edição.</p>
    {groups.map((group) => <fieldset key={group} disabled={disabled}>
      <legend>{group}</legend>
      <div className={styles.grid}>{fields.filter((field) => field.group === group).map((field) =>
        <label key={field.key}>
          {field.label}{field.unit ? ` (${field.unit})` : ""}
          <input type="number" step={field.integer ? 1 : "any"} min={field.minimum}
            required value={edits[field.key] ?? String(field.value)}
            onChange={(event) => onChange(field.key, event.target.value)} />
        </label>,
      )}</div>
    </fieldset>)}
    <button type="button" disabled={disabled} onClick={onReset}>Restaurar parâmetros originais</button>
  </section>;
}
