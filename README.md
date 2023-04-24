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
apt-get install python3-dev build-essential
```

**masscan**<br />
Example for running masscan (icmp/ping only)
```
https://gist.github.com/Ne00n/140bf52e94b195876d11dde063434f38
#Saves files as .txt uses way less space and memory
```
This will scan the entire internet, except a few excluded ranges with 50kpps<br />
I would suggest you talk to your ISP, especially on Virtual Machines before sending 50kpps if they are fine with it.

As of now, I have not seen a single abuse while doing so.

**Prepare**<br />
Put [masscan](https://github.com/robertdavidgraham/masscan) .txt files into masscan/<br />
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
Reduces about 6GB of raw data into a usable small file<br />

2. Run geolocator to get latency data from each location
```
python3 geolocator.py geolocate
```
This process is threaded, independent how many locations you have, it will likely take 60-80 minutes<br />

3. Generate the geo.mmdb file
```
python3 geolocator.py generate
```

4. #Lunch [gdnsd](https://github.com/gdnsd/gdnsd)
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