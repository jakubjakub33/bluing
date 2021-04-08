#!/usr/bin/env python3

import sys
import io
import logging
import threading
import subprocess
from subprocess import STDOUT

import pkg_resources
from bluepy.btle import Peripheral
from bluepy.btle import BTLEException, BTLEDisconnectError
from pyclui import green, blue, yellow, red, \
                   INFO_INDENT, ERROR_INDENT, WARNING_INDENT
from pyclui import Logger

import dbus
import dbus.service
import dbus.mainloop.glib
from dbus import SystemBus
from dbus import ObjectPath

from .common import BLUEZ_NAME, mainloop
from .agent import Agent


logger = Logger(__name__, logging.INFO)

from . import BlueScanner

IFACE_AGENT_MGR_1 = 'org.bluez.AgentManager1'

# char_uuid = pkg_resources.resource_string()
# service_uuid = pkg_resources.resource_string()

service_uuid_file = pkg_resources.resource_stream(__name__, "res/gatt-service-uuid.txt")
service_uuid_file = io.TextIOWrapper(service_uuid_file)

char_uuid_file = pkg_resources.resource_stream(__name__, 'res/gatt-characteristic-uuid.txt')
char_uuid_file = io.TextIOWrapper(char_uuid_file)

descriptor_uuid_file = pkg_resources.resource_stream(__name__, 'res/gatt-descriptor-uuid.txt')
descriptor_uuid_file = io.TextIOWrapper(descriptor_uuid_file)

services_spec = {}
characteristics_spec = {}
descriptors_spec = {}

indent = ' ' * 4
sig_uuid_suffix = '-0000-1000-8000-00805f9b34fb'

for line in service_uuid_file:
    items = line.strip().split('\t')
    uuid = items.pop(2)
    services_spec[uuid] = {
        'Name': items[0],
        'Uniform Type Identifier': items[1],
        'Specification': items[2]
    }

for line in char_uuid_file:
    items = line.strip().split('\t')
    uuid = items.pop(2)
    characteristics_spec[uuid] = {
        'Name': items[0],
        'Uniform Type Identifier': items[1],
        'Specification': items[2]
    }

for line in descriptor_uuid_file:
    items = line.strip().split('\t')
    uuid = items.pop(2)
    descriptors_spec[uuid] = {
        'Name': items[0],
        'Uniform Type Identifier': items[1],
        'Specification': items[2]
    }


class BluescanAgent(Agent):
    def __init__(self, bus: SystemBus, idx: int, ioc: str = 'NoInputNoOutput') -> None:
        super().__init__(bus, idx)
        self.io_capability = ioc


