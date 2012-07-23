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
        'ping',

        'TUI')

actors = dict(alerts=    dict(host="hub25m-p.apo.nmsu.edu", port=9995, actorName='alertsActor'),
              apo=       dict(host="hub25m-p.apo.nmsu.edu", port=9990, actorName='apoActor'),
              gcamera=   dict(host="hub25m-p.apo.nmsu.edu", port=9993, actorName='gcameraICC'),
              ecamera=   dict(host="hub25m-p.apo.nmsu.edu", port=9987, actorName='ecameraICC'),
              guider=    dict(host="hub25m-p.apo.nmsu.edu", port=9994, actorName='guiderActor'),
              platedb=   dict(host="hub25m-p.apo.nmsu.edu", port=9992, actorName='platedbActor'),
              sop=       dict(host="hub25m-p.apo.nmsu.edu", port=9989, actorName='sopActor'),
#              toy=       dict(host="hub25m-p.apo.nmsu.edu", port=9000, actorName='toyActor'),
              toy=       dict(host="localhost", port=9000, actorName='toyActor'),

              apogee=    dict(host="apogee-ics.apo.nmsu.edu", port=33221, actorName='apogeeICC'),
              apogeecal= dict(host="apogee-ics.apo.nmsu.edu", port=33222, actorName='apogeecalICC'),
              apogeeql=  dict(host="apogee-ql.apo.nmsu.edu", port=18282, actorName='apogeeqlActor'),

              boss=      dict(host="boss-icc-p.apo.nmsu.edu", port=9998, actorName='bossICC'),

              sos=       dict(host="sos3-p.apo.nmsu.edu", port=9988, actorName='sosActor'),
              )

httpHost = 'localhost'
httpRoot = '/'
