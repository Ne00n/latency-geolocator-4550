# latency-geolocator-4550

geodns databases are from the past, we gonna build our own with Blackjack and Hookers

**Dependencies**<br />
```
pip3 install pyasn
```

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
You may need to beforehand
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
This will take a few hours.

3. Generate the [gdnsd](https://github.com/gdnsd/gdnsd) datacenter subnet mapping file
```
python3 geolocator.py generate
```
This process is threaded, independent how many locations you have, it will likely take 3 hours<br />
Each Thread will consume up to 1.5GB of Memory, make sure you are not going OOM

4. #Lunch [gdnsd](https://github.com/gdnsd/gdnsd)
```
cp config /etc/gdnsd/
cp myahcdn.net /etc/gdnsd/zones
cp data/dc.conf /etc/gdnsd/geoip
/etc/init.d/gdnsd restart
```
