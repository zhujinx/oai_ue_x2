#!/usr/bin/env python

#
# Standard geni-lib/portal libraries
#
import geni.portal as portal
import geni.rspec.pg as rspec
import geni.rspec.emulab as elab
import geni.rspec.igext as IG
import geni.urn as URN


tourDescription = """

# EXPERIMENTAL PROFILE TO TEST SDR UE

Use this profile to instantiate an experiment using Open Air Interface
to realize an end-to-end SDR-based mobile network. This profile includes
the following resources:

  * SDR UE (Intel NUC + USRP B210) running OAI on Ubuntu 16 ('rue1')
  * SDR eNodeB (Intel NUC + USRP B210) running OAI on Ubuntu 16 ('enb1')
  * All-in-one EPC node (HSS, MME, SPGW) running OAI on Ubuntu 16 ('epc')

PhantomNet startup scripts automatically configure OAI for the
specific allocated resources.

For more detailed information:

  * [Getting Started](https://gitlab.flux.utah.edu/jczhu/OAI_UE/blob/master/README.md)

""";

tourInstructions = """
After booting is complete,

1 First you need to recompile eNB in node `enb1`:

cd /opt/oai/openairinterface5g

bash

source oaienv

cd cmake_targets/

sudo ./build_oai -c -C --eNB -w USRP


2 recompile UE in node `rue1`:

cd /opt/oai/openairinterface5g

bash

source oaienv

cd ./cmake_targets/

sudo ./build_oai -c -C --UE -w USRP # add -x for softscope

cd ./tools/

sudo ./init_nas_s1 UE

3 add ueinfo in node 'epc'

mysql -u root -p # password : linux

``` bash
mysql> use oai_db  
mysql> INSERT INTO pdn (`id`, `apn`, `pdn_type`, `pdn_ipv4`, `pdn_ipv6`, `aggregate_ambr_ul`, `aggregate_ambr_dl`, `pgw_id`, `users_imsi`, `qci`, `priority_level`,`pre_emp_cap`,`pre_emp_vul`, `LIPA-Permissions`) VALUES ('3',  'oai.ipv4','IPV4', '0.0.0.0', '0:0:0:0:0:0:0:0', '50000000', '100000000', '2',  '998981234560308', '9', '15', 'DISABLED', 'ENABLED', 'LIPA-ONLY');   
mysql> INSERT INTO users (`imsi`, `msisdn`, `imei`, `imei_sv`, `ms_ps_status`, `rau_tau_timer`, `ue_ambr_ul`, `ue_ambr_dl`, `access_restriction`, `mme_cap`, `mmeidentity_idmmeidentity`, `key`, `RFSP-Index`, `urrp_mme`, `sqn`, `rand`, `OPc`) VALUES ('998981234560308',  '33638060308', NULL, NULL, 'PURGED', '120', '50000000', '100000000', '47', '0000000000', '1', 0x00112233445566778899aabbccddeeff, '1', '0', 0, 0x00000000000000000000000000000000, 0x0ED47545168EAFE2C39C075829A7B61F);   
```

4 run oai enb and EPC in node `enb1`

sudo /local/repository/bin/start_oai.pl

5 run tdd ue in node `rue1`:

cd  /opt/oai/openairinterface5g/targets/bin

sudo ./lte-softmodem.Rel14  -U -T -C 2350000000 --ue-txgain 70 --ue-rxgain 90 --ue-scan-carrier -r 25 # add -d for softscope


""";


#
# PhantomNet extensions.
#
import geni.rspec.emulab.pnext as PN

