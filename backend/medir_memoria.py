"""
Mede o pico de memória (RAM) da API do AutoAudit durante auditorias e o tempo de cada uma.

Só Linux (lê /proc). Rode com a API JÁ NO AR, a partir da RAIZ do repositório:

    HF_HUB_OFFLINE=1 uvicorn backend.main:app --port 8000   # terminal 1, SEM --reload; esperar "busca semântica: pronto"
    python backend/medir_memoria.py                          # terminal 2 (mesmo usuário do terminal 1)
    python backend/medir_memoria.py outro.pdf outro.docx     # além dos arquivos padrão, mede estes também

Para cada arquivo (depois de uma auditoria de aquecimento, que não conta), mede:
  - pico de RAM do PROCESSO da API (VmHWM), zerado antes de cada auditoria com /proc/<pid>/clear_refs;
  - menor MemAvailable do SISTEMA durante a auditoria (amostrado a cada 10 ms) e o quanto caiu;
  - tempo da requisição, em segundos (medido no cliente: inclui rede local e gravação no MongoDB).
Antes de tudo imprime o pico do processo desde o início da API, que inclui a carga do modelo de embeddings.
Por isso, para medir a subida, rode este script logo depois de subir a API e antes de qualquer outra auditoria.

Atenção: cada auditoria é gravada de verdade no MongoDB (é o caminho real da demonstração). Depois, rode
    python db/limpar_testes.py --apagar
"""
from __future__ import annotations

import argparse
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path

import requests

RAIZ = Path(__file__).resolve().parent.parent
ARQUIVOS_PADRAO = [
    RAIZ / "data" / "samples" / "Politica_Seguranca_Nimbus_Logistica.docx",
    RAIZ / "data" / "samples" / "Politica_Seguranca_Alfa_Saude.pdf",
]


def ler_kb(caminho: str, campo: str) -> int:
    """Valor (em kB) de um campo de /proc/meminfo ou /proc/<pid>/status."""
    with open(caminho, encoding="ascii") as f:
        for linha in f:
            if linha.startswith(campo + ":"):
                return int(linha.split()[1])
    raise KeyError(f"{campo} não encontrado em {caminho}")


def mib(kb: int) -> float:
    return kb / 1024


def swap_usado_kb() -> int:
    return ler_kb("/proc/meminfo", "SwapTotal") - ler_kb("/proc/meminfo", "SwapFree")


def achar_pid() -> int:
    """PID da API: o processo do uvicorn com mais RAM (evita pegar um processo-pai vazio)."""
    saida = subprocess.run(["pgrep", "-f", "uvicorn backend.main"], capture_output=True, text=True).stdout.split()
    candidatos = []
    for texto in saida:
        try:
            candidatos.append((ler_kb(f"/proc/{texto}/status", "VmRSS"), int(texto)))
        except (OSError, KeyError):
            continue
    if not candidatos:
        sys.exit("Não achei o processo da API (uvicorn backend.main). Suba a API ou passe --pid.")
    return max(candidatos)[1]


def zerar_pico(pid: int) -> bool:
    """Zera o pico de RSS do processo (Linux >= 4.0). Devolve False se não conseguiu."""
    try:
        with open(f"/proc/{pid}/clear_refs", "w", encoding="ascii") as f:
            f.write("5")
    except OSError:
        return False
    # conferência: depois de zerar, o pico tem que ficar do tamanho da RAM atual (com folga pequena)
    return ler_kb(f"/proc/{pid}/status", "VmHWM") <= ler_kb(f"/proc/{pid}/status", "VmRSS") * 1.02


class Amostrador(threading.Thread):
    """Guarda o menor MemAvailable do sistema enquanto a auditoria roda."""

    def __init__(self, intervalo: float = 0.01) -> None:
        super().__init__(daemon=True)
        self.intervalo = intervalo
        self.minimo = ler_kb("/proc/meminfo", "MemAvailable")
        self._parar = threading.Event()

    def run(self) -> None:
        while not self._parar.is_set():
            self.minimo = min(self.minimo, ler_kb("/proc/meminfo", "MemAvailable"))
            time.sleep(self.intervalo)

    def parar(self) -> int:
        self._parar.set()
        self.join()
        self.minimo = min(self.minimo, ler_kb("/proc/meminfo", "MemAvailable"))
        return self.minimo


def auditar(url: str, arquivo: Path) -> dict:
    with open(arquivo, "rb") as f:
        r = requests.post(f"{url}/auditorias", files={"arquivo": (arquivo.name, f)},
                          data={"com_verificacao": "false"}, timeout=180)
    r.raise_for_status()
    return r.json()


