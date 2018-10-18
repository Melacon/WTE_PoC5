import logging
import subprocess
import copy
import datetime
import uuid

import wireless_emulator.emulator
from wireless_emulator.utils import addCoreDefaultValuesToNode, addCoreDefaultStatusValuesToNode

logger = logging.getLogger(__name__)


class MwpsInterface:
    def __init__(self, intfUuid, interfaceId, neObj, supportedAlarms, physicalPortRef, conditionalPackage):
        self.uuid = intfUuid
        self.id = interfaceId
        self.supportedAlarms = supportedAlarms
        self.physicalPortRef = physicalPortRef
        self.conditionalPackage = conditionalPackage

        alarm_list = supportedAlarms.split(",")
        if len(alarm_list) < 6:
            print("Interface %s does not supply at least 6 supported alarms!" % self.uuid)
            raise RuntimeError

        self.neObj = neObj
        self.layer = 'MWPS'
        self.prefixName = 'mwps-'
        #self.interfaceName = self.prefixName + str(self.uuid)
        self.interfaceName = str(self.uuid)
        self.ltpUuid = self.interfaceName
        self.lpUuid = self.ltpUuid + '-LP-1'
        self.clientLtpNode = None

        self.emEnv = wireless_emulator.emulator.Emulator()

        self.radioSignalId = self.findRadioSignalId()

        self.transmissionModeIdList = []

        logger.debug("MwpsInterface object having name=%s created", self.interfaceName)

    def getInterfaceUuid(self):
        return self.uuid

    def getInterfaceName(self):
        return self.interfaceName

    def getNeName(self):
        return self.neObj.dockerName

    def buildCoreModelConfigXml(self):
        neNode = self.neObj.networkElementConfigXmlNode

        ltpNode = copy.deepcopy(self.neObj.ltpConfigXmlNode)
        uuid = ltpNode.find('core-model:uuid', self.neObj.namespaces)
        #ltpUuid = "ltp-" + self.interfaceName
        ltpUuid = self.ltpUuid
        uuid.text = ltpUuid
        addCoreDefaultValuesToNode(ltpNode, ltpUuid, self.neObj.namespaces)

        clientLtp = ltpNode.find('core-model:client-ltp', self.neObj.namespaces)
        self.clientLtpNode = copy.deepcopy(clientLtp)
        ltpNode.remove(clientLtp)

        lpNode = ltpNode.find('core-model:lp', self.neObj.namespaces)
        uuid = lpNode.find('core-model:uuid', self.neObj.namespaces)
        #lpUuid = "lp-" + self.interfaceName
        lpUuid = self.lpUuid
        uuid.text = lpUuid
        layerProtocolName = lpNode.find('core-model:layer-protocol-name', self.neObj.namespaces)
        layerProtocolName.text = self.layer
        terminationState = lpNode.find('core-model:termination-state', self.neObj.namespaces)
        terminationState.text = 'terminated-bidirectional'

        extension = lpNode.find('core-model:extension', self.neObj.namespaces)
        extensionSaved = copy.deepcopy(extension)
        lpNode.remove(extension)

        addCoreDefaultValuesToNode(lpNode, lpUuid, self.neObj.namespaces)

        extension = copy.deepcopy(extensionSaved)
        valName = extension.find('core-model:value-name', self.neObj.namespaces)
        valName.text = "capability"
        value = extension.find('core-model:value', self.neObj.namespaces)
        value.text = "urn:onf:params:xml:ns:yang:microwave-model?module=microwave-model"
        lpNode.append(extension)

        extension = copy.deepcopy(extensionSaved)
        valName = extension.find('core-model:value-name', self.neObj.namespaces)
        valName.text = "revision"
        value = extension.find('core-model:value', self.neObj.namespaces)
        value.text = "2018-10-10"
        lpNode.append(extension)

        extension = copy.deepcopy(extensionSaved)
        valName = extension.find('core-model:value-name', self.neObj.namespaces)
        valName.text = "conditional-package"
        value = extension.find('core-model:value', self.neObj.namespaces)
        value.text = self.conditionalPackage
        lpNode.append(extension)

        ltpDirection = ltpNode.find('core-model:ltp-direction', self.neObj.namespaces)
        ltpDirection.text = 'bidirectional'

        physicalPortRef = ltpNode.find('core-model:physical-port-reference', self.neObj.namespaces)
        physicalPortRef.text = self.physicalPortRef

        #add an equipment connector node, associated with the interface
        equipmentNode = self.neObj.configRootXmlNode.find('core-model:equipment', self.neObj.namespaces)

        equipmentConnectorNode = copy.deepcopy(self.neObj.equipmentConnectorConfigXmlNode)

        uuidNode = equipmentConnectorNode.find('core-model:uuid', self.neObj.namespaces)
        uuidNode.text = self.physicalPortRef

        connectorNode = equipmentConnectorNode.find('core-model:connector', self.neObj.namespaces)
        connectorNode.text = self.physicalPortRef

        orientationNode = equipmentConnectorNode.find('core-model:orientation', self.neObj.namespaces)
        orientationNode.text = 'female'

        addCoreDefaultValuesToNode(equipmentConnectorNode, self.physicalPortRef, self.neObj.namespaces)

        equipmentNode.append(equipmentConnectorNode)

        neNode.append(ltpNode)

    def setCoreModelClientStateXml(self, clientLtpUuid):
        neNode = self.neObj.networkElementConfigXmlNode

        for ltpNode in neNode.findall('core-model:ltp', self.neObj.namespaces):
            uuid = ltpNode.find('core-model:uuid', self.neObj.namespaces)
            logger.debug("Found ltp with ltp=%s", uuid.text)
            #if uuid.text == ('ltp-' + self.interfaceName):
            if uuid.text == self.interfaceName:
                if self.clientLtpNode is not None:
                    newClient = copy.deepcopy(self.clientLtpNode)
                    newClient.text = clientLtpUuid
                    ltpNode.append(newClient)

    def buildCoreModelStatusXml(self):
        neStatusNode = self.neObj.networkElementStatusXmlNode

        ltpNode = copy.deepcopy(self.neObj.ltpStatusXmlNode)
        uuid = ltpNode.find('uuid')
        #ltpUuid = "ltp-" + self.interfaceName
        ltpUuid = self.ltpUuid
        uuid.text = ltpUuid
        addCoreDefaultStatusValuesToNode(ltpNode)

        lpNode = ltpNode.find('lp')
        uuid = lpNode.find('uuid')
        #lpUuid = "lp-" + self.interfaceName
        lpUuid = self.lpUuid
        uuid.text = lpUuid
        addCoreDefaultStatusValuesToNode(lpNode)

        neStatusNode.append(ltpNode)

        #add equipment model info (connector)
        equipmentNode = self.neObj.statusRootXmlNode.find('equipment')

        equipmentConnectorNode = copy.deepcopy(self.neObj.equipmentConnectorStatusXmlNode)
        uuid = equipmentConnectorNode.find('uuid')
        uuid.text = self.physicalPortRef
        addCoreDefaultStatusValuesToNode(equipmentConnectorNode)

        equipmentNode.append(equipmentConnectorNode)

    def buildMicrowaveModelXml(self):
        parentNode = self.neObj.configRootXmlNode

        airInterface = copy.deepcopy(self.neObj.airInterfacePacConfigXmlNode)
        #lpUuid = "lp-" + self.interfaceName
        lpUuid = self.lpUuid

        layerProtocol = airInterface.find('microwave-model:layer-protocol', self.neObj.namespaces)
        layerProtocol.text = lpUuid

        airInterfaceConfig = airInterface.find('microwave-model:air-interface-configuration', self.neObj.namespaces)

        if self.radioSignalId is not None:
            transmittedSignalId = airInterfaceConfig.find('microwave-model:transmitted-signal-id', self.neObj.namespaces)
            transmittedSignalId.text = self.radioSignalId
            expectedSignalId = airInterfaceConfig.find('microwave-model:expected-signal-id', self.neObj.namespaces)
            expectedSignalId.text = self.radioSignalId

        if len(self.transmissionModeIdList) != 0:
            transmissionModeMin = airInterfaceConfig.find('microwave-model:transmission-mode-min',
                                                          self.neObj.namespaces)
            transmissionModeMin.text = self.transmissionModeIdList[0]
            transmissionModeMax = airInterfaceConfig.find('microwave-model:transmission-mode-max',
                                                          self.neObj.namespaces)
            transmissionModeMax.text = self.transmissionModeIdList[9]

        cryptoKey = airInterfaceConfig.find('microwave-model:cryptographic-key', self.neObj.namespaces)
        cryptoKey.text = '********'

        problemKindSeverityList = airInterfaceConfig.find('microwave-model:problem-kind-severity-list', self.neObj.namespaces)

        problemKindNode = copy.deepcopy(problemKindSeverityList)
        airInterfaceConfig.remove(problemKindSeverityList)

        alarm_list = self.supportedAlarms.split(",")
        for alarm in alarm_list:
            newNode = copy.deepcopy(problemKindNode)
            name = newNode.find('microwave-model:problem-kind-name', self.neObj.namespaces)
            name.text = alarm
            severity = newNode.find('microwave-model:problem-kind-severity', self.neObj.namespaces)
            severity.text = "warning"
            airInterfaceConfig.append(newNode)

        parentNode.append(airInterface)

    def buildMicrowaveModelStatusXml(self):
        parentNode = self.neObj.statusRootXmlNode

        airInterface = copy.deepcopy(self.neObj.airInterfaceStatusXmlNode)
        #lpUuid = "lp-" + self.interfaceName
        lpUuid = self.lpUuid

        layerProtocol = airInterface.find('layer-protocol')
        layerProtocol.text = lpUuid

        #supportedAlarms = airInterface.find(
        #    'air-interface-capability/supported-alarms')
        #supportedAlarms.text = self.supportedAlarms

        airInterfaceCapability = airInterface.find('air-interface-capability')
        supportedAlarmsList = airInterfaceCapability.find('supported-alarm-list')
        supportedAlarmsListNode = copy.deepcopy(supportedAlarmsList)
        airInterfaceCapability.remove(supportedAlarmsList)

        alarm_list = self.supportedAlarms.split(",")
        for alarm in alarm_list:
            newAlarmNode = copy.deepcopy(supportedAlarmsListNode)
            newAlarmNode.text = alarm
            airInterfaceCapability.append(newAlarmNode)

        supportedChPlan = airInterface.find(
            'air-interface-capability/supported-channel-plan-list/supported-channel-plan')
        supportedChPlan.text = "plan_1"

        supportedChannelPlanList = airInterface.find(
            'air-interface-capability/supported-channel-plan-list')
        supportedChannelPlanListNode = copy.deepcopy(supportedChannelPlanList)

        trModeList = supportedChannelPlanList.find('transmission-mode-list')
        trModeListNode = copy.deepcopy(trModeList)
        supportedChannelPlanList.remove(trModeList)

        #add example for 28 MHz channels
        for i in range(2, 12):
            newTrModeListNode = copy.deepcopy(trModeListNode)

            trModeId = newTrModeListNode.find('transmission-mode-id')
            trModeUuid = uuid.uuid4()
            #save this UUID
            self.transmissionModeIdList.append(str(trModeUuid))
            trModeId.text = str(trModeUuid)

            trModeName = newTrModeListNode.find('transmission-mode-name')
            modulation = pow(2, i)
            trModeName.text = '0028-' + str(modulation) + 'QAM-188/204-1'

            channelBandwidth = newTrModeListNode.find('channel-bandwidth')
            channelBandwidth.text = '28000'

            modulationScheme = newTrModeListNode.find('modulation-scheme')
            modulationScheme.text = str(modulation)

            codeRate = newTrModeListNode.find('code-rate')
            codeRate.text = '92'

            supportedChannelPlanList.append(newTrModeListNode)

        #add example for 80 MHz channels
        for i in range(2, 12):
            newTrModeListNode = copy.deepcopy(trModeListNode)

            trModeId = newTrModeListNode.find('transmission-mode-id')
            trModeUuid = uuid.uuid4()
            #save this UUID
            self.transmissionModeIdList.append(str(trModeUuid))
            trModeId.text = str(trModeUuid)

            trModeName = newTrModeListNode.find('transmission-mode-name')
            modulation = pow(2, i)
            trModeName.text = '0080-' + str(modulation) + 'QAM-188/204-1'

            channelBandwidth = newTrModeListNode.find('channel-bandwidth')
            channelBandwidth.text = '80000'

            modulationScheme = newTrModeListNode.find('modulation-scheme')
            modulationScheme.text = str(modulation)

            codeRate = newTrModeListNode.find('code-rate')
            codeRate.text = '92'

            supportedChannelPlanList.append(newTrModeListNode)

        seqNum = airInterface.find('air-interface-current-problems/current-problem-list/sequence-number')
        seqNum.text = "1"

        problemName = airInterface.find('air-interface-current-problems/current-problem-list/problem-name')
        alarm_list = self.supportedAlarms.split(",")
        problemName.text = alarm_list[0]

        airInterfaceStatus = airInterface.find('air-interface-status')
        transmissionModeCur = airInterfaceStatus.find('transmission-mode-cur')
        transmissionModeCur.text = self.transmissionModeIdList[0]
        if self.radioSignalId is not None:
            receivedSignalId = airInterfaceStatus.find('received-signal-id')
            receivedSignalId.text = self.radioSignalId

        airInterfaceCurrentPerformance = airInterface.find('air-interface-current-performance')
        self.addCurrentPerformanceXmlValues(airInterfaceCurrentPerformance)

        airInterfaceHistoricalPerformances = airInterface.find('air-interface-historical-performances')
        self.addHistoricalPerformancesXmlValues(airInterfaceHistoricalPerformances)

        parentNode.append(airInterface)

    def addCurrentPerformanceXmlValues(self, parentNode):
        currentPerformanceDataList = parentNode.find('current-performance-data-list')
        savedNode = copy.deepcopy(currentPerformanceDataList)
        parentNode.remove(currentPerformanceDataList)

        currentPerformanceDataList = copy.deepcopy(savedNode)
        node = currentPerformanceDataList.find('scanner-id')
        node.text = "1"
        node = currentPerformanceDataList.find('granularity-period')
        node.text = "period-15-min"
        node = currentPerformanceDataList.find('suspect-interval-flag')
        node.text = "false"
        node = currentPerformanceDataList.find('timestamp')
        node.text = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%f')[:-5] + "Z"
        node = currentPerformanceDataList.find('administrative-state')
        node.text = "unlocked"
        node = currentPerformanceDataList.find('performance-data/time-x-states-list/transmission-mode')
        node.text = self.transmissionModeIdList[0]

        parentNode.append(currentPerformanceDataList)

        currentPerformanceDataList = copy.deepcopy(savedNode)
        node = currentPerformanceDataList.find('scanner-id')
        node.text = "2"
        node = currentPerformanceDataList.find('granularity-period')
        node.text = "period-24-hours"
        node = currentPerformanceDataList.find('suspect-interval-flag')
        node.text = "false"
        node = currentPerformanceDataList.find('timestamp')
        node.text = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%f')[:-5] + "Z"
        node = currentPerformanceDataList.find('administrative-state')
        node.text = "unlocked"
        node = currentPerformanceDataList.find('performance-data/time-x-states-list/transmission-mode')
        node.text = self.transmissionModeIdList[0]
        parentNode.append(currentPerformanceDataList)

    def addHistoricalPerformancesXmlValues(self, parentNode):
        histPerfDataList = parentNode.find('historical-performance-data-list')
        savedNode = copy.deepcopy(histPerfDataList)
        parentNode.remove(histPerfDataList)

        for i in range(0,96):
            self.addHistoricalPerformances15minutes(parentNode, savedNode, i)

        for i in range(0,7):
            self.addHistoricalPerformances24hours(parentNode, savedNode, i)

    def addHistoricalPerformances15minutes(self, parentNode, savedNode, index):
        histPerfDataList = copy.deepcopy(savedNode)
        timeNow = datetime.datetime.utcnow()

        node = histPerfDataList.find('history-data-id')
        node.text = str(index)
        node = histPerfDataList.find('granularity-period')
        node.text = "period-15-min"
        node = histPerfDataList.find('suspect-interval-flag')
        node.text = "false"
        node = histPerfDataList.find('period-end-time')
        timestamp = timeNow - datetime.timedelta(minutes=15*index)
        node.text = timestamp.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-5] + "Z"
        node = histPerfDataList.find('performance-data/time-x-states-list/transmission-mode')
        node.text = self.transmissionModeIdList[0]

        parentNode.append(histPerfDataList)

    def addHistoricalPerformances24hours(self, parentNode, savedNode, index):
        histPerfDataList = copy.deepcopy(savedNode)
        timeNow = datetime.datetime.utcnow()

        node = histPerfDataList.find('history-data-id')
        node.text = str(index + 96)
        node = histPerfDataList.find('granularity-period')
        node.text = "period-24-hours"
        node = histPerfDataList.find('suspect-interval-flag')
        node.text = "false"
        node = histPerfDataList.find('period-end-time')
        timestamp = timeNow - datetime.timedelta(days=1*index)
        node.text = timestamp.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-5] + "Z"
        node = histPerfDataList.find('performance-data/time-x-states-list/transmission-mode')
        node.text = self.transmissionModeIdList[0]

        parentNode.append(histPerfDataList)

    def buildPtpModelConfigXml(self):
        parentNode = self.neObj.ptpInstanceListConfigXmlNode

        defaultDs = parentNode.find('ptp:default-ds', self.neObj.namespaces)

        numberPorts = defaultDs.find('ptp:number-ports', self.neObj.namespaces)
        num = int(numberPorts.text)
        num += 1
        numberPorts.text = str(num)

        portDsList = copy.deepcopy(self.neObj.ptpPortDsListConfigXmlNode)
        #ltpUuid = "ltp-" + self.interfaceName
        ltpUuid = self.ltpUuid

        portNumber = portDsList.find('ptp:port-number', self.neObj.namespaces)
        portNumber.text = str(self.id)

        portIdentity = portDsList.find('ptp:port-identity', self.neObj.namespaces)
        clockIdentity = portIdentity.find('ptp:clock-identity', self.neObj.namespaces)
        # byteRepr = ' '.join(format(ord(x), 'b') for x in 'LOCAL-01')
        # byteRepr.replace(" ", "")
        clockIdentity.text = 'UFRQU2xhdmU='
        portNumber = portIdentity.find('ptp:port-number', self.neObj.namespaces)
        portNumber.text = str(self.id)

        portState = portDsList.find('ptp:port-state', self.neObj.namespaces)
        portState.text = 'LISTENING'

        logMinDelay = portDsList.find('ptp:log-min-delay-req-interval', self.neObj.namespaces)
        logMinDelay.text = '-4'

        logAnounceInterval = portDsList.find('ptp:log-announce-interval', self.neObj.namespaces)
        logAnounceInterval.text = '-3'

        announceReceiptTimeout = portDsList.find('ptp:announce-receipt-timeout', self.neObj.namespaces)
        announceReceiptTimeout.text = '3'

        logSyncInterval = portDsList.find('ptp:log-sync-interval', self.neObj.namespaces)
        logSyncInterval.text = '-4'

        delayMechanism = portDsList.find('ptp:delay-mechanism', self.neObj.namespaces)
        delayMechanism.text = 'E2E'

        versionNumber = portDsList.find('ptp:version-number', self.neObj.namespaces)
        versionNumber.text = '2'

        ltp = portDsList.find('ptp-ex:logical-termination-point', self.neObj.namespaces)
        ltp.text = ltpUuid

        parentNode.append(portDsList)

    def buildPtpModelStatusXml(self):
        parentNode = self.neObj.ptpInstanceListStatusXmlNode

        portDsList = copy.deepcopy(self.neObj.ptpPortDsListStatusXmlNode)
        #ltpUuid = "ltp-" + self.interfaceName

        portNumber = portDsList.find('port-number')
        portNumber.text = str(self.id)

        portIdentity = portDsList.find('port-identity')
        portNumber = portIdentity.find('port-number')
        portNumber.text = str(self.id)

        parentNode.append(portDsList)

    def buildXmlFiles(self):
        self.buildCoreModelConfigXml()


        self.buildCoreModelStatusXml()
        self.buildMicrowaveModelStatusXml()

        #this needs to be done after the microwave model status, for the transmission mode UUIDs to be generated
        self.buildMicrowaveModelXml()

        #if self.neObj.ptpEnabled is True:
        #    self.buildPtpModelConfigXml()
        #    self.buildPtpModelStatusXml()

    def findRadioSignalId(self):
        for link in self.emEnv.topoJson['topologies']['mwps']['links']:
            if self.neObj.getNeUuid() == link[0]['uuid'] and self.uuid == link[0]['ltp']:
                return link[0]['radio-signal-id']
            elif self.neObj.getNeUuid() == link[1]['uuid'] and self.uuid == link[1]['ltp']:
                return link[1]['radio-signal-id']
        return None


