import json
import urllib.request
import urllib.parse
from random import randint
from time import sleep

with open("match.json", 'r') as f:
    match =  json.load(f)

export = []

for ip in match:
    sleep(randint(2,8))
    print("Checking",ip)
    url = 'http://check.getipintel.net/check.php?ip='+ip+'&contact=test@test.com'
    f = urllib.request.urlopen(url)
    value = f.read().decode('utf-8')
    if float(value) > 0.9:
        print("Found",ip)
        export.append(ip)
        with open("dc.json", 'w') as f:
            json.dump(export, f)
