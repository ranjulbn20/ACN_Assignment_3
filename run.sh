# Start Ryu SDN controller
ryu-manager ryu.app.simple_switch

# Run the topology with s1 and s2 as switches
mn --custom learning_switch.py --topo customtopo --controller remote

# Conduct pings
echo "Pinging from h1 to h4"
mn h1 ping h4 -c 3

echo "Pinging from h2 to h5"
mn h2 ping h5 -c 3

echo "Pinging from h3 to h4"
mn h3 ping h4 -c 3

# Clean up Mininet
mn -c

# Stop Ryu SDN controller
pkill ryu-manager
