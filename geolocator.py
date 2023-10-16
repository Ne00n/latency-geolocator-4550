from Class.geolocator import Geolocator
import sys

print("Geolocator 4550 Premium Edition")
masscanDir = "/masscan/"

geolocator = Geolocator(masscanDir)

if len(sys.argv) == 1:
    print("masscan, fill, geolocate, generate, corrector, generate, debug, rerun, routing, compress")
elif sys.argv[1] == "masscan":
    if len(sys.argv) > 2:
        geolocator.masscan(sys.argv[2])
    else:
        geolocator.masscan()
elif sys.argv[1] == "fill":
    geolocator.fill()
elif sys.argv[1] == "mtr":
    geolocator.mtr()
elif sys.argv[1] == "geolocate":
    geolocator.geolocate()
elif sys.argv[1] == "generate":
    if len(sys.argv) > 2:
        geolocator.generate(sys.argv[2])
    else:
        geolocator.generate()
elif sys.argv[1] == "debug":
    geolocator.debug(sys.argv[2])
elif sys.argv[1] == "rerun":
    if len(sys.argv) > 3:
        geolocator.rerun(sys.argv[2],sys.argv[3])
    else:
        geolocator.rerun(sys.argv[2])