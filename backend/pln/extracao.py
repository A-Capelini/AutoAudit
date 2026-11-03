"""
Extração de texto (PDF e DOCX) e divisão do documento em seções e sentenças.

Primeira etapa do pipeline de PLN do AutoAudit:

    arquivo (bytes) -> texto limpo -> seções numeradas -> sentenças

As regras de detecção (regras.py) trabalham sobre as sentenças de cada seção, e a
"cláusula" mostrada ao usuário vem do título da seção (ex.: "Seção 4 — Controle de acesso").

Limitação conhecida: PDF escaneado (imagem) não tem texto; não há OCR nesta versão e o
backend devolve um erro claro em vez de analisar um documento vazio.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field

MIN_CARACTERES = 200  # abaixo disso o documento é considerado vazio / escaneado

# Ligaduras que o pypdf devolve em alguns PDFs ("ﬁctício", "deﬁne"). Troca feita à mão
# porque a normalização Unicode NFKC também mudaria "º" em "o".
LIGADURAS = {"ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff", "ﬃ": "ffi", "ﬄ": "ffl", "ﬅ": "st", "ﬆ": "st"}


class ErroExtracao(Exception):
    """Documento que não dá para ler (formato, senha, arquivo corrompido ou sem texto)."""


@dataclass
class Secao:
    numero: str | None            # "4", "4.2" ou None (título sem numeração / preâmbulo)
    titulo: str
    sentencas: list[str] = field(default_factory=list)

    @property
    def rotulo(self) -> str:
        """Texto exibido como `clausula` no relatório."""
        return f"Seção {self.numero} — {self.titulo}" if self.numero else self.titulo


# --------------------------------------------------------------------------- leitura

def detectar_formato(nome: str) -> str | None:
    nome = nome.lower()
    if nome.endswith(".pdf"):
        return "pdf"
    if nome.endswith(".docx"):
        return "docx"
    return None


def extrair_texto(nome: str, conteudo: bytes) -> str:
    """Devolve o texto do PDF/DOCX. Parágrafos reais ficam separados por linha em branco."""
    formato = detectar_formato(nome)
    if formato == "pdf":
        texto = _ler_pdf(conteudo)
    elif formato == "docx":
        texto = _ler_docx(conteudo)
    else:
        raise ErroExtracao("Formato não suportado: envie um arquivo .pdf ou .docx.")
    texto = _normalizar(texto)
    if len(texto.strip()) < MIN_CARACTERES:
        raise ErroExtracao(
            "O documento não tem texto suficiente para análise. Se for um PDF escaneado "
            "(imagem), ele precisa de OCR, que ainda não é suportado.")
    return texto


def _ler_pdf(conteudo: bytes) -> str:
    from pypdf import PdfReader

    try:
        leitor = PdfReader(io.BytesIO(conteudo))
        if leitor.is_encrypted:
            leitor.decrypt("")  # PDFs só com senha de proprietário abrem com senha vazia
        return "\n".join((pagina.extract_text() or "") for pagina in leitor.pages)
    except Exception as exc:  # pypdf levanta vários tipos de erro para arquivos ruins
        raise ErroExtracao(f"Não foi possível ler o PDF (corrompido ou protegido por senha): {exc}") from exc


def _ler_docx(conteudo: bytes) -> str:
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    try:
        doc = Document(io.BytesIO(conteudo))
    except Exception as exc:
        raise ErroExtracao(f"Não foi possível ler o DOCX (arquivo inválido): {exc}") from exc

    linhas: list[str] = []
    for filho in doc.element.body.iterchildren():  # na ordem em que aparecem no documento
        if filho.tag.endswith("}p"):
            par = Paragraph(filho, doc)
            texto = par.text.strip()
            if not texto:
                continue
            estilo = (par.style.name or "").lower() if par.style is not None else ""
            marca = "# " if estilo.startswith(("heading", "título", "titulo")) else ""
            linhas += [marca + texto, ""]            # linha em branco = fim de parágrafo
        elif filho.tag.endswith("}tbl"):
            for linha in Table(filho, doc).rows:
                celulas = list(dict.fromkeys(c.text.strip() for c in linha.cells if c.text.strip()))
                if celulas:                           # dict.fromkeys tira células mescladas repetidas
                    linhas += [" | ".join(celulas), ""]
    return "\n".join(linhas)


def _normalizar(texto: str) -> str:
    for antiga, nova in LIGADURAS.items():
        texto = texto.replace(antiga, nova)
    texto = texto.replace("­", "").replace("\x00", "").replace("\xa0", " ")
    texto = "\n".join(linha.rstrip() for linha in texto.splitlines())
    return re.sub(r"\n{3,}", "\n\n", texto).strip()


# --------------------------------------------------------------------------- seções

# "1. Objetivo", "2.1. Escopo" (com ponto final) ou "4.2 Senhas" (numeração com ponto interno).
# Exigir o ponto evita confundir "30 dias após a admissão" (linha quebrada) com um título.
RE_TITULO = re.compile(
    r"^(?:#\s+)?(?P<num>\d{1,2}(?:\.\d{1,2})*\.|\d{1,2}(?:\.\d{1,2})+)\s+(?P<tit>\S.{0,78})$")
RE_MARCADOR = re.compile(r"^(?:[•·▪●○*\-–—]\s+|\(?[a-z]\)\s+|\d+\)\s+)")
ABREVIACOES = ("art.", "arts.", "inc.", "ex.", "etc.", "nº.", "sr.", "dr.", "ltda.", "s.a.",
               "p.ex.", "cf.", "obs.")


def dividir_secoes(texto: str) -> list[Secao]:
    """Quebra o texto em seções (por título numerado) e cada seção em sentenças."""
    secoes = [Secao(None, "Preâmbulo")]
    paragrafo: list[str] = []

    def fechar() -> None:
        if paragrafo:
            secoes[-1].sentencas.extend(_sentencas(_juntar(paragrafo)))
            paragrafo.clear()

    for bruta in texto.splitlines():
        linha = bruta.strip()
        if not linha:
            fechar()
            continue
        achou = RE_TITULO.match(linha)
        if achou and achou["tit"][0].isupper() and not achou["tit"].endswith((".", ",", ";")):
            fechar()
            secoes.append(Secao(achou["num"].rstrip("."), achou["tit"].strip()))
        elif linha.startswith("# "):                  # título do Word sem numeração
            fechar()
            secoes.append(Secao(None, linha[2:].strip()))
        else:
            if RE_MARCADOR.match(linha):              # item de lista começa um novo parágrafo
                fechar()
            paragrafo.append(linha)
    fechar()
    return [s for s in secoes if s.sentencas or s.titulo != "Preâmbulo"]


def _juntar(linhas: list[str]) -> str:
    """Cola as linhas quebradas do PDF em um parágrafo corrido."""
    saida = linhas[0]
    for linha in linhas[1:]:
        if saida.endswith("-") and linha[:1].islower():   # "ex-" + "colaboradores"
            saida += linha
        else:
            saida += " " + linha
    return re.sub(r"\s+", " ", saida).strip()


def _sentencas(paragrafo: str) -> list[str]:
    partes = re.split(r"(?<=[.!?])\s+(?=[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ])", paragrafo)
    saida: list[str] = []
    for parte in partes:
        if saida and saida[-1].lower().endswith(ABREVIACOES):   # "Art. 46" não é fim de frase
            saida[-1] += " " + parte
        else:
            saida.append(parte)
    return [s.strip() for s in saida if len(s.strip()) > 2]
