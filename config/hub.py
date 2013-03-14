import os

# Where to save the logs -- let the ics_mhs_root product define it.
logDir = os.path.join(os.environ['ICS_MHS_LOGS_ROOT'], 'tron')

# What file has the passwords.
passwordFile = os.path.join(os.environ['ICS_MHS_TRON_DIR'], 'passwords')

# Which words to load internally.
vocabulary = ('hub', 'keys', 'msg')

# This lists the incoming Nub/ connections we listen on. 
listeners = ('cmdin',
             'client',
             'nclient',
             'TUI')

# This lists all the outgoing actor connections we know how to make.
actors = dict(toy=       dict(host="localhost", port=9000, actorName='toyActor'),
              mps=       dict(host="localhost", port=9001, actorName='mpsActor'),
              mcs=       dict(host="localhost", port=9002, actorName='mcsActor'),
              fil=       dict(host="localhost", port=9004, actorName='filActor'),
              pfics=     dict(host="localhost", port=9005, actorName='pficsActor'),
              archiver=  dict(host="localhost", port=9006, actorName='archiverActor'),
              alarms=    dict(host="localhost", port=9007, actorName='alertsActor'),
              sps1=      dict(host="localhost", port=9011, actorName='spsActor'),
              sps2=      dict(host="localhost", port=9012, actorName='spsActor'),
              sps3=      dict(host="localhost", port=9013, actorName='spsActor'),
              sps4=      dict(host="localhost", port=9014, actorName='spsActor'),
              )

httpHost = 'localhost'
httpRoot = '/'
