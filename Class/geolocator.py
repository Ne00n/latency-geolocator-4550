import subprocess, ipaddress, random, pyasn, sqlite3, netaddr, time, json, sys, re, os
from multiprocessing import Process, Queue
from datetime import datetime
from netaddr import IPNetwork
from threading import Thread
from shutil import copyfile
import geoip2.database

class Geolocator:

    masscanDir,locations,asndb,notPingable,pingableLength = "","","","",0
    connection = sqlite3.connect("file:subnets?mode=memory&cache=shared", uri=True)

    def __init__(self,masscanDir="/masscan/"):
        print("Loading asn.dat")
        self.asndb = pyasn.pyasn(os.getcwd()+'/asn.dat')
        self.masscanDir = os.getcwd()+masscanDir
        print("Loading locations.json")
        with open(os.getcwd()+"/locations.json", 'r') as f:
            self.locations = json.load(f)

    def loadPingable(self):
        print("Loading pingable.json")
        with open(os.getcwd()+"/pingable.json", 'r') as f:
            pingable = json.load(f)
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

    def cmd(self,cmd):
        p = subprocess.run(cmd, stdin=None, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        return [p.stdout.decode('utf-8'),p.stderr.decode('utf-8')]

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
            with open(self.masscanDir+"tmp"+file, 'r') as f:
                dumpJson = json.load(f)
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
                if routing is False or int(network[1]) > 20:
                    if len(list[subnet]) < 50: continue
                    list[subnet] = list[subnet][:50]
                else:
                    if len(list[subnet]) < int(2000/thread): continue
                    list[subnet] = list[subnet][:int(2000/thread)]
        print("Thread "+str(thread),"Done, saving file",'tmp'+str(thread)+'-pingable.json')
        with open(os.getcwd()+'/tmp'+str(thread)+'-pingable.json', 'w') as f:
            json.dump(list, f)

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
        for process in processes:
            process.start()
        for process in processes:
            process.join()
        print("Merging files")
        runs,pingable = 1,{}
        while runs <= coreCount:
            print("Loading","tmp"+str(runs)+"-pingable.json")
            with open(os.getcwd()+'/tmp'+str(runs)+'-pingable.json', 'r') as f:
                file = json.load(f)
                pingable = {**pingable, **file}
                os.remove(os.getcwd()+'/tmp'+str(runs)+'-pingable.json')
            runs  += 1
        print("Filtering list")
        for subnet in pingable:
            network = subnet.split("/")
            if routing is False or int(network[1]) > 20:
                if len(pingable[subnet]) < 50: continue
                pingable[subnet] = pingable[subnet][:50]
            else:
                if len(pingable[subnet]) < 2000: continue
                pingable[subnet] = pingable[subnet][:2000]
        print("Saving","pingable.json")
        with open(os.getcwd()+'/pingable.json', 'w') as f:
            json.dump(pingable, f)

    def getIPs(self,connection,row,length=1000):
        list = []
        pingable = self.getIPsFromSubnet(connection,"",row,length)
        for row in pingable:
            ips = row[1].split(",")
            list.append(ips[0])
        return list

    def SliceAndDice(self,notPingable,row):
        if row + 1000 > len(notPingable):
            maximale = len(notPingable)
        else:
            maximale = row + 1000
        return notPingable[row:maximale]

    def SubnetsToRandomIP(self,list):
        ips = []
        subnetsList = self.dumpDatabase()
        subnets = self.listToDict(subnetsList)
        for subnet in list:
            if subnet in subnets:
                ipaaaays = subnets[subnet].split(",")
                ips.append(random.choice(ipaaaays))
        return ips

    def getAvrg(self,result):
        latency = {}
        parsed = re.findall("([0-9.]+).*?:.*?([0-9+])%(.*?\/([0-9.]+))?",result, re.MULTILINE)
        for row in parsed:
            if row[3] != "":
                latency[row[0]] = row[3]
            else:
                latency[row[0]] = "retry"
        return latency

    def mapToSubnet(self,latency):
        subnet = {}
        for ip, ms in latency.items():
            lookup = self.asndb.lookup(ip)
            subnet[lookup[1]] = ms
        return subnet

    def csvToDict(self,csv):
        dict = {}
        for row in csv.splitlines():
            line = row.split(",")
            dict[line[0]] = line[1]
        return dict

    def dictToCsv(self,dict):
        csv = ""
        for line in dict.items():
            csv += str(line[0])+","+str(line[1])+"\n"
        return csv

    def listToDict(self,list,index=0,data=1):
        dict = {}
        for row in list:
            dict[row[index]] = row[data]
        return dict

    def fpingLocation(self,location,update=False,routing=False):
        length,row,map = self.pingableLength,0,{}
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
            subnets = self.mapToSubnet(latency)
            if routing is True:
                map = {**map, **latency}
            elif update is False:
                print(location['name'],"Updating",location['name']+"-subnets.csv")
                csv = self.dictToCsv(subnets)
                with open(os.getcwd()+'/data/'+location['name']+"-subnets.csv", "a") as f:
                    f.write(csv)
            elif update is True:
                print(location['name'],"Merging",location['name']+"-subnets.csv")
                with open(os.getcwd()+'/data/'+location['name']+"-subnets.csv", 'r') as f:
                    subnetsCurrentRaw = f.read()
                subnetsCurrent = self.csvToDict(subnetsCurrentRaw)
                subnetsCurrentRaw = ""
                for line in subnets.items():
                    if line[1] != "retry": subnetsCurrent[line[0]] = line[1]
                print(location['name'],"Saving",location['name']+"-subnets.csv")
                csv = self.dictToCsv(subnetsCurrent)
                with open(os.getcwd()+'/data/'+location['name']+"-subnets.csv", "w") as f:
                    f.write(csv)
            row += 1000
            print(location['name'],"Done",row,"of",length)
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

    def geolocate(self):
        print("Geolocate")
        self.loadPingable()
        print("Got",str(self.pingableLength),"subnets")

        run = self.checkFiles()

        threads = []
        for location in self.locations:
            if len(run) > 0 and location['name'] in run:
                threads.append(Thread(target=self.fpingLocation, args=([location])))
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

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
                    else:
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
        print("Fetching Random IPs")
        self.notPingable = self.SubnetsToRandomIP(notPingable)
        notPingable = ""

        print("Found",len(self.notPingable),"subnets")
        if len(self.notPingable) == 0: return False
        run = self.checkFiles("update")

        threads = []
        for location in self.locations:
            if len(run) > 0 and location['name'] in run:
                threads.append(Thread(target=self.fpingLocation, args=([location,True])))
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

    def routingWorker(self,queue,outQueue):
        cache = []
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
            network = netaddr.IPNetwork(subnet)
            networklist = [str(sn) for sn in network.subnet(21)]
            sus = {}
            sus['networks'],sus['ips'] = {},[]
            for net in networklist:
                if net in cache: continue
                for ip in ips:
                    if net in cache: break
                    if ipaddress.IPv4Address(ip) in ipaddress.IPv4Network(net):
                        sus['ips'].append(ip)
                        sus['networks'][ip] = {}
                        sus['networks'][ip]['latency'] = 0
                        sus['networks'][ip]['subnet'] = net
                        sus['networks'][ip]['network'] = subnet
                        cache.append(net)
                        ips.remove(ip)
            outQueue.put(sus)
        print("Worker closed")

    def routingLunch(self,queue,outQueue,coreCount,length):
        processes = [Process(target=self.routingWorker, args=(queue,outQueue,)) for _ in range(coreCount)]
        for process in processes:
            process.start()
        map,count = {},0
        while length != count:
            while not outQueue.empty():
                data = outQueue.get()
                count += 1
                if data == "": continue
                map = {**map, **data}
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
            if int(net[1]) >= 14 and int(net[1]) <= 20: subnets.append(data[0])
        print("Found",len(subnets),"subnets")
        self.loadPingable()
        for subnet in subnets:
            queue.put(subnet)
        coreCount = int(input("How many processes do you want? suggestion "+str(int(len(os.sched_getaffinity(0)) / 2))+": "))
        map = self.routingLunch(queue,outQueue,coreCount,len(subnets))
        random.shuffle(map['ips'])
        self.pingableLength = len(map['ips'])
        self.notPingable = map['ips']
        results = self.fpingLocation(self.locations[0],False,True)
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
        with open(os.getcwd()+'/networks.json', 'w') as f:
            json.dump(networks, f)
