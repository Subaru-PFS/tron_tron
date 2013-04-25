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
# For the PFS MHS, all the current actors use the same connection protocol, so we hand off 
# to a single manager, which reads this dictionary.
actors = dict(iic=       dict(host="localhost", port=9000, actorName='mhsActor'),

              mps=       dict(host="localhost", port=9001, actorName='mhsActor'),
              mcs=       dict(host="localhost", port=9002, actorName='mhsActor'),
              gen2=      dict(host="localhost", port=9003, actorName='mhsActor'),
              pfics=     dict(host="localhost", port=9005, actorName='mhsActor'),

              archiver=  dict(host="localhost", port=9006, actorName='mhsActor'),
              alarms=    dict(host="localhost", port=9007, actorName='mhsActor'),

              sps1=      dict(host="localhost", port=9011, actorName='mhsActor'),
              sps2=      dict(host="localhost", port=9012, actorName='mhsActor'),
              sps3=      dict(host="localhost", port=9013, actorName='mhsActor'),
              sps4=      dict(host="localhost", port=9014, actorName='mhsActor'),

              cam1=      dict(host="localhost", port=9021, actorName='mhsActor'),
              cam2=      dict(host="localhost", port=9022, actorName='mhsActor'),
              cam3=      dict(host="localhost", port=9023, actorName='mhsActor'),
              cam4=      dict(host="localhost", port=9024, actorName='mhsActor'),

              foo7=      dict(host="localhost", port=9997, actorName='mhsActor'),
              foo8=      dict(host="localhost", port=9998, actorName='mhsActor'),
              foo9=      dict(host="localhost", port=9999, actorName='mhsActor'),
              )

httpHost = 'localhost'
httpRoot = '/'
