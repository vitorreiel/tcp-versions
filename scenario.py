import csv
from mininet.net import Mininet
from mininet.node import OVSSwitch
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
DATA_SIZE = "10KB"  # Definir o tamanho dos dados a serem transferidos
PARALLEL_CONNECTIONS = 10  # Número de transferências paralelas

# Função para criar a topologia
def create_topology():
    net = Mininet(switch=OVSSwitch, link=TCLink)

    # Adiciona hosts
    h1 = net.addHost('h1')
    h2 = net.addHost('h2')

    # Adiciona switches
    s1 = net.addSwitch('s1', failMode='standalone')
    s2 = net.addSwitch('s2', failMode='standalone')

    # Adiciona links com parâmetros (bw em Mbps, delay em ms, loss em %)
    net.addLink(h1, s1, bw=100, delay='10ms', loss=5)  # Ajuste de perda para forçar retransmissões
    net.addLink(h2, s2, bw=100, delay='10ms', loss=5)
    net.addLink(s1, s2, bw=100, delay='10ms', loss=5)

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
    print(f"Executando iperf para {protocol} - {version}...")

    if protocol == "ipv4":
        # Iniciar servidor iperf em h2
        h2.cmd('iperf -s &')
        time.sleep(2)

        # Executar cliente iperf em h1 e definir o tamanho dos dados a serem transferidos
        result = h1.cmd(f'iperf -c {h2.IP()} -n {DATA_SIZE} -P {PARALLEL_CONNECTIONS}')
        print("Resultados iperf (IPv4):", result)
        h2.cmd('kill %iperf')

    elif protocol == "ipv6":
        # Iniciar servidor iperf para IPv6
        h2.cmd('iperf -s -V &')
        time.sleep(2)

        # Utilizar o endereço IPv6 configurado manualmente e definir o tamanho dos dados a serem transferidos
        result = h1.cmd(f'iperf -c 2001:db8::2 -V -n {DATA_SIZE} -P {PARALLEL_CONNECTIONS}')
        print("Resultados iperf (IPv6):", result)
        h2.cmd('kill %iperf')

    # Extrair throughput do resultado
    throughput = parse_iperf(result)
    return throughput

# Função para medir latência e perda de pacotes com ping e coletar métricas
def run_ping(h1, h2, protocol):
    print(f"Executando ping para {protocol}...")
    if protocol == "ipv4":
        result = h1.cmd(f'ping -c 10 {h2.IP()}')
    elif protocol == "ipv6":
        # Executar ping6 diretamente para o endereço configurado
        result = h1.cmd(f'ping6 -c 10 2001:db8::2')

    print("Resultados ping:", result)
    # Extrair latência média, perda de pacotes
    rtt, packet_loss = parse_ping(result)
    recovery_time = get_recovery_time(h1, h2)  # Calcular o tempo de recuperação
    return rtt, packet_loss, recovery_time

# Função para calcular tempo de recuperação após perda de pacotes (com base na retransmissão TCP)
def get_recovery_time(h1, h2):
    print("Capturando pacotes para detectar retransmissões...")
    dumpfile = 'dumpfile.pcap'
    start_time = time.time()

    # Iniciar o tcpdump para capturar pacotes retransmitidos
    h1.cmd(f'tcpdump -i h1-eth0 tcp and port 5001 -w {dumpfile} &')
    time.sleep(12)  # Captura durante o teste do iperf

    # Finalizar o tcpdump e calcular o tempo até a primeira retransmissão
    h1.cmd('kill %tcpdump')
    tcpdump_output = h1.cmd(f'tcpdump -nn -r {dumpfile} | grep "tcp" | grep "retransmission"')
    end_time = time.time()

    print(f"Saída do tcpdump: {tcpdump_output}")  # Verificar o que está sendo capturado

    # Verificar retransmissões
    if 'retransmission' in tcpdump_output:
        recovery_time = end_time - start_time
    else:
        recovery_time = 0  # Se não houve retransmissão, o tempo de recuperação é 0

    # Remover o arquivo de captura
    h1.cmd(f'rm {dumpfile}')
    return recovery_time

# Função para extrair throughput dos resultados do iperf
def parse_iperf(result):
    match = re.search(r'(\d+\.\d+) Mbits/sec', result)
    if match:
        return float(match.group(1))
    return 0.0

# Função para extrair latência e perda de pacotes dos resultados do ping
def parse_ping(result):
    rtt_match = re.search(r'rtt min/avg/max/mdev = .*?/(\d+\.\d+)/', result)
    loss_match = re.search(r'(\d+)% packet loss', result)

    rtt = float(rtt_match.group(1)) if rtt_match else 0.0
    loss = float(loss_match.group(1)) if loss_match else 0.0

    return rtt, loss

# Função para criar arquivo CSV separado para IPv4 e IPv6 e salvar os resultados dos testes
def save_to_csv(protocol, data):
    file_path = f'resultados_{protocol}.csv'
    fieldnames = ['Versão TCP', 'Protocolo', 'Teste', 'Throughput (Mbps)', 'RTT (ms)', 'Perda de Pacotes (%)', 'Tempo de Recuperação (s)']

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

            # Executar testes para cada versão TCP e protocolo
            for test_num in range(1, TESTS + 1):
                print(f"Executando teste {test_num}/{TESTS} para {protocol} - {version}")

                # Coletar Throughput
                throughput = run_iperf(h1, h2, protocol, version)
                # Coletar Latência, Perda de Pacotes e Tempo de Recuperação
                rtt, packet_loss, recovery_time = run_ping(h1, h2, protocol)

                # Organizar dados para salvar
                data = {
                    'Versão TCP': version,
                    'Protocolo': protocol,
                    'Teste': test_num,
                    'Throughput (Mbps)': throughput,
                    'RTT (ms)': rtt,
                    'Perda de Pacotes (%)': packet_loss,
                    'Tempo de Recuperação (s)': recovery_time
                }

                # Salvar dados em CSV separado para IPv4 e IPv6
                save_to_csv(protocol, data)

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