import csv
from mininet.net import Mininet
from mininet.node import Controller
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel
import time
import os
import re

# Definir os parâmetros de teste
TCP_VERSIONS = ["reno", "cubic", "bbr", "veno", "vegas", "westwood"]
TESTS = 3  # Quantidade de repetições
PROTOCOLS = ["ipv4", "ipv6"]  # IPv4 e IPv6

# Função para criar a topologia
def create_topology():
    net = Mininet(link=TCLink)

    # Adiciona hosts
    h1 = net.addHost('h1')
    h2 = net.addHost('h2')

    # Adiciona switches
    s1 = net.addSwitch('s1')
    s2 = net.addSwitch('s2')

   # Adiciona links com parâmetros (bw em Mbps, delay em ms, loss em %)
    net.addLink(h1, s1, bw=100, delay='100ms', loss=5) # Largura de banda de 100 Mbps, atraso de 100ms, perda de 5%
    net.addLink(h2, s2, bw=100, delay='100ms', loss=5)
    net.addLink(s1, s2, bw=100, delay='100ms', loss=5)

    net.start()
    return net, h1, h2

# Função para configurar a versão TCP em cada host
def set_tcp_version(host, version):
    host.cmd(f'sysctl -w net.ipv4.tcp_congestion_control={version}')

# Função para configurar IPv6 nos hosts
def set_ipv6(host, ip):
    host.cmd(f'ifconfig {host.name}-eth0 inet6 add {ip}/64')

# Função para executar testes de throughput com iperf e coletar a taxa de transferência
def run_iperf(h1, h2, protocol, version):
    if protocol == "ipv4":
        # Iniciar servidor iperf em h2
        h2.cmd('iperf -s &')
        time.sleep(2)

        # Executar cliente iperf em h1 e coletar resultados
        result = h1.cmd(f'iperf -c {h2.IP()} -t 60 -i 1') # Duração dos testes de Throughput
        h2.cmd('kill %iperf')

    elif protocol == "ipv6":
        # Iniciar servidor iperf para IPv6
        h2.cmd('iperf -s -V &')
        time.sleep(2)

        # Obter o endereço IPv6 da interface h2-eth0
        ipv6_address = h2.cmd("ip -6 addr show h2-eth0 | grep 'inet6' | awk '{print $2}' | cut -d/ -f1").strip()

        # Executar cliente iperf em h1 para IPv6
        result = h1.cmd(f'iperf -c {ipv6_address} -V -t 60 -i 1') # Duração dos testes de Throughput
        h2.cmd('kill %iperf')

    # Extrair throughput do resultado
    throughput = parse_iperf(result)
    return throughput

# Função para medir latência e perda de pacotes com ping e coletar métricas
def run_ping(h1, h2, protocol):
    if protocol == "ipv4":
        result = h1.cmd(f'ping -c 3 {h2.IP()}')
    elif protocol == "ipv6":
        # Obter o endereço IPv6 da interface h2-eth0
        ipv6_address = h2.cmd("ip -6 addr show h2-eth0 | grep 'inet6' | awk '{print $2}' | cut -d/ -f1").strip()
        result = h1.cmd(f'ping6 -c 3 {ipv6_address}')

    # Extrair latência média, perda de pacotes e jitter
    rtt, packet_loss, jitter = parse_ping(result)
    return rtt, packet_loss, jitter

# Função para extrair throughput dos resultados do iperf
def parse_iperf(result):
    match = re.search(r'(\d+\.\d+) Mbits/sec', result)
    if match:
        return float(match.group(1))
    return 0.0

# Função para extrair latência, perda de pacotes e jitter dos resultados do ping
def parse_ping(result):
    rtt_match = re.search(r'rtt min/avg/max/mdev = .*?/(\d+\.\d+)/', result)
    loss_match = re.search(r'(\d+)% packet loss', result)
    jitter_match = re.search(r'rtt min/avg/max/mdev = .*?/.*?/.*?/(\d+\.\d+)', result)

    rtt = float(rtt_match.group(1)) if rtt_match else 0.0
    loss = float(loss_match.group(1)) if loss_match else 0.0
    jitter = float(jitter_match.group(1)) if jitter_match else 0.0

    return rtt, loss, jitter

# Função para criar arquivo CSV e salvar os resultados dos testes
def save_to_csv(protocol, version, data):
    directory = f'resultados_csv/{protocol}'
    if not os.path.exists(directory):
        os.makedirs(directory)

    file_path = f'{directory}/teste_{version}.csv'
    fieldnames = ['Versão TCP', 'Protocolo', 'Teste', 'Throughput (Mbps)', 'RTT (ms)', 'Perda de Pacotes (%)', 'Jitter (ms)']

    # Se o arquivo não existir, crie o cabeçalho
    if not os.path.exists(file_path):
        with open(file_path, mode='w', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()

    # Escrever os dados do teste
    with open(file_path, mode='a', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writerow(data)

# Função para executar o ciclo de testes para cada versão do TCP
def run_tests(net, h1, h2):
    for version in TCP_VERSIONS:
        print(f"Testando versão TCP: {version}")
        # Configurar a versão TCP nos hosts
        set_tcp_version(h1, version)
        set_tcp_version(h2, version)
        
        for protocol in PROTOCOLS:
            print(f"Testando protocolo: {protocol}")
            if protocol == "ipv6":
                # Configurar IPv6 manualmente
                set_ipv6(h1, "2001:db8::1")
                set_ipv6(h2, "2001:db8::2")

            # Executar 100 testes para cada versão TCP e protocolo
            for test_num in range(1, TESTS + 1):
                print(f"Executando teste {test_num}/100 para {protocol} - {version}")

                # Coletar Throughput
                throughput = run_iperf(h1, h2, protocol, version)
                # Coletar Latência, Perda de Pacotes e Jitter
                rtt, packet_loss, jitter = run_ping(h1, h2, protocol)

                # Organizar dados para salvar
                data = {
                    'Versão TCP': version,
                    'Protocolo': protocol,
                    'Teste': test_num,
                    'Throughput (Mbps)': throughput,
                    'RTT (ms)': rtt,
                    'Perda de Pacotes (%)': packet_loss,
                    'Jitter (ms)': jitter
                }

                # Salvar dados em CSV
                save_to_csv(protocol, version, data)

# Função principal para automatizar todo o processo
def main():
    setLogLevel('info')
    net, h1, h2 = create_topology()

    try:
        run_tests(net, h1, h2)
    finally:
        # Parar a rede ao finalizar os testes
        net.stop()

if __name__ == '__main__':
    main()