class MwsInterface:

    def __init__(self, intfUuid, interfaceId, neObj, supportedAlarms, serverLtps, conditionalPackage):
        self.uuid = intfUuid
        self.id = interfaceId
        self.supportedAlarms = supportedAlarms
        self.conditionalPackage = conditionalPackage

        alarm_list = supportedAlarms.split(",")
        if len(alarm_list) < 1:
            print("Interface %s does not supply at least 1 supported alarms!" % self.uuid)
            raise RuntimeError

        self.neObj = neObj
        self.layer = 'MWS'
        self.prefixName = 'mws-'
        self.interfaceName = str(self.uuid)
        self.ltpUuid = self.interfaceName
        self.lpUuid = self.ltpUuid + "-LP-1"

        self.emEnv = wireless_emulator.emulator.Emulator()

        self.clientLtpNode = None
        self.serverLtpsList = []
        for ltp in serverLtps:
            self.serverLtpsList.append(ltp['id'])

        logger.debug("MwsInterface object having name=%s was created", self.interfaceName)

    def getInterfaceUuid(self):
        return self.uuid

    def getInterfaceName(self):
        return self.interfaceName

    def getNeName(self):
        return self.neObj.dockerName

    def buildCoreModelConfigXml(self):
        neNode = self.neObj.networkElementConfigXmlNode
        ltpNode = copy.deepcopy(self.neObj.ltpConfigXmlNode)
        uuid = ltpNode.find('core-model:uuid', self.neObj.namespaces)
        #ltpUuid = "ltp-" + self.interfaceName
        ltpUuid = self.ltpUuid
        uuid.text = ltpUuid
        addCoreDefaultValuesToNode(ltpNode, ltpUuid, self.neObj.namespaces)

        clientLtp = ltpNode.find('core-model:client-ltp', self.neObj.namespaces)
        self.clientLtpNode = copy.deepcopy(clientLtp)
        ltpNode.remove(clientLtp)

        serverLtp = ltpNode.find('core-model:server-ltp', self.neObj.namespaces)
        serverLtpNode = copy.deepcopy(serverLtp)
        ltpNode.remove(serverLtp)

        for ltp in self.serverLtpsList:
            server = copy.deepcopy(serverLtpNode)

            serverInterface = self.neObj.getInterfaceFromInterfaceUuid(ltp)
            #server.text = 'ltp-' + serverInterface.interfaceName
            server.text = serverInterface.interfaceName

            ltpNode.append(server)

            serverInterface.setCoreModelClientStateXml(self.ltpUuid)

        lpNode = ltpNode.find('core-model:lp', self.neObj.namespaces)
        uuid = lpNode.find('core-model:uuid', self.neObj.namespaces)
        #lpUuid = "lp-" + self.interfaceName
        lpUuid = self.lpUuid
        uuid.text = lpUuid
        layerProtocolName = lpNode.find('core-model:layer-protocol-name', self.neObj.namespaces)
        layerProtocolName.text = self.layer
        terminationState = lpNode.find('core-model:termination-state', self.neObj.namespaces)
        terminationState.text = 'terminated-bidirectional'

        extension = lpNode.find('core-model:extension', self.neObj.namespaces)
        extensionSaved = copy.deepcopy(extension)
        lpNode.remove(extension)

        addCoreDefaultValuesToNode(lpNode, lpUuid, self.neObj.namespaces)

        extension = copy.deepcopy(extensionSaved)
        valName = extension.find('core-model:value-name', self.neObj.namespaces)
        valName.text = "capability"
        value = extension.find('core-model:value', self.neObj.namespaces)
        value.text = "urn:onf:params:xml:ns:yang:microwave-model?module=microwave-model"
        lpNode.append(extension)

        extension = copy.deepcopy(extensionSaved)
        valName = extension.find('core-model:value-name', self.neObj.namespaces)
        valName.text = "revision"
        value = extension.find('core-model:value', self.neObj.namespaces)
        value.text = "2018-10-10"
        lpNode.append(extension)

        extension = copy.deepcopy(extensionSaved)
        valName = extension.find('core-model:value-name', self.neObj.namespaces)
        valName.text = "conditional-package"
        value = extension.find('core-model:value', self.neObj.namespaces)
        value.text = self.conditionalPackage
        lpNode.append(extension)

        ltpDirection = ltpNode.find('core-model:ltp-direction', self.neObj.namespaces)
        ltpDirection.text = 'bidirectional'

        neNode.append(ltpNode)

    def setCoreModelClientStateXml(self, clientLtpUuid):
        neNode = self.neObj.networkElementConfigXmlNode

        for ltpNode in neNode.findall('core-model:ltp', self.neObj.namespaces):
            uuid = ltpNode.find('core-model:uuid', self.neObj.namespaces)
            logger.debug("Found ltp with ltp=%s", uuid.text)
            #if uuid.text == ('ltp-' + self.interfaceName):
            if uuid.text == self.ltpUuid:
                if self.clientLtpNode is not None:
                    newClient = copy.deepcopy(self.clientLtpNode)
                    newClient.text = clientLtpUuid
                    ltpNode.append(newClient)

    def buildCoreModelStatusXml(self):
        neStatusNode = self.neObj.networkElementStatusXmlNode

        ltpNode = copy.deepcopy(self.neObj.ltpStatusXmlNode)
        uuid = ltpNode.find('uuid')
        #ltpUuid = "ltp-" + self.interfaceName
        ltpUuid = self.ltpUuid
        uuid.text = ltpUuid
        addCoreDefaultStatusValuesToNode(ltpNode)

        lpNode = ltpNode.find('lp')
        uuid = lpNode.find('uuid')
        #lpUuid = "lp-" + self.interfaceName
        lpUuid = self.lpUuid
        uuid.text = lpUuid
        addCoreDefaultStatusValuesToNode(lpNode)

        neStatusNode.append(ltpNode)

    def buildMicrowaveModelXml(self):
        parentNode = self.neObj.configRootXmlNode

        pureEthernetStructure = copy.deepcopy(self.neObj.pureEthernetPacConfigXmlNode)
        #lpUuid = "lp-" + self.interfaceName
        lpUuid = self.lpUuid

        layerProtocol = pureEthernetStructure.find('microwave-model:layer-protocol', self.neObj.namespaces)
        layerProtocol.text = lpUuid

        pureEthConfig = pureEthernetStructure.find('microwave-model:pure-ethernet-structure-configuration', self.neObj.namespaces)

        problemKindSeverityList = pureEthConfig.find('microwave-model:problem-kind-severity-list', self.neObj.namespaces)

        problemKindNode = copy.deepcopy(problemKindSeverityList)
        pureEthConfig.remove(problemKindSeverityList)

        alarm_list = self.supportedAlarms.split(",")
        for alarm in alarm_list:
            newNode = copy.deepcopy(problemKindNode)
            name = newNode.find('microwave-model:problem-kind-name', self.neObj.namespaces)
            name.text = alarm
            severity = newNode.find('microwave-model:problem-kind-severity', self.neObj.namespaces)
            severity.text = "warning"
            pureEthConfig.append(newNode)

        parentNode.append(pureEthernetStructure)

    def buildMicrowaveModelStatusXml(self):
        parentNode = self.neObj.statusRootXmlNode

        pureEthernetStructure = copy.deepcopy(self.neObj.pureEthernetStatusXmlNode)
        #lpUuid = "lp-" + self.interfaceName
        lpUuid = self.lpUuid

        layerProtocol = pureEthernetStructure.find('layer-protocol')
        layerProtocol.text = lpUuid

        structureId = pureEthernetStructure.find('pure-ethernet-structure-capability/structure-id')
        structureId.text = lpUuid

        supportedAlarms = pureEthernetStructure.find(
            'pure-ethernet-structure-capability/supported-alarms')
        supportedAlarms.text = self.supportedAlarms

        seqNum = pureEthernetStructure.find(
            'pure-ethernet-structure-current-problems/current-problem-list/sequence-number')
        seqNum.text = "1"

        problemName = pureEthernetStructure.find('pure-ethernet-structure-current-problems/current-problem-list/problem-name')
        alarm_list = self.supportedAlarms.split(",")
        problemName.text = alarm_list[0]

        currentPerformance = pureEthernetStructure.find('pure-ethernet-structure-current-performance')
        self.addCurrentPerformanceXmlValues(currentPerformance)

        historicalPerformances = pureEthernetStructure.find('pure-ethernet-structure-historical-performances')
        self.addHistoricalPerformancesXmlValues(historicalPerformances)

        parentNode.append(pureEthernetStructure)

    def addCurrentPerformanceXmlValues(self, parentNode):
        currentPerformanceDataList = parentNode.find('current-performance-data-list')
        savedNode = copy.deepcopy(currentPerformanceDataList)
        parentNode.remove(currentPerformanceDataList)

        currentPerformanceDataList = copy.deepcopy(savedNode)
        node = currentPerformanceDataList.find('scanner-id')
        node.text = "1"
        node = currentPerformanceDataList.find('granularity-period')
        node.text = "period-15-min"
        node = currentPerformanceDataList.find('suspect-interval-flag')
        node.text = "false"
        node = currentPerformanceDataList.find('timestamp')
        node.text = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%f')[:-5] + "Z"
        node = currentPerformanceDataList.find('administrative-state')
        node.text = "unlocked"
        parentNode.append(currentPerformanceDataList)

        currentPerformanceDataList = copy.deepcopy(savedNode)
        node = currentPerformanceDataList.find('scanner-id')
        node.text = "2"
        node = currentPerformanceDataList.find('granularity-period')
        node.text = "period-24-hours"
        node = currentPerformanceDataList.find('suspect-interval-flag')
        node.text = "false"
        node = currentPerformanceDataList.find('timestamp')
        node.text = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%f')[:-5] + "Z"
        node = currentPerformanceDataList.find('administrative-state')
        node.text = "unlocked"
        parentNode.append(currentPerformanceDataList)

    def addHistoricalPerformancesXmlValues(self, parentNode):
        histPerfDataList = parentNode.find('historical-performance-data-list')
        savedNode = copy.deepcopy(histPerfDataList)
        parentNode.remove(histPerfDataList)

        for i in range(0,96):
            self.addHistoricalPerformances15minutes(parentNode, savedNode, i)

        for i in range(0,7):
            self.addHistoricalPerformances24hours(parentNode, savedNode, i)

    def addHistoricalPerformances15minutes(self, parentNode, savedNode, index):
        histPerfDataList = copy.deepcopy(savedNode)
        timeNow = datetime.datetime.utcnow()

        node = histPerfDataList.find('history-data-id')
        node.text = str(index)
        node = histPerfDataList.find('granularity-period')
        node.text = "period-15-min"
        node = histPerfDataList.find('suspect-interval-flag')
        node.text = "false"
        node = histPerfDataList.find('period-end-time')
        timestamp = timeNow - datetime.timedelta(minutes=15*index)
        node.text = timestamp.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-5] + "Z"

        parentNode.append(histPerfDataList)

    def addHistoricalPerformances24hours(self, parentNode, savedNode, index):
        histPerfDataList = copy.deepcopy(savedNode)
        timeNow = datetime.datetime.utcnow()

        node = histPerfDataList.find('history-data-id')
        node.text = str(index + 96)
        node = histPerfDataList.find('granularity-period')
        node.text = "period-24-hours"
        node = histPerfDataList.find('suspect-interval-flag')
        node.text = "false"
        node = histPerfDataList.find('period-end-time')
        timestamp = timeNow - datetime.timedelta(days=1*index)
        node.text = timestamp.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-5] + "Z"

        parentNode.append(histPerfDataList)

    def buildXmlFiles(self):
        self.buildCoreModelConfigXml()
        self.buildMicrowaveModelXml()

        self.buildCoreModelStatusXml()
        self.buildMicrowaveModelStatusXml()


