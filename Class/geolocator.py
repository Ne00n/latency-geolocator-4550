import ipaddress, random, pyasn, sqlite3, time, json, math, sys, re, os
from aggregate_prefixes import aggregate_prefixes
from multiprocessing import Process, Queue
from netaddr import IPNetwork, IPSet
from mmdb_writer import MMDBWriter
from datetime import datetime
from netaddr import IPNetwork
from threading import Thread
from threading import Barrier
from Class.base import Base
from shutil import copyfile
import multiprocessing
import geoip2.database

class Geolocator(Base):

    masscanDir,locations,asndb,notPingable,pingableLength = "","","","",0
    subnetCache,subnetIPCache = {},[]
    connection = sqlite3.connect("file:subnets?mode=memory&cache=shared", uri=True)

    def __init__(self,masscanDir="/masscan/"):
        print("Loading asn.dat")
        self.asndb = pyasn.pyasn(os.getcwd()+'/asn.dat')
        self.masscanDir = os.getcwd()+masscanDir
        print("Loading locations.json")
        self.locations = self.loadJson(os.getcwd()+'/locations.json')

    def loadPingable(self,offloading=True):
        print("Loading pingable.json")
        pingable = self.loadJson(os.getcwd()+'/pingable.json')
        self.pingableLength = len(pingable)
        if offloading is False:
            self.pingable = pingable
            return
        print("Offloading pingable.json into SQLite Database")
        self.connection.execute("""CREATE TABLE subnets (subnet, sub, ips)""")
        for subnet in pingable:
            for sub,ips in pingable[subnet].items():
                ips = ','.join(ips)
                self.connection.execute(f"INSERT INTO subnets VALUES ('{subnet}','{sub}', '{ips}')")
        self.connection.commit()

    def getIPsFromSubnet(self,connection,subnet,start=0,end=0):
        if start != 0 or end != 0:
            return list(connection.execute("SELECT * FROM subnets LIMIT ?,?",(start,end)))
        else:
            return list(connection.execute("SELECT * FROM subnets WHERE subnet=?", (subnet,)))

    def dumpDatabase(self):
        return list(self.connection.execute("SELECT * FROM subnets"))

    def fill(self):
        #ignore DoD
        ignore = ["7","11","21","22","26","28","29","30","33"]
        print("Loading","pingable.json")
        pingable = open('pingable.json', 'r')
        pingable = json.load(pingable)
        notPingable = {}
        with open('asn.dat') as file:
            for line in file:
                if ";" in line: continue
                line = line.rstrip()
                subnet, asn = line.split("\t")
                if any(map(subnet.startswith, ignore)): continue
                if not subnet in pingable:
                    print(f"Adding {subnet}")
                    notPingable[subnet] = {}
                    subs = self.networkToSubs(subnet)
                    for sub in subs:
                        ip, prefix = sub.split("/")
                        ip = ip[:-1]
                        ip = f"{ip}1"
                        notPingable[subnet][sub] = [ip]
                else:
                    print(f"{subnet} already inside")
        self.saveJson(notPingable,os.getcwd()+'/notPingable.json')

    def debug(self,ip):
        lookup = self.asndb.lookup(ip)
        print("Subnet",lookup[1])
        subnets = {}
        for location in self.locations:
            print("Loading",location['name']+"-subnets.csv")
            with open(os.getcwd()+'/data/'+location['name']+"-subnets.csv", 'r') as f:
                file = f.read()
            dict = {}
            for row in file.splitlines():
                line = row.split(",")
                dict[line[0]] = line[1]
            subnets[location['name']] = dict
            if lookup[1] in subnets[location['name']]:
                print("Latency",subnets[location['name']][lookup[1]],"ms")
            else:
                print("Not found in",location['name'])

    def masscanFiles(self,files,thread):
        dataList,diff = {},0
        for index, file in enumerate(files):
            print(f"Thread {thread} {index} of {len(files)} files")
            current = int(datetime.now().timestamp())
            if file.endswith(".txt"):
                print(f"Thread {thread} Loading {file}")
                with open(self.masscanDir+file, 'r') as f:
                    dumpTxT = f.read()
                print(f"Thread {thread} Preparing list")
                pingable,currentSub,subsCache = [],"127.0.0.0/8",{}
                for ip in dumpTxT.splitlines(): pingable.append(ip)
                pingable = sorted(pingable, key = ipaddress.IPv4Address)
                print(f"Thread {thread} Building list")
                for ip in pingable:
                    lookup = self.asndb.lookup(ip)
                    if lookup[0] == None: continue
                    if lookup[1] != currentSub:
                        if not lookup[1] in subsCache: subsCache[lookup[1]] = self.networkToSubs(lookup[1])
                        currentSub = lookup[1]
                        dataList[lookup[1]] = {}
                        lastSub = 0
                        for sub in subsCache[lookup[1]]: dataList[lookup[1]][sub] = []
                    if len(subsCache[lookup[1]]) == 1:
                        if len(dataList[lookup[1]][lookup[1]]) > 20: continue
                        dataList[lookup[1]][lookup[1]].append(ip)
                        continue
                    else:
                        for iSub, sub in enumerate(subsCache[lookup[1]]):
                            if iSub < lastSub: continue
                            if ipaddress.IPv4Address(ip) in ipaddress.IPv4Network(sub):
                                if len(dataList[lookup[1]][sub]) > 20: break
                                dataList[lookup[1]][sub].append(ip)
                                lastSub = iSub
                                break
            #filter
            print(f"Thread {thread} Filtering list")
            for prefix in dataList:
                for sub in list(dataList[prefix]):
                    if not dataList[prefix][sub]: del dataList[prefix][sub]
            diff += int(datetime.now().timestamp()) - current
            devidor = 1 if index == 0 else index
            print(f"Thread {thread} Finished in approximately {round((diff / devidor) * (len(files) - index) / 60)} minute(s)")
        print("Thread "+str(thread),"Done, saving file",'tmp'+str(thread)+'-pingable.json')
        self.saveJson(dataList,os.getcwd()+'/tmp'+str(thread)+'-pingable.json')

    def masscan(self):
        print("Generating json")
        files = os.listdir(self.masscanDir)
        filelist,processes,runs = [],[],1
        for file in files:
            if os.stat(f"{self.masscanDir}/{file}").st_size == 0:
                print(f"Skipping empty file {file}")
                continue
            if file.endswith(".json") or  file.endswith(".txt"): filelist.append(file)
        print("Found",len(filelist),"file(s)")
        print("Notice: Make sure you got 1GB of memory available for each process")
        coreCount = int(input("How many processes do you want? suggestion "+str(int(len(os.sched_getaffinity(0)) / 2))+": "))
        split = int(len(filelist) / coreCount)
        diff = len(filelist) - (split * coreCount)
        while runs <= coreCount:
            list = filelist[ (runs -1) *split:( (runs -1) *split)+split]
            if runs == 1 and diff != 0: list.append(filelist[len(filelist)-diff:len(filelist)][0])
            processes.append(Process(target=self.masscanFiles, args=([list,runs])))
            runs += 1
        self.startJoin(processes)
        print("Merging files")
        runs,pingable = 1,{}
        while runs <= coreCount:
            print("Loading","tmp"+str(runs)+"-pingable.json")
            file = self.loadJson(os.getcwd()+'/tmp'+str(runs)+'-pingable.json')
            pingable = {**pingable, **file}
            os.remove(os.getcwd()+'/tmp'+str(runs)+'-pingable.json')
            runs  += 1
        print("Saving","pingable.json")
        self.saveJson(pingable,os.getcwd()+'/pingable.json')

    def getIPs(self,connection,row,length=1000):
        ips,mapping = [],{}
        pingable = self.getIPsFromSubnet(connection,"",row,length)
        for row in pingable:
            data = row[2].split(",")
            for index, ip in enumerate(data):
                ips.append(ip)
                mapping[ip] = row[1]
                if index == 1: break
        return ips,mapping

    def SubnetsToRandomIP(self,list):
        mapping,ips = {},[]
        #get the full pingable.json
        subnetsList = self.dumpDatabase()
        subnets = self.listToDict(subnetsList)
        #go through the subnets we should get a random ip for
        for subnet in list:
            #if the subnet is not in the pingable.json ignore it
            if subnet not in subnets: continue
            #get a list of the pingable ip's from that subnet
            ipaaaays = subnets[subnet].split(",")
            #get random ip
            randomIP = random.choice(ipaaaays)
            ips.append(randomIP)
            mapping[randomIP] = subnet
            #caching
            if not subnet in self.subnetCache:
                #split the original subnet into /22
                subs = self.networkToSubs(subnet)
                self.subnetCache[subnet] = subs
            else:
                subs = self.subnetCache[subnet]
            #counter so we don't check the same again
            current = 0
            #for each /22
            for sub in subs:
                for index, ip in enumerate(ipaaaays):
                    #make sure we don't check the same again
                    if index <= current: continue
                    if ip in self.subnetIPCache: continue
                    #check if the ip is in the given subnet
                    if ipaddress.IPv4Address(ip) in ipaddress.IPv4Network(sub):
                        ips.append(ip)
                        self.subnetIPCache.append(ip)
                        mapping[ip] = sub
                        current = index
                        break
        return ips,mapping

    def mapToSubnet(self,latency,mapping):
        subnets = {}
        for ip, ms in latency.items():
            if mapping:
                lookup = mapping[ip]
            else:
                lookup = self.mapping[ip]
            subnets[lookup] = ms
        return subnets

    def fpingLocation(self,location,barrier=False,update=False,multiplicator=2):
        loaded,mapping,length,row,map = False,{},self.pingableLength,0,{}
        connection = sqlite3.connect("file:subnets?mode=memory&cache=shared", uri=True)
        if update: length = len(self.notPingable)
        while row < length:
            current = int(datetime.now().timestamp())
            if update is False:  ips,mapping = self.getIPs(connection,row,1000 * multiplicator)
            if update is True: ips = self.SliceAndDice(self.notPingable,row,1000 * multiplicator)
            command,commands = "ssh root@"+location['ip']+" fping -c2",[]
            loops = math.ceil(len(ips) / 1000 )
            for index in range(0,loops):
                if ips[index*1000:(index+1)*1000]: commands.append(f"{command} {' '.join(ips[index*1000:(index+1)*1000])}")
            print(location['name'],f"Running fping with {multiplicator} threads and {len(commands)} batches")
            pool = multiprocessing.Pool(processes = multiplicator)
            results = pool.map(self.cmd, commands)
            latency = self.getAvrg(results) 
            subnets = self.mapToSubnet(latency,mapping)
            print(f"Got {len(subnets)} from {1000 * multiplicator}")
            if update is False:
                print(location['name'],"Updating",location['name']+"-subnets.csv")
                csv = self.dictToCsv(subnets)
                with open(os.getcwd()+'/data/'+location['name']+"-subnets.csv", "a") as f:
                    f.write(csv)
            elif update is True:
                print(location['name'],"Merging",location['name']+"-subnets.csv")
                if loaded == False:
                    with open(os.getcwd()+'/data/'+location['name']+"-subnets.csv", 'r') as f:
                        subnetsCurrentRaw = f.read()
                    subnetsCurrent = self.csvToDict(subnetsCurrentRaw)
                    subnetsCurrentRaw,loaded = True,{}
                for line in subnets.items():
                    subnetsCurrent[line[0]] = line[1]
                if row + 4000 >= length:
                    print(location['name'],"Saving",location['name']+"-subnets.csv")
                    csv = self.dictToCsv(subnetsCurrent)
                    with open(os.getcwd()+'/data/'+location['name']+"-subnets.csv", "w") as f:
                        f.write(csv)
            row += 1000 * multiplicator
            print(location['name'],"Done",row,"of",length)
            if barrier is not False:
                print(location['name'],"Waiting")
                barrier.wait()
            diff = int(datetime.now().timestamp()) - current
            print(location['name'],"Finished in approximately",round(diff * ( (length - row) / (1000 * multiplicator)) / 60),"minute(s)")
        print(location['name'],"Done")

    def checkFiles(self,type="rebuild"):
        run,yall = {},False
        for location in self.locations:
            if os.path.exists(os.getcwd()+'/data/'+location['name']+"-subnets.csv"):
                if yall == False:
                    answer = input(location['name']+"-subnets.csv already exists. Do you want to "+type+"? (y/n): ")
                else:
                    answer = "yall"
                if answer != "y" and answer != "yall": continue
                if answer == "yall": yall = True
                run[location['name']] = "y"
                print(location['name'],"backing up existing file")
                if os.path.exists(os.getcwd()+'/data/'+location['name']+"-subnets.csv.bak") and not yall:
                    answer = input(location['name']+"-subnets.csv.bak already exists. Override? (y/n): ")
                    if answer == "y":
                        copyfile(os.getcwd()+'/data/'+location['name']+"-subnets.csv", os.getcwd()+'/data/'+location['name']+"-subnets.csv.bak")
                else:
                    copyfile(os.getcwd()+'/data/'+location['name']+"-subnets.csv", os.getcwd()+'/data/'+location['name']+"-subnets.csv.bak")
                if type == "rebuild":
                    os.remove((os.getcwd()+'/data/'+location['name']+"-subnets.csv"))
            else:
                run[location['name']] = "y"
        return run

    def geolocate(self):
        print("Geolocate")
        run = self.checkFiles()
        barriers = 0
        for location in self.locations:
            if len(run) > 0 and location['name'] in run: barriers += 1

        barrier = Barrier(barriers)

        self.loadPingable()
        print("Got",str(self.pingableLength),"subnets")

        threads = []
        for location in self.locations:
            if len(run) > 0 and location['name'] in run:
                threads.append(Thread(target=self.fpingLocation, args=([location,barrier,False])))
        self.startJoin(threads)

    def generate(self):
        print("Generate")
        subnets,latency,export = {},{},{}
        print("Preparing Build")
        for location in self.locations:
            print("Loading",location['name']+"-subnets.csv")
            with open(os.getcwd()+'/data/'+location['name']+"-subnets.csv", 'r') as f:
                file = f.read()
            map = {}
            for row in file.splitlines():
                line = row.split(",")
                map[line[0]] = line[1]
            subnets[location['id']] = map
        print("Building geo.mmdb")
        firstNode = self.locations[0]['id']
        for subnet in subnets[firstNode]:
            for location in self.locations:
                if not subnet in subnets[location['id']]:
                    print(f"Warning unable to find {subnet} in {location['country']}")
                    continue
                if subnets[location['id']][subnet] == "retry": continue
                if not subnet in latency: latency[subnet] = {"location":None,"latency":None}
                ms = subnets[location['id']][subnet]
                if latency[subnet]['latency'] == None or float(ms) < float(latency[subnet]['latency']): 
                    latency[subnet] = {"location":location['id'],"latency":ms}
        for subnet,data in latency.items():
            if not data['location'] in export: export[data['location']] = {"subnets":[]}
            export[data['location']]['subnets'].append(subnet)
        print("Saving geo.mmdb")
        writer = MMDBWriter(4, 'GeoIP2-City', languages=['EN'], description="yammdb")
        for location,data in export.items():
            locationData = self.getDataFromLocationID(location)
            writer.insert_network(IPSet(data['subnets']), {'country':{'iso_code':locationData['country']},'location':{"latitude":float(locationData['latitude']),"longitude":float(locationData['longitude'])}})
        writer.to_db_file('geo.mmdb')

    def getDataFromLocationID(self,location):
        for row in self.locations:
            if row['id'] == location: return row

    def followingSub(self,index,dc):
        currentSub = dc[index]['subnet']
        nextSub = dc[index+1]['subnet']
        first, second, third, fourth = currentSub.split('.')
        stops = [1,1,2,4]
        for i in stops:
            third = int(third) + i
            possible = f"{first}.{second}.{third}.{fourth}"
            if possible == nextSub: return True

    def sameTargets(self,targets,nextTargets):
        targetsNextRaw = nextTargets.replace("[","").replace("]","")
        targetsNext = targetsNextRaw.split(",")
        targetsRaw = targets.replace("[","").replace("]","")
        targets = targetsRaw.split(",")
        if targets[:3] == targetsNext[:3]: return True

    def allFollowingSubs(self,dc,current):
        count = 0
        for index in range(current, len(dc) -1):
            if dc[index] == "" or dc[index+1] == "": return count
            if self.followingSub(index,dc): 
                count += 1
            else:
                return count
        return count

    def rerun(self,type="retry",latency=0):
        print("Rerun")

        runs = int(input("How many runs?: "))
        run = self.checkFiles("update")
        barrier = self.barrier(run)

        if os.path.exists(os.getcwd()+"/GeoLite2-Country.mmdb"):
            print("Loading GeoLite2-Country.mmdb")
            reader = geoip2.database.Reader(os.getcwd()+"/GeoLite2-Country.mmdb")
        else:
            print("Could not find GeoLite2-Country.mmdb")

        self.loadPingable()

        current = 0
        while current < runs:
            notPingable = []
            for location in self.locations:
                print("Loading",location['name']+"-subnets.csv")
                with open(os.getcwd()+'/data/'+location['name']+"-subnets.csv", 'r') as f:
                    file = f.read()
                tmp = self.csvToDict(file)
                for line in tmp.items():
                    if type == "retry" and line[1] == "retry":
                        notPingable.append(line[0])
                    if type == "latency" and line[1] != "retry" and float(line[1]) > float(latency):
                        notPingable.append(line[0])
                    if type == "geo" and line[1] != "retry" and float(line[1]) > float(latency):
                        ip = re.sub(r'[0-9]+/[0-9]+', '1', line[0])
                        try:
                            response = reader.country(ip)
                            if location['country'].upper() == response.country.iso_code: notPingable.append(line[0])
                        except Exception as e:
                            print("Skipping",line[0])
            notPingable,tmp = list(set(notPingable)),""
            print("Fetching Random IPs")
            self.notPingable,self.mapping = self.SubnetsToRandomIP(notPingable)
            notPingable = ""

            print("Found",len(self.notPingable),"subnets")
            if len(self.notPingable) == 0: return False

            threads = []
            for location in self.locations:
                if len(run) > 0 and location['name'] in run:
                    threads.append(Thread(target=self.fpingLocation, args=([location,barrier,True])))
            self.startJoin(threads)
            current += 1
