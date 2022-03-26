# homelab-vmware-shutdown
Shutdown virtual machines in vCenter

This Python program uses VMware vCenter APIs to get a list of running virtual machines and shut them down gracefully.

It was written for:

- VMware vCenter Server Appliance 7.0.3
- VMware ESXi 7.0.3

I created this to use with [apcupsd](http://www.apcupsd.org/manual/manual.html) on Linux. The goal is to shutdown all running virtual machines on an ESXi host with a vCenter appliance. After the VMs are shutdown, the vCenter machine is shutdown. It locates the vCenter VM by searching for a VM with "vcenter" in the name.

It does not shutdown the ESXi host. I use a separate script that does an ssh into the ESXi host to power it off gracefully.

For more information about how the program works read [Shutdown Virtual Machines using Python](http://tmblog.mwbinc.com/general/2022/03/15/shutdown-virtual-machines.html).