class MwEthContainerInterface:

    def __init__(self, intfUuid, interfaceId, neObj, supportedAlarms, serverLtps, conditionalPackage):
        self.uuid = intfUuid
        self.id = interfaceId
        self.supportedAlarms = supportedAlarms
        self.type = None
        self.conditionalPackage = conditionalPackage

        alarm_list = supportedAlarms.split(",")
        if len(alarm_list) < 2:
            print("Interface %s does not supply at least 2 supported alarms!" % self.uuid)
            raise RuntimeError

        self.neObj = neObj
        self.layer = 'ETC'
        self.prefixName = 'etc-'
        self.interfaceName = str(self.uuid)
        self.ltpUuid = self.interfaceName
        self.lpUuid = self.ltpUuid + "-LP-1"

        self.emEnv = wireless_emulator.emulator.Emulator()

        self.clientLtpNode = None
        self.serverLtps = []
        for ltp in serverLtps:
            self.serverLtps.append(ltp['id'])

        logger.debug("MwEthContainerInterface object having name=%s was created", self.interfaceName)

    def getInterfaceUuid(self):
        return self.uuid

    def getInterfaceName(self):
        return self.interfaceName

    def getNeName(self):
        return self.neObj.dockerName

    def buildCoreModelConfigXml(self):
        neNode = self.neObj.networkElementConfigXmlNode

        fdLtp = copy.deepcopy(self.neObj.fdLtpXmlNode)
        fdLtp.text = self.ltpUuid

        forwardingDomain = neNode.find('core-model:fd', self.neObj.namespaces)
        forwardingDomain.append(fdLtp)

        ltpNode = copy.deepcopy(self.neObj.ltpConfigXmlNode)
        uuid = ltpNode.find('core-model:uuid', self.neObj.namespaces)
        #ltpUuid = "ltp-" + self.interfaceName
        ltpUuid = self.ltpUuid
        uuid.text = ltpUuid
        addCoreDefaultValuesToNode(ltpNode, ltpUuid, self.neObj.namespaces)

        clientLtp = ltpNode.find('core-model:client-ltp', self.neObj.namespaces)
        self.clientLtpNode = copy.deepcopy(clientLtp)
        ltpNode.remove(clientLtp)

        serverLtp = ltpNode.find('core-model:server-ltp', self.neObj.namespaces)
        serverLtpNode = copy.deepcopy(serverLtp)
        ltpNode.remove(serverLtp)

        for ltp in self.serverLtps:
            server = copy.deepcopy(serverLtpNode)

            serverInterface = self.neObj.getInterfaceFromInterfaceUuid(ltp)
            server.text = serverInterface.interfaceName

            ltpNode.append(server)

            serverInterface.setCoreModelClientStateXml(self.ltpUuid)

        lpNode = ltpNode.find('core-model:lp', self.neObj.namespaces)
        uuid = lpNode.find('core-model:uuid', self.neObj.namespaces)
        #lpUuid = "lp-" + self.interfaceName
        lpUuid = self.lpUuid
        uuid.text = lpUuid
        layerProtocolName = lpNode.find('core-model:layer-protocol-name', self.neObj.namespaces)
        layerProtocolName.text = self.layer
        terminationState = lpNode.find('core-model:termination-state', self.neObj.namespaces)
        terminationState.text = 'terminated-bidirectional'

        extension = lpNode.find('core-model:extension', self.neObj.namespaces)
        extensionSaved = copy.deepcopy(extension)
        lpNode.remove(extension)

        addCoreDefaultValuesToNode(lpNode, lpUuid, self.neObj.namespaces)

        extension = copy.deepcopy(extensionSaved)
        valName = extension.find('core-model:value-name', self.neObj.namespaces)
        valName.text = "capability"
        value = extension.find('core-model:value', self.neObj.namespaces)
        value.text = "urn:onf:params:xml:ns:yang:microwave-model?module=microwave-model"
        lpNode.append(extension)

        extension = copy.deepcopy(extensionSaved)
        valName = extension.find('core-model:value-name', self.neObj.namespaces)
        valName.text = "revision"
        value = extension.find('core-model:value', self.neObj.namespaces)
        value.text = "2018-10-10"
        lpNode.append(extension)

        extension = copy.deepcopy(extensionSaved)
        valName = extension.find('core-model:value-name', self.neObj.namespaces)
        valName.text = "conditional-package"
        value = extension.find('core-model:value', self.neObj.namespaces)
        value.text = self.conditionalPackage
        lpNode.append(extension)

        ltpDirection = ltpNode.find('core-model:ltp-direction', self.neObj.namespaces)
        ltpDirection.text = 'bidirectional'

        neNode.append(ltpNode)

    def setCoreModelClientStateXml(self, clientLtpUuid):
        neNode = self.neObj.networkElementConfigXmlNode

        for ltpNode in neNode.findall('core-model:ltp', self.neObj.namespaces):
            uuid = ltpNode.find('core-model:uuid', self.neObj.namespaces)
            logger.debug("Found ltp with ltp=%s", uuid.text)
            if uuid.text == self.ltpUuid:
                if self.clientLtpNode is not None:
                    newClient = copy.deepcopy(self.clientLtpNode)
                    newClient.text = clientLtpUuid
                    ltpNode.append(newClient)

    def buildCoreModelStatusXml(self):
        neStatusNode = self.neObj.networkElementStatusXmlNode

        ltpNode = copy.deepcopy(self.neObj.ltpStatusXmlNode)
        uuid = ltpNode.find('uuid')
        #ltpUuid = "ltp-" + self.interfaceName
        ltpUuid = self.ltpUuid
        uuid.text = ltpUuid
        addCoreDefaultStatusValuesToNode(ltpNode)

        lpNode = ltpNode.find('lp')
        uuid = lpNode.find('uuid')
        #lpUuid = "lp-" + self.interfaceName
        lpUuid = self.lpUuid
        uuid.text = lpUuid
        addCoreDefaultStatusValuesToNode(lpNode)

        neStatusNode.append(ltpNode)

    def buildMicrowaveModelXml(self):
        parentNode = self.neObj.configRootXmlNode

        ethernetContainer = copy.deepcopy(self.neObj.ethernetContainerPacConfigXmlNode)
        #lpUuid = "lp-" + self.interfaceName
        lpUuid = self.lpUuid

        layerProtocol = ethernetContainer.find('microwave-model:layer-protocol', self.neObj.namespaces)
        layerProtocol.text = lpUuid

        ethContainerConfig = ethernetContainer.find('microwave-model:ethernet-container-configuration', self.neObj.namespaces)

        cryptoKey = ethContainerConfig.find('microwave-model:cryptographic-key', self.neObj.namespaces)
        cryptoKey.text = '********'

        problemKindSeverityList = ethContainerConfig.find('microwave-model:problem-kind-severity-list', self.neObj.namespaces)

        problemKindNode = copy.deepcopy(problemKindSeverityList)
        ethContainerConfig.remove(problemKindSeverityList)

        alarm_list = self.supportedAlarms.split(",")
        for alarm in alarm_list:
            newNode = copy.deepcopy(problemKindNode)
            name = newNode.find('microwave-model:problem-kind-name', self.neObj.namespaces)
            name.text = alarm
            severity = newNode.find('microwave-model:problem-kind-severity', self.neObj.namespaces)
            severity.text = "warning"
            ethContainerConfig.append(newNode)

        segmentsIdList = ethContainerConfig.find('microwave-model:segments-id-list',
                                                          self.neObj.namespaces)
        segmentsIdListSaved = copy.deepcopy(segmentsIdList)
        ethContainerConfig.remove(segmentsIdList)

        for struct in self.serverLtps:
            newSegmentsIdList = copy.deepcopy(segmentsIdListSaved)
            structureIdRef = newSegmentsIdList.find('microwave-model:structure-id-ref', self.neObj.namespaces)
            structureIdRef.text = 'lp-mws-' + struct
            segmentIdRef = newSegmentsIdList.find('microwave-model:segment-id-ref', self.neObj.namespaces)
            segmentIdRef.text = '1'
            ethContainerConfig.append(newSegmentsIdList)

        parentNode.append(ethernetContainer)

    def buildMicrowaveModelStatusXml(self):
        parentNode = self.neObj.statusRootXmlNode

        ethernetContainer = copy.deepcopy(self.neObj.ethernetContainerStatusXmlNode)
        #lpUuid = "lp-" + self.interfaceName
        lpUuid = self.lpUuid

        layerProtocol = ethernetContainer.find('layer-protocol')
        layerProtocol.text = lpUuid

        supportedAlarms = ethernetContainer.find(
            'ethernet-container-capability/supported-alarms')
        supportedAlarms.text = self.supportedAlarms

        seqNum = ethernetContainer.find(
            'ethernet-container-current-problems/current-problem-list/sequence-number')
        seqNum.text = "1"

        problemName = ethernetContainer.find('ethernet-container-current-problems/current-problem-list/problem-name')
        alarm_list = self.supportedAlarms.split(",")
        problemName.text = alarm_list[0]

        currentPerformance = ethernetContainer.find('ethernet-container-current-performance')
        self.addCurrentPerformanceXmlValues(currentPerformance)

        historicalPerformances = ethernetContainer.find('ethernet-container-historical-performances')
        self.addHistoricalPerformancesXmlValues(historicalPerformances)

        parentNode.append(ethernetContainer)

    def addCurrentPerformanceXmlValues(self, parentNode):
        currentPerformanceDataList = parentNode.find('current-performance-data-list')
        savedNode = copy.deepcopy(currentPerformanceDataList)
        parentNode.remove(currentPerformanceDataList)

        currentPerformanceDataList = copy.deepcopy(savedNode)
        node = currentPerformanceDataList.find('scanner-id')
        node.text = "1"
        node = currentPerformanceDataList.find('granularity-period')
        node.text = "period-15-min"
        node = currentPerformanceDataList.find('suspect-interval-flag')
        node.text = "false"
        node = currentPerformanceDataList.find('timestamp')
        node.text = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%f')[:-5] + "Z"
        node = currentPerformanceDataList.find('administrative-state')
        node.text = "unlocked"
        parentNode.append(currentPerformanceDataList)

        currentPerformanceDataList = copy.deepcopy(savedNode)
        node = currentPerformanceDataList.find('scanner-id')
        node.text = "2"
        node = currentPerformanceDataList.find('granularity-period')
        node.text = "period-24-hours"
        node = currentPerformanceDataList.find('suspect-interval-flag')
        node.text = "false"
        node = currentPerformanceDataList.find('timestamp')
        node.text = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%f')[:-5] + "Z"
        node = currentPerformanceDataList.find('administrative-state')
        node.text = "unlocked"
        parentNode.append(currentPerformanceDataList)

    def addHistoricalPerformancesXmlValues(self, parentNode):
        histPerfDataList = parentNode.find('historical-performance-data-list')
        savedNode = copy.deepcopy(histPerfDataList)
        parentNode.remove(histPerfDataList)

        for i in range(0,96):
            self.addHistoricalPerformances15minutes(parentNode, savedNode, i)

        for i in range(0,7):
            self.addHistoricalPerformances24hours(parentNode, savedNode, i)

    def addHistoricalPerformances15minutes(self, parentNode, savedNode, index):
        histPerfDataList = copy.deepcopy(savedNode)
        timeNow = datetime.datetime.utcnow()

        node = histPerfDataList.find('history-data-id')
        node.text = str(index)
        node = histPerfDataList.find('granularity-period')
        node.text = "period-15-min"
        node = histPerfDataList.find('suspect-interval-flag')
        node.text = "false"
        node = histPerfDataList.find('period-end-time')
        timestamp = timeNow - datetime.timedelta(minutes=15*index)
        node.text = timestamp.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-5] + "Z"

        parentNode.append(histPerfDataList)

    def addHistoricalPerformances24hours(self, parentNode, savedNode, index):
        histPerfDataList = copy.deepcopy(savedNode)
        timeNow = datetime.datetime.utcnow()

        node = histPerfDataList.find('history-data-id')
        node.text = str(index + 96)
        node = histPerfDataList.find('granularity-period')
        node.text = "period-24-hours"
        node = histPerfDataList.find('suspect-interval-flag')
        node.text = "false"
        node = histPerfDataList.find('period-end-time')
        timestamp = timeNow - datetime.timedelta(days=1*index)
        node.text = timestamp.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-5] + "Z"

        parentNode.append(histPerfDataList)

    def buildXmlFiles(self):
        self.buildCoreModelConfigXml()
        self.buildMicrowaveModelXml()

        self.buildCoreModelStatusXml()
        self.buildMicrowaveModelStatusXml()

