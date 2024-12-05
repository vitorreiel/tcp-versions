#!/bin/bash
sudo apt update && sudo apt install mininet openvswitch-switch iperf iperf3 python3-psutil -y
cd scenario-I
sudo python3 script.py
cd ../scenario-II
sudo python3 script.py
cd ../scenario-III
sudo python3 script.py
cd ../scenario-IV
sudo python3 script.py