import subprocess,json, time, math, sys
import multiprocessing

targets = sys.argv[1:]

multiplicator = 100
loops = math.ceil(len(targets) / multiplicator )
command,commands = f"fping -c2",[]

for index in range(0,loops):
    if targets[index*multiplicator:(index+1)*multiplicator]: commands.append(f"{command} {' '.join(targets[index*multiplicator:(index+1)*multiplicator])}")

def ping(command): 
    p = subprocess.run(command, stdin=None, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    return [p.stdout.decode('utf-8'),p.stderr.decode('utf-8')]

pool = multiprocessing.Pool(processes = 5)

start_time = time.time()
results = pool.map(ping, commands)
for result in results:
    for row in result: print(row)

pool.close()
pool.join()
