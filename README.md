# ftool-parser-python

Parser e conversor em Python para arquivos `.ftl` do FTool 4.00 e 4.01.

O projeto lê o arquivo textual do FTool, reconstrói a topologia estrutural e
entrega um modelo Python com materiais, seções, barras, nós, apoios, cargas
nodais e cotas. Todas as grandezas são normalizadas para o Sistema
Internacional antes de serem expostas pela API.

> Projeto independente e não oficial. O FTool é desenvolvido pela
> PUC-Rio/Tecgraf.

## Funcionalidades

- Leitura de arquivos FTL 4.00 (`400 0`) e 4.01 (`401 0`).
- Reconstrução de barras dos blocos `2 1` e `4 1`.
- Derivação e deduplicação geométrica dos nós.
- Preservação da conectividade entre barras e nós.
- Leitura de materiais e seções genéricas.
- Leitura de apoios livres, articulados, móveis, engastados e elásticos.
- Leitura e associação de cargas pontuais nodais.
- Leitura das linhas de cota usadas na representação gráfica.
- Identificação de rótulas e restrições de deformação das barras.
- Conversão de geometria, propriedades, apoios e cargas para o anaStruct.
- Solução estrutural e plots de geometria e resultados com o anaStruct.
- Conversão do modelo para dicionário serializável em JSON.
- Testes de regressão e validação visual no notebook.

## Como o parser interpreta o FTL

O FTool não serializa todos os nós como entidades independentes. A topologia é
implícita nas barras:

- blocos `2 1 ...` possuem 16 linhas e criam pelo menos um endpoint;
- blocos `4 1 ...` possuem 12 linhas e conectam endpoints existentes;
- endpoints coincidentes, dentro da tolerância de `1 mm`, representam o mesmo
  nó;
- apoio e carga nodal pertencem ao endpoint proprietário dentro do bloco da
  barra;
- marcadores `-1 1 ...` e bounding boxes sentinela fazem parte da subdivisão
  interna de barras.

