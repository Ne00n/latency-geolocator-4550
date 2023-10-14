import ipaddress, in_place, random, pyasn, sqlite3, time, json, math, sys, re, os
from concurrent.futures import ProcessPoolExecutor as Pool
from aggregate_prefixes import aggregate_prefixes
from multiprocessing import Process, Queue
from netaddr import IPNetwork, IPSet
from mmdb_writer import MMDBWriter
from functools import partial
from datetime import datetime
from netaddr import IPNetwork
from threading import Thread
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
        print("Loading mtr.json")
        self.mtrLocations = self.loadJson(os.getcwd()+'/mtr.json')

    def loadPingable(self,offloading=True):
        print("Loading pingable.json")
        pingable = self.loadJson(os.getcwd()+'/pingable.json')
        if offloading is False:
            self.pingable = pingable
            return
        print("Offloading pingable.json into SQLite Database")
        self.connection.execute("""CREATE TABLE subnets (subnet, sub, ips)""")
        self.pingableLength = 0
        for subnet in pingable:
            for sub,ips in pingable[subnet].items():
                ips = ','.join(ips)
                if ips: 
                    self.pingableLength += 1
                    self.connection.execute(f"INSERT INTO subnets VALUES ('{subnet}','{sub}', '{ips}')")
        self.connection.commit()

    @staticmethod
    def getIPsFromSubnet(connection,subnet,start=0,end=0):
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
                        if not lookup[1] in dataList: dataList[lookup[1]] = {}
                        currentSub = lookup[1]
                        if not dataList[lookup[1]]:
                            for sub in subsCache[lookup[1]]: dataList[lookup[1]][sub] = []
                    sub, prefix = lookup[1].split("/")
                    if int(prefix) == 24:
                        if len(dataList[lookup[1]][lookup[1]]) > 20: continue
                        #only append last octet
                        dataList[lookup[1]][lookup[1]].append(ip.split(".")[-1])
                        continue
                    else:
                        for sub in list(subsCache[lookup[1]]):
                            if ipaddress.IPv4Address(ip) in ipaddress.IPv4Network(sub):
                                if len(dataList[lookup[1]][sub]) > 20: 
                                    subsCache[lookup[1]].remove(sub)
                                    break
                                #only append last octet 
                                dataList[lookup[1]][sub].append(ip.split(".")[-1])
                                break
                            else:
                                #since its a ordered list of ips, we can just drop any subnets that we have no data on
                                subsCache[lookup[1]].remove(sub)
            diff += int(datetime.now().timestamp()) - current
            devidor = 1 if index == 0 else index
            print(f"Thread {thread} Finished in approximately {round((diff / devidor) * (len(files) - index) / 60)} minute(s)")
        print("Thread "+str(thread),"Done, saving file",'tmp'+str(thread)+'-pingable.json')
        self.saveJson(dataList,os.getcwd()+'/tmp'+str(thread)+'-pingable.json')

    def masscan(self,coreCount=None):
        print("Generating json")
        files = os.listdir(self.masscanDir)
        filelist,processes,runs = [],[],1
        for file in files:
            if os.stat(f"{self.masscanDir}/{file}").st_size == 0:
                print(f"Skipping empty file {file}")
                continue
            if file.endswith(".json") or  file.endswith(".txt"): filelist.append(file)
        print("Found",len(filelist),"file(s)")
        if coreCount == None:
            print("Notice: Make sure you got 1GB of memory available for each process")
            coreCount = int(input("How many processes do you want? suggestion "+str(int(len(os.sched_getaffinity(0)) / 2))+": "))
        print(f"Using {coreCount} Cores")
        split = int(len(filelist) / int(coreCount))
        diff = len(filelist) - (split * int(coreCount))
        while runs <= int(coreCount):
            list = filelist[ (runs -1) *split:( (runs -1) *split)+split]
            if runs == 1 and diff != 0: list.append(filelist[len(filelist)-diff:len(filelist)][0])
            processes.append(Process(target=self.masscanFiles, args=([list,runs])))
            runs += 1
        self.startJoin(processes)
        print("Merging files")
        runs,pingable = 1,{}
        while runs <= int(coreCount):
            print("Loading","tmp"+str(runs)+"-pingable.json")
            file = self.loadJson(os.getcwd()+'/tmp'+str(runs)+'-pingable.json')
            pingable = {**pingable, **file}
            os.remove(os.getcwd()+'/tmp'+str(runs)+'-pingable.json')
            runs  += 1
        print("Saving","pingable.json")
        self.saveJson(pingable,os.getcwd()+'/pingable.json')

    @staticmethod
    def getIPsSimple(connection,start=0,end=0):
        return list(connection.execute("SELECT * FROM subnets LIMIT ?,?",(start,end)))

    @staticmethod
    def getIPs(connection,row,length=1000):
        ips,mapping = [],{}
        pingable = Geolocator.getIPsFromSubnet(connection,"",row,length)
        for row in pingable:
            data = row[2].split(",")
            for index, ip in enumerate(data):
                if ip == "": continue
                ips.append(ip)
                mapping[ip] = row[1]
                if index == 0: break
        return ips,mapping

    def SubnetsToRandomIP(self,list,blacklist=[]):
        mapping,ips = {},[]
        blacklistSet = set(blacklist)
        #get the full pingable.json
        subnetsList = self.dumpDatabase()
        subnets = Geolocator.listToDict(subnetsList)
        #go through the subnets we should get a random ip for
        for subnet in list:
            #if the subnet is not in the pingable.json ignore it
            if subnet not in subnets: continue
            #get a list of the pingable ip's from that subnet
            ipaaaays = subnets[subnet].split(",")
            #get random ip
            for runs in range(3):
                randomIP = random.choice(ipaaaays)
                if randomIP in blacklistSet: continue
                ips.append(randomIP)
                mapping[randomIP] = subnet
                break
        return ips,mapping

    @staticmethod
    def fpingLocation(location,barrier=False,update=False,length=0,notPingable=[],mapping={},multiplicator=1,batchSize=1000):
        row,map,failedIPs,subnets,networks = 0,{},[],{},{}
        connection = sqlite3.connect("file:subnets?mode=memory&cache=shared", uri=True)
        while row < length:
            current = int(datetime.now().timestamp())
            if update is False:  ips,mapping = Geolocator.getIPs(connection,row,batchSize * multiplicator)
            if update is True: ips = Geolocator.SliceAndDice(notPingable,row,batchSize * multiplicator)
            if ips:
                command,commands = f"ssh {location['user']}@{location['ip']} python3 fping.py",[]
                loops = math.ceil(len(ips) / batchSize )
                for index in range(0,loops):
                    if ips[index*batchSize:(index+1)*batchSize]: commands.append(f"{command} {' '.join(ips[index*batchSize:(index+1)*batchSize])}")
                print(location['name'],f"Running fping with {multiplicator} threads and {len(commands)} batches")
                pool = multiprocessing.Pool(processes = multiplicator)
                results = pool.map(Geolocator.cmd, commands)
                latency = Geolocator.getAvrg(results)
                if not latency:
                    for ip in ips:
                        latency[mapping[ip]] = "retry"
                subnets,networks = Geolocator.mapToSubnet(latency,mapping,subnets,networks)
                if row + (batchSize * multiplicator) >= length or row % ((batchSize * multiplicator) * 20) == 0:
                    if update is False:
                        print(location['name'],"Updating",location['name']+"-subnets.csv")
                        csv = Geolocator.dictToCsv(subnets)
                        with open(os.getcwd()+'/data/'+location['name']+"-subnets.csv", "a+") as f:
                            f.write(csv)
                    elif update is True:
                            print(location['name'],"Merging",location['name']+"-subnets.csv")
                            #read line by line, to avoid memory fuckery
                            with in_place.InPlace(os.getcwd()+'/data/'+location['name']+"-subnets.csv") as fp:
                                for line in fp:
                                    if not "," in line: continue
                                    prefix, latency = line.split(",")
                                    if prefix in subnets: 
                                        fp.write(f"{prefix},{subnets[prefix]}\n")
                                        if "retry" == subnets[prefix]: failedIPs.append(networks[prefix])
                                    else:
                                        fp.write(line)
                    subnets,networks = {},{}
            row += batchSize * multiplicator
            print(location['name'],"Done",row,"of",length)
            if barrier is not False:
                print(location['name'],"Waiting")
                barrier.wait()
            diff = int(datetime.now().timestamp()) - current
            print(location['name'],"Finished in approximately",round(diff * ( (length - row) / (1000 * multiplicator)) / 60),"minute(s)")
        print(location['name'],"Done")
        return failedIPs

    @staticmethod
    def mtrLocation(location,barrier,length,locations,update=False,parallel=12,multiplicator=1):
        try:
            connection = sqlite3.connect("file:subnets?mode=memory&cache=shared", uri=True)
            part = (length / locations)
            ips,row,count = [],0,0
            row = round(part * (int(location['id']) -1))
            length = round(part * (int(location['id']) +1))
            while row < length:
                current = int(datetime.now().timestamp())
                targets = Geolocator.getIPsSimple(connection,row,100 * multiplicator)
                command,commands = f"ssh {location['user']}@{location['ip']} mtr --report --report-cycles 1 --no-dns --gracetime 1 ",[]
                for target in targets:
                    targetIP = target[1] 
                    commands.append([command,targetIP])
                print(location['name'],f"Running mtr with {parallel} threads and {len(commands)} batches")
                pool = multiprocessing.Pool(processes = parallel)
                for i in range(3):
                    results = pool.map(Geolocator.cmdInitial, commands)
                    mtrs = Geolocator.parseMTR(results)
                    response = Geolocator.getLastIP(mtrs)
                    if response: 
                        ips.extend(response)
                        break
                    print(location['name'],f"Retrying mtr in 10s")
                    time.sleep(10)
                if row + (100 * multiplicator) >= length or count % ((100 * multiplicator) * 10) == 0:
                    if update is False:
                        print(location['name'],"Updating",location['name']+"-subnets.csv")
                        csv = Geolocator.listToCsv(ips)
                        with open(os.getcwd()+'/mtr/'+location['name']+"-subnets.csv", "a+") as f:
                            f.write(csv)
                        ips = []
                row += 100 * multiplicator
                count += 100
                print(location['name'],"Done",row,"of",length)
                diff = int(datetime.now().timestamp()) - current
                print(location['name'],"Finished in approximately",round(diff * ( (length - row) / (100 * multiplicator)) / 60),"minute(s)")
                #print(location['name'],"Waiting")
                #barrier.wait()
        except Exception as err:
            print("Error",err)

    def checkFiles(self,type="rebuild",yall=False):
        run = {}
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

        barrier = multiprocessing.Barrier(barriers)

        self.loadPingable()
        print("Got",str(self.pingableLength),"subnets")
        print("Preflight")
        for location in self.locations:
            print(f"Checking {location['name']} {location['ip']}")
            command = f"ssh {location['user']}@{location['ip']}"
            result = Geolocator.cmdInitial([command,"fping -c1 1.1.1.1"])
            if not result[0]:
                print(location)
                exit(result)
            self.cmd(f"scp fping.py {location['user']}@{location['ip']}:/home/{location['user']}/")
            result = Geolocator.cmdInitial([command,"ls"])

        threads = []
        for location in self.locations:
            if len(run) > 0 and location['name'] in run:
                threads.append(Thread(target=Geolocator.fpingLocation, args=([location,barrier,False,self.pingableLength])))
        self.startJoin(threads)

    def mtrGenerate(self):
        print("Generate")
        subnets,latency,export = {},{},{}
        print("Preparing Build")
        subnets = self.getLocationMap()
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
        print("Building export list")
        gap = {}
        for subnet,data in latency.items():
            ms = int(float(data['latency']))
            if not data['location'] in export: export[data['location']] = {}
            if not ms in export[data['location']]: export[data['location']][ms] = {"subnets":[]}
            export[data['location']][ms]['subnets'].append(subnet)
            ip, prefix = subnet.split("/")
            if int(prefix) < 24:
                lookup = self.asndb.lookup(ip)
                if lookup[0] == None: continue
                ip, prefix = lookup[1].split("/")
                if int(prefix) > 23: continue
                if not lookup[1] in gap: gap[lookup[1]] = {}
                gap[lookup[1]][subnet] = {"location":data['location'],'ms':ms}
        print("Filling the gaps")
        for subnet,data in gap.items():
            subs,last = self.networkToSubs(subnet),""
            for sub in subs:
                if sub in gap[subnet]:
                    last = sub
                else:
                    if last == "": last = next(iter(data))
                    subData = data[last]
                    export[subData['location']][subData['ms']]['subnets'].append(sub)
        print("Saving geoLite.mmdb")
        writer = MMDBWriter(4, 'GeoIP2-City', languages=['EN'], description="yammdb")
        for location,latency in export.items():
            locationData = self.getDataFromLocationID(location)
            for ms,subnets in latency.items():
                info = {'country':{'iso_code':locationData['country']},
                        'continent':{'code':locationData['continent']},
                        'location':{"accuracy_radius":float(ms),"latitude":float(locationData['latitude']),"longitude":float(locationData['longitude'])}}
                writer.insert_network(IPSet(subnets['subnets']), info)
        print("Writing geoLite.mmdb")
        writer.to_db_file('geoLite.mmdb')
        print("Preparing mmdb")
        query = geoip2.database.Reader("geoLite.mmdb")
        print("Preparing Build")
        ips = []
        for location in self.locations:
            print("Loading",location['name']+"-subnets.csv")
            with open(os.getcwd()+'/mtr/'+location['name']+"-subnets.csv", 'r') as f:
                file = f.read()
            for row in file.splitlines():
                line = row.split(",")
                ips.append([line[0],line[1]])
        print("Building export list")
        for ip in ips:
            try:
                response = query.city(ip[1])
                lookup = self.asndb.lookup(ip[1])
                if lookup[0] == None: continue
                ms = int(float(response.location.accuracy_radius))
                geo = f"{response.location.latitude},{response.location.longitude}"
                if not geo in export: export[geo] = {}
                if not ms in export[geo]: export[geo][ms] = {"continent":response.continent.code,"country":response.country.iso_code,"subnets":[]}
                export[geo][ms]['subnets'].append(lookup[1])
            except Exception as e:
                continue
        print("Saving geo.mmdb")
        writer = MMDBWriter(4, 'GeoIP2-City', languages=['EN'], description="yammdb")
        for location,latency in export.items():
            locationData = self.getDataFromLocationID(location)
            for ms,subnets in latency.items():
                info = {'country':{'iso_code':locationData['country']},
                        'continent':{'code':locationData['continent']},
                        'location':{"accuracy_radius":float(ms),"latitude":float(locationData['latitude']),"longitude":float(locationData['longitude'])}}
                writer.insert_network(IPSet(subnets['subnets']), info)
        print("Writing geo.mmdb")
        writer.to_db_file('geo.mmdb')
        print("Writing geo.csv")
        csv = "Subnet,Continent,Country,Latitude,Longitude,Latency\n"
        for location,latency in export.items():
            locationData = self.getDataFromLocationID(location)
            for ms,data in latency.items():
                for subnet in data['subnets']:
                    csv += f"{subnet},{locationData['continent']},{locationData['country']},{locationData['latitude']},{locationData['longitude']},{ms}\n"
        with open("geo.csv", "w+") as f: f.write(csv)

    def getCords(self,cords):
        closestCords = ""
        for index, (locationID,latency) in enumerate(cords.items()):
            closestData = self.getDataFromLocationID(locationID)
            closestCords += f"{closestData['latitude']} {closestData['longitude']}"
            if index == 2: break
            if index != len(cords) -1: closestCords += ","
        return closestCords

    def generate(self):
        print("Generate")
        latency,export = {},{}
        print("Building latency dict")
        for location in self.locations:
            current = self.getLocationPart(location['name'])
            for subnet,ms in current.items():
                if current[subnet] == "retry": continue
                if not subnet in latency: latency[subnet] = {}
                latency[subnet][location['id']] = float(ms)
                latency[subnet] = dict(sorted(latency[subnet].items(), key=lambda item: item[1]))
                #we only need the lowest anyway
                latency[subnet] = {list(latency[subnet].keys())[0]:list(latency[subnet].values())[0]}
        print("Building export list")
        gap = {}
        for subnet,data in latency.items():
            location = list(data)[0]
            latency = data[location]
            cords = self.getCords(data)
            if not location in export: export[location] = {}
            if not cords in export[location]: export[location][cords] = {}
            if not latency in export[location][cords]: export[location][cords][latency] = []
            export[location][cords][latency].append(subnet)
            ip, prefix = subnet.split("/")
            if int(prefix) < 24:
                lookup = self.asndb.lookup(ip)
                if lookup[0] == None: continue
                ip, prefix = lookup[1].split("/")
                if int(prefix) > 23: continue
                if not lookup[1] in gap: gap[lookup[1]] = {}
                gap[lookup[1]][subnet] = {"location":location,'latency':latency,"closest":data}
        latency = {}
        print("Filling the gaps")
        for subnet,data in gap.items():
            subs,last = self.networkToSubs(subnet),""
            for sub in subs:
                if sub in gap[subnet]:
                    last = sub
                else:
                    if last == "": last = next(iter(data))
                    subData = data[last]
                    cords = self.getCords(subData['closest'])
                    export[subData['location']][cords][subData['latency']].append(sub)
        gap = {}
        print("Saving geo.mmdb")
        writer = MMDBWriter(4, 'GeoIP2-City', languages=['EN'], description="yammdb")
        for location,cords in export.items():
            locationData = self.getDataFromLocationID(location)
            for cord, latency in cords.items():
                for ms,subnets in latency.items():
                    info = {'country':{'iso_code':locationData['country']},
                            'continent':{'code':locationData['continent']},
                            'location':{"accuracy_radius":float(ms),"latitude":float(locationData['latitude']),"longitude":float(locationData['longitude'])},
                            'city':{"geoname_id":cord}}
                    writer.insert_network(IPSet(subnets), info)
        print("Writing geo.mmdb")
        writer.to_db_file('geo.mmdb')
        print("Writing geo.csv")
        csv = "Subnet,Continent,Country,Latitude,Longitude,Latency\n"
        for location,cords in export.items():
            locationData = self.getDataFromLocationID(location)
            for cord, latency in cords.items():
                for ms,subnets in latency.items():
                    for subnet in subnets:
                        csv += f"{subnet},{locationData['continent']},{locationData['country']},{locationData['latitude']},{locationData['longitude']},{ms}\n"
        with open("geo.csv", "w+") as f: f.write(csv)
        return export

    def getDataFromLocationID(self,location):
        for row in self.locations:
            if row['id'] == location: return row

    def mtr(self):
        print("Preparing")
        subnets,possibleTargets,targets = {},{},[]
        subnets = self.getLocationMap()
        for location,data in subnets.items():
            for subnet,latency in data.items():
                if not subnet in possibleTargets: possibleTargets[subnet] = 0
                possibleTargets[subnet] = possibleTargets[subnet] +1
        print(f"Found {len(possibleTargets)} possible targets")

        subnets = {}
        for subnet,count in possibleTargets.items():
            if count == len(self.locations): targets.append(subnet)
        print(f"Found {len(targets)} targets")

        possibleTargets = {}
        manager = multiprocessing.Manager()
        barrier = manager.Barrier(len(self.mtrLocations))

        print("Offloading Query list")
        self.connection.execute("""CREATE TABLE subnets (subnet, ip)""")
        length = 0
        for subnet in targets:
            ip, prefix = subnet.split("/")
            ip = ip[:-1]
            ip = f"{ip}1"
            self.connection.execute(f"INSERT INTO subnets VALUES ('{subnet}','{ip}')")
            length += 1
        self.connection.commit()

        targets = {}
        print(f"Found {length} subnets")

        pool = Pool(max_workers = len(self.mtrLocations))
        mtr = partial(self.mtrLocation, barrier=barrier,length=length,locations=len(self.mtrLocations))
        pool.map(mtr, self.mtrLocations)
        #wait for everything
        pool.shutdown(wait=True)

    def rerun(self,type="retry",latency=0):
        print("Rerun")

        run = self.checkFiles("update",True)
        manager = multiprocessing.Manager()
        barrier = manager.Barrier(len(self.locations))

        if os.path.exists(os.getcwd()+"/GeoLite2-Country.mmdb"):
            print("Loading GeoLite2-Country.mmdb")
            reader = geoip2.database.Reader(os.getcwd()+"/GeoLite2-Country.mmdb")
        else:
            print("Could not find GeoLite2-Country.mmdb")

        self.loadPingable()

        current,runs,failedIPs = 0,1,[]
        if type == "retry" and float(latency) > 0: runs = float(latency)
        print(f"Running {runs} times")
        while current < runs:
            notPingable = []
            for location in self.locations:
                print("Loading",location['name']+"-subnets.csv")
                with open(os.getcwd()+'/data/'+location['name']+"-subnets.csv") as file:
                    for line in file:
                        line = line.rstrip()
                        if not "," in line: continue
                        prefix, ms = line.split(",")
                        if type == "retry" and ms == "retry":
                            notPingable.append(prefix)
                        if type == "latency" and ms != "retry" and float(ms) > float(latency):
                            notPingable.append(prefix)
                        if type == "geo" and ms != "retry" and float(ms) > float(latency):
                            ip = re.sub(r'[0-9]+/[0-9]+', '1', prefix)
                            try:
                                response = reader.country(ip)
                                if location['country'].upper() == response.country.iso_code: notPingable.append(prefix)
                            except Exception as e:
                                print("Skipping",prefix)
            notPingable,tmp = list(set(notPingable)),""
            print("Fetching Random IPs")
            self.notPingable,self.mapping = self.SubnetsToRandomIP(notPingable,failedIPs)
            notPingable = ""

            print("Found",len(self.notPingable),"subnets")
            if len(self.notPingable) == 0: return False

            pool = Pool(max_workers = len(self.locations))
            fping = partial(self.fpingLocation, barrier=barrier,update=True,length=len(self.notPingable),notPingable=self.notPingable,mapping=self.mapping)
            results = pool.map(fping, self.locations)
            #wait for everything
            pool.shutdown(wait=True)
            print("Processing ips")
            ips = {}
            #if we crash here, likely a exception crashed the thread in the pool
            for result in results:
                for ip in result:
                    if not ip in ips: ips[ip] = 0
                    ips[ip] += 1
            for ip,count in ips.items():
                if count == len(self.locations):
                    failedIPs.append(ip)
            failedIPs = list(set(failedIPs))
            current += 1