import os

# Where to save the logs
logDir = '/data/logs/tron'

# What file has the passwords.
passwordFile = os.path.join(os.environ['TRON_DIR'], 'passwords')

# Which words to load internally.
vocabulary = ('perms', 'hub', 'keys', 'msg')
nubs = ('client',
        'ping',
        'TUI',
        'tcc25m',
        'mcp'
        )

httpHost = 'hub25m.apo.nmsu.edu'
httpRoot = '/'
