# cisco_funcs.py
#
# helper functions for mds switches
# uses netmiko and ciscoconfparse

import re
from sys import exit

# check if netmiko python library is already installed
try:
    from netmiko import ConnectHandler
    has_netmiko = True
except:
    has_netmiko = False

# check if ciscoconfparse python library is already installed
try:
    from ciscoconfparse import CiscoConfParse
    has_ciscoconfparse = True
except:
    has_ciscoconfparse = False

# if none of libraries was installed a friendly message will be displayed
if not has_netmiko :
    print "netmiko is required to use this script, download installation from:"
    print "https://github.com/ktbyers/netmiko/tree/master/netmiko"
    exit(1)

if not has_ciscoconfparse :
    print "The ciscoconfparse module is needed. Download "
    print "installation from: https://github.com/mpenning/ciscoconfparse"
    exit(1)

def parsefcaliases(cisco_cfg) :
    """ parse fcalias data from cisco show running-config into list of dictionaries """
    fcalias_dict = {}
    fcaliases = cisco_cfg.find_objects(r"^fcalias name")
    for fcalias_line in fcaliases :
        fcalias_line_list = fcalias_line.text.strip().split()
        curfcalias = fcalias_line_list[2]
        fcalias_dict[curfcalias] = {}
        curfcalias_dict = {}
        curfcalias_dict['name'] = curfcalias
        curfcalias_dict['vsan'] = fcalias_line_list[4]
        pwwn_list = []
        for members_line in fcalias_line.children :
            members_line_list = members_line.text.strip().split()
            pwwn_list.append(members_line_list[2])
            curfcalias_dict['pwwns'] = pwwn_list
        if pwwn_list == [] :
            curfcalias_dict['pwwns'] = []
        fcalias_dict[curfcalias] = curfcalias_dict

    return(fcalias_dict)

def nonblank_lines(f):
    for l in f:
        line = l.strip()
        if line:
            yield line

def handle_mds_continue(net_connect, cmd):
    net_connect.remote_conn.sendall(cmd)
    time.sleep(1)
    output = net_connect.remote_conn.recv(65535).decode('utf-8')       
    if 'want to continue' in output:
        net_connect.remote_conn.sendall('y\n')
        output += net_connect.remote_conn.recv(65535).decode('utf-8')
        return output

def getzones(sh_zones) :
    ''' get a list of zone dictionies and their memberchildren in lists of dictionaries'''
    zones = sh_zones.find_objects(r"zone name")
    zones_list = []
    for zone in zones :
        zone_list = []
        zoneline_dict = {}
        zoneline = zone.text.strip().split()
        zoneline_dict['vsan'] = zoneline[4]
        zoneline_dict['name'] = zoneline[2]
        zone_list.append(zoneline_dict)
        for fcalias in zone.children :
            fcaliases = []
            fcaliasline = fcalias.text.strip().split()
            fcaliasline_dict = {}
            try:
                fcaliasline_dict['fcalias'] = fcaliasline[2]
            except:
                fcaliasline_dict['fcalias'] = None
            fcaliases.append(fcaliasline_dict)
            for member in fcalias.children:
                members = []
                memberline = member.text.strip().split()
                memberline_dict = {}
                memberline_dict['pwwn'] = memberline[1]
                members.append(memberline_dict)
                fcaliases.append(members)
            zone_list.append(fcaliases)
        zones_list.append(zone_list)
            
    return(zones_list)

class SmartZone(object):
    """Class to work with SmartZone by using NetMiko base connection"""

    def __init__(self, mds):
        super(SmartZone, self).__init__()
        __mds = mds
        # Create a connection by instantiate a netmiko session with MDS
        self.__conn = ConnectHandler(**__mds)

    def exists(self, zone_name, vsan_id):
        """Check if a specifc zone name exists on MDS switch opening a connection with MDS switch
        and execute "show zoneset brief" commands receiving vsan id as a param"""

        # Receive VSAN ID param and define the zoneset command,
        # send to MDS, store the result into a variable
        command = 'show zoneset brief vsan %s' % vsan_id
        zoneset_brief = self.__conn.send_command(command)
        
        # Compile a regex with the received zone name
        # make a search into the zoneset resukt variable,
        # return True if the zone name was found or False if doesn't
        regex = re.compile(zone_name)

        if regex.search(zoneset_brief):
            return True
        else:
            return False

    def count_members(self, zone_name):
        """Count the total members existent on a specifc smartzone, including initiator and target members"""

        # Receive zone name as a param and define the command to be
        # send to MDS, store the result into a variable
        command = 'show zone name %s' % zone_name
        zone_members = self.__conn.send_command(command)
        
        # Compile a regex with the received zone name
        # make a search into the zone result variable,
        # and count the total number of matches
        regex = re.compile('pwwn.*(init|target)')

        members = 0

        for member in zone_members.split('\n'):
            if regex.search(member):
                members += 1
                
        return members

    def close(self):
        """ Close connection with MDS switch """
        self.__conn.disconnect()

class DeviceAlias(object):
    """Class to work with DeviceAlias by using NetMiko base connection"""

    def __init__(self, mds):
        super(DeviceAlias, self).__init__()
        __mds = mds
        # Create a connection by instantiate a netmiko session with MDS
        self.__conn = ConnectHandler(**__mds)

    def exists(self, pwwn):
        """Count the total members existent on a specifc smartzone, including initiator and target members """
        
        # Load device-alias database
        command = 'show device-alias database'
        device_alias_db = self.__conn.send_command(command)

        # Compile a regex with the received pwwn
        # make a search into the device-alias database
        # result variable, and count the total number of matches
        regex = re.compile('device-alias\sname\s(.*)pwwn\s(%s)' % pwwn, re.IGNORECASE)

        for device_alias in device_alias_db.split('\n'):
            if regex.search(device_alias):
                return device_alias.split()[2]

    def close(self):
        """ Close connection with MDS switch """
        self.__conn.disconnect()

class ZoneSet(object):
    """Class to work with ZoneSet by using NetMiko base connection"""

    def __init__(self, mds):
        super(ZoneSet, self).__init__()
        __mds = mds
        # Create a connection by instantiate a netmiko session with MDS
        self.__conn = ConnectHandler(**__mds)

    def exists(self, zoneset_name, vsan_id):
        """Check if a specifc zoneset name exists on MDS switch opening a connection with MDS switch
        and execute \"show zoneset brief\" commands receiving vsan id as a param"""

        # Receive VSAN ID param and define the zoneset command,
        # send to MDS, store the result into a variable
        command = 'show zoneset brief vsan %s' % vsan_id
        zoneset_brief = self.__conn.send_command(command)
        
        # Compile a regex with the received zoneset name
        # make a search into the zoneset result variable,
        # return True if the zoneset name and VSAN ID was found or False if doesn't
        regex = re.compile("^zoneset.*(%s).vsan.*(%s)" % (zoneset_name,vsan_id))
        
        if regex.search(zoneset_brief):
            return True
        else:
            return False
        
    def close(self):
        """ Close connection with MDS switch """
        self.__conn.disconnect()