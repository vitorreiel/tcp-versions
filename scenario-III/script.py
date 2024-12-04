from mininet.net import Mininet
from mininet.link import TCLink
from mininet.log import setLogLevel
from mininet.cli import CLI
from time import sleep
import psutil
import csv
import json
import os
import math

def enable_ip_forwarding(router):
    """Ativa o encaminhamento de pacotes IPv4 e IPv6 em um roteador."""
    router.cmd("sysctl -w net.ipv4.ip_forward=1")
    router.cmd("sysctl -w net.ipv6.conf.all.forwarding=1")

def create_topology():
    """Create a simple Mininet topology with 2 routers and 2 hosts."""
    net = Mininet(link=TCLink)

    print("Creating network topology...")
    
    # Add routers
    r1 = net.addHost("r1", ip="10.0.1.1/24")
    r2 = net.addHost("r2", ip="10.0.2.1/24")

    # Add hosts with IPv4 configuration
    h1 = net.addHost("h1", ip="10.0.1.2/24", defaultRoute="via 10.0.1.1")
    h2 = net.addHost("h2", ip="10.0.2.2/24", defaultRoute="via 10.0.2.1")

    # Link hosts to routers
    net.addLink(h1, r1, bw=100000, loss=0, delay='0ms') # 20Gbps/1%/10ms
    net.addLink(h2, r2, bw=100000, loss=0, delay='0ms') # 20Gbps/1%/10ms

    # Link routers
    net.addLink(r1, r2, bw=100000, loss=5, delay='100ms', intfName1="r1-eth1", intfName2="r2-eth1") # 20Gbps/1%/10ms

    r1.setIP("192.168.1.1/30", intf="r1-eth1")
    r2.setIP("192.168.1.2/30", intf="r2-eth1")

    r1.cmd("ip -6 addr add 2001:db8:1::1/64 dev r1-eth1")
    r2.cmd("ip -6 addr add 2001:db8:1::2/64 dev r2-eth1")

    h1.cmd("ip -6 addr add 2001:db8:0:1::2/64 dev h1-eth0")
    h2.cmd("ip -6 addr add 2001:db8:0:2::2/64 dev h2-eth0")
    h1.cmd("ip -6 route add default via 2001:db8:0:1::1")
    h2.cmd("ip -6 route add default via 2001:db8:0:2::1")

    r1.cmd("ip -6 addr add 2001:db8:0:1::1/64 dev r1-eth0")
    r2.cmd("ip -6 addr add 2001:db8:0:2::1/64 dev r2-eth0")

    net.start()

    enable_ip_forwarding(r1)
    enable_ip_forwarding(r2)

    r1.cmd("ip route add 10.0.2.0/24 via 192.168.1.2")
    r2.cmd("ip route add 10.0.1.0/24 via 192.168.1.1")

    # Configuração de rotas IPv6 nos roteadores
    r1.cmd("ip -6 route add 2001:db8:0:2::/64 via 2001:db8:1::2")
    r2.cmd("ip -6 route add 2001:db8:0:1::/64 via 2001:db8:1::1")

    return net, h1, h2

def calculate_rtt_variance(rtt_values):
    """Calculate RTT Variance based on a list of RTT values."""
    if not rtt_values:
        return 0
    mean_rtt = sum(rtt_values) / len(rtt_values)  # Calculate the mean RTT
    # Calculate the variance
    variance = sum((rtt - mean_rtt) ** 2 for rtt in rtt_values) / len(rtt_values)
    return round(variance, 2)  # Return variance rounded to 2 decimal places

def configure_tcp_version(host, tcp_version):
    """Configure TCP version for the given host."""
    host.cmd(f"sysctl -w net.ipv4.tcp_congestion_control={tcp_version}")

