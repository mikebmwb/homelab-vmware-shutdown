import requests
import json
import time
import logging
import os
import sys
from requests.packages.urllib3.exceptions import InsecureRequestWarning

# Settings
#
vcip = "X.X.X.X" # vCenter server ip address/FQDN
vcacct = "YOUR_USER@vsphere.local"
vcpw = "YOUR_PASSWORD"
max_shutdown_wait_count = 30      # the number of wait loops 30 x 10 = 300 seconds or 5 minutes
#max_shutdown_wait_count = 3      # shorter wait for testing
shutdown_wait_time = 10           # the number of seconds to sleep between loops
#shutdown_vcenter_wait_time = 10  # shorter wait for testing
shutdown_vcenter_wait_time = 180  # the number of seconds to sleep after requesting vcenter to shutdown

# Global log
#log_level = logging.DEBUG
log_level = logging.INFO 

logging.basicConfig(level = log_level,
                    format = "%(asctime)s %(levelname)s %(module)s %(message)s")

log = logging.getLogger()

# Function to get the vCenter server session
def get_vc_session(s, vcip, username, password):
    s.verify = False   # disable checking server certificate
    s.auth = (username, password) # Basic authentication
    try:
        r = s.post("https://" + vcip + "/api/session")
    except requests.exceptions.ConnectionError:
        log.error("Error connecting to vCenter: " + str(vcip))
        sys.exit(1)
    log.debug(r.headers)
    log.debug(r.request.headers)
    log.debug(str(r.status_code))
    if r.status_code == 401:
        log.error("Invalid credentials for vCenter")
        sys.exit(1)
    if r.status_code != 201:
        log.error(str(r.status_code))
        sys.exit(1)
    log.debug(r.headers['vmware-api-session-id'])
    s.headers.update({'vmware-api-session-id': r.headers['vmware-api-session-id']})
    return s

# Function to get all the VMs from vCenter inventory
def get_vm_list(s, vcip):
    r = s.get("https://" + vcip + "/api/vcenter/vm")
    log.debug(r.url)
    log.debug(r.headers)
    log.debug(r.request.headers)
    log.debug(str(r.status_code))
    log.debug(r.text)
    return r

# Function to get all the VMs from vCenter inventory that are powered on
def get_vm_poweredon_list(s, vcip):
    vm_query_params = {"power_states":["POWERED_ON"]}
    r = s.get("https://" + vcip + "/api/vcenter/vm", params = vm_query_params)
    log.debug(r.url)
    log.debug(r.headers)
    log.debug(r.request.headers)
    log.debug(str(r.status_code))
    log.debug(r.text)
    return r

# Guest power status
def get_guest_power(s, vmid, vcip):
    r = s.get("https://" + vcip + "/api/vcenter/vm/" + vmid + "/guest/power")
    log.debug(r.url)
    log.debug(r.headers)
    log.debug(r.request.headers)
    log.debug(str(r.status_code))
    log.debug(r.text)
    return r

# Guest shutdown
def guest_shutdown(s, vmid, vcip):
    vm_action = {"action": "shutdown"}
    r = s.post("https://" + vcip + "/api/vcenter/vm/" + vmid + "/guest/power", params = vm_action)
    log.debug(r.url)
    log.debug(r.headers)
    log.debug(r.request.headers)
    log.debug(str(r.status_code))
    log.debug(r.text)
    return r

# Power on vm
def vm_poweron(s, vmid, vcip):
    vm_action = {"action": "start"}
    r = s.post("https://" + vcip + "/api/vcenter/vm/" + vmid + "/power", params = vm_action)
    log.debug(r.url)
    log.debug(r.headers)
    log.debug(r.request.headers)
    log.debug(str(r.status_code))
    log.debug(r.text)
    return r

# Power off vm (this is not a guest OS shutdown)
def poweroff_vm(s, vmid, vcip):
    r = s.post("https://" + vcip + "/api/vcenter/vm/" + vmid + "/power/stop")
    log.debug(r.url)
    log.debug(r.headers)
    log.debug(r.request.headers)
    log.debug(str(r.status_code))
    log.debug(r.text)
    return r

def main() -> int:

    log.info("Creating vCenter Rest API session")

    #Get vCenter server session
    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
    s = requests.Session()
    s = get_vc_session(s, vcip, vcacct, vcpw)

    # Get list of VMs powered on
    json_vm_list = get_vm_poweredon_list(s, vcip)
    if json_vm_list.status_code != 200:
        log.error("List VMs status_code: " + str(json_vm_list.status_code))
