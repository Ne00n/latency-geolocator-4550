import timeit, json
from netaddr import IPNetwork, IPAddress

print("Loading","ipinfo.json.json")
with open("ipinfo.json", 'r') as f:
    db = json.load(f)

start = timeit.default_timer()
lookup = "5.5.5.5"
splitted = lookup.split(".")

rows = db[splitted[0]]
for row,location in rows.items():
    if IPAddress(lookup) in IPNetwork(row):
        print(location)
        break

stop = timeit.default_timer()

print('Time: ', stop - start)  