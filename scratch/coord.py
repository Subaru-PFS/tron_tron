class coord:
  def __init__(self, lo, hi):
    self.lo = lo-1
    self.hi = hi-1
    self.binning = 1
    self.set()
    
  def __str__(self):
    return "coord(lo=%d hi=%d, binning=%d, blo=%d, bhi=%d)" % \
           (self.lo, self.hi, self.binning, self.lo / self.binning + 1, self.hi /self.binning + 1)
  
  def set(self):
    print "skip=%d width=%d" % (self.lo, (self.hi-self.lo+1) / self.binning)
    
  def bin(self, b):
    self.binning = b
    self.set()
    
  def window(self, nlo, nhi):
    self.lo = (nlo-1) * self.binning
    self.hi = (nhi-1) * self.binning
    self.set()
    
  def cwindow(self, c, w):
    nlo = c - w
    nhi = c + w
    self.window(nlo, nhi)
    
if __name__ == "__main__":
  c = coord(1, 100)
  print c
  
  c.window(1,10)
  print c
  
  c.bin(2)
  print c
  
  c.bin(3)
  print c
  
  c.window(1, 20)
  print c
  
  c.bin(1)
  print c
  
  c.cwindow(50,0)
  print c
  
  c.cwindow(50,10)
  print c
            
  del c
  