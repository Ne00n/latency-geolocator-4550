# latency-geolocator-4550

geodns databases are from the past, we gonna build our own with Blackjack and Hookers

**Dependencies**<br />
```
pip3 install pyasn
```

**Prepare**<br />
Put masscan json files into masscan/<br />
Rename locations.example.json to locations.json and fill it up<br />
Get latest routing table dump
```
pyasn_util_download.py --latest
pyasn_util_convert.py --single rib.2021* asn.dat
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

3. Generate the gdnsd datacenter subnet mapping file
```
python3 geolocator.py generate
```
