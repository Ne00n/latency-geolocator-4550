from Class.geolocator import Geolocator
import sys

print("Geolocator 4550 Premium Edition")
masscanDir = "/masscan/"

geolocator = Geolocator(masscanDir)

if len(sys.argv) == 1:
    print("masscan, fill, geolocate, generate, corrector, generate, debug, rerun, routing, compress")
elif sys.argv[1] == "masscan":
    geolocator.masscan()
elif sys.argv[1] == "fill":
    geolocator.fill()
elif sys.argv[1] == "geolocate":
    geolocator.geolocate()
elif sys.argv[1] == "generate":
    geolocator.generate()
elif sys.argv[1] == "debug":
    geolocator.debug(sys.argv[2])
elif sys.argv[1] == "rerun":
    if len(sys.argv) > 3:
        geolocator.rerun(sys.argv[2],sys.argv[3])
    else:
        geolocator.rerun(sys.argv[2])
elif sys.argv[1] == "routing":
    geolocator.routing()
elif sys.argv[1] == "compress":
    geolocator.compress()
