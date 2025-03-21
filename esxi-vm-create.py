import argparse                   # Argument parser
import datetime                   # For current Date/Time
import os.path                    # To check if file exists
import sys                        # For args
import re                         # For regex
import paramiko                   # For remote ssh
import yaml
import warnings

from esxi_vm_functions import *

#      Defaults and Variable setup
ConfigData = setup_config()
NAME = ""
LOG = ConfigData['LOG']
isDryRun = ConfigData['isDryRun']
isVerbose = ConfigData['isVerbose']
isSummary = ConfigData['isSummary']
HOST = ConfigData['HOST']
USER = ConfigData['USER']
PASSWORD = ConfigData['PASSWORD']
CPU = ConfigData['CPU']
MEM = ConfigData['MEM']
HDISK = int(ConfigData['HDISK'])
DISKFORMAT = ConfigData['DISKFORMAT']
VIRTDEV = ConfigData['VIRTDEV']
STORE = ConfigData['STORE']
NET = ConfigData['NET']
ISO = ConfigData['ISO']
GUESTOS = ConfigData['GUESTOS']
VMXOPTS = ConfigData['VMXOPTS']

ErrorMessages = ""
MAC = ""
GeneratedMAC = ""
ISOfound = False
CheckHasErrors = False
LeastUsedDS = ""
DSPATH=""
DSSTORE=""
FullPathExists = False

#
#      Process Arguments
#
parser = argparse.ArgumentParser(description='ESXi Create VM utility.')

parser.add_argument('-d', '--dry', dest='isDryRunarg', action='store_true', help="Enable Dry Run mode  (" + str(isDryRun) + ")")
parser.add_argument("-H", "--Host", dest='HOST', type=str, help="ESXi Host/IP  (" + str(HOST) + ")")
parser.add_argument("-U", "--User", dest='USER', type=str, help="ESXi Host username  (" + str(USER) + ")")
parser.add_argument("-P", "--Password", dest='PASSWORD', type=str, help="ESXi Host password  (*****)")
parser.add_argument("-n", "--name", dest='NAME', type=str, help="VM name")
parser.add_argument("-c", "--cpu", dest='CPU', type=int, help="Number of vCPUS  (" + str(CPU) + ")")
parser.add_argument("-m", "--mem", type=int, help="Memory in GB  (" + str(MEM) + ")")
parser.add_argument("-v", "--vdisk", dest='HDISK', type=str, help="Size of virt hdisk  (" + str(HDISK) + ")")
parser.add_argument("-i", "--iso", dest='ISO', type=str, help="CDROM ISO Path | None  (" + str(ISO) + ")")
parser.add_argument("-N", "--net", dest='NET', type=str, help="Network Interface | None  (" + str(NET) + ")")
parser.add_argument("-M", "--mac", dest='MAC', type=str, help="MAC address")
parser.add_argument("-S", "--store", dest='STORE', type=str, help="vmfs Store | LeastUsed  ("  + str(STORE) + ")")
parser.add_argument("-g", "--guestos", dest='GUESTOS', type=str, help="Guest OS. (" + str(GUESTOS) + ")")
parser.add_argument("-o", "--options", dest='VMXOPTS', type=str, default='NIL', help="Comma list of VMX Options.")
parser.add_argument('-V', '--verbose', dest='isVerbosearg', action='store_true', help="Enable Verbose mode  (" + str(isVerbose) + ")")
parser.add_argument('--summary', dest='isSummaryarg', action='store_true', help="Display Summary  (" + str(isSummary) + ")")
parser.add_argument("-u", "--updateDefaults", dest='UPDATE', action='store_true', help="Update Default VM settings stored in ~/.esxi-vm.yml")
#parser.add_argument("--showDefaults", dest='SHOW', action='store_true', help="Show Default VM settings stored in ~/.esxi-vm.yml")


args = parser.parse_args()

if args.isDryRunarg:
    isDryRun = True
if args.isVerbosearg:
    isVerbose = True
if args.isSummaryarg:
    isSummary = True
