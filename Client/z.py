import time

from client import *

def checkTemps():
    reply = call('echelle', 'tcheck:')
    print reply
    
run(debug=0)
hub("setProgram APO")

while 1:
    checkTemps()
    time.sleep(15)