#
# Globals
#
class GLOBALS(object):
    OAI_DS = "urn:publicid:IDN+emulab.net:powdersandbox+ltdataset+OAI"
    OAI_SIM_DS = "urn:publicid:IDN+emulab.net:phantomnet+dataset+PhantomNet:oai"
    UE_IMG  = URN.Image(PN.PNDEFS.PNET_AM, "PhantomNet:ANDROID444-STD")
    ADB_IMG = URN.Image(PN.PNDEFS.PNET_AM, "PhantomNet:UBUNTU14-64-PNTOOLS")
    OAI_EPC_IMG = URN.Image(PN.PNDEFS.PNET_AM, "PhantomNet:UBUNTU16-64-OAIEPC")
    OAI_ENB_IMG = URN.Image(PN.PNDEFS.PNET_AM, "PhantomNet:OAI-Real-Hardware.enb1")
    OAI_SIM_IMG = URN.Image(PN.PNDEFS.PNET_AM, "PhantomNet:UBUNTU14-64-OAI")
    OAI_CONF_SCRIPT = "/usr/bin/sudo /local/repository/bin/config_oai.pl"
    SIM_HWTYPE = "d430"
    NUC_HWTYPE = "nuc5300"
    UE_HWTYPE = "nexus5"

def connectOAI_DS(node, sim):
    # Create remote read-write clone dataset object bound to OAI dataset
    bs = request.RemoteBlockstore("ds-%s" % node.name, "/opt/oai")
    if sim == 1:
	bs.dataset = GLOBALS.OAI_SIM_DS
    else:
	bs.dataset = GLOBALS.OAI_DS
    bs.rwclone = True

    # Create link from node to OAI dataset rw clone
    node_if = node.addInterface("dsif_%s" % node.name)
    bslink = request.Link("dslink_%s" % node.name)
    bslink.addInterface(node_if)
    bslink.addInterface(bs.interface)
    bslink.vlan_tagging = True
    bslink.best_effort = True

#
# This geni-lib script is designed to run in the PhantomNet Portal.
#
pc = portal.Context()

#
# Profile parameters.
#
pc.defineParameter("FIXED_UE", "Bind to a specific UE",
                   portal.ParameterType.STRING, "", advanced=True,
                   longDescription="Input the name of a PhantomNet UE node to allocate (e.g., 'ue1').  Leave blank to let the mapping algorithm choose.")
pc.defineParameter("FIXED_ENB", "Bind to a specific eNodeB",
                   portal.ParameterType.STRING, "", advanced=True,
                   longDescription="Input the name of a PhantomNet eNodeB device to allocate (e.g., 'nuc1').  Leave blank to let the mapping algorithm choose.  If you bind both UE and eNodeB devices, mapping will fail unless there is path between them via the attenuator matrix.")

pc.defineParameter("TYPE", "Experiment type",
                   portal.ParameterType.STRING,"ota",[("sim","Simulated UE"),("atten","Real UE with attenuator"),("ota","Over the air")],
                   longDescription="*Simulated UE*: OAI simulated UE connects to an OAI eNodeB and EPC. *Real UE with attenuator*: Real RF devices will be connected via transmission lines with variable attenuator control. *Over the air*: Real RF devices with real antennas and transmissions propagated through free space will be selected.")

#pc.defineParameter("RADIATEDRF", "Radiated (over-the-air) RF transmissions",
#                   portal.ParameterType.BOOLEAN, False,
#                   longDescription="When enabled, RF devices with real antennas and transmissions propagated through free space will be selected.  Leave disabled (default) to assign RF devices connected via transmission lines with variable attenuator control.")

params = pc.bindParameters()

#
# Give the library a chance to return nice JSON-formatted exception(s) and/or
# warnings; this might sys.exit().
#
pc.verifyParameters()

#
# Create our in-memory model of the RSpec -- the resources we're going
# to request in our experiment, and their configuration.
#
request = pc.makeRequestRSpec()
epclink = request.Link("s1-lan")

# Checking for oaisim

