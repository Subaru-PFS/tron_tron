import telnetlib
from traceback import print_exc
import time
from telmech import DEBUG, DEBUG_EXC

tn = None

def logout (host, port):
    global tn
    DEBUG('logging out tcc_encl')
    try:
        tn = telnetlib.Telnet(host,2000)
        #tn.set_debuglevel(5)
        time.sleep(0.5)
        tn.write('\r')
        tn.read_until('#',4)
        tn.write('access\r')
        tn.read_until('Enter username> ',4)
        tn.write('host-session\r')
        tn.read_until('Xyplex> ',4)
        tn.write('set priv\r')
        tn.read_until('Password> ',4)
        tn.write('%s\r' % ('208volts'))
        tn.read_until('Xyplex>> ',4)
        tn.write('logout port %d\r' % port)
        tn.read_until('Xyplex>> ',4)
        time.sleep(0.5)
        tn.write('logout\r')
    except:
        raise 'failed to logout tcc_encl port'
    DEBUG('successfully logged out tcc_encl')


def call(msg):
    global tn
    msg = msg.upper()
    if not tn:
        try:
            tn = telnetlib.Telnet('tccserv35m',3100)
        except:
            DEBUG_EXC()
            #raise '''Failed to login to telnet enclosure controller.'''
            DEBUG('failed to login to tcc_encl, logout')
            logout('tccserv35m', 11)
            time.sleep(1.5)
            tn = telnetlib.Telnet('tccserv35m',3100)
            time.sleep(0.5)
            DEBUG('Connected to tcc_encl')
    
    tn.write(msg+'\r')
    DEBUG('send message: %s' % (msg))
    reply = tn.read_until('OK',1.0)
    parts = reply.split('\r')
    reply = parts[-1]
    index = reply.find(' OK')
    DEBUG('reply is: %s' % (reply[:index]))
    #tn.close()
    return reply[:index]
