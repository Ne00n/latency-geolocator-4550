import subprocess, json, sys, re

peak = float(sys.argv[1])
print(f"Latency: {peak}")

with open("targets.json", 'r') as f:
    targets =  json.load(f)

count = 0
match = []
while True:
    if count > len(targets): break
    fping = ["fping", "-c", "5"]
    for target in targets[count:count+50]: fping.append(target)
    print(f"Running {count}/{len(targets)}")
    p = subprocess.run(fping, stdin=None, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
    parsed = re.findall("([0-9.]+).*?([0-9]+.[0-9]|timed out).*?([0-9]+)% loss",p.stdout.decode('utf-8'), re.MULTILINE)
    for ip,ms,loss in parsed:
        if "timed out" in ms: continue
        if float(ms) < peak and ip not in match: 
            print(f"Found {ip}")
            match.append(ip)
    count = count + 50
    with open("match.json", 'w') as f:
        json.dump(match, f)
