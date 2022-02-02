# latency-geolocator-4550

geodns databases are from the past, we gonna build our own with Blackjack and Hookers

**Dependencies**<br />
```
pip3 install pyasn
pip3 install netaddr
pip3 install geoip2
```
Wot, you install maxmind geoip, BETRAYAL!

You may need run beforehand
```
apt-get install python-dev build-essential
```

**masscan**<br />
Example for running masscan (icmp/ping only)
```
masscan --randomize-hosts 0.0.0.0/0 --ping  --excludefile exclude.conf --rate 50000 --rotate 5min --rotate-dir /var/log/masscan/ --output-format json --output-filename icmp.json
#or
https://gist.github.com/Ne00n/140bf52e94b195876d11dde063434f38
#Saves files as .csv uses way less space and memory
```
This will scan the entire internet, except a few excluded ranges with 50kpps randomly<br />
I would suggest you talk to your ISP, especially on Virtual Machines before sending 50kpps if they are fine with it.

As of now, I have not seen a single abuse while doing so.

**Prepare**<br />
Put [masscan](https://github.com/robertdavidgraham/masscan) .json or .csv files into masscan/<br />
Rename locations.example.json to locations.json and fill it up<br />
```
cp locations.example.json locations.json
```
Get latest routing table dump
```
pyasn_util_download.py --latest
pyasn_util_convert.py --single rib.2022* asn.dat
```

**Usage**<br />
1. Run geolocator to generate the list<br />
```
python3 geolocator.py masscan
```
Reduces about 70GB of raw data into a usable small file<br />
Be warned, the memory usage will be up to 5 times the masscan .json file size!<br />

```
python3 geolocator.py masscan routing
```
Will generate a bigger pingable.json with up to 3000 IP's per Subnet instead of 64

2. Run geolocator to get latency data from each location
```
python3 geolocator.py geolocate
```
This process is threaded, independent how many locations you have, it will likely take 3-4 hours<br />

3. Generate the [gdnsd](https://github.com/gdnsd/gdnsd) datacenter subnet mapping file
```
python3 geolocator.py generate
```
To reduce memory usage and gdnsd boot time, you can specify the failover nodes.<br>
If one machine dies, it gets routed to the next one and so on, until all of them die, then it gets forwarded to the next available.<br>

Depending on your use case, you should adjust it, you can of course use the full list,<br>
however more memory usage, eventually you hit 2GB+ and the boot times will be painful.<br>

4. Compress the [gdnsd](https://github.com/gdnsd/gdnsd) datacenter subnet mapping file
```
python3 geolocator.py compress
```
The idea behind compressing is, putting multiple /24, /23, /22 or /21 subnets into bigger ones.<br>
This Reduces memory usage of gdnsd and boot time, however should have no impact on routing.<br>
Besides if there is no data for a specific subnet, the subnet could be included in a different one with data and shitrouted.<br>

TLDR: makes the config shorter<br>

5. #Lunch [gdnsd](https://github.com/gdnsd/gdnsd)
```
cp config /etc/gdnsd/
cp myahcdn.net /etc/gdnsd/zones
cp data/dc.conf /etc/gdnsd/geoip
/etc/init.d/gdnsd restart
```

**Optimization**<br />
Rerun specific latency messurements on demand
```
python3 geolocator.py rerun retry
```
- Finds subnets with "retry"
```
python3 geolocator.py rerun latency 400
```
- Subnets with reported latency over 400
```
python3 geolocator.py rerun geo 100
```
- Subnet is geographically in the same country where you have a Server, which exceeds the latency of 100<br />
- You need the [GeoLite2-Country.mmdb](https://dev.maxmind.com/geoip/geolite2-free-geolocation-data) from maxmind for that
```
python3 geolocator.py routing
```
- Generates networks.json for better optimized messurements
Some Networks like Google or Microsoft only announce a big Subnet like a /16 and rout the rest internally.<br>
Usually the System only grabs one Pingable IP per Subnet to determine the origins.<br>
However, this can lead the false results, if the subnet is routed internally and not announced separate.<br><br>

How we try to solve this, is splitting bigger subnets into smaller ones, and for each small one, we use a IP do determine the origins.<br>
Thats why you should run routing before using any rerun commands, plus you should ran masscan with routing to ensure we find IP's for each small Subnet.<br><br>

By default we have only 64 IP's per Subnet, which if you get a big Subnet such as a /64 is pretty bad, routing configures the pingable.json with up 3k IP's per Subnet.<br>

