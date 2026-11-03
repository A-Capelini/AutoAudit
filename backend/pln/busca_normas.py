"""
Busca semântica nas normas (NIST SP 800-53 e LGPD) com o índice FAISS de data/processed/.

O índice é montado por `python db/build_faiss.py` (não vai para o Git). Aqui só se LÊ:
  * normas.index          vetores (768 dimensões, produto interno = cosseno)
  * normas_trechos.json   faiss_id -> (fonte, identificador, texto do trecho)
  * normas_index.json     metadados, inclusive o nome do modelo de embeddings

O modelo é multilíngue: uma cláusula em português encontra um controle do NIST em inglês.
Roda sempre na CPU (device="cpu"), de propósito: a GPU antiga (sm_50) não é suportada pelo
PyTorch instalado e quebraria a API.

Se o índice não existir ou o modelo não carregar, a API continua funcionando sem a busca
(quem chama trata a exceção).
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Callable

import numpy as np

log = logging.getLogger("autoaudit.busca")

RAIZ = Path(__file__).resolve().parents[2]
PASTA_PADRAO = RAIZ / "data" / "processed"
MODELO_PADRAO = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
MAX_TOKENS = 256  # o mesmo usado ao montar o índice


class BuscaIndisponivel(RuntimeError):
    """Índice ausente ou modelo que não carregou."""


class BuscadorNormas:
    def __init__(self, pasta: Path | None = None,
                 codificar: Callable[[list[str]], np.ndarray] | None = None) -> None:
        """`codificar` permite injetar outro codificador (testes); por padrão usa o modelo real."""
        self.pasta = Path(pasta) if pasta else PASTA_PADRAO
        self._codificar = codificar
        self._trava = threading.Lock()
        self._indice = None
        self._trechos: dict[int, dict] = {}
        self._modelo = None
        self.erro: str | None = None

    # ------------------------------------------------------------------ estado
    @property
    def arquivos_existem(self) -> bool:
        return (self.pasta / "normas.index").exists() and (self.pasta / "normas_trechos.json").exists()

    @property
    def pronto(self) -> bool:
        return self._indice is not None

    @property
    def estado(self) -> str:
        if self.pronto:
            return "pronto"
        if self.erro:
            return "indisponível"
        return "carregando" if self.arquivos_existem else "indisponível (índice não encontrado)"

    # ------------------------------------------------------------------ carga
    def carregar(self) -> None:
        with self._trava:
            if self._indice is not None:
                return
            if self.erro:
                raise BuscaIndisponivel(self.erro)
            try:
                if not self.arquivos_existem:
                    raise BuscaIndisponivel("Índice FAISS não encontrado. Rode: python db/build_faiss.py")
                import faiss

                indice = faiss.read_index(str(self.pasta / "normas.index"))
                trechos = {t["faiss_id"]: t for t in json.loads(
                    (self.pasta / "normas_trechos.json").read_text(encoding="utf-8"))}
                if self._codificar is None:
                    nome = MODELO_PADRAO
                    meta = self.pasta / "normas_index.json"
                    if meta.exists():
                        nome = json.loads(meta.read_text(encoding="utf-8")).get("modelo", MODELO_PADRAO)
                    from sentence_transformers import SentenceTransformer

                    log.info("Carregando modelo de embeddings %s (CPU)…", nome)
                    self._modelo = SentenceTransformer(nome, device="cpu")
                    self._modelo.max_seq_length = MAX_TOKENS
                self._indice, self._trechos = indice, trechos
                log.info("Busca semântica pronta: %d vetores.", indice.ntotal)
            except Exception as exc:
                self.erro = f"{exc.__class__.__name__}: {exc}"
                log.warning("Busca semântica indisponível: %s", self.erro)
                raise BuscaIndisponivel(self.erro) from exc

    # ------------------------------------------------------------------ consulta
    def _vetores(self, textos: list[str]) -> np.ndarray:
        if self._codificar is not None:
            vetores = self._codificar(textos)
        else:
            vetores = self._modelo.encode(textos, batch_size=16, show_progress_bar=False,
                                          normalize_embeddings=True)
        return np.asarray(vetores, dtype="float32")

    def buscar_varias(self, consultas: list[str], top: int = 3) -> list[list[dict]]:
        """Para cada consulta, as `top` normas mais próximas: [{fonte, identificador, nota}].

        Vários trechos da mesma norma viram um resultado só (o de maior nota).
        """
        if not consultas:
            return []
        self.carregar()
        with self._trava:  # o modelo não é thread-safe; a API roda requisições em threads
            vetores = self._vetores(consultas)
            notas, ids = self._indice.search(vetores, min(top * 6, self._indice.ntotal))
        saida = []
        for linha_notas, linha_ids in zip(notas, ids):
            vistos, achados = set(), []
            for nota, fid in zip(linha_notas, linha_ids):
                trecho = self._trechos.get(int(fid))
                if trecho is None:
                    continue
                chave = (trecho["fonte"], trecho["identificador"])
                if chave in vistos:
                    continue
                vistos.add(chave)
                achados.append({"fonte": chave[0], "identificador": chave[1], "nota": float(nota)})
                if len(achados) == top:
                    break
            saida.append(achados)
        return saida

    def buscar(self, consulta: str, top: int = 3) -> list[dict]:
        return self.buscar_varias([consulta], top)[0]