if args.HOST:
   HOST=args.HOST
if args.USER:
    USER=args.USER
if args.PASSWORD:
    PASSWORD=args.PASSWORD
if args.NAME:
    NAME=args.NAME
if args.CPU:
    CPU=int(args.CPU)
if args.mem:
    MEM=int(args.mem)
if args.HDISK:
    HDISK=int(args.HDISK)
if args.ISO:
    ISO=args.ISO
if args.NET:
    NET=args.NET
if args.MAC:
    MAC=args.MAC
if args.STORE:
    STORE=args.STORE
if STORE == "":
    STORE = "LeastUsed"
if args.GUESTOS:
    GUESTOS=args.GUESTOS
if args.VMXOPTS == '' and VMXOPTS != '':
    VMXOPTS=''
if args.VMXOPTS and args.VMXOPTS != 'NIL':
    VMXOPTS=args.VMXOPTS.split(",")


if args.UPDATE:
    print("Saving new Defaults to ~/.esxi-vm.yml")
    ConfigData['isDryRun'] = isDryRun
    ConfigData['isVerbose'] = isVerbose
    ConfigData['isSummary'] = isSummary
    ConfigData['HOST'] = HOST
    ConfigData['USER'] = USER
    ConfigData['PASSWORD'] = PASSWORD
    ConfigData['CPU'] = CPU
    ConfigData['MEM'] = MEM
    ConfigData['HDISK'] = HDISK
    ConfigData['DISKFORMAT'] = DISKFORMAT
    ConfigData['VIRTDEV'] = VIRTDEV
    ConfigData['STORE'] = STORE
    ConfigData['NET'] = NET
    ConfigData['ISO'] = ISO
    ConfigData['GUESTOS'] = GUESTOS
    ConfigData['VMXOPTS'] = VMXOPTS
    SaveConfig(ConfigData)
    if NAME == "":
        sys.exit(0)

#
#      main()
#
LogOutput = '{'
LogOutput += '"datetime":"' + str(theCurrDateTime()) + '",'

if NAME == "":
    print("ERROR: Missing required option --name")
    sys.exit(1)

try:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD)

    (stdin, stdout, stderr) = ssh.exec_command("esxcli system version get |grep Version")
    type(stdin)
    if re.match("Version", str(stdout.readlines())) is not None:
        print("Unable to determine if this is a ESXi Host: %s, username: %s" % (HOST, USER))
        sys.exit(1)
except:
    print("The Error is " + str(sys.exc_info()[0]))
    print("Unable to access ESXi Host: %s, username: %s" % (HOST, USER))
    sys.exit(1)

#
#      Get list of DataStores, store in VOLUMES
#
try:
    (stdin, stdout, stderr) = ssh.exec_command("esxcli storage filesystem list |grep '/vmfs/volumes/.*true  VMFS' |sort -nk7")
    type(stdin)
    VOLUMES = {}
    for line in stdout.readlines():
        splitLine = line.split()
        VOLUMES[splitLine[0]] = splitLine[1]
        LeastUsedDS = splitLine[1]
except:
    print("The Error is " + str(sys.exc_info()[0]))
    sys.exit(1)

if STORE == "LeastUsed":
    STORE = LeastUsedDS


#
#      Get list of Networks available, store in VMNICS
#
try:
    (stdin, stdout, stderr) = ssh.exec_command("esxcli network vswitch standard list|grep Portgroups|sed 's/^   Portgroups: //g'")
    type(stdin)
    VMNICS = []
    for line in stdout.readlines():
        splitLine = re.split(',|\n', line)
        VMNICS.append(splitLine[0])
except:
    print("The Error is " + str(sys.exc_info()[0]))
    sys.exit(1)

#
#      Check MAC address
#
MACarg = MAC
if MAC != "":
    MACregex = '^([a-fA-F0-9]{2}[:|\-]){5}[a-fA-F0-9]{2}$'
    if re.compile(MACregex).search(MAC):
        # Full MAC found. OK
        MAC = MAC.replace("-",":")
    elif re.compile(MACregex).search("00:50:56:" + MAC):
        MAC="00:50:56:" + MAC.replace("-",":")
    else:
        print("ERROR: " + MAC + " Invalid MAC address.")
        ErrorMessages += " " + MAC + " Invalid MAC address."
        CheckHasErrors = True


