# Interface web

Next.js, React e TypeScript estrito, com App Router, ESLint e CSS Modules.
Requer Node.js 20.9+ e npm. Dependências e lockfile ficam nesta pasta.

## Desenvolvimento

```bash
cd web
npm ci
npm run dev
```

Abra http://localhost:3000. No PowerShell, use `npm.cmd` se a política bloquear `npm.ps1`.

## Validação e produção

```bash
npm run lint
npm run typecheck
npm run build
npm start
```

## Organização

- `src/app/`: rotas, layout e estilos.
- `public/`: arquivos estáticos.
- `@/*`: alias para `src/*` desta aplicação.

Esta versão permite selecionar ou arrastar um arquivo `.ftl` de até 10 MB,
conferir nome, tamanho e versão, substituir ou remover a seleção. O conteúdo é
lido em memória no navegador como Latin-1, compatível com o parser Python.
Não há envio para servidor nem persistência após recarregar a página.
A validação inicial verifica extensão, tamanho e assinatura FTool 4.00/4.01.
Em seguida, o parser Python interpreta o arquivo em um Web Worker com Pyodide
0.28.0 e apresenta nós, barras e dimensões gerais em uma prévia SVG. O usuário
confirma a ponte ou seleciona outro arquivo; trocar ou remover o arquivo apaga
a confirmação anterior. A prévia é apenas geométrica, sem apoios, cargas ou
resultados de esforços. Confirmar executa `render_report` com anaStruct 1.7.0,
dimensiona os palitos e apresenta, nesta ordem, os gráficos do notebook:
diagrama axial, deformação e quantidade de palitos. Os gráficos são SVGs gerados
pelas funções de `src/visualizer.py`, com download disponível. As tabelas de
esforços e reações ficam em uma seção expansível. Falhas mantêm a
prévia e permitem tentar novamente. Trocar/remover o arquivo cancela a análise
em andamento e limpa seus resultados.

A deformação usa origem local `(0, 0)`, eixos em cm com proporção igual e
escala visual automática: o maior deslocamento amostrado ocupa 8% do maior vão
geométrico. O gráfico informa o fator aplicado e o deslocamento real em mm,
comparando a estrutura original tracejada com a deformada azul.

O runtime é baixado do jsDelivr e precisa de conexão na primeira leitura.
Após a confirmação, NumPy, SciPy e Matplotlib são carregados do mesmo CDN; o fonte oficial
do anaStruct 1.7.0 é baixado do PyPI, com SHA-256 verificado. O worker utiliza o
fallback Python do anaStruct, sem compilar extensões nativas. Matplotlib usa
o backend Agg para gerar os gráficos no worker.
Esses downloads também precisam de conexão caso não estejam em cache.
O arquivo FTL não é enviado ao CDN. `predev` e `prebuild` geram
`public/python/parser.json` a partir dos módulos Python na raiz do repositório.
Reinicie `npm run dev` após alterar esses módulos.

Para os testes de navegador, com o fixture `../inputs/ponte_3.ftl` disponível:

```bash
npx playwright install chromium
npm run test:e2e
```

O motor Python permanece em `../src/`. A prévia chama
`src.pyodide_api.handle_request_json` com a operação `parse`, sem carregar
anaStruct, NumPy ou SciPy. As operações disponíveis na API
Python são `parse`, `analyze_axial`, `size_sticks` e `render_report`. As fórmulas permanecem em
Python; os componentes React consomem o resultado JSON. Consulte o contrato
no README da raiz e os testes em `../tests/test_pyodide_api.py`.
