# latency-geolocator-4550

geodns databases are from the past, we gonna build our own with Blackjack and Hookers

**Dependencies**<br />
```
pip3 install pyasn
```

**masscan**<br />
Example for running masscan (icmp/ping only)
```
masscan --randomize-hosts 0.0.0.0/0 --ping  --excludefile exclude.conf --rate 50000 --rotate 5min --rotate-dir /var/log/masscan/ --output-format json --output-filename icmp.json
```
This will scan the entire internet, except a few excluded ranges with 50kpps randomly<br />
I would suggest you talk to your ISP, especially on Virtual Machines before sending 50kpps if they are fine with it.

As of now, I have not seen a single abuse while doing so.

**Prepare**<br />
Put [masscan](https://github.com/robertdavidgraham/masscan) json files into masscan/<br />
Rename locations.example.json to locations.json and fill it up<br />
```
cp locations.example.json locations.json
```
Get latest routing table dump
```
pyasn_util_download.py --latest
pyasn_util_convert.py --single rib.2021* asn.dat
```
You may need run beforehand
```
apt-get install gcc python3-dev
```

**Usage**<br />
1. Run geolocator to generate the list<br />
```
python3 geolocator.py masscan
```
Reduces about 70GB of raw data into a usable small file<br />
Be warned, the memory usage will be up to 5 times the masscan .json file size!<br />

2. Run geolocator to get latency data from each location
```
python3 geolocator.py geolocate
```
This process is threaded, independent how many locations you have, it will likely take 3-4 hours<br />

3. Optional: Corrector, Applying some magic
```
python3 geolocator.py corrector
```
- Finds subnets with "retry" and pings them over a different IP

4. Generate the [gdnsd](https://github.com/gdnsd/gdnsd) datacenter subnet mapping file
```
python3 geolocator.py generate
```

5. #Lunch [gdnsd](https://github.com/gdnsd/gdnsd)
```
cp config /etc/gdnsd/
cp myahcdn.net /etc/gdnsd/zones
cp data/dc.conf /etc/gdnsd/geoip
/etc/init.d/gdnsd restart
```
