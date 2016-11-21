#!/usr/bin/python
# Copyright 2016 Mirantis, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import collectd

import collectd_base as base

from pyroute2 import IPRoute

NAME = 'vrrp'


class VrrpPlugin(base.Base):

    def __init__(self, *args, **kwargs):
        super(VrrpPlugin, self).__init__(*args, **kwargs)
        self.plugin = NAME
        self.ip_addresses = []
        self.ipr = IPRoute()

    def config_callback(self, conf):
        """Parse the plugin configuration.

        Example:

        <Module "collectd_vrrp">
            <IPAddress>
                address "172.16.10.254"
                label "Foo"
            </IPAddress>
            <IPAddress>
                address "172.16.10.253"
            </IPAddress>
        </Module>
        """
        super(VrrpPlugin, self).config_callback(conf)

        for node in conf.children:
            if node.key == 'IPAddress':
                item = {}
                for child_node in node.children:
                    if child_node.key not in ('address', 'label'):
                        continue
                    item[child_node.key] = child_node.values[0]
                if 'address' not in item:
                    self.logger.error("vrrp: Missing 'address' parameter")
                self.ip_addresses.append(item)

        if len(self.ip_addresses) == 0:
            self.logger.error("vrrp: Missing 'IPAddress' parameter")

    def itermetrics(self):
        for ip_address in self.ip_addresses:
            v = 1 if self.ipr.get_addr(address=ip_address['address']) else 0
            data = {'values': v, 'meta': {'ip_address': ip_address['address']}}
            if 'label' in ip_address:
                data['meta']['label'] = ip_address['label']
            yield data


plugin = VrrpPlugin(collectd)


def config_callback(conf):
    plugin.config_callback(conf)


def read_callback():
    plugin.read_callback()

collectd.register_config(config_callback)
collectd.register_read(read_callback)