class ElectricalEtyInterface:

    def __init__(self, intfUuid, interfaceId, neObj, physicalPortRef):
        self.uuid = intfUuid
        self.id = interfaceId

        self.neObj = neObj
        self.layer = 'ETY'
        self.prefixName = 'ety-'
        self.interfaceName = str(self.uuid)
        self.ltpUuid = self.interfaceName
        self.lpUuid = self.ltpUuid + "-LP-1"

        self.emEnv = wireless_emulator.emulator.Emulator()

        self.physicalPortRef = physicalPortRef
        self.clientLtpNode = None
        self.serverLtpsList = []

        self.conditionalPackage = 'wire-interface-pac'

        self.supportedAlarms = "txFault,rxLos,tempHigh,tempLow,rxLevelHigh,rxLevelLow"

        logger.debug("ElectricalEtyInterface object having name=%s was created",
                     self.interfaceName)


    def getInterfaceUuid(self):
        return self.uuid

    def getInterfaceName(self):
        return self.interfaceName

    def getNeName(self):
        return self.neObj.dockerName

    def buildCoreModelConfigXml(self):
        neNode = self.neObj.networkElementConfigXmlNode

        fdLtp = copy.deepcopy(self.neObj.fdLtpXmlNode)
        fdLtp.text = self.ltpUuid

        forwardingDomain = neNode.find('core-model:fd', self.neObj.namespaces)
        forwardingDomain.append(fdLtp)

        ltpNode = copy.deepcopy(self.neObj.ltpConfigXmlNode)
        uuid = ltpNode.find('core-model:uuid', self.neObj.namespaces)
        #ltpUuid = "ltp-" + self.interfaceName
        ltpUuid = self.ltpUuid
        uuid.text = ltpUuid
        addCoreDefaultValuesToNode(ltpNode, ltpUuid, self.neObj.namespaces)

        clientLtp = ltpNode.find('core-model:client-ltp', self.neObj.namespaces)
        self.clientLtpNode = copy.deepcopy(clientLtp)
        ltpNode.remove(clientLtp)

        lpNode = ltpNode.find('core-model:lp', self.neObj.namespaces)
        uuid = lpNode.find('core-model:uuid', self.neObj.namespaces)
        #lpUuid = "lp-" + self.interfaceName
        lpUuid = self.lpUuid
        uuid.text = lpUuid
        layerProtocolName = lpNode.find('core-model:layer-protocol-name', self.neObj.namespaces)
        layerProtocolName.text = self.layer
        terminationState = lpNode.find('core-model:termination-state', self.neObj.namespaces)
        terminationState.text = 'terminated-bidirectional'
        addCoreDefaultValuesToNode(lpNode, lpUuid, self.neObj.namespaces)

        physicalPortRef = ltpNode.find('core-model:physical-port-reference', self.neObj.namespaces)
        physicalPortRef.text = self.physicalPortRef

        extension = lpNode.find('core-model:extension', self.neObj.namespaces)
        extensionSaved = copy.deepcopy(extension)
        lpNode.remove(extension)

        extension = copy.deepcopy(extensionSaved)
        valName = extension.find('core-model:value-name', self.neObj.namespaces)
        valName.text = "capability"
        value = extension.find('core-model:value', self.neObj.namespaces)
        value.text = "urn:onf:params:xml:ns:yang:microwave-model?module=microwave-model"
        lpNode.append(extension)

        extension = copy.deepcopy(extensionSaved)
        valName = extension.find('core-model:value-name', self.neObj.namespaces)
        valName.text = "revision"
        value = extension.find('core-model:value', self.neObj.namespaces)
        value.text = "2018-10-10"
        lpNode.append(extension)

        extension = copy.deepcopy(extensionSaved)
        valName = extension.find('core-model:value-name', self.neObj.namespaces)
        valName.text = "conditional-package"
        value = extension.find('core-model:value', self.neObj.namespaces)
        value.text = self.conditionalPackage
        lpNode.append(extension)

        #add an equipment connector node, associated with the interface
        equipmentNode = self.neObj.configRootXmlNode.find('core-model:equipment', self.neObj.namespaces)

        equipmentConnectorNode = copy.deepcopy(self.neObj.equipmentConnectorConfigXmlNode)

        uuidNode = equipmentConnectorNode.find('core-model:uuid', self.neObj.namespaces)
        uuidNode.text = self.physicalPortRef

        connectorNode = equipmentConnectorNode.find('core-model:connector', self.neObj.namespaces)
        connectorNode.text = self.physicalPortRef

        orientationNode = equipmentConnectorNode.find('core-model:orientation', self.neObj.namespaces)
        orientationNode.text = 'female'

        addCoreDefaultValuesToNode(equipmentConnectorNode, self.physicalPortRef, self.neObj.namespaces)

        equipmentNode.append(equipmentConnectorNode)

        neNode.append(ltpNode)

    def buildCoreModelStatusXml(self):
        neStatusNode = self.neObj.networkElementStatusXmlNode

        ltpNode = copy.deepcopy(self.neObj.ltpStatusXmlNode)
        uuid = ltpNode.find('uuid')
        #ltpUuid = "ltp-" + self.interfaceName
        ltpUuid = self.ltpUuid
        uuid.text = ltpUuid
        addCoreDefaultStatusValuesToNode(ltpNode)

        lpNode = ltpNode.find('lp')
        uuid = lpNode.find('uuid')
        #lpUuid = "lp-" + self.interfaceName
        lpUuid = self.lpUuid
        uuid.text = lpUuid
        addCoreDefaultStatusValuesToNode(lpNode)

        neStatusNode.append(ltpNode)

        #add equipment model info (connector)
        equipmentNode = self.neObj.statusRootXmlNode.find('equipment')

        equipmentConnectorNode = copy.deepcopy(self.neObj.equipmentConnectorStatusXmlNode)
        uuid = equipmentConnectorNode.find('uuid')
        uuid.text = self.physicalPortRef
        addCoreDefaultStatusValuesToNode(equipmentConnectorNode)

        equipmentNode.append(equipmentConnectorNode)

    def setCoreModelClientStateXml(self, clientLtpUuid):
        neNode = self.neObj.networkElementConfigXmlNode

        for ltpNode in neNode.findall('core-model:ltp', self.neObj.namespaces):
            uuid = ltpNode.find('core-model:uuid', self.neObj.namespaces)
            logger.debug("Found ltp with ltp=%s", uuid.text)
            if uuid.text == self.ltpUuid:
                if self.clientLtpNode is not None:
                    newClient = copy.deepcopy(self.clientLtpNode)
                    newClient.text = clientLtpUuid
                    ltpNode.append(newClient)

