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
import re

import collectd_base as base

NAME = 'glusterfs'
GLUSTER_BINARY = '/usr/sbin/gluster'

peer_re = re.compile(r'^Hostname: (?P<peer>.+)$', re.MULTILINE)
state_re = re.compile(r'^State: (?P<state>.+)$', re.MULTILINE)

vol_status_re = re.compile(r'\n\s*\n', re.MULTILINE)
vol_block_re = re.compile(r'^-+', re.MULTILINE)
volume_re = re.compile(r'^Status of volume:\s+(?P<volume>.+)', re.MULTILINE)
brick_server_re = re.compile(r'^Brick\s*:\s*Brick\s*(?P<peer>[^:]+)',
                             re.MULTILINE)
disk_free_re = re.compile(
    r'^Disk Space Free\s*:\s+(?P<disk_free>[.\d]+)(?P<unit>\S+)',
    re.MULTILINE)
disk_total_re = re.compile(
    r'^Total Disk Space\s*:\s+(?P<disk_total>[.\d]+)(?P<unit>\S+)',
    re.MULTILINE)
inode_free_re = re.compile(r'^Free Inodes\s*:\s+(?P<inode_free>\d+)',
                           re.MULTILINE)
inode_count_re = re.compile(r'^Inode Count\s*:\s+(?P<inode_count>\d+)',
                            re.MULTILINE)


def convert_to_bytes(v, unit):
    try:
        i = ('B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB').index(unit)
    except ValueError:
        i = 1
    return float(v) * (1024 ** i)


class GlusterfsPlugin(base.Base):

    def __init__(self, *args, **kwargs):
        super(GlusterfsPlugin, self).__init__(*args, **kwargs)
        self.plugin = NAME

    def itermetrics(self):
        # Collect peers' metrics
        out, err = self.execute([GLUSTER_BINARY, 'peer', 'status'],
                                shell=False)
        if not out:
            raise base.CheckException("Failed to execute 'gluster peer'")

        total = 0
        total_by_state = {
            'up': 0,
            'down': 0
        }

        for line in out.split('\n\n'):
            peer_m = peer_re.search(line)
            state_m = state_re.search(line)
            if peer_m and state_m:
                total += 1
                if state_m.group('state') == 'Peer in Cluster (Connected)':
                    v = 1
                    total_by_state['up'] += 1
                else:
                    v = 0
                    total_by_state['down'] += 1
                yield {
                    'type_instance': 'peer_state',
                    'values': v,
                    'meta': {
                        'peer': peer_m.group('peer')
                    }
                }

        for state, count in total_by_state.items():
            yield {
                'type_instance': 'peers_count',
                'values': count,
                'meta': {
                    'state': state
                }
            }
            yield {
                'type_instance': 'peers_percent',
                'values': 100.0 * count / total,
                'meta': {
                    'state': state
                }
            }

        # Collect volumes' metrics
        out, err = self.execute(
            [GLUSTER_BINARY, 'volume', 'status', 'all', 'detail'],
            shell=False)
        if not out:
            raise base.CheckException("Failed to execute 'gluster volume'")

        for vol_block in vol_status_re.split(out):
            volume_m = volume_re.search(vol_block)
            if not volume_m:
                continue
            volume = volume_m.group('volume')
            for line in vol_block_re.split(vol_block):
                peer_m = brick_server_re.search(line)
                if not peer_m:
                    continue
                volume = volume_m.group('volume')
                peer = peer_m.group('peer')
                disk_free_m = disk_free_re.search(line)
                disk_total_m = disk_total_re.search(line)
                inode_free_m = inode_free_re.search(line)
                inode_count_m = inode_count_re.search(line)
                if disk_free_m and disk_total_m:
                    free = convert_to_bytes(
                        disk_free_m.group('disk_free'),
                        disk_free_m.group('unit'))
                    total = convert_to_bytes(
                        disk_total_m.group('disk_total'),
                        disk_total_m.group('unit'))
                    used = total - free
                    yield {
                        'type_instance': 'space_free',
                        'values': free,
                        'meta': {
                            'volume': volume,
                            'peer': peer,
                        }
                    }
                    yield {
                        'type_instance': 'space_percent_free',
                        'values': free * 100.0 / total,
                        'meta': {
                            'volume': volume,
                            'peer': peer,
                        }
                    }
                    yield {
                        'type_instance': 'space_used',
                        'values': used,
                        'meta': {
                            'volume': volume,
                            'peer': peer,
                        }
                    }
                    yield {
                        'type_instance': 'space_percent_used',
                        'values': used * 100.0 / total,
                        'meta': {
                            'volume': volume,
                            'peer': peer,
                        }
                    }
                if inode_free_m and inode_count_m:
                    free = int(inode_free_m.group('inode_free'))
                    total = int(inode_count_m.group('inode_count'))
                    used = total - free
                    yield {
                        'type_instance': 'inodes_free',
                        'values': free,
                        'meta': {
                            'volume': volume,
                            'peer': peer,
                        }
                    }
                    yield {
                        'type_instance': 'inodes_percent_free',
                        'values': free * 100.0 / total,
                        'meta': {
                            'volume': volume,
                            'peer': peer,
                        }
                    }
                    yield {
                        'type_instance': 'inodes_used',
                        'values': used,
                        'meta': {
                            'volume': volume,
                            'peer': peer,
                        }
                    }
                    yield {
                        'type_instance': 'inodes_percent_used',
                        'values': used * 100.0 / total,
                        'meta': {
                            'volume': volume,
                            'peer': peer,
                        }
                    }


plugin = GlusterfsPlugin(collectd)


def init_callback():
    plugin.restore_sigchld()


def config_callback(conf):
    plugin.config_callback(conf)


def read_callback():
    plugin.read_callback()

collectd.register_init(init_callback)
collectd.register_config(config_callback)
collectd.register_read(read_callback)
