import logging
import copy

from wireless_emulator.utils import addCoreDefaultValuesToNode, printErrorAndExit, addCoreDefaultStatusValuesToNode


logger = logging.getLogger(__name__)


class EthCrossConnect:

    def __init__(self, id, neObj, ethCrossConnect):
        self.id = id
        self.neObj = neObj
        self.hostAvailable = ethCrossConnect['host']
        self.uuid = None

        self.fcPortList = ethCrossConnect['fcPorts']
        self.fcRoute = ethCrossConnect['fcRoute']

        self.interfacesObj = []

        if len(self.fcPortList) != 2:
            logger.critical("Incorrect ethernet cross connection defined in JSON config file. It does not contain exactly two interfaces!")
            raise ValueError("Incorrect ethernet cross connection defined in JSON config file. It does not contain exactly two interfaces!")

        if self.validateXConnEnds() is False:
            logger.critical("Interfaces defining eth cross connect not valid: ", self.fcPortList[0], self.fcPortList[1])
            raise ValueError("Interfaces defining eth cross connect not valid: ", self.fcPortList[0], self.fcPortList[1])

        logger.debug("Link object was created")

    def validateXConnEnds(self):

        intfObj = self.neObj.getInterfaceFromInterfaceUuid(self.fcPortList[0]['ltp'])
        if intfObj is not None:
            if intfObj.layer == 'ETH':
                self.interfacesObj.append(intfObj)
            else:
                logger.critical("Interface=%s is not of type ETH in NE=%s", self.fcPortList[0]['ltp'], self.neObj.uuid)
        else:
            logger.critical("Interface=%s not found in NE=%s", self.fcPortList[0]['ltp'], self.neObj.uuid)

        intfObj = self.neObj.getInterfaceFromInterfaceUuid(self.fcPortList[1]['ltp'])

        if intfObj is not None:
            if intfObj.layer == 'ETH':
                self.interfacesObj.append(intfObj)
            else:
                logger.critical("Interface=%s is not of type ETH in NE=%s", self.fcPortList[1]['ltp'], self.neObj.uuid)
        else:
            logger.critical("Interface=%s not found in NE=%s", self.fcPortList[1]['ltp'], self.neObj.uuid)

        if len(self.interfacesObj) != 2:
            return False

        self.uuid = self.interfacesObj[0].serverLtpsList[0] + '-' + self.interfacesObj[0].vlanId + ',' + \
                    self.interfacesObj[1].serverLtpsList[0] + '-' + self.interfacesObj[1].vlanId

        return True

    #TODO implement host functionality
    def addXConn(self):

        bridgeName = 'xc_br' + str(self.id)

        print("Adding bridge interface %s to docker container %s..." % (bridgeName, self.neObj.uuid))

        command = "ip link add name %s type bridge" % bridgeName
        self.neObj.executeCommandInContainer(command)

        command = "ip link set dev %s master %s" % (self.interfacesObj[0].getInterfaceName(), bridgeName)
        self.neObj.executeCommandInContainer(command)

        command = "ip link set dev %s master %s" % (self.interfacesObj[1].getInterfaceName(), bridgeName)
        self.neObj.executeCommandInContainer(command)

        if self.hostAvailable is True:
            ipAddress = str(self.neObj.emEnv.intfIpFactory.getFreeInterfaceIp())
            mask = str(self.neObj.emEnv.intfIpFactory.netmask)

            command = "ip address add %s/%s dev %s" % (ipAddress, mask, bridgeName)
            self.neObj.executeCommandInContainer(command)
            print("Adding IP address %s for host in bridge %s" % (ipAddress, bridgeName))

        command = "ip link set dev %s up" % bridgeName
        self.neObj.executeCommandInContainer(command)

    def addXConnToScript(self):

        bridgeName = 'xc_br' + str(self.id)

        command = "ip link add name %s type bridge\n" % bridgeName
        self.neObj.scriptIntf.write(command)

        command = "ip link set dev %s master %s\n" % (self.interfacesObj[0].getInterfaceName(), bridgeName)
        self.neObj.scriptIntf.write(command)

        command = "ip link set dev %s master %s\n" % (self.interfacesObj[1].getInterfaceName(), bridgeName)
        self.neObj.scriptIntf.write(command)

        if self.hostAvailable is True:
            ipAddress = str(self.neObj.emEnv.intfIpFactory.getFreeInterfaceIp())
            mask = str(self.neObj.emEnv.intfIpFactory.netmask)

            command = "ip address add %s/%s dev %s\n" % (ipAddress, mask, bridgeName)
            self.neObj.scriptIntf.write(command)

        command = "ip link set dev %s up\n" % bridgeName
        self.neObj.scriptIntf.write(command)

    def buildXmlFiles(self):
        self.buildConfigXmlFiles()
        self.buildStatusXmlFiles()

    def buildConfigXmlFiles(self):
        parentNode = self.neObj.configRootXmlNode

        forwardingDomain = self.neObj.networkElementConfigXmlNode.find('core-model:fd', self.neObj.namespaces)
        fd_fc_node = copy.deepcopy(self.neObj.forwardingDomainForwardingConstructXmlNode)
        fd_fc_node.text = self.uuid
        forwardingDomain.append(fd_fc_node)

        forwardingConstruct = copy.deepcopy(self.neObj.forwardingConstructConfigXmlNode)

        uuid = forwardingConstruct.find('core-model:uuid', self.neObj.namespaces)
        uuid.text = self.uuid

        layerProtocolName = forwardingConstruct.find('core-model:layer-protocol-name', self.neObj.namespaces)
        layerProtocolName.text = 'ETH'

        fcRoute = forwardingConstruct.find('core-model:fc-route', self.neObj.namespaces)
        fcRoute.text = self.fcRoute

        fcPort = forwardingConstruct.find('core-model:fc-port', self.neObj.namespaces)

        fcPortSaved = copy.deepcopy(fcPort)
        forwardingConstruct.remove(fcPort)

        for i in range(0,2):
            fcPort = copy.deepcopy(fcPortSaved)
            fcPortUuid = self.interfacesObj[i].getInterfaceUuid() + '_fc_port'

            uuid = fcPort.find('core-model:uuid', self.neObj.namespaces)
            uuid.text = fcPortUuid

            role = fcPort.find('core-model:role', self.neObj.namespaces)
            fcPort.remove(role)

            fcRouteNeeds = fcPort.find('core-model:fc-route-feeds-fc-port-egress', self.neObj.namespaces)
            fcPort.remove(fcRouteNeeds)

            ltpNode = fcPort.find('core-model:ltp', self.neObj.namespaces)
            ltpNode.text = self.interfacesObj[i].ltpUuid

            fcPortDirection = fcPort.find('core-model:fc-port-direction', self.neObj.namespaces)
            fcPortDirection.text = 'bidirectional'

            isProtectionLockout = fcPort.find('core-model:is-protection-lock-out', self.neObj.namespaces)
            isProtectionLockout.text = 'false'

            selectionPriority = fcPort.find('core-model:selection-priority', self.neObj.namespaces)
            selectionPriority.text = '0'

            addCoreDefaultValuesToNode(fcPort, fcPortUuid, self.neObj.namespaces)

            forwardingConstruct.append(fcPort)

        uselessNode = forwardingConstruct.find('core-model:fc-switch', self.neObj.namespaces)
        forwardingConstruct.remove(uselessNode)

        forwardingDirection = forwardingConstruct.find('core-model:forwarding-direction', self.neObj.namespaces)
        forwardingDirection.text = 'bidirectional'

        isProtectionLockout = forwardingConstruct.find('core-model:is-protection-lock-out', self.neObj.namespaces)
        isProtectionLockout.text = 'false'

        servicePriority = forwardingConstruct.find('core-model:service-priority', self.neObj.namespaces)
        servicePriority.text = '0'

        addCoreDefaultValuesToNode(forwardingConstruct, self.uuid, self.neObj.namespaces)

        parentNode.append(forwardingConstruct)

    def buildStatusXmlFiles(self):
        parentNode = self.neObj.statusRootXmlNode

        forwardingConstruct  = copy.deepcopy(self.neObj.forwardingConstructStatusXmlNode)
        uuid = forwardingConstruct.find('uuid')
        uuid.text = self.uuid

        fcPort = forwardingConstruct.find('fc-port')

        fcPortSaved = copy.deepcopy(fcPort)
        forwardingConstruct.remove(fcPort)

        for i in range(0, 2):
            fcPort = copy.deepcopy(fcPortSaved)
            fcPortUuid = self.interfacesObj[i].getInterfaceUuid() + '_fc_port'

            uuid = fcPort.find('uuid')
            uuid.text = fcPortUuid

            addCoreDefaultStatusValuesToNode(fcPort)

            forwardingConstruct.append(fcPort)

        addCoreDefaultStatusValuesToNode(forwardingConstruct)

        parentNode.append(forwardingConstruct)