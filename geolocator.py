from Class.geolocator import Geolocator
import sys

print("Geolocator 4550 Premium Edition")
masscanDir = "/masscan/"

geolocator = Geolocator(masscanDir)

if len(sys.argv) == 1:
    print("masscan, geolocate, generate")
elif sys.argv[1] == "masscan":
    geolocator.masscan()
elif sys.argv[1] == "geolocate":
    geolocator.geolocate()
elif sys.argv[1] == "generate":
    geolocator.generate()
elif sys.argv[1] == "debug":
    geolocator.debug(sys.argv[2])
elif sys.argv[1] == "corrector":
    geolocator.corrector()
