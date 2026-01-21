import re
import socket
import os
import sys
from collections import defaultdict

# Definição de cores ANSI para o terminal (equivalente ao -ForegroundColor)
CYAN = "\033[96m"
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
GREY = "\033[90m"
RESET = "\033[0m"

# Nome do arquivo de entrada
arquivo_entrada = "Relatorio_Servidores.txt"

def main():
    # Verifica se o arquivo existe
    if not os.path.exists(arquivo_entrada):
        print(f"{RED}Erro: O arquivo '{arquivo_entrada}' não foi encontrado.{RESET}")
        return

    print(f"{CYAN}Lendo arquivo e extraindo domínios...{RESET}")

    try:
        with open(arquivo_entrada, 'r', encoding='utf-8') as f:
            conteudo = f.read()
    except Exception as e:
        print(f"{RED}Erro ao ler o arquivo: {e}{RESET}")
        return

    # Regex para capturar domínios (http://dominio.com:porta)
    # Python re.findall retorna todas as correspondências
    regex = r"https?://([^/:]+)"
    dominios_unicos = sorted(list(set(re.findall(regex, conteudo))))

    resultados = []

    print(f"{YELLOW}Encontrados {len(dominios_unicos)} domínios únicos. Resolvendo DNS...{RESET}")
    print("-" * 64)

    # Configura timeout para não travar muito tempo em domínios mortos
    socket.setdefaulttimeout(3)

    for dominio in dominios_unicos:
        ipv4_list = set()
        ipv6_list = set()
        status_color = RED # Padrão erro
        
        try:
            # Tenta resolver DNS (Busca tanto IPv4 quanto IPv6)
            # socket.AF_UNSPEC permite buscar ambas as famílias
            addr_infos = socket.getaddrinfo(dominio, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
            
            for family, _, _, _, sockaddr in addr_infos:
                ip = sockaddr[0]
                if family == socket.AF_INET:   # IPv4
                    ipv4_list.add(ip)
                elif family == socket.AF_INET6: # IPv6
                    ipv6_list.add(ip)
            
            ipv4_str = ", ".join(sorted(ipv4_list)) if ipv4_list else "N/A"
            ipv6_str = ", ".join(sorted(ipv6_list)) if ipv6_list else "N/A"
            
            # Se não achou IPv4, consideramos como falha para agrupar depois? 
            # O script original considera sucesso se o comando rodar, mas vamos focar no IPv4 principal
            if not ipv4_list and not ipv6_list:
                raise socket.gaierror("Nenhum IP encontrado")

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

    # Agrupar resultados pelo IPv4
    # Usamos defaultdict para criar listas de grupos automaticamente
    agrupados = defaultdict(list)
    for item in resultados:
        agrupados[item['IPv4']].append(item)

    print("\n" + "=" * 64)
    print("RELATÓRIO DE SERVIDORES AGRUPADOS POR IP (DESTINO FINAL)")
    print("=" * 64)

    # Processa grupos com sucesso
    for ip, itens in agrupados.items():
        if ip != "FALHA":
            print(f"\n{CYAN}📂 DESTINO IP (IPv4): {ip}{RESET}")
            
            # Pega o IPv6 do primeiro item (referência)
            ipv6_ref = itens[0]['IPv6']
            print(f"{GREY}   IPv6: {ipv6_ref}{RESET}")
            
            print("   🔗 Domínios apontando para cá:")
            for item in itens:
                print(f"      - {item['Dominio']}")

    print("\n" + "-" * 64)
    print("Domínios que falharam na resolução:")
    
    # Processa falhas
    if "FALHA" in agrupados:
        for item in agrupados["FALHA"]:
            print(f"   {RED}❌ {item['Dominio']}{RESET}")
    else:
        print("   (Nenhuma falha encontrada)")

if __name__ == "__main__":
    main()