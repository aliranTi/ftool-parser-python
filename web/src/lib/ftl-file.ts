export const MAX_FTL_BYTES = 10 * 1024 * 1024;

export type ImportedFtl = {
  name: string;
  size: number;
  text: string;
  version: "400" | "401";
};

export async function readFtlFile(file: File): Promise<ImportedFtl> {
  if (!/\.ftl$/i.test(file.name)) {
    throw new Error("Selecione um arquivo com a extensão .ftl.");
  }
  if (file.size === 0) throw new Error("O arquivo está vazio.");
  if (file.size > MAX_FTL_BYTES) {
    throw new Error("O arquivo deve ter no máximo 10 MB.");
  }

  const bytes = new Uint8Array(await file.arrayBuffer());
  // Match Python's latin-1 decoding exactly, including bytes 0x80–0x9f.
  // TextDecoder('latin1') uses Windows-1252 instead.
  const chunks: string[] = [];
  for (let offset = 0; offset < bytes.length; offset += 8192) {
    chunks.push(String.fromCharCode(...bytes.subarray(offset, offset + 8192)));
  }
  const text = chunks.join("");
  const signature = /^(400|401)\s+[+-]?\d+$/.exec(text.split(/\r?\n/, 1)[0].trim());
  if (!signature || text.includes("\0")) {
    throw new Error("Cabeçalho não reconhecido. Selecione um arquivo FTool 4.00 ou 4.01.");
  }

  return { name: file.name, size: file.size, text, version: signature[1] as ImportedFtl["version"] };
}
