import os

# Where to save the logs
logDir = '/data/logs/tron'

# What file has the passwords.
passwordFile = os.path.join(os.environ['TRON_DIR'], 'passwords')

# Which words to load internally.
vocabulary = ('hub', 'keys', 'msg')

nubs = ('cmdin',
        'client',
        'nclient',
        'toy',
        'TUI')

actors = dict(toy=       dict(host="localhost", port=9000, actorName='toyActor'),
              mps=       dict(host="localhost", port=9001, actorName='mpsActor'),
              mcs=       dict(host="localhost", port=9002, actorName='mcsActor'),
              shutter=   dict(host="localhost", port=9003, actorName='shutterActor'),
              lamps=     dict(host="localhost", port=9004, actorName='lampsActor'),
              pfics=     dict(host="localhost", port=9005, actorName='pficsActor'),
              archiver=  dict(host="localhost", port=9006, actorName='archiverActor'),
              )

httpHost = 'localhost'
httpRoot = '/'
