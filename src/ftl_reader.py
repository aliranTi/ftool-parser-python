from pathlib import Path
from typing import List

class FtlReader:

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def read(self) -> List[str]:
        """
        O FTL usa bytes que não são UTF-8.

        Nos arquivos fornecidos, latin-1 permite preservar
        os bytes sem perder informação.
        """

        return self.from_bytes(self.path.read_bytes())

    @staticmethod
    def from_bytes(raw: bytes) -> List[str]:
        """Decodifica bytes FTL sem depender do filesystem."""

        return FtlReader.from_text(raw.decode("latin-1"))

    @staticmethod
    def from_text(text: str) -> List[str]:
        """Normaliza conteúdo FTL já carregado em memória."""

        if not isinstance(text, str):
            raise TypeError("O conteúdo FTL deve ser uma string")
        return [line.rstrip() for line in text.splitlines()]
