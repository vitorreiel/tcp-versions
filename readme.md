[ Dependências ]

sudo apt install mininet iperf -y


[ Cenário de Testes ]

Pacotes no ping:

O número de pacotes no comando ping foi aumentado para 1000 pacotes para melhorar a precisão da medição de latência.
Tempo do iperf:

O tempo do teste iperf foi estendido para 60 segundos para capturar melhor as variações de throughput ao longo do tempo.
Largura de Banda:

A largura de banda dos links foi ajustada para 100 Mbps, o que reflete velocidades mais modernas de rede.
Atraso no Link:

O atraso foi ajustado para 50 ms, simulando redes de longa distância.
Perda de Pacotes:

Uma perda de pacotes de 1% foi introduzida para simular redes com degradação e testar a resiliência dos algoritmos TCP.
Essas alterações ajustam os parâmetros para refletir melhor cenários mais representativos e robustos em seu experimento. Se precisar de mais ajustes, estou à disposição!