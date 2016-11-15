# -*- coding: utf-8 -*-
from __future__ import absolute_import

import os
import sys
import socket
import struct
import subprocess
import time

from libcloud.compute.types import NodeState, Provider
from libcloud.compute.providers import get_driver
from libcloud.compute.drivers.cloudsigma import CloudSigmaNodeSize, CloudSigmaDrive

from nixops import known_hosts
from nixops.util import wait_for_tcp_port, ping_tcp_port
from nixops.util import attr_property, create_key_pair
from nixops.ssh_util import SSHCommandFailed
from nixops.backends import MachineDefinition, MachineState
from nixops.nix_expr import nix2py


class CloudSigmaDefinition(MachineDefinition):
    """
    Definition of a CloudSigma machine.
    """
    @classmethod
    def get_type(cls):
        return "cloudsigma"

    def __init__(self, xml, config):
        MachineDefinition.__init__(self, xml, config)
        x = xml.find("attrs/attr[@name='cloudsigma']/attrs")
        assert x is not None
        for var, valtype in [("username", "string"),
                             ("password", "string"),
                             ("region", "string"),
                             ("cpu", "int"),
                             ("ram", "int"),
                             ("disk", "int")]:
            attr = x.find("attr[@name='" + var + "']/" + valtype)
            setattr(self, var, int(attr.get("value")) if valtype == 'int' else attr.get("value"))


class CloudSigmaState(MachineState):
    """
    State of a CloudSigma machine.
    """
    @classmethod
    def get_type(cls):
        return "cloudsigma"

    state = attr_property("state", MachineState.UNKNOWN, int)

    public_ipv4 = attr_property("publicIpv4", None)
    private_ipv4 = attr_property("privateIpv4", None)

    username = attr_property("cloudsigma.username", None)
    password = attr_property("cloudsigma.password", None)
    region = attr_property("cloudsigma.region", None)

    #_ssh_private_key = attr_property('cloudsigma.sshPrivateKey', None)
    #_ssh_public_key = attr_property('cloudsigma.sshPublicKey', None)

    def __init__(self, depl, name, id):
        MachineState.__init__(self, depl, name, id)
        self._driver = None

    @property
    def resource_id(self):
        return self.vm_id

    def _connect(self, defn):
        """
        Connect to the CloudSigma API by using the admin credetials in
        'self.main_username' and 'self.main_password'.
        """
        if self._driver is not None:
            return self._driver

        cls = get_driver(Provider.CLOUDSIGMA)
        self._driver = cls(defn.username, defn.password,
                           region=defn.region, api_version='2.0')
        return self._driver

    def get_ssh_name(self):
        return self.public_ipv4

    #def get_ssh_private_key_file(self):
    #    if self._ssh_private_key_file:
    #        return self._ssh_private_key_file
    #    else:
    #        return self.write_ssh_private_key(self._ssh_private_key)

    def create(self, defn, check, allow_reboot, allow_recreate):
        assert isinstance(defn, CloudSigmaDefinition)

        if self.state == self.UP:
            return

        if not self._driver:
            self._connect(defn)

        if not self.vm_id:
            self.log("creating CloudSigma VM in '{0}'...".format(defn.region))
            self._create_vm(defn)

        if self.state == self.STOPPED:
            self.log("starting CloudSigma VM {0}".format(self.vm_id))
            self._start_vm()

        self.state = self.STARTING
        self.ssh_pinged = False
        self._wait_for_vm_state(NodeState.RUNNING)
        self.log("started CloudSigma VM {0}".format(self.vm_id))

        self.state == self.UP

        self._update_state()

    def _create_vm(self, defn):
        #if not self._ssh_public_key:
        #    key_name = "NixOps client key for {0}".format(defn.name)
        #    self._ssh_private_key, self._ssh_public_key = \
        #        create_key_pair(key_name=key_name)

        size = CloudSigmaNodeSize(id=1,
                                  name=defn.name, cpu=defn.cpu, ram=defn.ram, disk=defn.disk,
                                  bandwidth=None, price=0, driver=self._driver)
        node = self._driver.create_node(name=defn.name, size=size, image=self._base_image(),
                                        ex_pubkeys = ["04865e9c-844a-460a-9dc7-a76851f99160"])
        self.vm_id = node.id

    def _base_image(self):
        for d in self._driver.ex_list_user_drives():
            if d.name == "nixos-base":
                return d
        raise Exception("Can't find 'nixos-base' image in user drives")

    def _wait_for_vm_state(self, state):
        while True:
            node = self._driver.ex_get_node(self.vm_id)

            if node.state == state:
                break

            time.sleep(1)

    def _start_vm(self):
        assert False, "not implemented"

    def _update_state(self):
        assert self.vm_id, "unknown VM"

        node = self._driver.ex_get_node(self.vm_id)

        if node.private_ips:
            setattr(self, 'private_ipv4', node.private_ips[0])
        if node.public_ips:
            setattr(self, 'public_ipv4', node.public_ips[0])
