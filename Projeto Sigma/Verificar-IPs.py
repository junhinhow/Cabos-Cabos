import re
import socket
import os
import sys
from collections import defaultdict
from datetime import datetime

# --- CONFIGURAÇÕES DE CORES (ANSI) ---
CYAN = "\033[96m"
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
GREY = "\033[90m"
RESET = "\033[0m"

# --- CONFIGURAÇÕES DE ARQUIVOS ---
PASTA_BASE = "TXTs"
NOME_ARQUIVO_ENTRADA = "Relatorio_Servidores.txt"
NOME_ARQUIVO_SAIDA = "Relatorio_IP_Servidores.txt"

def main():
    # Monta os caminhos completos (ex: TXTs/Relatorio_IP_Servidores.txt)
    caminho_entrada = os.path.join(PASTA_BASE, NOME_ARQUIVO_ENTRADA)
    caminho_saida = os.path.join(PASTA_BASE, NOME_ARQUIVO_SAIDA)

    # 1. Garante que a pasta 'TXTs' existe
    if not os.path.exists(PASTA_BASE):
        try:
            os.makedirs(PASTA_BASE)
            print(f"{CYAN}Pasta '{PASTA_BASE}' criada.{RESET}")
        except OSError as e:
            print(f"{RED}Erro crítico ao criar a pasta '{PASTA_BASE}': {e}{RESET}")
            return

    # 2. Verifica se o arquivo de entrada existe DENTRO da pasta
    if not os.path.exists(caminho_entrada):
        print(f"{YELLOW}O arquivo '{caminho_entrada}' não foi encontrado.{RESET}")
        try:
            # Cria o arquivo vazio dentro da pasta TXTs
            with open(caminho_entrada, 'w', encoding='utf-8') as f:
                f.write("") 
            
            print(f"{GREEN}✔ Arquivo criado automaticamente em: {caminho_entrada}{RESET}")
            print(f"{CYAN}➡ Por favor, abra a pasta '{PASTA_BASE}', cole os links no arquivo '{NOME_ARQUIVO_ENTRADA}' e rode o script novamente.{RESET}")
            return
        except OSError as e:
            print(f"{RED}Erro ao criar o arquivo de entrada: {e}{RESET}")
            return

    print(f"{CYAN}Lendo arquivo '{caminho_entrada}'...{RESET}")

    try:
        with open(caminho_entrada, 'r', encoding='utf-8') as f:
            conteudo = f.read()
            
        if not conteudo.strip():
            print(f"{YELLOW}⚠ O arquivo está vazio.{RESET}")
            print(f"Cole o relatório dentro de '{caminho_entrada}' e tente novamente.")
            return

    except Exception as e:
        print(f"{RED}Erro ao ler o arquivo: {e}{RESET}")
        return

    # Regex para capturar domínios
    regex = r"https?://([^/:]+)"
    dominios_unicos = sorted(list(set(re.findall(regex, conteudo))))

    if not dominios_unicos:
        print(f"{RED}Nenhum domínio (http/https) encontrado no arquivo.{RESET}")
        return

    resultados = []

    print(f"{YELLOW}Encontrados {len(dominios_unicos)} domínios únicos. Resolvendo DNS...{RESET}")
    print("-" * 64)

    socket.setdefaulttimeout(3)

    for dominio in dominios_unicos:
        ipv4_list = set()
        ipv6_list = set()
        
        try:
            addr_infos = socket.getaddrinfo(dominio, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
            
            for family, _, _, _, sockaddr in addr_infos:
                ip = sockaddr[0]
                if family == socket.AF_INET:
                    ipv4_list.add(ip)
                elif family == socket.AF_INET6:
                    ipv6_list.add(ip)
            
            if not ipv4_list and not ipv6_list:
                raise socket.gaierror("Nenhum IP encontrado")

            ipv4_str = ", ".join(sorted(ipv4_list)) if ipv4_list else "N/A"
            ipv6_str = ", ".join(sorted(ipv6_list)) if ipv6_list else "N/A"
            
            print(f"{GREEN}Resolvido: {dominio}{RESET}")
            
            resultados.append({
                "Dominio": dominio,
                "IPv4": ipv4_str,
                "IPv6": ipv6_str
            })

        except (socket.gaierror, socket.timeout):
            print(f"{RED}Falha ao resolver: {dominio}{RESET}")
            resultados.append({
                "Dominio": dominio,
                "IPv4": "FALHA",
                "IPv6": "FALHA"
            })

    # Agrupa resultados
    agrupados = defaultdict(list)
    for item in resultados:
        agrupados[item['IPv4']].append(item)

    # --- SALVA O RESULTADO NA MESMA PASTA (TXTs) ---
    try:
        with open(caminho_saida, 'w', encoding='utf-8') as f_out:
            data_hora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            f_out.write("=" * 80 + "\n")
            f_out.write(f"RELATÓRIO DE IPs RESOLVIDOS - {data_hora}\n")
            f_out.write("=" * 80 + "\n\n")

            for ip, itens in agrupados.items():
                if ip != "FALHA":
                    ipv6_ref = itens[0]['IPv6']
                    f_out.write(f"DESTINO IP (IPv4): {ip}\n")
                    f_out.write(f"IPv6: {ipv6_ref}\n")
                    f_out.write("Domínios vinculados:\n")
                    for item in itens:
                        f_out.write(f"   - {item['Dominio']}\n")
                    f_out.write("-" * 40 + "\n\n")

            if "FALHA" in agrupados:
                f_out.write("DOMÍNIOS COM FALHA NA RESOLUÇÃO:\n")
                for item in agrupados["FALHA"]:
                    f_out.write(f"   X {item['Dominio']}\n")
            
        print(f"\n{GREEN}Sucesso! O relatório foi salvo em: {caminho_saida}{RESET}")

    except Exception as e:
        print(f"\n{RED}Erro ao salvar o arquivo: {e}{RESET}")

    # Resumo no Console
    print("\n" + "=" * 64)
    print("RESUMO RÁPIDO")
    print("=" * 64)
    for ip, itens in agrupados.items():
        if ip != "FALHA":
            print(f"{CYAN}IP: {ip} {RESET}({len(itens)} domínios)")

if __name__ == "__main__":
    main()