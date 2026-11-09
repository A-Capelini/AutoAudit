"""Gera a versão "revisada" da política Nimbus, escrita seguindo as sugestões do relatório do
AutoAudit. Documento FICTÍCIO, só para demonstrar a nota subindo depois da correção.

    python data/samples/gerar_nimbus_revisada.py
"""
from pathlib import Path

from docx import Document

SECOES = [
    ("1. Objetivo", [
        "Esta política estabelece as diretrizes de segurança da informação da Nimbus Logística, com o "
        "propósito de proteger os ativos de informação da empresa, de seus clientes e de seus parceiros."]),
    ("2. Responsabilidades", [
        "A diretoria é responsável pela segurança da informação na empresa. Todos os colaboradores devem "
        "zelar pela proteção das informações a que tiverem acesso.",
        "A empresa designa um Encarregado de Proteção de Dados (DPO), nomeado pela diretoria, que atua como "
        "canal de comunicação com os titulares e com a ANPD, conforme a LGPD (Lei nº 13.709/2018).",
        "O tratamento de dados pessoais segue os artigos 6º, 7º e 46 da LGPD, com medidas técnicas e "
        "administrativas para proteger os dados contra acessos não autorizados."]),
    ("3. Uso aceitável dos recursos", [
        "Os equipamentos e sistemas da empresa devem ser usados exclusivamente para fins profissionais. É "
        "proibido instalar software não homologado pela área de TI e compartilhar credenciais de acesso "
        "entre colaboradores. O uso de serviços de armazenamento pessoal em nuvem para dados da empresa é vedado.",
        "Dispositivos pessoais só podem acessar sistemas da empresa após cadastro e aprovação da área de TI, "
        "com bloqueio de tela e criptografia de disco obrigatórios."]),
    ("4. Controle de acesso e senhas", [
        "As senhas devem ter no mínimo 12 caracteres, combinando letras, números e símbolos, e ser trocadas "
        "a cada 180 dias. A conta é bloqueada após 5 tentativas de login malsucedidas.",
        "Os acessos aos sistemas são concedidos conforme a função de cada colaborador e revistos "
        "semestralmente pelo gestor da área. Os acessos de colaboradores desligados devem ser revogados em "
        "até 24 horas.",
        "Os acessos e os eventos de segurança dos sistemas são registrados em logs, mantidos por 12 meses e "
        "analisados pela área de TI."]),
    ("5. Acesso remoto", [
        "O acesso remoto à rede da empresa é permitido mediante autorização do gestor imediato e exige "
        "autenticação multifator (MFA) e conexão por VPN corporativa."]),
    ("6. Rede e serviços", [
        "Os serviços de rede não necessários são desativados em até 30 dias após a revisão trimestral, sob "
        "responsabilidade do gerente de infraestrutura. A rede corporativa é protegida por firewall."]),
    ("7. Cópias de segurança", [
        "Cópias de segurança dos sistemas críticos são realizadas diariamente e armazenadas em local externo "
        "ao datacenter. A restauração das cópias é testada a cada três meses, e o resultado do teste é "
        "registrado e arquivado."]),
    ("8. Incidentes de segurança", [
        "Todo incidente de segurança deve ser comunicado à equipe de TI em até 2 horas após a detecção. O "
        "gerente de segurança da informação é o responsável por coordenar a resposta.",
        "Quando o incidente envolver dados pessoais com risco aos titulares, o Encarregado (DPO) comunica a "
        "ANPD e os titulares em até 3 dias úteis, conforme o art. 48 da LGPD."]),
    ("9. Treinamento e conscientização", [
        "Todos os colaboradores devem concluir, anualmente, o treinamento obrigatório de segurança da "
        "informação. Novos colaboradores devem concluí-lo em até 30 dias após a admissão."]),
    ("10. Revisão da política", [
        "Esta política deve ser revisada pela diretoria, no mínimo, uma vez por ano ou sempre que houver "
        "mudança relevante no ambiente tecnológico ou na legislação."]),
]

if __name__ == "__main__":
    doc = Document()
    doc.add_paragraph("Nimbus Logística Ltda.")
    doc.add_paragraph("Política de Segurança da Informação")
    doc.add_paragraph("Versão 2.0 (revisada) — documento fictício para testes do AutoAudit")
    for titulo, paragrafos in SECOES:
        doc.add_heading(titulo, level=1)
        for p in paragrafos:
            doc.add_paragraph(p)
    destino = Path(__file__).parent / "Politica_Seguranca_Nimbus_Logistica_Revisada.docx"
    doc.save(destino)
    print("Gerado:", destino)