def memoria_docker() -> str | None:
    """Memória dos contêineres do projeto (MongoDB, mongo-express), se o Docker responder."""
    try:
        r = subprocess.run(["docker", "stats", "--no-stream", "--format", "{{.Name}}: {{.MemUsage}}"],
                           capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return None
    linhas = [l for l in r.stdout.splitlines() if l.startswith("autoaudit")]
    return "\n    ".join(linhas) or None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("arquivos", nargs="*", type=Path, help="PDF/DOCX extras para medir")
    ap.add_argument("--sem-padrao", action="store_true", help="não mede os arquivos padrão (só os informados)")
    ap.add_argument("--url", default="http://localhost:8000", help="endereço da API (padrão: %(default)s)")
    ap.add_argument("--pid", type=int, help="PID da API (padrão: procura o uvicorn)")
    ap.add_argument("-n", "--repeticoes", type=int, default=3, help="auditorias medidas por arquivo (padrão: %(default)s)")
    args = ap.parse_args()

    arquivos = ([] if args.sem_padrao else ARQUIVOS_PADRAO) + args.arquivos
    if not arquivos:
        sys.exit("Nenhum arquivo para medir: informe PDF/DOCX ou tire o --sem-padrao.")
    faltando = [a for a in arquivos if not a.is_file()]
    if faltando:
        sys.exit("Arquivo não encontrado: " + ", ".join(str(a) for a in faltando))

    try:
        saude = requests.get(f"{args.url}/saude", timeout=10).json()
    except (requests.RequestException, ValueError):
        sys.exit(f"A API não respondeu em {args.url}/saude. Ela está no ar?")
    if saude.get("mongo") != "ok" or saude.get("busca_semantica") != "pronto":
        sys.exit(f"API ainda não está pronta: {saude}. Espere 'busca semântica: pronto' e rode de novo.")

    pid = args.pid or achar_pid()
    status = f"/proc/{pid}/status"
    print(f"API: PID {pid} | sistema: {mib(ler_kb('/proc/meminfo', 'MemTotal')):.0f} MiB de RAM, "
          f"{mib(ler_kb('/proc/meminfo', 'MemAvailable')):.0f} MiB disponíveis, "
          f"swap em uso {mib(swap_usado_kb()):.0f} MiB")
    print(f"Pico do processo da API desde o início (inclui a carga do modelo): {mib(ler_kb(status, 'VmHWM')):.0f} MiB "
          f"| RAM atual: {mib(ler_kb(status, 'VmRSS')):.0f} MiB")
    if not zerar_pico(pid):
        sys.exit("Não consegui zerar o pico de RAM (clear_refs). Rode este script com o mesmo usuário da API, "
                 "num kernel Linux >= 4.0.")

    linhas = []
    aquecimentos = []
    swap_antes = swap_usado_kb()
    for arquivo in arquivos:
        auditar(args.url, arquivo)  # aquecimento: não entra na tabela, mas o pico dele é registrado
        aquecimentos.append((arquivo.name, mib(ler_kb(status, "VmHWM")), mib(ler_kb(status, "VmRSS"))))
        for i in range(1, args.repeticoes + 1):
            zerar_pico(pid)
            disponivel_antes = ler_kb("/proc/meminfo", "MemAvailable")
            amostrador = Amostrador()
            amostrador.start()
            t0 = time.perf_counter()
            rel = auditar(args.url, arquivo)
            segundos = time.perf_counter() - t0
            minimo = amostrador.parar()
            linhas.append({
                "arquivo": arquivo.name, "i": i, "s": segundos,
                "pico": mib(ler_kb(status, "VmHWM")), "rss": mib(ler_kb(status, "VmRSS")),
                "min_disp": mib(minimo), "queda": mib(disponivel_antes - minimo),
                "nota": rel.get("saude_compliance"), "lacunas": len(rel.get("lacunas", [])),
            })

    print("\nAuditoria de aquecimento (a 1ª é a auditoria 'fria', logo depois da subida da API); pico do processo em MiB:")
    for nome, pico, rss in aquecimentos:
        print(f"    {nome[:70]:<71}pico {pico:>6.0f} | RAM depois {rss:>6.0f}")
    print(f"\n{'arquivo':<46}{'#':>2}{'tempo s':>9}{'pico API':>10}{'RAM API':>9}{'disp. mín.':>11}{'queda':>8}{'nota':>6}{'lac.':>5}")
    for l in linhas:
        print(f"{l['arquivo'][:45]:<46}{l['i']:>2}{l['s']:>9.2f}{l['pico']:>10.0f}{l['rss']:>9.0f}"
              f"{l['min_disp']:>11.0f}{l['queda']:>8.0f}{l['nota']:>6}{l['lacunas']:>5}")
    print("(memória em MiB; 'pico API' = pico de RAM do processo durante a auditoria; 'disp. mín.' = menor MemAvailable do sistema)")

    tempos = [l["s"] for l in linhas]
    pico_geral = max([l["pico"] for l in linhas] + [a[1] for a in aquecimentos])
    print(f"\nResumo de {len(linhas)} auditorias medidas: pico máximo da API {max(l['pico'] for l in linhas):.0f} MiB "
          f"(com os aquecimentos: {pico_geral:.0f} MiB) | "
          f"menor MemAvailable {min(l['min_disp'] for l in linhas):.0f} MiB | "
          f"tempo mediana {statistics.median(tempos):.2f} s, máximo {max(tempos):.2f} s | "
          f"swap usado: {mib(swap_antes):.0f} -> {mib(swap_usado_kb()):.0f} MiB")
    docker = memoria_docker()
    if docker:
        print(f"Contêineres (memória agora):\n    {docker}")
    print("\nLembrete: as auditorias ficaram gravadas no MongoDB. Rode: python db/limpar_testes.py --apagar")


if __name__ == "__main__":
    main()