if params.TYPE == "sim":
    sim_enb = request.RawPC("sim-enb")
    sim_enb.disk_image = GLOBALS.OAI_SIM_IMG
    sim_enb.hardware_type = GLOBALS.SIM_HWTYPE
    sim_enb.addService(rspec.Execute(shell="sh", command=GLOBALS.OAI_CONF_SCRIPT + " -r SIM_ENB"))
    connectOAI_DS(sim_enb, 1)
    epclink.addNode(sim_enb)
else:
    # Add a node to act as the ADB target host
    #adb_t = request.RawPC("adb-tgt")
    #adb_t.disk_image = GLOBALS.ADB_IMG

    # Add a NUC eNB node.
    enb1 = request.RawPC("enb1")
    if params.FIXED_ENB:
        enb1.component_id = params.FIXED_ENB
    enb1.hardware_type = GLOBALS.NUC_HWTYPE
    enb1.disk_image = GLOBALS.OAI_ENB_IMG
    enb1.Desire( "rf-radiated" if params.TYPE == "ota" else "rf-controlled", 1 )
    connectOAI_DS(enb1, 0)
    enb1.addService(rspec.Execute(shell="sh", command=GLOBALS.OAI_CONF_SCRIPT + " -r ENB"))
    enb1_rue1_rf = enb1.addInterface("rue1_rf")

	    # Add a NUC eNB node.
    enb2 = request.RawPC("enb2")
    if params.FIXED_ENB:
        enb2.component_id = params.FIXED_ENB
    enb2.hardware_type = GLOBALS.NUC_HWTYPE
    enb2.disk_image = GLOBALS.OAI_ENB_IMG
    enb2.Desire( "rf-radiated" if params.TYPE == "ota" else "rf-controlled", 1 )
    connectOAI_DS(enb2, 0)
    enb2.addService(rspec.Execute(shell="sh", command=GLOBALS.OAI_CONF_SCRIPT + " -r ENB"))
    enb2_rue1_rf = enb2.addInterface("rue1_rf")
	
    # Add an OTS (Nexus 5) UE
    rue1 = request.RawPC("rue1")
    if params.FIXED_UE:
        rue1.component_id = params.FIXED_UE
    rue1.hardware_type = GLOBALS.NUC_HWTYPE
    rue1.disk_image = GLOBALS.OAI_ENB_IMG
    rue1.Desire( "rf-radiated" if params.TYPE == "ota" else "rf-controlled", 1 )
    connectOAI_DS(rue1, 0)
    enb1.addService(rspec.Execute(shell="sh", command=GLOBALS.OAI_CONF_SCRIPT + " -r UE"))
    rue1_enb1_rf = rue1.addInterface("enb1_rf")
    rue1_enb2_rf = rue1.addInterface("enb2_rf")

	
    # Create the RF link between the Nexus 5 UE and eNodeB
    rflink1 = request.RFLink("rflink1")
    rflink1.addInterface(enb1_rue1_rf)
    rflink1.addInterface(rue1_enb1_rf)

    # Create the RF link between the Nexus 5 UE and eNodeB
    rflink2 = request.RFLink("rflink2")
    rflink2.addInterface(enb2_rue1_rf)
    rflink2.addInterface(rue1_enb2_rf)
	
    # Add a link connecting the NUC eNB and the OAI EPC node.
    epclink.addNode(enb1)
    epclink.addNode(enb2)

	
# Add OAI EPC (HSS, MME, SPGW) node.
epc = request.RawPC("epc")
epc.disk_image = GLOBALS.OAI_EPC_IMG
epc.addService(rspec.Execute(shell="sh", command=GLOBALS.OAI_CONF_SCRIPT + " -r EPC"))
connectOAI_DS(epc, 0)
 
epclink.addNode(epc)
epclink.link_multiplexing = True
epclink.vlan_tagging = True
epclink.best_effort = True

tour = IG.Tour()
tour.Description(IG.Tour.MARKDOWN, tourDescription)
tour.Instructions(IG.Tour.MARKDOWN, tourInstructions)
request.addTour(tour)

#
# Print and go!
#
pc.printRequestRSpec(request)