#
#      Get from ESXi host if ISO exists
#
ISOarg = ISO
if ISO == "None":
    ISO = ""
if ISO != "":
    try:
        #  If ISO has no "/", try to find the ISO
        if not re.match('/', ISO):
            (stdin, stdout, stderr) = ssh.exec_command("find /vmfs/volumes/ -type f -name " + ISO + " -exec sh -c 'echo $1; kill $PPID' sh {} 2>/dev/null \;")
            type(stdin)
            FoundISOPath = str(stdout.readlines()[0]).strip('\n')
            if isVerbose:
                print("FoundISOPath: " + str(FoundISOPath))
            ISO = str(FoundISOPath)

        (stdin, stdout, stderr) = ssh.exec_command("ls " + str(ISO))
        type(stdin)
        if stdout.readlines() and not stderr.readlines():
            ISOfound = True

    except:
        print("The Error is " + str(sys.exc_info()[0]))
        sys.exit(1)

#
#      Check if VM already exists
#
VMID = -1
try:
    (stdin, stdout, stderr) = ssh.exec_command("vim-cmd vmsvc/getallvms")
    type(stdin)
    for line in stdout.readlines():
        splitLine = line.split()
        if NAME == splitLine[1]:
            VMID = splitLine[0]
            print("ERROR: VM " + NAME + " already exists.")
            ErrorMessages += " VM " + NAME + " already exists."
            CheckHasErrors = True
except:
        print("The Error is " + str(sys.exc_info()[0]))
        sys.exit(1)

#
#      Do checks here
#

#  Check CPU
if CPU < 1 or CPU > 128:
    print(str(CPU) + " CPU out of range. [1-128].")
    ErrorMessages += " " + str(CPU) + " CPU out of range. [1-128]."
    CheckHasErrors = True

#  Check MEM
if MEM < 1 or MEM > 4080:
    print(str(MEM) + "GB Memory out of range. [1-4080].")
    ErrorMessages += " " + str(MEM) + "GB Memory out of range. [1-4080]."
    CheckHasErrors = True

#  Check HDISK
if HDISK < 1 or HDISK > 63488:
    print("Virtual Disk size " + str(HDISK) + "GB out of range. [1-63488].")
    ErrorMessages += " Virtual Disk size " + str(HDISK) + "GB out of range. [1-63488]."
    CheckHasErrors = True

#  Convert STORE to path and visa-versa
V = []
for Path in VOLUMES:
    V.append(VOLUMES[Path])
    if STORE == Path or STORE == VOLUMES[Path]:
        DSPATH = Path
        DSSTORE = VOLUMES[Path]

if DSSTORE not in V:
    print("ERROR: Disk Storage " + STORE + " doesn't exist. ")
    print("    Available Disk Stores: " + str([str(item) for item in V]))
    print("    LeastUsed Disk Store : " + str(LeastUsedDS))
    ErrorMessages += " Disk Storage " + STORE + " doesn't exist. "
    CheckHasErrors = True

#  Check NIC  (NIC record)
if (NET not in VMNICS) and (NET != "None"):
    print("ERROR: Virtual NIC " + NET + " doesn't exist.")
    print("    Available VM NICs: " + str([str(item) for item in VMNICS]) + " or 'None'")
    ErrorMessages += " Virtual NIC " + NET + " doesn't exist."
    CheckHasErrors = True

#  Check ISO exists
if ISO != "" and not ISOfound:
    print("ERROR: ISO " + ISO + " not found.  Use full path to ISO")
    ErrorMessages += " ISO " + ISO + " not found.  Use full path to ISO"
    CheckHasErrors = True

