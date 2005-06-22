
import CPL
import client
import GuideFrame

class CameraShim(object):
    def __init__(self, name, size, controller):
        self.name = name
        self.size = size
        self.controller = controller

    def statusCmd(self, cmd, doFinish=True):
        cmd.respond('camera="connected"')
        if doFinish:
            cmd.finish()
            
    def cbExpose(self, cmd, cb, type, itime, frame, filename=None):
        """
        Args:
             cb        callback that gets (filename, frame)
        """

        def _cb(ret):
            CPL.log('cbExpose', '_cb got %s' % (ret))
            camFilename = ret.KVs.get('camFile', None)
            if not camFilename:
                cb(None, None)
                return
            camFilename = cmd.qstr(camFilename)
            
            frame = GuideFrame.ImageFrame(self.size)
            frame.setImageFromFITSFile(camFilename)

            cb(camFilename, frame)

        client.callback(self.name,
                        '%s exptime=%0.1f bin=%d,%d offset=%d,%d size=%d,%d filename=%s' % \
                        (type, itime,
                         frame.frameBinning[0], frame.frameBinning[1], 
                         frame.frameOffset[0], frame.frameOffset[1], 
                         frame.frameSize[0], frame.frameSize[1],
                         filename),
                        cid=self.controller.cidForCmd(cmd),
                        callback=_cb)

    def cbFakefile(self, cmd, cb, filename):
        """
        Args:
             cb        callback that gets (filename, frame)
        """

        def _cb(ret):
            CPL.log('cbFakefile', '_cb got %s' % (ret))
            filename = ret.KVs.get('camFile', None)
            if not filename:
                cb(None, None)
                return

            frame = GuideFrame.ImageFrame(self.size)
            frame.setImageFromFITSFile(filename)

            cb(cmd, filename, frame)

        client.callback(self.name,
                        'expose usefile=%s' % (filename),
                        cid=self.controller.cidForCmd(cmd),
                        callback=_cb)