#TODO this interface does not have yet a model, it is only present in the Core Model
    def buildMicrowaveModelXml(self):
        parentNode = self.neObj.configRootXmlNode

        wireInterface = copy.deepcopy(self.neObj.wireInterfaceConfigXmlNode)
        #lpUuid = "lp-" + self.interfaceName
        lpUuid = self.lpUuid

        layerProtocol = wireInterface.find('microwave-model:layer-protocol', self.neObj.namespaces)
        layerProtocol.text = lpUuid

        wireInterfaceConfig = wireInterface.find('microwave-model:wirebased-interface-configuration', self.neObj.namespaces)

        problemKindSeverityList = wireInterfaceConfig.find('microwave-model:problem-kind-severity-list', self.neObj.namespaces)

        problemKindNode = copy.deepcopy(problemKindSeverityList)
        wireInterfaceConfig.remove(problemKindSeverityList)

        alarm_list = self.supportedAlarms.split(",")
        for alarm in alarm_list:
            newNode = copy.deepcopy(problemKindNode)
            name = newNode.find('microwave-model:problem-kind-name', self.neObj.namespaces)
            name.text = alarm
            severity = newNode.find('microwave-model:problem-kind-severity', self.neObj.namespaces)
            severity.text = "warning"
            wireInterfaceConfig.append(newNode)

        parentNode.append(wireInterface)

    def buildMicrowaveModelStatusXml(self):
        parentNode = self.neObj.statusRootXmlNode

        wireInterface = copy.deepcopy(self.neObj.wireInterfaceStatusXmlNode)
        #lpUuid = "lp-" + self.interfaceName
        lpUuid = self.lpUuid

        layerProtocol = wireInterface.find('layer-protocol')
        layerProtocol.text = lpUuid

        mauIdNode = wireInterface.find('wirebased-interface-capability/available-mau-list/mau-id')
        mauId = uuid.uuid4()
        mauIdNode.text = str(mauId)

        wireInterfaceCurrentPerformance = wireInterface.find('wirebased-interface-current-performance')
        self.addCurrentPerformanceXmlValues(wireInterfaceCurrentPerformance)

        wireInterfaceHistoricalPerformances = wireInterface.find('wirebased-interface-historical-performances')
        self.addHistoricalPerformancesXmlValues(wireInterfaceHistoricalPerformances)

        parentNode.append(wireInterface)

    def addCurrentPerformanceXmlValues(self, parentNode):
        currentPerformanceDataList = parentNode.find('current-performance-data-list')
        savedNode = copy.deepcopy(currentPerformanceDataList)
        parentNode.remove(currentPerformanceDataList)

        currentPerformanceDataList = copy.deepcopy(savedNode)
        node = currentPerformanceDataList.find('scanner-id')
        node.text = "1"
        node = currentPerformanceDataList.find('granularity-period')
        node.text = "period-15-min"
        node = currentPerformanceDataList.find('suspect-interval-flag')
        node.text = "false"
        node = currentPerformanceDataList.find('timestamp')
        node.text = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%f')[:-5] + "Z"
        node = currentPerformanceDataList.find('administrative-state')
        node.text = "unlocked"

        parentNode.append(currentPerformanceDataList)

        currentPerformanceDataList = copy.deepcopy(savedNode)
        node = currentPerformanceDataList.find('scanner-id')
        node.text = "2"
        node = currentPerformanceDataList.find('granularity-period')
        node.text = "period-24-hours"
        node = currentPerformanceDataList.find('suspect-interval-flag')
        node.text = "false"
        node = currentPerformanceDataList.find('timestamp')
        node.text = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%f')[:-5] + "Z"
        node = currentPerformanceDataList.find('administrative-state')
        node.text = "unlocked"

        parentNode.append(currentPerformanceDataList)

    def addHistoricalPerformancesXmlValues(self, parentNode):
        histPerfDataList = parentNode.find('historical-performance-data-list')
        savedNode = copy.deepcopy(histPerfDataList)
        parentNode.remove(histPerfDataList)

        for i in range(0, 96):
            self.addHistoricalPerformances15minutes(parentNode, savedNode, i)

        for i in range(0, 7):
            self.addHistoricalPerformances24hours(parentNode, savedNode, i)

    def addHistoricalPerformances15minutes(self, parentNode, savedNode, index):
        histPerfDataList = copy.deepcopy(savedNode)
        timeNow = datetime.datetime.utcnow()

        node = histPerfDataList.find('history-data-id')
        node.text = str(index)
        node = histPerfDataList.find('granularity-period')
        node.text = "period-15-min"
        node = histPerfDataList.find('suspect-interval-flag')
        node.text = "false"
        node = histPerfDataList.find('period-end-time')
        timestamp = timeNow - datetime.timedelta(minutes=15 * index)
        node.text = timestamp.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-5] + "Z"

        parentNode.append(histPerfDataList)

    def addHistoricalPerformances24hours(self, parentNode, savedNode, index):
        histPerfDataList = copy.deepcopy(savedNode)
        timeNow = datetime.datetime.utcnow()

        node = histPerfDataList.find('history-data-id')
        node.text = str(index + 96)
        node = histPerfDataList.find('granularity-period')
        node.text = "period-24-hours"
        node = histPerfDataList.find('suspect-interval-flag')
        node.text = "false"
        node = histPerfDataList.find('period-end-time')
        timestamp = timeNow - datetime.timedelta(days=1 * index)
        node.text = timestamp.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-5] + "Z"

        parentNode.append(histPerfDataList)


    def buildPtpModelConfigXml(self):
        parentNode = self.neObj.ptpInstanceListConfigXmlNode

        defaultDs = parentNode.find('ptp:default-ds', self.neObj.namespaces)

        numberPorts = defaultDs.find('ptp:number-ports', self.neObj.namespaces)
        num = int(numberPorts.text)
        num += 1
        numberPorts.text = str(num)

        portDsList = copy.deepcopy(self.neObj.ptpPortDsListConfigXmlNode)
        #ltpUuid = "ltp-" + self.interfaceName
        ltpUuid = self.ltpUuid

        portNumber = portDsList.find('ptp:port-number', self.neObj.namespaces)
        portNumber.text = str(self.id)

        portIdentity = portDsList.find('ptp:port-identity', self.neObj.namespaces)
        clockIdentity = portIdentity.find('ptp:clock-identity', self.neObj.namespaces)
        # byteRepr = ' '.join(format(ord(x), 'b') for x in 'LOCAL-01')
        # byteRepr.replace(" ", "")
        clockIdentity.text = 'UFRQU2xhdmU='
        portNumber = portIdentity.find('ptp:port-number', self.neObj.namespaces)
        portNumber.text = str(self.id)

        portState = portDsList.find('ptp:port-state', self.neObj.namespaces)
        portState.text = 'LISTENING'

        logMinDelay = portDsList.find('ptp:log-min-delay-req-interval', self.neObj.namespaces)
        logMinDelay.text = '-4'

        logAnounceInterval = portDsList.find('ptp:log-announce-interval', self.neObj.namespaces)
        logAnounceInterval.text = '-3'

        announceReceiptTimeout = portDsList.find('ptp:announce-receipt-timeout', self.neObj.namespaces)
        announceReceiptTimeout.text = '3'

        logSyncInterval = portDsList.find('ptp:log-sync-interval', self.neObj.namespaces)
        logSyncInterval.text = '-4'

        delayMechanism = portDsList.find('ptp:delay-mechanism', self.neObj.namespaces)
        delayMechanism.text = 'E2E'

        versionNumber = portDsList.find('ptp:version-number', self.neObj.namespaces)
        versionNumber.text = '2'

        ltp = portDsList.find('ptp-ex:logical-termination-point', self.neObj.namespaces)
        ltp.text = ltpUuid

        parentNode.append(portDsList)

    def buildPtpModelStatusXml(self):
        parentNode = self.neObj.ptpInstanceListStatusXmlNode

        portDsList = copy.deepcopy(self.neObj.ptpPortDsListStatusXmlNode)
        #ltpUuid = "ltp-" + self.interfaceName

        portNumber = portDsList.find('port-number')
        portNumber.text = str(self.id)

        portIdentity = portDsList.find('port-identity')
        portNumber = portIdentity.find('port-number')
        portNumber.text = str(self.id)

        parentNode.append(portDsList)

    def buildXmlFiles(self):

        self.buildCoreModelConfigXml()
        self.buildCoreModelStatusXml()

        self.buildMicrowaveModelXml()
        self.buildMicrowaveModelStatusXml()

        #if self.neObj.ptpEnabled is True:
        #    self.buildPtpModelConfigXml()
        #    self.buildPtpModelStatusXml()