#  Check if DSPATH/NAME aready exists
try:
    FullPath = DSPATH + "/" + NAME
    (stdin, stdout, stderr) = ssh.exec_command("ls -d " + FullPath)
    type(stdin)
    if stdout.readlines() and not stderr.readlines():
        print("ERROR: Directory " + FullPath + " already exists.")
        ErrorMessages += " Directory " + FullPath + " already exists."
        CheckHasErrors = True
except:
    pass

#
#      Create the VM
#
VMX = []
VMX.append('config.version = "8"')
VMX.append('virtualHW.version = "8"')
VMX.append('vmci0.present = "TRUE"')
VMX.append('displayName = "' + NAME + '"')
VMX.append('floppy0.present = "FALSE"')
VMX.append('numvcpus = "' + str(CPU) + '"')
VMX.append('scsi0.present = "TRUE"')
VMX.append('scsi0.sharedBus = "none"')
VMX.append('scsi0.virtualDev = "pvscsi"')
VMX.append('memsize = "' + str(MEM * 1024) + '"')
VMX.append('scsi0:0.present = "TRUE"')
VMX.append('scsi0:0.fileName = "' + NAME + '.vmdk"')
VMX.append('scsi0:0.deviceType = "scsi-hardDisk"')
if ISO == "":
    VMX.append('ide1:0.present = "TRUE"')
    VMX.append('ide1:0.fileName = "emptyBackingString"')
    VMX.append('ide1:0.deviceType = "atapi-cdrom"')
    VMX.append('ide1:0.startConnected = "FALSE"')
    VMX.append('ide1:0.clientDevice = "TRUE"')
else:
    VMX.append('ide1:0.present = "TRUE"')
    VMX.append('ide1:0.fileName = "' + ISO + '"')
    VMX.append('ide1:0.deviceType = "cdrom-image"')
VMX.append('pciBridge0.present = "TRUE"')
VMX.append('pciBridge4.present = "TRUE"')
VMX.append('pciBridge4.virtualDev = "pcieRootPort"')
VMX.append('pciBridge4.functions = "8"')
VMX.append('pciBridge5.present = "TRUE"')
VMX.append('pciBridge5.virtualDev = "pcieRootPort"')
VMX.append('pciBridge5.functions = "8"')
VMX.append('pciBridge6.present = "TRUE"')
VMX.append('pciBridge6.virtualDev = "pcieRootPort"')
VMX.append('pciBridge6.functions = "8"')
VMX.append('pciBridge7.present = "TRUE"')
VMX.append('pciBridge7.virtualDev = "pcieRootPort"')
VMX.append('pciBridge7.functions = "8"')
VMX.append('guestOS = "' + GUESTOS + '"')
if NET != "None":
    VMX.append('ethernet0.virtualDev = "vmxnet3"')
    VMX.append('ethernet0.present = "TRUE"')
    VMX.append('ethernet0.networkName = "' + NET + '"')
    if MAC == "":
        VMX.append('ethernet0.addressType = "generated"')
    else:
        VMX.append('ethernet0.addressType = "static"')
        VMX.append('ethernet0.address = "' + MAC + '"')

#
#   Merge extra VMX options
for VMXopt in VMXOPTS:
    try:
        k,v = VMXopt.split("=")
    except:
        k=""
        v=""
    key = k.lstrip().strip()
    value = v.lstrip().strip()
    for i in VMX:
        try:
            ikey,ivalue = i.split("=")
        except:
            break
        if ikey.lstrip().strip().lower() == key.lower():
            index = VMX.index(i)
            VMX[index] = ikey + " = " + value
            break
    else:
        if key != '' and value != '':
            VMX.append(key + " = " + value)

if isVerbose and VMXOPTS != '':
    print("VMX file:")
    for i in VMX:
        print(i)

MyVM = FullPath + "/" + NAME
if CheckHasErrors:
    Result = "Errors"
else:
    Result = "Success"

