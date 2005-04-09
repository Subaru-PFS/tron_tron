__all__ = ['BinaryReplyDecoder']

import os
import re
import struct
import tempfile
import pixel16

import g
import CPL
from RO.Alg import OrderedDict
from Parsing import *

from ReplyDecoder import ReplyDecoder

class BinaryReplyDecoder(ReplyDecoder):
    msg_re = re.compile(r"""
    \s*                          # Skip leading whitespace
    (?P<flag>[iw:f>!])           # The flag. Should allow more characters, and check them elsewhere.
    (?P<rest>.*)""",
                         re.VERBOSE | re.IGNORECASE)

    def __init__(self, scratchDir, **argv):
        ReplyDecoder.__init__(self, **argv)
        
        # Where do we save scratch data.
        #
        self.scratchDir = scratchDir
        self.imageBuf = None

        # Whether to byte-swap or sign-flip the data.
        self.doByteSwapFirst = argv.get('byteSwapFirst', False)
        self.doByteSwapLast = argv.get('byteSwapLast', False)
        self.doSignFlip = argv.get('signFlip', False)
        self.BZERO = argv.get('BZERO', 0.0)
        
    def saveImageData(self, image, xpix, ypix, bitpix):
        """ Save image data to a scratch FITS file, register and return the file name. """

        f, fname = tempfile.mkstemp('.fits', "%s-" % (self.nubID), self.scratchDir)

        # Create a minimal header.
        hdr = []
        fmt = "%-08s=%21s / %-47s"
        hdr.append(fmt % ('SIMPLE', 'T', ''))
        hdr.append(fmt % ('BITPIX', `bitpix`, 'Number of bits/data pixel'))
        hdr.append(fmt % ('NAXIS', '2', 'An image'))
        hdr.append(fmt % ('NAXIS1', `xpix`, 'The number of columns'))
        hdr.append(fmt % ('NAXIS2', `ypix`, 'The number of rows'))

        if self.BZERO != 0.0:
            hdr.append(fmt % ('BSCALE', 1.0, ''))
            hdr.append(fmt % ('BZERO', `self.BZERO`, ''))
            
        hdr.append('%-80s' % ('END'))
        
        hdr_s = ''.join(hdr)
        remain = len(hdr_s) % 2880
        os.write(f, hdr_s + ' ' * (2880 - remain))

        # Possibly fiddle the data bits.
        if self.doByteSwapFirst:
            CPL.log("Binary.saveImage", "byteswap first")
            pixel16.byteswap(image)
        if self.doSignFlip:
            CPL.log("Binary.saveImage", "signflip")
            pixel16.uflip(image)
        if self.doByteSwapLast:
            CPL.log("Binary.saveImage", "byteswap last")
            pixel16.byteswap(image)

        written = os.write(f, image)
        assert (written == len(image)), "SHORT WRITE ON IMAGE DATA: written=%d len(image)=%d" % (written, len(image))
        
        # Pad data to FITS 2880-byte block.
        remain = len(image) % 2880

        if remain > 0:
            CPL.log("Binary.saveImage", "padding %d-byte data with %d null bytes" % (len(image), 2880-remain))
            os.write(f, '\000' * (2880 - remain))
                 
        os.close(f)

        # Register the filename. We probably eventually want to register the data, but this is safer.
        #
        g.KVs.setKV('images', '%sFile' % (self.nubID), fname, None)

        return fname

    def decode(self, buf, newData):

        if newData:
            buf += newData
        
        # The binary protocol encapsulates each message in a 10-byte header and a 2-byte trailer:
        #
        # 1(1 byte)
        #        I have no idea what this is about.
        # isfile(1 byte)
        #        Nor this, really. In the hub, if the value is > 1, the data is saved to a file.
        # length(4 bytes)
        #        Length of the complete packet, including the header and trailer.
        # mid(2 bytes) cid(2 bytes)
        #        Note the range: 0..64k
        #        We don't use the cid.
        # if (isfile <= 1):
        #     message
        # else:
        #     xpix(2 bytes)
        #     ypix(2 bytes)
        #     bitpix(2 bytes) (or 1?)
        #     data
        # 
        # checksum(1 byte)
        #        1-byte XOR of the message body.
        # 4(1 byte)
        #        No idea. Just send 4.

        # Quick check for minimal length.
        #
        if len(buf) < 12:
            return None, buf

        # Examine first part, especially the length
        #
        dummy, is_file, length, cid, mid = \
               struct.unpack('>BBihh', buf[:10])
        if dummy != 1:
            # Complain, but don't fail.
            CPL.log('Hub.decap', 'dummy=%d is_file=%d length=%d mid=%d cid=%d' % \
                    (dummy, is_file, length, mid, cid))
        is_file = is_file > 1
        
        if self.debug >= 5:
            CPL.log("Binary.decap", "is_file=%s length=%d (%d) cid=%d mid=%d" %\
                    (is_file, length, len(buf), cid, mid))

        fullLength = length + 10 + 2
            
        if len(buf) < fullLength:
            return None, buf

        # We don't have a complete command yet. Keep waiting.
        #
        if is_file:
            headerLength = 16
        else:
            headerLength = 10

        if is_file:
            xpix, ypix, bitpix = struct.unpack('>hhh', buf[10:16])
        msg = buf[headerLength:fullLength - 2]

        # Trailer parts.
        csum, trailer = struct.unpack('>BB', buf[fullLength-2:fullLength])

        # Calculate & check checksum of message body.
        #   Because images come through here, we need to C this. -- CPL
        #
        my_csum = 0
        if not is_file:
            for i in xrange(10, fullLength - 10 + 1):
                my_csum ^= ord(buf[i])
            if my_csum != csum:
                CPL.log('Hub.decap', 'csum(%d) != calculated csum(%d)' %
                        (csum, my_csum))

        # Magic trailer value. I don't know what this means, but ctrl-d can be Unix EOF.    
        #
        if trailer != 4:
            CPL.error('Hub.decap', 'trailer is not 4 (%d)' % (trailer))
            CPL.log('Hub.decap', "mid=%d cid=%d len=%d msg='%s'" \
                    % (mid, cid, length, msg))

        buf = buf[fullLength:]
        
        if self.debug >= 7:
            CPL.log("Binary.decap", "csum=%d match=%s trailer=%d left=%d (%r) msg=(%r)" %\
                    (csum, csum == my_csum, trailer, len(buf), buf, msg))
        elif self.debug >= 5:
            CPL.log("Binary.decap", "csum=%d match=%s trailer=%d left=%d (%r)" %\
                    (csum, csum == my_csum, trailer, len(buf), buf))

        d = {'mid':mid,
             'cid':cid
             }

        if is_file:
            d['flag'] = 'i'
            d['rest'] = ''
            KVs = OrderedDict()
            KVs['xpix'] = xpix
            KVs['ypix'] = ypix
            KVs['bitpix'] = bitpix
            KVs['scratchFile'] = self.saveImageData(msg, xpix, ypix, bitpix)

            d['KVs'] = KVs
        else:
            match = self.msg_re.match(msg)
            if match == None:
                d['flag'] = 'w'
                KVs = OrderedDict()
                KVs['UNPARSEDTEXT'] = CPL.qstr(msg)
                d['KVs'] = KVs

                return d, buf

            msg_d = match.groupdict()
        
            d['flag'] = msg_d['flag']
            d['rest'] = msg_d['rest']
        
            try:
                KVs = parseKVs(msg_d['rest'])
            except ParseException, e:
                KVs = e.KVs
                KVs['UNPARSEDTEXT'] = CPL.qstr(e.leftoverText)
            except Exception, e:
                CPL.log("parseASCIIReply", "unexpected Exception: %s" % (e))
                KVs = OrderedDict()
                KVs['RawLine'] = CPL.qstr(msg_d['rest'])
        
            d['KVs'] = KVs

        return d, buf
    

