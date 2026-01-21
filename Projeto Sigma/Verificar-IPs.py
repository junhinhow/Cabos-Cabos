import re
import socket
import os
import sys
from collections import defaultdict
from datetime import datetime

# Definição de cores para o TERMINAL (não irão para o arquivo)
CYAN = "\033[96m"
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
GREY = "\033[90m"
RESET = "\033[0m"

# Configurações de Entrada e Saída
ARQUIVO_ENTRADA = "Relatorio_Servidores.txt"
PASTA_SAIDA = "TXTs"
NOME_ARQUIVO_SAIDA = "Relatorio_IPs_Final.txt"

def main():
    # 1. Verifica se o arquivo de entrada existe
    if not os.path.exists(ARQUIVO_ENTRADA):
        print(f"{RED}Erro: O arquivo '{ARQUIVO_ENTRADA}' não foi encontrado.{RESET}")
        return

    # 2. Cria a pasta TXTs se ela não existir
    if not os.path.exists(PASTA_SAIDA):
        try:
            os.makedirs(PASTA_SAIDA)
            print(f"{CYAN}Pasta '{PASTA_SAIDA}' criada com sucesso.{RESET}")
        except OSError as e:
            print(f"{RED}Erro ao criar pasta: {e}{RESET}")
            return

    caminho_completo_saida = os.path.join(PASTA_SAIDA, NOME_ARQUIVO_SAIDA)

    print(f"{CYAN}Lendo arquivo e extraindo domínios...{RESET}")

    try:
        with open(ARQUIVO_ENTRADA, 'r', encoding='utf-8') as f:
            conteudo = f.read()
    except Exception as e:
        print(f"{RED}Erro ao ler o arquivo: {e}{RESET}")
        return

    # Regex para capturar domínios
    regex = r"https?://([^/:]+)"
    dominios_unicos = sorted(list(set(re.findall(regex, conteudo))))

    resultados = []

    print(f"{YELLOW}Encontrados {len(dominios_unicos)} domínios únicos. Resolvendo DNS...{RESET}")
    print("-" * 64)

    # Configura timeout
    socket.setdefaulttimeout(3)

    for dominio in dominios_unicos:
        ipv4_list = set()
        ipv6_list = set()
        
        try:
            # Tenta resolver DNS
            addr_infos = socket.getaddrinfo(dominio, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
            
            for family, _, _, _, sockaddr in addr_infos:
                ip = sockaddr[0]
                if family == socket.AF_INET:   # IPv4
                    ipv4_list.add(ip)
                elif family == socket.AF_INET6: # IPv6
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

    # --- GERAÇÃO DO ARQUIVO DE SAÍDA ---
    try:
        with open(caminho_completo_saida, 'w', encoding='utf-8') as f_out:
            
            # Cabeçalho do arquivo
            data_hora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            f_out.write("=" * 80 + "\n")
            f_out.write(f"RELATÓRIO DE IPs RESOLVIDOS - {data_hora}\n")
            f_out.write("=" * 80 + "\n\n")

            # Processa Sucessos
            for ip, itens in agrupados.items():
                if ip != "FALHA":
                    ipv6_ref = itens[0]['IPv6']
                    
                    # Escreve no arquivo (Sem cores)
                    f_out.write(f"DESTINO IP (IPv4): {ip}\n")
                    f_out.write(f"IPv6: {ipv6_ref}\n")
                    f_out.write("Domínios vinculados:\n")
                    for item in itens:
                        f_out.write(f"   - {item['Dominio']}\n")
                    f_out.write("-" * 40 + "\n\n")

            # Processa Falhas
            if "FALHA" in agrupados:
                f_out.write("DOMÍNIOS COM FALHA NA RESOLUÇÃO:\n")
                for item in agrupados["FALHA"]:
                    f_out.write(f"   X {item['Dominio']}\n")
            
        print(f"\n{GREEN}Sucesso! O relatório foi salvo em: {caminho_completo_saida}{RESET}")

    except Exception as e:
        print(f"\n{RED}Erro ao salvar o arquivo na pasta TXTs: {e}{RESET}")

    # Exibição Final no Console (Resumo Rápido)
    print("\n" + "=" * 64)
    print("RESUMO VISUAL (Detalhes salvos na pasta TXTs)")
    print("=" * 64)
    
    for ip, itens in agrupados.items():
        if ip != "FALHA":
            print(f"{CYAN}IP: {ip} {RESET}({len(itens)} domínios)")

if __name__ == "__main__":
    main()