if not isDryRun and not CheckHasErrors:
    try:

        # Create NAME.vmx
        if isVerbose:
            print("Create " + NAME + ".vmx file")
        (stdin, stdout, stderr) = ssh.exec_command("mkdir " + FullPath )
        type(stdin)
        for line in VMX:
            (stdin, stdout, stderr) = ssh.exec_command("echo " + line + " >>" + MyVM + ".vmx")
            type(stdin)

        # Create vmdk
        if isVerbose:
            print("Create " + NAME + ".vmdk file")
        (stdin, stdout, stderr) = ssh.exec_command("vmkfstools -c " + str(HDISK) + "G -d " + DISKFORMAT + " " + MyVM + ".vmdk")
        type(stdin)

        # Register VM
        if isVerbose:
            print("Register VM")
        (stdin, stdout, stderr) = ssh.exec_command("vim-cmd solo/registervm " + MyVM + ".vmx")
        type(stdin)
        VMID = int(stdout.readlines()[0])

        # Power on VM
        if isVerbose:
            print("Power ON VM")
        (stdin, stdout, stderr) = ssh.exec_command("vim-cmd vmsvc/power.on " + str(VMID))
        type(stdin)
        if stderr.readlines():
            print("Error Power.on VM.")
            Result="Fail"

        # Get Generated MAC
        if NET != "None":
            (stdin, stdout, stderr) = ssh.exec_command(
                "grep -i 'ethernet0.*ddress = ' " + MyVM + ".vmx |tail -1|awk '{print $NF}'")
            type(stdin)
            GeneratedMAC = str(stdout.readlines()[0]).strip('\n"')

    except:
        print("There was an error creating the VM.")
        ErrorMessages += " There was an error creating the VM."
        Result = "Fail"

#      Print Summary

#
#   The output log string
LogOutput += '"Host":"' + HOST + '",'
LogOutput += '"Name":"' + NAME + '",'
LogOutput += '"CPU":"' + str(CPU) + '",'
LogOutput += '"Mem":"' + str(MEM) + '",'
LogOutput += '"Hdisk":"' + str(HDISK) + '",'
LogOutput += '"DiskFormat":"' + DISKFORMAT + '",'
LogOutput += '"Virtual Device":"' + VIRTDEV + '",'
LogOutput += '"Store":"' + STORE + '",'
LogOutput += '"Store Used":"' + DSPATH + '",'
LogOutput += '"Network":"' + NET + '",'
LogOutput += '"ISO":"' + ISOarg + '",'
LogOutput += '"ISO used":"' + ISO + '",'
LogOutput += '"Guest OS":"' + GUESTOS + '",'
LogOutput += '"MAC":"' + MACarg + '",'
LogOutput += '"MAC Used":"' + GeneratedMAC + '",'
LogOutput += '"Dry Run":"' + str(isDryRun) + '",'
LogOutput += '"Verbose":"' + str(isVerbose) + '",'
if ErrorMessages != "":
    LogOutput += '"Error Message":"' + ErrorMessages + '",'
LogOutput += '"Result":"' + Result + '",'
LogOutput += '"Completion Time":"' + str(theCurrDateTime()) + '"'
LogOutput += '}\n'
try:
    with open(LOG, "a+w") as FD:
        FD.write(LogOutput)
except:
    print("Error writing to log file: " + LOG)

if isSummary:
    if isDryRun:
        print("\nDry Run summary:")
    else:
        print("\nCreate VM Success:")

    if isVerbose:
        print("ESXi Host: " + HOST)
    print("VM NAME: " + NAME)
    print("vCPU: " + str(CPU))
    print("Memory: " + str(MEM) + "GB")
    print("VM Disk: " + str(HDISK) + "GB")
    if isVerbose:
        print("Format: " + DISKFORMAT)
    print("DS Store: " + DSSTORE)
    print("Network: " + NET)
    if ISO:
        print("ISO: " + ISO)
    if isVerbose:
        print("Guest OS: " + GUESTOS)
        print("MAC: " + GeneratedMAC)
else:
    pass

if CheckHasErrors:
    if isDryRun:
        print("Dry Run: Failed.")
    sys.exit(1)
else:
    if isDryRun:
        print("Dry Run: Success.")
    else:
        print(GeneratedMAC)
    sys.exit(0)

