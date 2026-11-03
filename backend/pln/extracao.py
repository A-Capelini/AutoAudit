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
from collections import Counter
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
        paginas = [(pagina.extract_text() or "") for pagina in leitor.pages]
    except Exception as exc:  # pypdf levanta vários tipos de erro para arquivos ruins
        raise ErroExtracao(f"Não foi possível ler o PDF (corrompido ou protegido por senha): {exc}") from exc
    return _limpar_paginas(paginas)


# "Página 3", "3 de 20", "3/20" e números soltos de página.
RE_NUM_PAGINA = re.compile(r"^(?:p[áa]g(?:ina)?\.?\s*)?\d{1,4}(?:\s*(?:de|/)\s*\d{1,4})?$", re.IGNORECASE)


def _limpar_paginas(paginas: list[str]) -> str:
    """Junta as páginas tirando o que não é conteúdo: numeração de página e cabeçalhos/rodapés
    (linha curta que se repete na maioria das páginas, ex.: "Classificação: Uso interno")."""
    linhas = [[l.strip() for l in texto.splitlines()] for texto in paginas]
    repetidas: set[str] = set()
    if len(paginas) >= 3:
        contagem = Counter(l for pagina in linhas for l in set(pagina) if l and len(l) <= 120)
        minimo = max(3, int(0.6 * len(paginas)))
        repetidas = {l for l, n in contagem.items() if n >= minimo}
    saida = [l for pagina in linhas for l in pagina if l not in repetidas and not RE_NUM_PAGINA.match(l)]
    return "\n".join(saida)


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
# ABNT: "1 OBJETIVO" / "2 Escopo" (número sem ponto). Só vale se for o número ESPERADO na sequência
# (1, 2, 3…), para não confundir com linha quebrada ("24 horas depois…").
RE_TITULO_SIMPLES = re.compile(r"^(?P<num>\d{1,2})\s+(?P<tit>[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][^.!?;:]{2,60})$")
# Título só em maiúsculas, sem número ("OBJETIVO", "RESPONSABILIDADES E COMPETÊNCIAS").
RE_MAIUSCULO = re.compile(r"^[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-ZÁÀÂÃÉÊÍÓÔÕÚÇ0-9 /,&–-]{4,59}$")
# Linha de sumário: "1. Objetivo ........ 3".
RE_SUMARIO = re.compile(r"(?:\.{3,}|…)\s*\d+\s*$")
# Título numerado de verdade é curto e não é frase: "4.2 Senhas" sim; "1.1 A política tem por objetivo
# proteger…" (item numerado do corpo, comum em PoSIC de órgãos públicos) não.
RE_VERBO_FRASE = re.compile(r"\b(?:deve|devem|dever[áa]|ser[áa]|ser[ãa]o|é|s[ãa]o|poder[áa]|compete|cabe|tem|possui)\b",
                            re.IGNORECASE)
RE_CAPITULO = re.compile(r"^(?:CAP[ÍI]TULO|T[ÍI]TULO|SE[ÇC][ÃA]O|ANEXO|PARTE)\b", re.IGNORECASE)


def _parece_titulo(titulo: str) -> bool:
    titulo = titulo.strip()
    return (len(titulo) <= 60 and len(titulo.split()) <= 9 and ":" not in titulo
            and not titulo.endswith((".", ",", ";")) and not RE_VERBO_FRASE.search(titulo))


RE_MARCADOR = re.compile(r"^(?:[•·▪●○*\-–—]\s+|\(?[a-z]\)\s+|\d+\)\s+)")
ABREVIACOES = ("art.", "arts.", "inc.", "ex.", "etc.", "nº.", "sr.", "dr.", "ltda.", "s.a.",
               "p.ex.", "cf.", "obs.")


def dividir_secoes(texto: str) -> list[Secao]:
    """Quebra o texto em seções (por título numerado) e cada seção em sentenças."""
    secoes = [Secao(None, "Preâmbulo")]
    paragrafo: list[str] = []
    ultimo_numero = 0  # número da última seção numerada (para validar "2 Escopo" sem ponto)

    def fechar() -> None:
        if paragrafo:
            secoes[-1].sentencas.extend(_sentencas(_juntar(paragrafo)))
            paragrafo.clear()

    def abrir_sem_numero(titulo: str) -> None:
        """Título sem número. "CAPÍTULO II" sozinho numa linha e o título na seguinte viram UMA seção."""
        anterior = secoes[-1]
        if not anterior.sentencas and anterior.numero is None and RE_CAPITULO.match(anterior.titulo) \
                and not RE_CAPITULO.match(titulo):
            anterior.titulo = f"{anterior.titulo} — {titulo}"
        else:
            secoes.append(Secao(None, titulo))

    for bruta in texto.splitlines():
        linha = bruta.strip()
        if not linha:
            fechar()
            continue
        if RE_SUMARIO.search(linha):                  # linha do sumário: não é conteúdo nem título
            continue
        achou = RE_TITULO.match(linha)
        simples = RE_TITULO_SIMPLES.match(linha)
        if achou and achou["tit"][0].isupper() and _parece_titulo(achou["tit"]):
            fechar()
            secoes.append(Secao(achou["num"].rstrip("."), achou["tit"].strip()))
            ultimo_numero = int(achou["num"].split(".")[0])
        elif simples and int(simples["num"]) == ultimo_numero + 1:
            fechar()
            secoes.append(Secao(simples["num"], simples["tit"].strip()))
            ultimo_numero = int(simples["num"])
        elif linha.startswith("# "):                  # título do Word sem numeração
            fechar()
            abrir_sem_numero(linha[2:].strip())
        elif RE_MAIUSCULO.match(linha) and len(linha.split()) <= 6 and len(linha) >= 5:
            fechar()                                  # título em maiúsculas, sem número
            abrir_sem_numero(linha.strip())
        else:
            if RE_MARCADOR.match(linha):              # item de lista começa um novo parágrafo
                fechar()
            paragrafo.append(linha)
    fechar()
    resultado = [s for s in secoes if s.sentencas or s.titulo != "Preâmbulo"]
    if len(resultado) == 1 and resultado[0].titulo == "Preâmbulo":
        resultado[0].titulo = "Documento"             # nenhum título reconhecido: o texto todo é uma seção
    return resultado


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