class GATTScanner(BlueScanner):
    def __init__(self, iface: str = 'hci0', ioc: str = 'NoInputNoOutput'):
        super().__init__(iface=iface)
        
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        sys_bus = SystemBus()
        
        self.agent_registered = False
        
        def register_agent_callback():
            logger.info('Agent object registered')
            print(INFO_INDENT, "IO capability: {}".format(self.bluescan_agent.io_capability), sep='')
            self.agent_registered = True
        def register_agent_error_callback(error):
            logger.error("Failed to register agent object")
            print(ERROR_INDENT, "{}".format(error), sep='')
            print(ERROR_INDENT, "IO capability: {}".format(self.bluescan_agent.io_capability), sep='')
            self.agent_registered = False
        self.bluescan_agent = BluescanAgent(sys_bus, 0, ioc)
        self.agent_mgr_1_iface = dbus.Interface(
            sys_bus.get_object(BLUEZ_NAME, '/org/bluez'), IFACE_AGENT_MGR_1)
        self.agent_mgr_1_iface.RegisterAgent(
            ObjectPath(self.bluescan_agent.path), 
            self.bluescan_agent.io_capability,
            reply_handler=register_agent_callback,
            error_handler=register_agent_error_callback)


    def scan(self, bdaddr, addr_type, include_descriptor:bool):
        """
        bdaddr - Remote BD_ADDR
        """
        def run_mainloop():
            mainloop.run()
        mainloop_thread = threading.Thread(target=run_mainloop, args=[])
        mainloop_thread.start()
        
        try:
            try:
                target = Peripheral(bdaddr, iface=self.devid, addrType=addr_type)
            except BTLEDisconnectError as e:
                logger.error("BTLEDisconnectError")
                print(ERROR_INDENT, e, sep='')
                return

            services = target.getServices()
            print("Number of services: %s\n\n" % len(services))

            # Show service
            for service in services:
                logger.debug('Start handle: {}'.format(service.hndStart))
                logger.debug('End handle: {}'.format(service.hndEnd))
                
                try:
                    characteristics = []
                    characteristics = service.getCharacteristics()
                except BTLEException as e:
                    logger.warning("BTLEException")
                    print(WARNING_INDENT, e, sep='')
                    # continue

                print(blue('Service'), '(0x%04x - 0x%04x, %s characteristics)' % (service.hndStart, service.hndEnd, len(characteristics)))
                print(indent+'Handle: 0x%04x'%service.hndStart) # ", "\"attr handle\" by using gatttool -b <BD_ADDR> --primary
                print(indent+'Type: (May be primary service 0x2800)')
                print(indent+'Value (Service UUID): ', blue(str(service.uuid).replace(sig_uuid_suffix, '')), end=' ')
                try:
                    print('(' + services_spec[
                        '0x' + ("%s" % service.uuid)[4:8].upper()
                    ]['Name'] + ')', '\x1B[0m')
                except KeyError:
                    print('('+red('unknown')+')', '\x1B[0m')
                print(indent+'Permission: Read Only, No Authentication, No Authorization\n')
                    

                # Show characteristic
                for characteristic in characteristics:
                    descriptors = []
                    # 对每个 characteristic 都获取 descriptor 会很耗时
                    # 有些设备会因此断开连接。于是这里提供了一个是否获取 descriptor 的选项
                    if include_descriptor:
                        descriptors = characteristic.getDescriptors()
                    
                    try:
                        print(indent+yellow('Characteristic'), '(%s descriptors)' % len(descriptors))
                        #print('-'*8)
                        print(indent*2+'Handle: %#06x' % (characteristic.getHandle() - 1))
                        print(indent*2+'Type: 0x2803 (Characteristic)')
                        print(indent*2+'Value:')
                        print(indent*3+'Characteristic properties:', green(characteristic.propertiesToString()))
                        print(indent*3+'Characteristic value handle: %#06x' % characteristic.getHandle())
                        print(indent*3+'Characteristic UUID: ', green(str(characteristic.uuid).replace(sig_uuid_suffix, '')), end=' ') # This UUID is also the type field of characteristic value declaration attribute.
                        try:
                            print('(' + characteristics_spec[
                                '0x' + ("%s" % characteristic.uuid)[4:8].upper()
                            ]['Name'] + ')')
                        except KeyError:
                            print('('+red('unknown')+')')
                        print(indent*3+'Permission: Read Only, No Authentication, No Authorization')
                        
                        if characteristic.supportsRead():
                            print(indent+yellow('Characteristic value'))
                            print(indent*2+'Handle:', green('%#06x' % characteristic.getHandle()))
                            print(indent*2+'Type:', str(characteristic.uuid).replace(sig_uuid_suffix, ''))
                            print(indent*2+'Value:', green(str(characteristic.read())))
                            print(indent*2+'Permission: Higher layer profile or implementation-specific')
                    except BTLEException as e:
                        print('        ' + str(e))

                    # Show descriptor
                    for descriptor in descriptors:
                        try:
                            print(indent+yellow('Descriptor'))
                            print(indent*2+'Handle:', green('%#06x' % descriptor.handle))
                            print(indent*2+'Type:', str(descriptor.uuid).replace(
                                sig_uuid_suffix, ''), end=' ')
                            try:
                                print('(' + descriptors_spec[
                                    '0x' + ("%s" % descriptor.uuid)[4:8].upper()
                                ]['Name'] + ')')
                            except KeyError:
                                print('(Unknown descriptor)')
                            print(indent*2+'Value:', green(str(descriptor.read())))
                            print(indent*2+'Permissions:')
                        except BTLEException as e:
                            print(indent*2 + str(e))
                    print()
                print()

            # Set remote device untursted
            output = subprocess.check_output(' '.join(['bluetoothctl', 'untrust', 
                                                    bdaddr]), 
                        stderr=STDOUT, timeout=60, shell=True)
            logger.info(output.decode())

            # output = subprocess.check_output(
            #     ' '.join(['sudo', 'systemctl', 'stop', 'bluetooth.service']), 
            #     stderr=STDOUT, timeout=60, shell=True)

            # output = subprocess.check_output(
            #     ' '.join(['sudo', 'rm', '-rf', '/var/lib/bluetooth/' + \
            #               self.hci_bdaddr + '/' + bdaddr.upper()]), 
            #     stderr=STDOUT, timeout=60, shell=True)

            # output = subprocess.check_output(
            #     ' '.join(['sudo', 'systemctl', 'start', 'bluetooth.service']), 
            #     stderr=STDOUT, timeout=60, shell=True)
        finally:
            if self.agent_registered:
                self.agent_mgr_1_iface.UnregisterAgent(
                    ObjectPath(self.bluescan_agent.path))
                logger.info('Unregistered Agent object')
                
                mainloop.quit()


if __name__ == "__main__":
    pass
