#!/usr/bin/env python
import argparse
import boto
import boto.ec2
import boto.s3
import boto.rds
import datetime
import logging
import os
import sys

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger(__name__)

class EC2State(object):

    def __init__(self, cliArgs):
        regionInfo = boto.ec2.regions()
        self.validRegions = [r.name for r in regionInfo]
        if cliArgs.ec2RegionName is not None and not cliArgs.ec2RegionName in self.validRegions:
            raise Exception("Invalid region name %s" % cliArgs.ec2RegionName)
        self.regions = [cliArgs.ec2RegionName] if cliArgs.ec2RegionName else self.validRegions
        self.instances = {}
        self.ec2conn = {}
        for r in self.regions:
            self.ec2conn[r] = boto.ec2.connect_to_region(r)
            try:
                self.instances[r] = self.ec2conn[r].get_all_instances()
                LOG.info("Region %s has %u instances" % (r, len(self.instances[r])))
            except boto.exception.EC2ResponseError as e:
                LOG.exception('Region %s encountered exception %s. Ignoring' % (r, e))

    def clone_ec2_instance(self, instanceName):
        for (r, i) in self.instances.iteritems():
            if i == instanceName:
                LOG.info("Found instance '%s' in region ''%s'" % (i, r))
                return True
        raise Exception('No such instance name %s' % instanceName)


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument('-v', '--verbose', default=False, action='store_true',
      help='print additional verbose logs')
    parser.add_argument('-c', '--country', default=None, type=str, action='store',
      help='name of the country to migrate')
    parser.add_argument('-i', '--ec2instanceType', default='t2.large', type=str, action='store',
      help='EC2 instance to spin up for this country')
    parser.add_argument('-d', '--rdsInstanceName', default=None, type=str, action='store',
      help='RDS database name')
    parser.add_argument('-r', '--rdsInstanceSize', default=4, type=int, action='store',
      help='RDS database size in GB')
    parser.add_argument('-k', '--ec2RegionName', default=None, type=str, action='store',
      help='EC2 region name(s) where instances are being hosted currently')

    return parser.parse_args()


def main():
    cliArgs = parse_arguments()

    ts = datetime.datetime.now()
    LOG.setLevel(logging.DEBUG if cliArgs.verbose else logging.INFO)
    if cliArgs.country is None:
        LOG.error('Please specify country name to break out')
        return -1

    if cliArgs.rdsInstanceName is None:
        cliArgs.rdsInstanceName = 'harmony_rds_{}.{}'.format(cliArgs.country, str(ts).replace(' ', ''))

    LOG.info('Splitting out country %s on instance %s' % (cliArgs.country, cliArgs.ec2instanceType))
    LOG.info('DB name %s and size %s GB' % (cliArgs.rdsInstanceName, cliArgs.rdsInstanceSize))

    aolAssets = EC2State(cliArgs)
    return 0

if __name__ == '__main__':
    sys.exit(main())
