import re
import smtplib
import time
from email.MIMEText import MIMEText

from client import *

class NoteChange(object):
    """ Generate email notifications on some state change. """
    
    def __init__(self, fromAddr, toAddrs, state=None, debug=0):
        """ Track a system's state, and send mail if it changes.

        Args:
           fromAddr	- who the mail should come From:
           toAddrs 	- who the mail should be sent To:
           state	- how we should start off.
           debug	- an integer. 0 = quiet
        """
        
        self.fromAddr = fromAddr
        self.toAddrs = toAddrs
        self.state = state
        self.debug = debug
        
    def note(self, state, msg):
        """ Register a possibly new state, and send email if it has changed.

        Args:
           state	- a string describing our state.
           msg		- details of the state.

        If the given state 
        """
        
        if self.debug > 0:
            print "state=%s self.state=%s" % (state, self.state)
            
        if state != self.state:
            body = MIMEText(msg)
            body['Subject'] = state
            body['From'] = self.fromAddr
            body['To'] = ", ".join(self.toAddrs)
            
            server = smtplib.SMTP('mail.apo.nmsu.edu')
            if self.debug > 0:
                server.set_debuglevel(1)
            server.sendmail(self.fromAddr, self.toAddrs, body.as_string())
            server.close()
   
            self.state = state

# Match the single line '0 TCHECK' reply from the saddlebag.
#
ln2_re = re.compile(r"""
    ^.*HEATER\ VOLTAGE\s*
    (?P<voltage>\S+)\ V                  # Keep
    .*DAC\ SET\ AT[^=]*=\s*              # Skip
    (?P<dacvolts>\S+)\ V                 # Keep
    [^=]*=\s*                            # Skip
    (?P<dactemp>\S+)\ C                  # Keep
    .*MEASURED\s*                        # Skip
    (?P<meastemp>\S+)\ C                 # Keep
    """, re.VERBOSE)

def echelle_ln2stat(note):
    """ Fetch Echelle temperature state, and update the error state. """

    # Get the single reply line
    r = call("echelle", "tcheck:")
    rline = r['lines'][0]['ECHELLETXT']

    # Parse the variables we care about, as numbers.
    match = ln2_re.search(rline)
    if match == None:
        note.note("Echelle temperature parsing problem", "Raw 0 TCHECK reply:\n%s" % (rline))
        return
    
    match_d = match.groupdict()
    voltage = setpoint = meastemp = -9999999
    try:
        voltage = float(match_d['dacvolts'])
        setpoint = int(match_d['dactemp']) + 31
        meastemp = int(match_d['meastemp'])
    except:
        pass

    # Fill in some informative message body.
    msg =  "Echelle temperatures:\n\n"
    msg += "    setpoint = %s\n" % (setpoint)
    msg += "    measured = %s (heater voltage %s V)\n" % (meastemp, voltage)

    # The meat: if the CCD is much warmer than what we asked for, screech.
    #
    if meastemp == -9999999 or meastemp > setpoint + 7:
        note.note("Possible Echelle temperature problem", msg)
    else:
        note.note("Echelle temperatures OK", msg)
        
def echelle_camcheck(note):
    r = call("echelle", "camcheck:")
    rline = r['lines'][0]['ECHELLETXT']

    rline = rline[1:-1]                 # Strip quotes.
    rline = rline.strip()               # Strip WS.

    if rline != "CAMCHECK  ok":
        note.note("Possible Echelle problem", "Raw CAMCHECK output:\n\n%s" % ("\n    ".join(rline.split('\t'))))
    else:
        note.note("Echelle appears OK", rline)


run()
call('hub', 'setProgram APO')
call('hub', 'setUsername check_echelle')

notify = ["cloomis@apo.nmsu.edu",
          "cloomis@pvtnetworks.net",
          "obs-spec@apo.nmsu.edu",
          "mklaene@apo.nmsu.edu"]

ln2Note = NoteChange("cloomis@apo.nmsu.edu", notify, state="Echelle temperatures OK")
camcheckNote = NoteChange("cloomis@apo.nmsu.edu", notify, state="Echelle appears OK")

while 1:
    try:
        echelle_ln2stat(ln2Note)
        echelle_camcheck(camcheckNote)
    except:
        raise

    time.sleep(900)
