#!/usr/bin/env python

import argparse
import boto3
assert boto3.__version__ >= '1.4.4', \
    "Older version of boto3 installed {} which doesn't support instance tagging on creation. Update with command 'pip install -U boto3>=1.4.4".format(boto3.__version__)
import botocore
assert botocore.__version__ >= '1.5.63', \
   "Older version of botocore installed {} which doesn't support instance tagging on creation. Update with command 'pip install -U botocore>=1.5.63".format(botocore.__version__)

import re
import datetime
import time
import logging
import os
import sys
import distutils.util

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger(__name__)

class ARecord(object):
   def __init__(self, ip, ttl):
       self.ip = ip
       self.ttl = ttl

   def __repr__(self):
       return "A record ({0}, {1})".format(self.ip, self.ttl)

class TxtRecord(object):
   def __init__(self, text, ttl):
       self.text = text
       self.ttl = ttl

   def __repr__(self):
       return "TXT record ({0}, {1})".format(self.text, self.ttl)

class MXRecord(object):
   def __init__(self, emailServer, order, ttl):
       self.emailServer = emailServer
       self.order = order
       self.ttl = ttl

   def __repr__(self):
       return "MX record ({0}, {1}, {2})".format(self.emailServer, self.order, self.ttl)

class CNameRecords(object):
   def __init__(self, cname, ttl):
       self.cname = cname
       self.ttl = ttl

   def __repr__(self):
       return "CName record ({0}, {1})".format(self.cname, self.ttl)


class TinyDNS(object):
    def __init__(self):
        self.arecords = {}
	self.txtrecords = {}
	self.mxrecords = {}
	self.cnamerecords = {}
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
		 self.arecords[domainName] = ARecord(ipAddress, ttl)
	      elif (d[0] == "'"):
		 domainName = r[0]
		 txt = r[1]
		 if (len(r) == 3):
	             ttl = r[2]
		     self.txtrecords[domainName] = TxtRecord(txt, ttl)
	      elif (d[0] == '@'):
		 domainName = r[0]
		 emailServer = r[2]
		 order = r[3]
		 ttl = r[4]
		 if (self.mxrecords.get(domainName) == None):
	            self.mxrecords[domainName] = []
		 self.mxrecords[domainName].append(MXRecord(emailServer, order, ttl))
	      elif (d[0] == 'C'):
	         domainName = r[0]
		 canonicalName = r[1]
		 ttl = r[2]
		 self.cnamerecords[domainName] = CNameRecords(canonicalName, ttl)