#        sys.exit(1)
        return 1

    # Parse the JSON response into a python list
    vm_list = json.loads(json_vm_list.text)

    num_vms = len(vm_list)

    log.debug("All the VM response data - powered on vms: " + str(num_vms))
    if log.isEnabledFor(logging.DEBUG):
        for vm in vm_list:
            log.debug(vm)

    # search for a vm named vcenter
    # need to move vCenter to the last in the list, it is the API endpoint
    vcenter_vm_location = 0
    item_num = 0
    vcenter_vm_found = False

    log.debug("Reorder the list with vcenter last")
    # move the VM with vcenter in its name to last
    # moves the last instance if there is more than 1 match
    for vm in vm_list:
        if "vcenter" in vm["name"].lower():
            log.debug("vcenter found in " + vm["name"])
            log.debug(str(item_num))
            vcenter_vm_location = item_num
            vcenter_vm_found = True
        item_num += 1
    # adjust the size to exclude vCenter VM
    if vcenter_vm_found:
        vm_list.append(vm_list.pop(vcenter_vm_location))
        num_vms -= 1  # don't count vcenter in the main list

    log.debug("Print all of the new vm list items")
    if log.isEnabledFor(logging.DEBUG):
        for vm in vm_list:
            log.debug(vm)

    log.info("Number of running VMs not including vCenter: " + str(num_vms))

    vm_info_str = ""
    vm_list_size = len(vm_list)

    # make a string with the names of the VMs to shutdown for logging
    for i in range(len(vm_list)):
        vm_info_str += vm_list[i]["name"] + ":" + vm_list[i]["vm"]
        if i < (vm_list_size - 1):
            vm_info_str += ","

    log.info("The following VMs will be shutdown: " + vm_info_str)
    log.info("Shutting down VMs")

    # loop through the list and shutdown each vm
    for i in range(num_vms):
        log.info("Shutting down: " + vm_list[i]["name"] + ":" + vm_list[i]["vm"])
        guest_shutdown(s, vm_list[i]["vm"], vcip)


    # Loop and check until all of the VMs are off
    for i in range(max_shutdown_wait_count):
        time.sleep(shutdown_wait_time)
        log.info("Timeout remaining: " + str((max_shutdown_wait_count - i - 1) * shutdown_wait_time))
    
        # Get list of VMs powered on
        json_vm_list = get_vm_poweredon_list(s, vcip)
        log.info("List VMs status_code: " + str(json_vm_list.status_code))
        if json_vm_list.status_code != 200:
            log.error("List VMs status_code: " + str(json_vm_list.status_code))
#            sys.exit(1)
            return 1

        # Parse the JSON response into a python list
        vm_list = json.loads(json_vm_list.text)

        num_vms = len(vm_list)
        if vcenter_vm_found:
            num_vms -= 1
        log.info("Number of running VMs excluding vCenter: " + str(num_vms))
        if num_vms <= 0:
           break   # all the vms are shutdown, don't need to wait any longer


    if vcenter_vm_found:
        # Get list of VMs powered on
        json_vm_list = get_vm_poweredon_list(s, vcip)
        log.info("List VMs status_code: " + str(json_vm_list.status_code))
        if json_vm_list.status_code != 200:
            log.error("List VMs status_code: " + str(json_vm_list.status_code))
#            sys.exit(1)
            return 1

        # Parse the JSON response into a python list
        vm_list = json.loads(json_vm_list.text)

        num_vms = len(vm_list)
        log.info("Number of running VMs remaining: " + str(num_vms))

        if num_vms > 1:
            log.error("Some VMs failed to shutdown before the timeout.")
    
            # make a string with the names of the VMs to shutdown
            vm_info_str = ""
            for i in range(len(vm_list)):
                if "vcenter" in vm_list[i]["name"].lower():
                    continue
                vm_info_str += vm_list[i]["name"] + ":" + vm_list[i]["vm"]
                if i < (vm_list_size - 1):
                    vm_info_str += ","

            log.error("The following VMs did not shutdown: " + vm_info_str)

            # find the vcenter vm in the current list
            item_num = 0
            vcenter_vm_location = 0
            for vm in vm_list:
                if "vcenter" in vm["name"].lower():
                    log.debug("vcenter is in " + vm["name"])
                    log.debug(str(item_num))
                    vcenter_vm_location = item_num
                item_num += 1

        else:
            vcenter_vm_location = 0; # if the number of vms is 1, then the only one should be vcenter

        # shutdown the vcenter vm
        log.info("Shutting down: " + vm_list[vcenter_vm_location]["name"] + ":" + vm_list[vcenter_vm_location]["vm"])
        guest_shutdown(s, vm_list[vcenter_vm_location]["vm"], vcip)

        # use a fixed sleep time to pause for vcenter to shutdown before exiting

        log.info("Shutdown sent for vCenter. Pausing for " + str(shutdown_vcenter_wait_time) + " seconds.")
        time.sleep(shutdown_vcenter_wait_time)

        return 0

if __name__ == '__main__':
    sys.exit(main()) 

