import { readFile, mkdir, writeFile } from "node:fs/promises";

const names = ["__init__.py", "models.py", "utils.py", "ftl_reader.py", "parser.py", "pyodide_api.py", "converter_anastruct.py", "exporter.py", "stick_sizing.py", "visualizer.py", "web_report.py"];
const files = Object.fromEntries(await Promise.all(names.map(async (name) => [
  name, await readFile(new URL(`../../src/${name}`, import.meta.url), "utf8"),
])));
const directory = new URL("../public/python/", import.meta.url);
await mkdir(directory, { recursive: true });
await writeFile(new URL("parser.json", directory), JSON.stringify(files));
