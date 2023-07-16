import subprocess, json, sys, re

def mtr(target):
    mtr = ['mtr','--aslookup','--report','--report-cycles','5','--report-wide','--aslookup','--show-ips', target]
    return subprocess.run(mtr, stdin=None, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False).stdout.decode('utf-8')

def classify(mtr):
    carriersOnRoute = []
    for line in mtr.split('\n'):
        asn = re.findall("AS([0-9]+)(.*?)[0-9]+\.[0-9]+%",line, re.MULTILINE)
        if asn:
            host = asn[0][1].replace(" ","")
            carriersOnRoute.append(f"{asn[0][0]}, {host}")
    return carriersOnRoute

min = float(sys.argv[1])
max = float(sys.argv[2])
print(f"Latency: {min}/{max}")

with open("targets.json", 'r') as f:
    targets =  json.load(f)

count = 0
match = {}
while True:
    if count > len(targets): break
    fping = ["fping", "-c", "5"]
    for target in targets[count:count+50]: fping.append(target)
    print(f"Running {count}/{len(targets)}")
    p = subprocess.run(fping, stdin=None, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
    parsed = re.findall("([0-9.]+).*?([0-9]+.[0-9]|timed out).*?([0-9]+)% loss",p.stdout.decode('utf-8'), re.MULTILINE)
    for ip,ms,loss in parsed:
        if "timed out" in ms: continue
        if float(ms) > min and float(ms) < max and ip not in match: 
            print(f"Found {ip}")
            match[ip] = {"mtr":""}
            print(f"Running MTR for {ip}")
            response = mtr(ip)
            match[ip]['mtr'] = classify(response)
    count = count + 50
    with open("match.json", 'w') as f:
        json.dump(match, f, indent=4)