def measure_metrics(net, h1, h2, output_csv, output_log, test_id, tcp_version, ip_version):
    """Measure TCP performance metrics and save them to a CSV file and a log file."""
    print(f"Starting TCP performance tests for {tcp_version} with {ip_version}...")

    # Configure TCP version and IP version
    configure_tcp_version(h1, tcp_version)
    configure_tcp_version(h2, tcp_version)

    # Start iperf server on h2
    if ip_version == "IPv6":
        h2.cmd("iperf3 -s -6 -p 5202 &")  # Start server with IPv6
    else:
        h2.cmd("iperf3 -s -p 5201 &")  # Start server with IPv4
    sleep(2)  # Give the server time to start

    metrics = []

    # Open log file for writing
    with open(output_log, 'w') as log_file:
        # Run iperf test from h1 to h2
        print("Running iperf test...")
        log_file.write(f"Running iperf test for {tcp_version} with {ip_version}...\n")

        # Capture CPU usage before the test
        cpu_usage_before = psutil.cpu_percent(interval=1)

        if ip_version == "IPv6":
            # Use the fixed IPv6 address of h2 for iperf test
            iperf_result = h1.cmd(f"iperf3 -c 2001:db8:0:2::2%h1-eth0 -6 -p 5202 -t 30 -J")  # IPv6 test
        else:
            iperf_result = h1.cmd(f"iperf3 -c {h2.IP()} -p 5201 -t 30 -J")  # IPv4 test

        # Capture CPU usage after the test
        cpu_usage_after = psutil.cpu_percent(interval=1)

        # Average CPU usage during the test
        avg_cpu_usage = round((cpu_usage_before + cpu_usage_after) / 2, 2)

        # Write full output to log file
        #logss = h1.cmd("ifconfig")
        #logss2 = h2.cmd("ifconfig")
        #print(f"{logss}")
        #print(f"{logss2}")
        #print(f"{iperf_result}")
        log_file.write(iperf_result)
        log_file.write("\n")

        # Parse results
        try:
            iperf_data = json.loads(iperf_result)

            # Verify and extract the relevant metrics
            throughput_bps = iperf_data['end']['sum_received']['bits_per_second']
            throughput_gbps = round(throughput_bps / 1e9, 2)

            retransmissions = iperf_data['end']['sum_sent']['retransmits']
            recovery_time_total = round(iperf_data['end']['sum_sent']['seconds'], 2)
            mean_rtt = iperf_data['end']['streams'][0]['sender'].get('mean_rtt', 0)

            # Extract RTTs for variance calculation
            rtt_values = [stream['rtt'] for interval in iperf_data['intervals'] for stream in interval['streams'] if 'rtt' in stream]
            rtt_variance = calculate_rtt_variance(rtt_values)

            # Total Packets Sent (rounded)
            total_bytes_sent = iperf_data['end']['sum_sent']['bytes']
            tcp_mss = iperf_data['start']['tcp_mss_default']
            total_packets_sent = round(total_bytes_sent / tcp_mss, 2)

            packet_loss = "{:.2f}".format((retransmissions / total_packets_sent) * 100 if total_packets_sent > 0 else 0)
            max_bandwidth = 100 * 1e9  # 100 Gbps
            bandwidth_efficiency = round((throughput_bps / max_bandwidth) * 100, 2)

            max_rtt = iperf_data['end']['streams'][0]['sender'].get('max_rtt', 0)
            max_cwnd = iperf_data['end']['streams'][0]['sender'].get('max_snd_cwnd', 0)

            cpu_sender = round(iperf_data['end']['cpu_utilization_percent']['host_total'], 2)
            cpu_receiver = round(iperf_data['end']['cpu_utilization_percent']['remote_total'], 2)

            # Append metrics with ID to identify the test run
            metrics.append({
                'ID': test_id,
                'TCP Version': tcp_version,
                'IP Version': ip_version,
                'Throughput (Gbps)': throughput_gbps,
                'Packet Loss (%)': packet_loss,
                'Total Recovery Time (s)': recovery_time_total,
                'Mean RTT (ms)': mean_rtt,
                'RTT Variance (ms)': rtt_variance,
                'Maximum RTT (ms)': max_rtt,
                'Retransmissions': retransmissions,
                'Total Packets Sent': total_packets_sent,
                'Bandwidth Efficiency (%)': bandwidth_efficiency,
                'Max cwnd (bytes)': max_cwnd,
                'CPU Sender (%)': cpu_sender,
                'CPU Receiver (%)': cpu_receiver,
                'CPU Usage Local (%)': avg_cpu_usage
            })

        except KeyError as e:
            log_file.write(f"Error: Missing key {str(e)} in iperf result.\n")

    # Write metrics to CSV file
    output_filename = f"dataset_{ip_version.lower()}_{tcp_version.lower()}.csv"
    with open(output_filename, 'a', newline='') as csvfile:  # 'a' to append data without overwriting
        fieldnames = [
            'ID', 
            'TCP Version', 
            'IP Version',
            'Throughput (Gbps)', 
            'Packet Loss (%)', 
            'Total Recovery Time (s)', 
            'Mean RTT (ms)', 
            'RTT Variance (ms)', 
            'Maximum RTT (ms)', 
            'Retransmissions', 
            'Total Packets Sent', 
            'Bandwidth Efficiency (%)', 
            'Max cwnd (bytes)', 
            'CPU Sender (%)', 
            'CPU Receiver (%)',
            'CPU Usage Local (%)'
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        if csvfile.tell() == 0:  # Write header only if file is empty
            writer.writeheader()
        writer.writerows(metrics)

    print(f"Metrics saved to {output_filename}")
    print(f"Full output saved to {output_log}")

def cleanup(net):
    """Stop the Mininet network and clean up processes."""
    print("Stopping network...")
    net.stop()
    os.system("pkill -f iperf3")

if __name__ == '__main__':
    setLogLevel('info')

    output_log = "full_output.log"

    # Loop through TCP versions and IP versions, run 3 times for each configuration
    tcp_versions = ['reno', 'cubic', 'bbr', 'vegas', 'veno', 'westwood']
    ip_versions = ['IPv4', 'IPv6']

    for tcp_version in tcp_versions:
        for ip_version in ip_versions:
            for test_id in range(1, 31):  # Loop 30 times for each combination
                print(f"Starting test {test_id} for TCP {tcp_version} and {ip_version}")
                # Create topology
                net, h1, h2 = create_topology()
                try:
                    # Measure metrics
                    measure_metrics(net, h1, h2, f"scenario-III/dataset_{ip_version.lower()}_{tcp_version.lower()}.csv", output_log, test_id, tcp_version, ip_version)
                finally:
                    # Clean up
                    cleanup(net)

    print("All tests completed.")