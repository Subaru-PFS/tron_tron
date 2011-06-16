import os

# Where to save the logs
logDir = '/data/logs/tron'

# What file has the passwords.
passwordFile = os.path.join(os.environ['TRON_DIR'], 'passwords')

# Which words to load internally.
vocabulary = ('perms', 'hub', 'keys', 'msg')
nubs = ('client',
        'nclient',
        'ping',

        'mcp',
        'tcc25m',
        'apo',

        'sop',
        'platedb',
        'gcamera',
        'boss',
        'sos'
        'guider',
        'apogeecal',
        'apogee',
        'apogeeql',
        'tcc2guider',
        'alerts',

        'TUI')

actors = dict(alerts=    dict(host="hub25m-p.apo.nmsu.edu", port=9995),
              apo=       dict(host="hub25m-p.apo.nmsu.edu", port=9990),
              ecamera=   dict(host="hub25m-p.apo.nmsu.edu", port=9987),
              gcamera=   dict(host="hub25m-p.apo.nmsu.edu", port=9993),
              guider=    dict(host="hub25m-p.apo.nmsu.edu", port=9994),
              platedb=   dict(host="hub25m-p.apo.nmsu.edu", port=9992),
              sop=       dict(host="hub25m-p.apo.nmsu.edu", port=9989),

              apogee=    dict(host="apogee-ics.apo.nmsu.edu", port=33221),
              apogeecal= dict(host="apogee-ics.apo.nmsu.edu", port=33222),
              apogeeql=  dict(host="apogee-ql.apo.nmsu.edu", port=18282),

              boss=      dict(host="boss-icc-p.apo.nmsu.edu", port=9998),

              sos=       dict(host="sos3-p.apo.nmsu.edu", port=9988),
              )

httpHost = 'hub25m.apo.nmsu.edu'
httpRoot = '/'
