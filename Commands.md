[ Commands ]

  - Verificar qual versão atual do TCP -
    sysctl net.ipv4.tcp_congestion_control

  - Para listar todas as versões do TCP -
    sysctl net.ipv4.tcp_available_congestion_control

  - Alterar versão do TCP -
    sudo sysctl -w net.ipv4.tcp_congestion_control=<version>
      # version = reno | cubic | vegas | bbr | westwood | veno

  - Verificar se o IPv6 está habilitado -
    sysctl net.ipv6.conf.all.disable_ipv6
      # se o resultado for 1, habilite o IPv6:
        sudo sysctl -w net.ipv6.conf.all.disable_ipv6=0
        sudo sysctl -w net.ipv6.conf.default.disable_ipv6=0