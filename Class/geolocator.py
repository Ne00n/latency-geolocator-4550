import ipaddress, random, pyasn, sqlite3, time, sys, re, os
from multiprocessing import Process, Queue
from datetime import datetime
from netaddr import IPNetwork
from threading import Thread
from threading import Barrier
from Class.base import Base
from shutil import copyfile
import geoip2.database

class Geolocator(Base):

    masscanDir,locations,asndb,notPingable,pingableLength = "","","","",0
    connection = sqlite3.connect("file:subnets?mode=memory&cache=shared", uri=True)

    def __init__(self,masscanDir="/masscan/"):
        print("Loading asn.dat")
        self.asndb = pyasn.pyasn(os.getcwd()+'/asn.dat')
        self.masscanDir = os.getcwd()+masscanDir
        print("Loading locations.json")
        self.locations = self.loadJson(os.getcwd()+'/locations.json')

    def loadPingable(self):
        print("Loading pingable.json")
        pingable = self.loadJson(os.getcwd()+'/pingable.json')
        self.pingableLength = len(pingable)
        print("Offloading pingable.json into SQLite Database")
        self.connection.execute("""CREATE TABLE subnets (subnet, ips)""")
        for row in pingable.items():
            self.connection.execute("INSERT INTO subnets VALUES ('"+row[0]+"', '"+','.join(row[1])+"')")
        self.connection.commit()

    def getIPsFromSubnet(self,connection,subnet,start=0,end=0):
        if start != 0 or end != 0:
            return list(connection.execute("SELECT * FROM subnets LIMIT ?,?",(start,end)))
        else:
            return list(connection.execute("SELECT * FROM subnets WHERE subnet=?", (subnet,)))

    def dumpDatabase(self):
        return list(self.connection.execute("SELECT * FROM subnets"))

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

    def masscanFiles(self,files,thread,routing=False):
        list = {}
        for file in files:
            print("Thread "+str(thread),"Loading",file)
            with open(self.masscanDir+file, 'r') as f:
                dump = f.read()
            print("Thread "+str(thread),"Modifying",file)
            dump = re.sub(r'\[\s,', '[', dump)
            dump = dump+"]"
            with open(self.masscanDir+"tmp"+file, 'a') as out:
                out.write(dump)
            print("Thread "+str(thread),"Parsing",file)
            dumpJson = self.loadJson(self.masscanDir+"tmp"+file)
            os.remove(self.masscanDir+"tmp"+file)
            print("Thread "+str(thread),"Building list")
            for line in dumpJson:
                if line['ports'][0]['status'] != "open": continue
                lookup = self.asndb.lookup(line['ip'])
                if lookup[0] == None:
                    print("Thread "+str(thread),"IP not found in asn.dat",line['ip'])
                    continue
                if lookup[1] not in list:
                    list[lookup[1]] = []
                    list[lookup[1]].append(line['ip'])
                    continue
                list[lookup[1]].append(line['ip'])
            print("Thread "+str(thread),"Filtering list")
            for subnet in list:
                network = subnet.split("/")
                if routing is False or int(network[1]) > 64:
                    if len(list[subnet]) < 64: continue
                    list[subnet] = list[subnet][:64]
                else:
                    if len(list[subnet]) < int(3000/thread): continue
                    list[subnet] = list[subnet][:int(3000/thread)]
        print("Thread "+str(thread),"Done, saving file",'tmp'+str(thread)+'-pingable.json')
        self.saveJson(list,os.getcwd()+'/tmp'+str(thread)+'-pingable.json')

    def masscan(self,routing=False):
        print("Generating json")
        files = os.listdir(self.masscanDir)
        filelist,processes,runs = [],[],1
        for file in files:
            if ".json" in file: filelist.append(file)
        print("Found",len(filelist),"file(s)")
        print("Notice: Make sure you got 3GB+ memory available for each process")
        coreCount = int(input("How many processes do you want? suggestion "+str(int(len(os.sched_getaffinity(0)) / 2))+": "))
        split = int(len(filelist) / coreCount)
        diff = len(filelist) - (split * coreCount)
        while runs <= coreCount:
            list = filelist[ (runs -1) *split:( (runs -1) *split)+split]
            if runs == 1 and diff != 0: list.append(filelist[len(filelist)-diff:len(filelist)][0])
            processes.append(Process(target=self.masscanFiles, args=([list,runs,routing])))
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
        print("Filtering list")
        for subnet in pingable:
            network = subnet.split("/")
            if routing is False or int(network[1]) > 64:
                if len(pingable[subnet]) < 64: continue
                pingable[subnet] = pingable[subnet][:64]
            else:
                if len(pingable[subnet]) < 3000: continue
                pingable[subnet] = pingable[subnet][:3000]
        print("Saving","pingable.json")
        self.saveJson(pingable,os.getcwd()+'/pingable.json')

    def getIPs(self,connection,row,length=1000):
        list = []
        pingable = self.getIPsFromSubnet(connection,"",row,length)
        for row in pingable:
            ips = row[1].split(",")
            list.append(ips[0])
        return list

    def SubnetsToRandomIP(self,list,networks):
        mapping,ips = {},[]
        subnetsList = self.dumpDatabase()
        subnets = self.listToDict(subnetsList)
        for subnet in list:
            if subnet not in subnets: continue
            ipaaaays = subnets[subnet].split(",")
            random.shuffle(ipaaaays)
            if subnet not in networks:
                ips.append(random.choice(ipaaaays))
                continue
            subnetIP = random.choice(ipaaaays)
            ips.append(subnetIP)
            mapping[subnetIP] = subnet
            subs = self.networkToSubs(subnet)
            for sub in subs:
                for ip in ipaaaays:
                    if ipaddress.IPv4Address(ip) in ipaddress.IPv4Network(sub):
                        ips.append(ip)
                        mapping[ip] = sub
                        ipaaaays.remove(ip)
                        break
        return ips,mapping

    def mapToSubnet(self,latency,networks,subnetCache):
        subnet = {}
        for ip, ms in latency.items():
            lookup = self.asndb.lookup(ip)
            if lookup[1] not in networks:
                subnet[lookup[1]] = ms
                continue
            if lookup[1] not in subnetCache:
                subnetCache[lookup[1]] = 1
                subnet[lookup[1]] = ms
                continue
            subnet[self.mapping[ip]] = ms
        return subnet,subnetCache

    def fpingLocation(self,location,barrier=False,update=False,routing=False,networks=[]):
        loaded,subnetCache,length,row,map = False,{},self.pingableLength,0,{}
        connection = sqlite3.connect("file:subnets?mode=memory&cache=shared", uri=True)
        if update: length = len(self.notPingable)
        while row < length:
            current = int(datetime.now().timestamp())
            if update is False and routing is False: ips = self.getIPs(connection,row)
            if update is True or routing is True: ips = self.SliceAndDice(self.notPingable,row)
            print(location['name'],"Running fping")
            cmd = "ssh root@"+location['ip']+" fping -c2 "
            cmd += " ".join(ips)
            result = self.cmd(cmd)
            latency = self.getAvrg(result[1])
            subnets,subnetCache = self.mapToSubnet(latency,networks,subnetCache)
            if routing is True:
                map = {**map, **latency}
            elif update is False:
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
                    if line[1] != "retry": subnetsCurrent[line[0]] = line[1]
                print(location['name'],"Saving",location['name']+"-subnets.csv")
                csv = self.dictToCsv(subnetsCurrent)
                with open(os.getcwd()+'/data/'+location['name']+"-subnets.csv", "w") as f:
                    f.write(csv)
            row += 1000
            print(location['name'],"Done",row,"of",length)
            if barrier is not False:
                print(location['name'],"Waiting")
                barrier.wait()
            diff = int(datetime.now().timestamp()) - current
            print(location['name'],"Finished in approximately",round(diff * ( (length - row) / 1000) / 60),"minute(s)")
        print(location['name'],"Done")
        if routing: return map

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
                if os.path.exists(os.getcwd()+'/data/'+location['name']+"-subnets.csv.bak"):
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

    def barrier(self,run):
        print("Waits for the slowest thread, makes measurements more accurate")
        answer = input("Uses barriers? (y/n): ")
        if answer != "y": return False
        barriers = 0
        for location in self.locations:
            if len(run) > 0 and location['name'] in run: barriers += 1

        barrier = Barrier(barriers)
        return barrier

    def geolocate(self):
        print("Geolocate")
        self.loadPingable()
        print("Got",str(self.pingableLength),"subnets")

        barrier = self.barrier(run)
        run = self.checkFiles()

        threads = []
        for location in self.locations:
            if len(run) > 0 and location['name'] in run:
                threads.append(Thread(target=self.fpingLocation, args=([location,barrier,False,False])))
        self.startJoin(threads)

    def generate(self):
        print("Generate")
        print("Loading asn.dat")
        with open(os.getcwd()+'/asn.dat', 'r') as f:
            asn = f.read()
        subnets,routing = {},{}
        for location in self.locations:
            print("Loading",location['name']+"-subnets.csv")
            with open(os.getcwd()+'/data/'+location['name']+"-subnets.csv", 'r') as f:
                file = f.read()
            dict = {}
            for row in file.splitlines():
                line = row.split(",")
                dict[line[0]] = line[1]
            subnets[location['name']] = dict
        lines = asn.splitlines()
        for line in lines:
            data = line.split("\t")
            for location in self.locations:
                if data[0] in subnets[location['name']]:
                    if data[0] not in routing:
                        routing[data[0]] = {}
                        routing[data[0]]['latency'] = subnets[location['name']][data[0]]
                        routing[data[0]]['datacenter'] = location['name']
                        continue
                    if routing[data[0]]['latency'] == "retry" or subnets[location['name']][data[0]] == "retry":
                        print("Skipping",data[0])
                        continue
                    if float(routing[data[0]]['latency']) > float(subnets[location['name']][data[0]]):
                        routing[data[0]]['latency'] = subnets[location['name']][data[0]]
                        routing[data[0]]['datacenter'] = location['name']
                else:
                    print("Could not find",data[0],"in",location['name'])
        export = ""
        print("Saving","db.conf")
        for row in routing.items():
            export += row[0]+" => "+row[1]['datacenter']+"\n"
        with open(os.getcwd()+'/data/dc.conf', 'w+') as out:
            out.write(export)

    def rerun(self,type="retry",latency=0):
        print("Rerun")
        if os.path.exists(os.getcwd()+"/GeoLite2-Country.mmdb"):
            print("Loading GeoLite2-Country.mmdb")
            reader = geoip2.database.Reader(os.getcwd()+"/GeoLite2-Country.mmdb")
        else:
            print("Could not find GeoLite2-Country.mmdb")
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
        self.loadPingable()
        networks = self.loadNetworks()
        print("Fetching Random IPs")
        self.notPingable,self.mapping = self.SubnetsToRandomIP(notPingable,networks)
        notPingable = ""

        print("Found",len(self.notPingable),"subnets")
        if len(self.notPingable) == 0: return False
        barrier = self.barrier(run)
        run = self.checkFiles("update")

        threads = []
        for location in self.locations:
            if len(run) > 0 and location['name'] in run:
                threads.append(Thread(target=self.fpingLocation, args=([location,barrier,True,False,networks])))
        self.startJoin(threads)

    def routingWorker(self,queue,outQueue):
        connection = sqlite3.connect("file:subnets?mode=memory&cache=shared", uri=True)
        while queue.qsize() > 0 :
            subnet = queue.get()
            print(subnet)
            ipsRaw = self.getIPsFromSubnet(connection,subnet)
            if not ipsRaw:
                print("No IPs found for",subnet)
                outQueue.put("")
                continue
            ips = ipsRaw[0][1].split(",")
            ips = sorted(ips, key = ipaddress.IPv4Address)
            networklist = self.networkToSubs(subnet)
            sus = {}
            sus['networks'],sus['ips'] = {},[]
            for net in networklist:
                for index, ip in enumerate(ips):
                    if ipaddress.IPv4Address(ip) in ipaddress.IPv4Network(net):
                        sus['ips'].append(ip)
                        sus['networks'][ip] = {}
                        sus['networks'][ip]['latency'] = 0
                        sus['networks'][ip]['subnet'] = net
                        sus['networks'][ip]['network'] = subnet
                        ips = ips[index:]
                        break
            outQueue.put(sus)
        print("Worker closed")

    def routingLunch(self,queue,outQueue,coreCount,length):
        processes = [Process(target=self.routingWorker, args=(queue,outQueue,)) for _ in range(coreCount)]
        for process in processes:
            process.start()
        map,count = {},0
        map['networks'],map['ips'] = {},[]
        while length != count:
            while not outQueue.empty():
                data = outQueue.get()
                count += 1
                if data == "": continue
                for ip in data['ips']:
                    map['networks'][ip] = data['networks'][ip]
                    map['ips'].append(ip)
            time.sleep(0.05)
        for process in processes:
            process.join()
        return map

    def routing(self):
        queue,outQueue = Queue(),Queue()
        print("Routing")
        print("Loading asn.dat")
        with open(os.getcwd()+'/asn.dat', 'r') as f:
            asn = f.read()
        lines = asn.splitlines()
        subnets = []
        for line in lines:
            data = line.split("\t")
            if len(data) == 1: continue
            net = data[0].split("/")
            if int(net[1]) <= 20: subnets.append(data[0])
        print("Found",len(subnets),"subnets")
        self.loadPingable()
        for subnet in subnets:
            queue.put(subnet)
        coreCount = int(input("How many processes do you want? suggestion "+str(int(len(os.sched_getaffinity(0)) / 2))+": "))
        map = self.routingLunch(queue,outQueue,coreCount,len(subnets))
        random.shuffle(map['ips'])
        self.pingableLength = len(map['ips'])
        self.notPingable = map['ips']
        results = self.fpingLocation(self.locations[0],False,False,True)
        del map['ips']
        for ip,latency in results.items():
            map['networks'][ip]['latency'] = latency
        del results
        data = {}
        for ip,row in map['networks'].items():
            if row['network'] not in data: data[row['network']] = {}
            data[row['network']][ip] = {}
            data[row['network']][ip]['latency'] = row['latency']
            data[row['network']][ip]['subnet'] = row['subnet']
        del map
        networks = []
        for network,ips in data.items():
            initial,flagged = 0,False
            for ip,latency in ips.items():
                if latency['latency'] == "retry": continue
                if initial == 0: initial = float(latency['latency'])
                if float(latency['latency']) > (initial + 20) or float(latency['latency']) < (initial - 20): flagged = True
            if flagged: networks.append(network)
        print("Saving","networks.json")
        self.saveJson(networks,os.getcwd()+'/networks.json')
