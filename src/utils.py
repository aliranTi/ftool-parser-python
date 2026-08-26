import re
from typing import List, Optional, Tuple

NUMBER_RE = re.compile(
    r"""
    [+-]?
    (?:
        \d+(?:\.\d*)?
        |
        \.\d+
    )
    (?:
        [eE][+-]?\d+
    )?
    """,
    re.VERBOSE
)


def parse_numbers(line: str) -> List[float]:
    """
    Extrai números de uma linha.

    Exemplos aceitos:

        3.25
        +3.25000e+000
        -1.00000e+030
        0.00784
    """

    return [
        float(value)
        for value in NUMBER_RE.findall(line)
    ]


def parse_ints(line: str) -> List[int]:
    """
    Extrai inteiros de uma linha.
    """

    return [
        int(value)
        for value in line.split()
        if re.fullmatch(r"[+-]?\d+", value)
    ]


def is_integer_line(line: str) -> bool:
    values = line.split()

    if not values:
        return False

    return all(
        re.fullmatch(r"[+-]?\d+", value)
        for value in values
    )


def is_numeric_line(line: str) -> bool:
    return bool(parse_numbers(line))


def extract_quoted_string(line: str) -> Optional[str]:
    """
    Extrai:

        'palito'

    de:

        'palito' 0
    """

    match = re.search(r"'([^']*)'", line)

    if match:
        return match.group(1)

    return None


def parse_quoted_record(line: str) -> Optional[Tuple[str, List[float]]]:
    """Separa o nome entre aspas dos valores numéricos posteriores.

    Assim, dígitos contidos em nomes como ``'Aço A36'`` não são confundidos
    com propriedades numéricas do registro.
    """

    match = re.fullmatch(r"\s*'([^']*)'\s*(.*?)\s*", line)
    if match is None:
        return None

    return match.group(1), parse_numbers(match.group(2))