class EthCtpInterface:

    def __init__(self, intfUuid, interfaceId, neObj, serverLtps, conditionalPackage):
        self.uuid = intfUuid
        self.id = interfaceId
        self.conditionalPackage = conditionalPackage

        self.neObj = neObj
        self.layer = 'ETH'
        self.prefixName = 'eth-'
        self.interfaceName = str(self.uuid)
        self.ltpUuid = self.interfaceName
        self.lpUuid = self.ltpUuid + "-LP-1"

        self.serverLtpsList = []
        for ltp in serverLtps:
            self.serverLtpsList.append(ltp['id'])

        self.emEnv = wireless_emulator.emulator.Emulator()

        self.vlanId = self.findVlanId()

        logger.debug("EthCtpInterface object having name=%s was created", self.interfaceName)

    def getInterfaceUuid(self):
        return self.uuid

    def getInterfaceName(self):
        return self.interfaceName

    def getNeName(self):
        return self.neObj.dockerName

    def findVlanId(self):
        for link in self.emEnv.topoJson['topologies']['ety']['links']:
            if self.neObj.getNeUuid() == link[0]['uuid'] and self.uuid == link[0]['ltp']:
                return link[0]['vlan-id']
            elif self.neObj.getNeUuid() == link[1]['uuid'] and self.uuid == link[1]['ltp']:
                return link[1]['vlan-id']
        for xconn in self.neObj.eth_x_connect:
            if xconn['fcPorts'][0]['ltp'] == self.uuid:
                return xconn['fcPorts'][0]['vlan-id']
            elif xconn['fcPorts'][1]['ltp'] == self.uuid:
                return xconn['fcPorts'][1]['vlan-id']
        return '0'

    def buildCoreModelConfigXml(self):
        neNode = self.neObj.networkElementConfigXmlNode
        ltpNode = copy.deepcopy(self.neObj.ltpConfigXmlNode)
        uuid = ltpNode.find('core-model:uuid', self.neObj.namespaces)
        #ltpUuid = "ltp-" + self.interfaceName
        ltpUuid = self.ltpUuid
        uuid.text = ltpUuid
        addCoreDefaultValuesToNode(ltpNode, ltpUuid, self.neObj.namespaces)

        lpNode = ltpNode.find('core-model:lp', self.neObj.namespaces)
        uuid = lpNode.find('core-model:uuid', self.neObj.namespaces)
        #lpUuid = "lp-" + self.interfaceName
        lpUuid = self.lpUuid
        uuid.text = lpUuid
        layerProtocolName = lpNode.find('core-model:layer-protocol-name', self.neObj.namespaces)
        layerProtocolName.text = self.layer
        terminationState = lpNode.find('core-model:termination-state', self.neObj.namespaces)
        terminationState.text = 'lp-can-never-terminate'

        extension = lpNode.find('core-model:extension', self.neObj.namespaces)
        extensionSaved = copy.deepcopy(extension)
        lpNode.remove(extension)

        addCoreDefaultValuesToNode(lpNode, lpUuid, self.neObj.namespaces)

        extension = copy.deepcopy(extensionSaved)
        valName = extension.find('core-model:value-name', self.neObj.namespaces)
        valName.text = "capability"
        value = extension.find('core-model:value', self.neObj.namespaces)
        value.text = "urn:onf:params:xml:ns:yang:onf-ethernet-conditional-packages?module=onf-ethernet-conditional-packages"
        lpNode.append(extension)

        extension = copy.deepcopy(extensionSaved)
        valName = extension.find('core-model:value-name', self.neObj.namespaces)
        valName.text = "revision"
        value = extension.find('core-model:value', self.neObj.namespaces)
        value.text = "2017-04-02"
        lpNode.append(extension)

        extension = copy.deepcopy(extensionSaved)
        valName = extension.find('core-model:value-name', self.neObj.namespaces)
        valName.text = "conditional-package"
        value = extension.find('core-model:value', self.neObj.namespaces)
        value.text = self.conditionalPackage
        lpNode.append(extension)

        ltpDirection = ltpNode.find('core-model:ltp-direction', self.neObj.namespaces)
        ltpDirection.text = 'bidirectional'

        serverLtp = ltpNode.find('core-model:server-ltp', self.neObj.namespaces)
        serverLtpNode = copy.deepcopy(serverLtp)
        ltpNode.remove(serverLtp)

        for ltp in self.serverLtpsList:
            server = copy.deepcopy(serverLtpNode)

            serverInterface = self.neObj.getInterfaceFromInterfaceUuid(ltp)
            server.text = serverInterface.interfaceName
            ltpNode.append(server)

            serverInterface.setCoreModelClientStateXml(self.ltpUuid)

        neNode.append(ltpNode)

    def buildCoreModelStatusXml(self):
        neStatusNode = self.neObj.networkElementStatusXmlNode

        ltpNode = copy.deepcopy(self.neObj.ltpStatusXmlNode)
        uuid = ltpNode.find('uuid')
        #ltpUuid = "ltp-" + self.interfaceName
        ltpUuid = self.ltpUuid
        uuid.text = ltpUuid
        addCoreDefaultStatusValuesToNode(ltpNode)

        lpNode = ltpNode.find('lp')
        uuid = lpNode.find('uuid')
        #lpUuid = "lp-" + self.interfaceName
        lpUuid = self.lpUuid
        uuid.text = lpUuid
        addCoreDefaultStatusValuesToNode(lpNode)

        neStatusNode.append(ltpNode)

    def buildEthernetModelConfigXml(self):
        parentNode = self.neObj.configRootXmlNode

        ethernetPac = copy.deepcopy(self.neObj.ethernetPacConfigXmlNode)
        #lpUuid = "lp-" + self.interfaceName
        lpUuid = self.lpUuid

        layerProtocol = ethernetPac.find('onf-ethernet-conditional-packages:layer-protocol', self.neObj.namespaces)
        layerProtocol.text = lpUuid

        ethernetConfig = ethernetPac.find('onf-ethernet-conditional-packages:ethernet-configuration',
                                          self.neObj.namespaces)
        vlanId = ethernetConfig.find('onf-ethernet-conditional-packages:vlan-id', self.neObj.namespaces)
        if self.vlanId is not None:
            vlanId.text = self.vlanId
        else:
            vlanId.text = '0'

        #TODO need to implement

        parentNode.append(ethernetPac)

    def buildEthernetModelStatusXml(self):
        parentNode = self.neObj.statusRootXmlNode

        ethernetPac = copy.deepcopy(self.neObj.ethernetPacStatusXmlNode)
        #lpUuid = "lp-" + self.interfaceName
        lpUuid = self.lpUuid

        layerProtocol = ethernetPac.find('layer-protocol')
        layerProtocol.text = lpUuid

        # TODO need to implement

        parentNode.append(ethernetPac)

    def buildXmlFiles(self):

        self.buildCoreModelConfigXml()
        self.buildCoreModelStatusXml()
        #self.buildEthernetModelConfigXml()
        #self.buildEthernetModelStatusXml()