A implementação foi baseada na análise dos arquivos de exemplo deste projeto e
na documentação comunitária de engenharia reversa do formato:
[ftool-reverse-engineering](https://github.com/nicchonsanchez/ftool-reverse-engineering).

## Unidades

Os arquivos FTL analisados armazenam propriedades mecânicas e carregamentos em
unidades baseadas em kN. O parser converte esses valores para SI:

| Grandeza | Unidade no modelo Python |
|---|---|
| Coordenadas e comprimentos | `m` |
| Área | `m²` |
| Momento de inércia | `m⁴` |
| Forças | `N` |
| Momentos | `N·m` |
| Módulo de elasticidade | `N/m²` (`Pa`) |
| Peso específico | `N/m³` |
| Molas translacionais | `N/m` |
| Mola rotacional | `N·m/rad` |
| Ângulo de apoio | graus |
| Coeficiente de dilatação térmica | `1/°C` |

Exemplo: uma carga armazenada no FTL como `Fy = -0.36788 kN` é retornada pelo
parser como `Fy = -367.88 N`.

## Requisitos

- Python 3.10 ou superior.
- anaStruct 1.7 para análise e visualização.
- Jupyter opcional para executar o notebook.

## Instalação

Clone o repositório e crie um ambiente virtual:

```bash
git clone https://github.com/aliranTi/ftool-parser-python.git
cd ftool-parser-python
python -m venv .venv
```

Ative o ambiente no Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

No Linux ou macOS:

```bash
source .venv/bin/activate
```

Instale as dependências:

```bash
python -m pip install -r requirements.txt
```

Para executar o notebook, instale também o Jupyter:

```bash
python -m pip install jupyter
```

## Uso básico

```python
from src.parser import FtlParser

parser = FtlParser("inputs/ponte_1.ftl")
model = parser.parse()

print(f"Materiais: {len(model.materials)}")
print(f"Seções: {len(model.sections)}")
print(f"Nós: {len(model.nodes)}")
print(f"Barras: {len(model.members)}")
print(f"Cargas nodais: {len(model.point_loads)}")
print(f"Cotas: {len(model.dimensions)}")
```

O método `parse()` devolve uma nova instância de `FtoolModel` a cada execução e
pode ser chamado novamente no mesmo parser sem duplicar dados.

## Inspeção dos dados

### Nós, apoios e cargas

```python
for node in model.nodes:
    print(
        node.id,
        (node.x, node.y),
        (node.support.ux, node.support.uy, node.support.rz),
        node.load,
    )
```

Os estados de cada grau de liberdade do apoio são:

| Valor | Estado |
|---:|---|
| `0` | livre |
| `1` | restringido |
| `2` | mola elástica |

O objeto `Support` fornece propriedades auxiliares como `is_free`, `is_fixed`,
`is_pinned`, `is_roller_x`, `is_roller_y` e `has_spring`.

### Barras e conectividade

```python
for member in model.members:
    print(
        f"B{member.id}: "
        f"N{member.start_node_id} -> N{member.end_node_id}, "
        f"L={member.length:.4f} m, "
        f"material={member.material_name}, "
        f"seção={member.section_name}"
    )
```

### Resumo de depuração

```python
parser.debug()
```

O resumo mostra nós, conectividade, comprimentos, materiais, seções, apoios e
cargas associadas.

## Conversão e análise com anaStruct

```python
from src.converter_anastruct import to_anastruct

analysis = to_anastruct(model)
analysis.solve()

print(analysis.get_reaction_results(ftool_node_id=1))
print(analysis.get_member_results(ftool_member_id=1))
```

O objeto `analysis.system` é uma instância de `anastruct.SystemElements`. Os
dicionários `analysis.node_ids` e `analysis.member_ids` relacionam os IDs do
parser aos IDs criados pelo anaStruct.

Barras com momento de inércia nulo ou rótulas nas duas extremidades são
convertidas em elementos de treliça. Barras com rigidez à flexão são convertidas
em elementos de pórtico, com liberações rotacionais de extremidade quando
indicadas pelo FTool.

## Visualização

O plot da estrutura usa diretamente o renderizador do anaStruct:

```python
from src.visualizer import plot_ftool_model

analysis, _ = plot_ftool_model(model)
```

Os identificadores são exibidos como `n1`, `n2`, ... para nós e `m1`, `m2`,
... para barras. Cargas verticais negativas, como `Fy = -367.88 N`, são
desenhadas apontando para baixo. As identificações podem ser ocultadas
individualmente com `show_node_ids=False` ou `show_member_ids=False`.

Em scripts que precisam salvar ou manipular a figura sem abrir uma janela:

```python
analysis, fig = plot_ftool_model(model, show=False)
fig.savefig("estrutura.png", dpi=150, bbox_inches="tight")
```

Para visualizar esforços, reações ou deslocamentos, resolva primeiro o modelo:

```python
from src.visualizer import plot_anastruct_result

analysis.solve()
plot_anastruct_result(analysis, "reactions")
plot_anastruct_result(analysis, "axial")
plot_anastruct_result(analysis, "shear")
plot_anastruct_result(analysis, "moment")
plot_anastruct_result(analysis, "displacement")
```

Os nomes aceitos são `reactions`, `axial`, `shear`, `moment` e
`displacement`. Argumentos adicionais são encaminhados ao método de plot
correspondente do anaStruct, por exemplo `verbosity=1`, `scale=1.2` ou
`figsize=(12, 7)`.

## Conversão para dicionário/JSON

```python
import json

data = model.to_dict()

with open("modelo.json", "w", encoding="utf-8") as file:
    json.dump(data, file, ensure_ascii=False, indent=2)
```

## Notebook de validação

O arquivo [`notebook.ipynb`](notebook.ipynb) executa testes sobre os três
fixtures em `inputs/` e gera a validação visual de cada estrutura.

Inicie o Jupyter com:

```bash
jupyter notebook notebook.ipynb
```

Também é possível executar todas as células sem interface gráfica:

```bash
jupyter nbconvert --execute --to notebook --stdout notebook.ipynb
```

Os snapshots atuais são:

| Arquivo | Nós | Barras | Materiais | Seções | Cargas | Cotas |
|---|---:|---:|---:|---:|---:|---:|
| `ponte_1.ftl` | 7 | 11 | 1 | 2 | 1 | 7 |
| `ponte_2.ftl` | 8 | 13 | 1 | 2 | 1 | 7 |
| `ponte_3.ftl` | 8 | 12 | 1 | 2 | 1 | 7 |

## Estrutura do projeto

```text
ftool-parser-python/
├── inputs/                 # Arquivos FTL usados como fixtures
├── src/
│   ├── converter_anastruct.py # Conversão e interface de análise
│   ├── ftl_reader.py          # Leitura textual com encoding latin-1
│   ├── models.py              # Dataclasses do modelo estrutural
│   ├── parser.py              # Parser sequencial FTL 4.00/4.01
│   ├── utils.py               # Utilitários de parsing numérico
│   └── visualizer.py          # Plots fornecidos pelo anaStruct
├── notebook.ipynb          # Testes de regressão e gráficos
├── requirements.txt
└── README.md
```

## Limitações atuais

- O parser foi validado principalmente com arquivos FTL 4.00 presentes em
  `inputs/` e com a estrutura documentada para o FTL 4.01.
- Cargas uniformes, lineares, térmicas e momentos de extremidade são consumidos
  durante a leitura para preservar o alinhamento do arquivo, mas ainda não são
  expostos por `FtoolModel`.
- Trens de carga são reconhecidos e consumidos, mas ainda não são representados
  no modelo Python.
- Seções provenientes de tabelas comerciais internas do FTool podem exigir um
  mapeamento específico de catálogo.
- A conversão atual contempla cargas pontuais e momentos nodais. As demais
  cargas ainda não chegam ao modelo público e, portanto, não são enviadas ao
  anaStruct.
- A opção do FTool para ignorar deformação axial não possui correspondência
  segura no anaStruct e gera um erro explícito durante a conversão.
- O arquivo `.ftl` é um formato proprietário e não possui especificação pública
  oficial; compatibilidade com variantes antigas ou futuras não é garantida.

## Próximos passos

- Expor cargas distribuídas, lineares, térmicas e momentos de extremidade.
- Representar recalques prescritos e casos de carregamento no modelo público.
- Ampliar os fixtures e testes automatizados.
- Ampliar a cobertura da conversão para o anaStruct conforme novas cargas forem
  expostas pelo parser.
