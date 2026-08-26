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

        raw = self.path.read_bytes()

        text = raw.decode("latin-1")

        return [
            line.rstrip()
            for line in text.splitlines()
        ]