class Route53(object):
    def __init__(self):
        self.client = boto3.client('route53')
        self.zones = {}
	self.allrecords = {}
	allZones = self.client.list_hosted_zones()
        for z in allZones.iteritems():
           if (z[0] == 'HostedZones'):
              for z1 in z[1]:
		 Id = z1["Id"].split("/")[2]
		 self.zones[z1["Name"]] = Id

        for (domain, id) in self.zones.iteritems():
	   if (self.allrecords.get(domain) == None):
	      self.allrecords[domain] = []
	   paginator = self.client.get_paginator('list_resource_record_sets')
	   try:
	      domRecords = paginator.paginate(HostedZoneId=id)
	      for d in domRecords:
		  self.allrecords[domain].append(d)
	   except Exception as e:
	      LOG.exception("Failed to get hosted zone records %s", e)

    def printExistingRecords(self):
        for (domain, r) in self.allrecords.iteritems():
          LOG.info(domain)
	  for records in r:
	     for recs in records['ResourceRecordSets']:
	        LOG.info("%s %s", recs['Type'], recs['ResourceRecords'])

    def __importARecords(self, zoneId, domain, record):
	d = datetime.datetime.now()
	timestamp = d.strftime("%Y-%m-%d")
	commentString = "[A] Record change initiated on {0}".format(timestamp)
	domainName = "{0}.".format(domain)
	self.client.change_resource_record_sets(
	   HostedZoneId=zoneId,
	   ChangeBatch={
              "Comment": commentString,
	      "Changes" : [
	         {
	            "Action": "UPSERT",
		    "ResourceRecordSet": {
			"Name": domainName,
			"Type": 'A',
			"TTL" : int(record.ttl),
			"ResourceRecords": [
			   {
			      "Value" : record.ip
			   }
			]
		     }
		 }
	      ]
	   }
        )

    def __importTxtRecords(self, zoneId, domain, record):
	d = datetime.datetime.now()
	timestamp = d.strftime("%Y-%m-%d")
	commentString = "[TXT] Record change initiated on {0}".format(timestamp)
	domainName = "{0}.".format(domain)
	recordText = record.text
	if (len(recordText) > 255):
	   recordText = " ".join('"{0}"'.format(recordText[i:i+255]) for i in range(0, len(recordText), 255))
	else:
	   recordText = '"{0}"'.format(recordText)
	self.client.change_resource_record_sets(
	   HostedZoneId=zoneId,
	   ChangeBatch={
              "Comment": commentString,
	      "Changes" : [
	         {
	            "Action": "UPSERT",
		    "ResourceRecordSet": {
			"Name": domainName,
			"Type": 'TXT',
			"TTL" : int(record.ttl),
			"ResourceRecords": [
			   {
			      "Value" : recordText
			   }
			]
		     }
		 }
	      ]
	   }
        )

    def __importCNameRecords(self, zoneId, domain, record):
	d = datetime.datetime.now()
	timestamp = d.strftime("%Y-%m-%d")
	commentString = "[CNAME] Record change initiated on {0}".format(timestamp)
	domainName = "{0}.".format(domain)
	self.client.change_resource_record_sets(
	   HostedZoneId=zoneId,
	   ChangeBatch={
              "Comment": commentString,
	      "Changes" : [
	         {
	            "Action": "UPSERT",
		    "ResourceRecordSet": {
			"Name": domainName,
			"Type": 'CNAME',
			"TTL" : int(record.ttl),
			"ResourceRecords": [
			   {
			      "Value" : record.cname
			   }
			]
		     }
		 }
	      ]
	   }
        )

    def __importMXRecords(self, zoneId, domain, records):
	d = datetime.datetime.now()
	timestamp = d.strftime("%Y-%m-%d")
	commentString = "[MX] Record change initiated on {0}".format(timestamp)
	domainName = "{0}.".format(domain)
        mxValueStr = "".join("{0} {1}\n".format(mx.order, mx.emailServer) for mx in sorted(records))
	mxValueStr.strip('\n')
	self.client.change_resource_record_sets(
	   HostedZoneId=zoneId,
	   ChangeBatch={
              "Comment": commentString,
	      "Changes" : [
	         {
	            "Action": "UPSERT",
		    "ResourceRecordSet": {
			"Name": domainName,
			"Type": 'MX',
			"TTL" : int(records[0].ttl),
			"ResourceRecords": [
			   {
			      "Value" : mxValueStr
			   }
			]
		     }
		 }
	      ]
	   }
        )

    def importRecordsFromTinyDNS(self, tdns):
        for domains in self.allrecords.iterkeys():
	    zoneId = self.zones[domains]
	    # Strip out the trailing "." at the end of the domain name
	    re1 = re.compile(domains[0:len(domains)-1])
	    for (d, r) in tdns.arecords.iteritems():
	       s1 = re1.search(d)
	       if s1 is not None:
		  # Valid matches are
                  # subdomain.artofliving.org,
                  # artofliving.org, but not artofliving.org.de
		  sp1 = s1.span()[1]
		  if len(d) <= sp1:
		     LOG.info("Importing A record for %s -> %s to Route53", d, r)
		     try:
		         self.__importARecords(zoneId, d, r)
		     except botocore.errorfactory.InvalidChangeBatch as e:
		         LOG.error("Invalid TXT record update %s", e)
   	    for (d, r) in tdns.txtrecords.iteritems():
	       s1 = re1.search(d)
	       if s1 is not None:
		  sp1 = s1.span()[1]
		  if len(d) <= sp1:
	             LOG.info("Importing TXT record for %s -> %s to Route53", d, r)
		     try:
		         self.__importTxtRecords(zoneId, d, r)
		     except botocore.errorfactory.InvalidChangeBatch as e:
		         LOG.error("Invalid TXT record update %s", e)
	    for (d, r) in tdns.mxrecords.iteritems():
	       s1 = re1.search(d)
	       if s1 is not None:
		  sp1 = s1.span()[1]
		  if len(d) <= sp1:
	             LOG.info("Importing MX records for %s -> %s to Route53", d, r)
		     try:
		        self.__importMXRecords(zoneId, d, r)
		     except botocore.errorfactory.InvalidChangeBatch as e:
		         LOG.error("Invalid MX record update %s", e)
	    for (d, r) in tdns.cnamerecords.iteritems():
	       s1 = re1.search(d)
	       if s1 is not None:
		  sp1 = s1.span()[1]
		  if len(d) <= sp1:
	             LOG.info("Importing CNAME records for %s -> %s to Route53", d, r)
		     try:
		         self.__importCNameRecords(zoneId, d, r)
		     except botocore.errorfactory.InvalidChangeBatch as e:
		         LOG.error("Invalid CName record update %s", e)

        return None
 
def main():
    r53 = Route53()
    r53.printExistingRecords()
    r53.importRecordsFromTinyDNS(TinyDNS())
    return 0

if __name__ == '__main__':
    sys.exit(main())
