#!/usr/bin/env python

import argparse
import datetime
import time
import re
import logging
import os
import sys
import distutils.util

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger(__name__)


def prefixName(domainName, zone):
    re1 = re.compile(zone)
    s1 = re1.search(domainName)
    if s1 is not None:
       sp1 = s1.span()[0]
       return domainName[0:sp1-1]


class DNSRecord(object):
   def __init__(self, domainName):
       self.domainName = domainName
       

class ARecord(DNSRecord):
   def __init__(self, domainName, ip, ttl):
       super(ARecord, self).__init__(domainName)
       self.ip = ip
       self.ttl = ttl

   def __repr__(self):
       return "A record {0} -> ({1}, {2})".format(self.domainName, self.ip, self.ttl)

class TxtRecord(DNSRecord):
   def __init__(self, domainName, text, ttl):
       super(TxtRecord, self).__init__(domainName)
       self.text = text
       self.ttl = ttl

   def __repr__(self):
       return "TXT record {0} -> ({1}, {2})".format(self.domainName, self.text, self.ttl)

class NSRecord(DNSRecord):
   def __init__(self, domainName, nameServer):
       super(NSRecord, self).__init__(domainName)
       self.nameServer = nameServer

   def __repr__(self):
       return "NS record {0} -> {1}".format(self.domainName, self.nameServer)

class MXRecord(DNSRecord):
   def __init__(self, domainName, emailServer, order, ttl):
       super(MXRecord, self).__init__(domainName)
       self.emailServer = emailServer
       self.order = order
       self.ttl = ttl

   def __repr__(self):
       return "MX record {0} -> ({1}, {2}, {3})".format(self.domainName, self.emailServer, self.order, self.ttl)

class CNameRecord(DNSRecord):
   def __init__(self, domainName, cname, ttl):
       super(CNameRecord, self).__init__(domainName)
       self.cname = cname
       self.ttl = ttl

   def __repr__(self):
       return "CName record {0} -> ({1}, {2})".format(self.domainName, self.cname, self.ttl)


class TinyDNS(object):
    def __init__(self):
        self.records = []
        with open('/etc/tinydns/root/data') as f:
	   data = f.read()
	
	data = data.split('\n')
	for d in data:
           if len(d) > 0:
	      r = d[1:]
	      r = r.split(':')
	      if (d[0] == '+'):
		 domainName = r[0]
		 ipAddress = r[1]
		 ttl = r[2]
		 self.records.append(ARecord(domainName, ipAddress, ttl))
	      elif (d[0] == "'"):
		 domainName = r[0]
		 txt = r[1]
		 if (len(r) == 3):
	             ttl = r[2]
		     self.records.append(TxtRecord(domainName, txt, ttl))
	      elif (d[0] == '@'):
		 domainName = r[0]
		 emailServer = r[2]
		 order = r[3]
		 ttl = r[4]
		 self.records.append(MXRecord(domainName, emailServer, order, ttl))
	      elif (d[0] == 'C'):
	         domainName = r[0]
		 canonicalName = r[1]
		 ttl = r[2]
		 self.records.append(CNameRecord(domainName, canonicalName, ttl))
	      elif (d[0] == '&'):
	         domainName = r[0]
		 nameServer = r[2]
		 self.records.append(NSRecord(domainName, nameServer))

    def getheader(self, zone):
        h = """\
        $TTL 3600
        @  IN  SOA ns1.artofliving.org. hostmaster.%s.     (
                %s01           ; serial
		14400          ; refresh
	        3600           ; retry
                1048576        ; expire
		2560           ; minimum
	) """ % (zone, datetime.datetime.now().strftime('%Y%m%d'))
	return h


    def writeBindZoneFiles(self):
        zones = ['artofliving.org', 'srisriravishankar.org']
	for z in zones:
	    with open(z, 'w+') as fh:
		fh.write(self.getheader(z))
		fh.write('\n')
                fh.write('{0:<45} IN  NS    {1}.\n'.format(' ', 'ns1.artofliving.org'))
                fh.write('{0:<45} IN  NS    {1}.\n'.format(' ', 'ns2.artofliving.org'))
	        re1 = re.compile(z)
	        for r in self.records:
		    s1 = re1.search(r.domainName)
		    if s1 is not None:
		       # Valid matches are
		       # subdomain.artofliving.org,
		       # artofliving.org, but not artofliving.org.de
		       sp1 = s1.span()[1]
		       if len(r.domainName) <= sp1:
		          LOG.info("Importing %s", r)
			  if isinstance(r, ARecord):
			      if r.domainName != z:
			         fh.write('{0:<45} IN  A     {1}\n'.format(prefixName(r.domainName, z), r.ip))   
			      else:
			         fh.write('{0:<45} IN  A     {1}\n'.format(r.domainName + ".", r.ip))   
			  elif isinstance(r, CNameRecord):
			      fh.write('{0:<45} IN  CNAME {1}.\n'.format(prefixName(r.domainName, z), r.cname))
			  elif isinstance(r, TxtRecord):
			      if r.domainName != z:
			         fh.write('{0:<45} IN  TXT {1}\n'.format(prefixName(r.domainName, z), r.text))
			      else:
			         fh.write('{0:<45} IN  TXT {1}\n'.format(r.domainName + ".", r.text))
			  elif isinstance(r, MXRecord):
			      fh.write('{0:<45} IN  MX    {1:<5} {2}\n'.format(r.domainName + ".", r.order, r.emailServer))

def main():
    t = TinyDNS();
    t.writeBindZoneFiles()
    return 0

if __name__ == '__main__':
    sys.exit(main())
