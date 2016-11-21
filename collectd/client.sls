{%- from "collectd/map.jinja" import client with context %}
{%- if client.enabled %}

{%- if grains.os == 'Ubuntu' and (grains.osrelease in ['10.04', '12.04']) %}

collectd_repo:
  pkgrepo.managed:
  - human_name: Collectd
  - ppa: nikicat/collectd
  - file: /etc/apt/sources.list.d/collectd.list
  - require_in:
    - pkg: collectd_client_packages

collectd_amqp_packages:
  pkg.installed:
  - names: 
    - librabbitmq0

{%- endif %}

collectd_client_packages:
  pkg.installed:
  - names: {{ client.pkgs }}

/etc/collectd:
  file.directory:
  - user: root
  - mode: 750
  - makedirs: true
  - require:
    - pkg: collectd_client_packages

collectd_client_conf_dir:
  file.directory:
  - name: {{ client.config_dir }}
  - user: root
  - mode: 750
  - makedirs: true
  - require:
    - pkg: collectd_client_packages

collectd_client_conf_dir_clean:
  file.directory:
  - name: {{ client.config_dir }}
  - clean: true

collectd_client_grains_dir:
  file.directory:
  - name: /etc/salt/grains.d
  - mode: 700
  - makedirs: true
  - user: root

/usr/lib/collectd-python:
  file.recurse:
  - source: salt://collectd/files/plugin

{%- set service_grains = {'collectd': {'remote_plugin': {}, 'local_plugin': {}}} %}

{%- for service_name, service in pillar.items() %}
{%- if service.get('_support', {}).get('collectd', {}).get('enabled', False) %}

{%- set grains_fragment_file = service_name+'/meta/collectd.yml' %}
{%- macro load_grains_file() %}{% include grains_fragment_file ignore missing %}{% endmacro %}
{%- set grains_yaml = load_grains_file()|load_yaml %}

{%- if grains_yaml is mapping %}
{%- set service_grains = salt['grains.filter_by']({'default': service_grains}, merge={'collectd': grains_yaml}) %}
{%- endif %}

{%- endif %}
{%- endfor %}

{%- set remote_plugin = {} %}

{%- if client.remote_collector %}

{%- for node_name, node_grains in salt['mine.get']('*', 'grains.items').iteritems() %}

{%- if node_grains.collectd is defined %}

{%- set remote_plugin = salt['grains.filter_by']({'default': remote_plugin}, merge=node_grains.collectd.get('remote_plugin', {})) %}

{%- endif %}

{%- endfor %}

{%- endif %}

collectd_client_grain:
  file.managed:
  - name: /etc/salt/grains.d/collectd
  - source: salt://collectd/files/collectd.grain
  - template: jinja
  - user: root
  - mode: 600
  - defaults:
    service_grains: {{ service_grains|yaml }}
  - require:
    - pkg: collectd_client_packages
    - file: collectd_client_grains_dir

collectd_client_grain_validity_check:
  cmd.wait:
  - name: python -c "import yaml; stream = file('/etc/salt/grains.d/collectd', 'r'); yaml.load(stream); stream.close()"
  - require:
    - pkg: collectd_client_packages
  - watch:
    - file: collectd_client_grain

{%- for plugin_name, plugin in service_grains.collectd.local_plugin.iteritems() %}

{%- if plugin.get('plugin', 'native') not in ['python'] %}

{{ client.config_dir }}/{{ plugin_name }}.conf:
  file.managed:
  {%- if plugin.template is defined %}
  - source: salt://{{ plugin.template }}
  - template: jinja
  - defaults:
    plugin: {{ plugin|yaml }}
  {%- else %}
  - contents: "<LoadPlugin {{ plugin.plugin }}>\n  Globals false\n</LoadPlugin>\n"
  {%- endif %}
  - user: root
  - mode: 660
  - require:
    - file: collectd_client_conf_dir
  - require_in:
    - file: collectd_client_conf_dir_clean
  - watch_in:
    - service: collectd_service

{%- endif %}

{%- endfor %}

{%- if client.remote_collector %}

{%- for plugin_name, plugin in remote_plugin.iteritems() %}

{%- if plugin.get('plugin', 'native') not in ['python'] %}

{{ client.config_dir }}/{{ plugin_name }}.conf:
  file.managed:
  {%- if plugin.template is defined %}
  - source: salt://{{ plugin.template }}
  - template: jinja
  - defaults:
    plugin: {{ plugin|yaml }}
  {%- else %}
  - contents: "<LoadPlugin {{ plugin.plugin }}>\n  Globals false\n</LoadPlugin>\n"
  {%- endif %}
  - user: root
  - mode: 660
  - require:
    - file: collectd_client_conf_dir
  - require_in:
    - file: collectd_client_conf_dir_clean
  - watch_in:
    - service: collectd_service

{%- endif %}

{%- endfor %}

{%- endif %}

{%- if client.file_logging %}

/etc/collectd/conf.d/00_collectd_logfile.conf:
  file.managed:
  - source: salt://collectd/files/collectd_logfile.conf
  - user: root
  - group: root
  - mode: 660
  - watch_in:
    - service: collectd_service
  - require:
    - file: collectd_client_conf_dir
  - require_in:
    - file: collectd_client_conf_dir_clean

{%- endif %}

/etc/collectd/conf.d/collectd_python.conf:
  file.managed:
  - source: salt://collectd/files/collectd_python.conf
  - template: jinja
  - user: root
  - group: root
  - mode: 660
  - defaults:
      local_plugin: {{ service_grains.collectd.local_plugin|yaml }}
      remote_plugin: {{ remote_plugin|yaml }}
  - watch_in:
    - service: collectd_service
  - require:
    - file: collectd_client_conf_dir
  - require_in:
    - file: collectd_client_conf_dir_clean

/etc/collectd/filters.conf:
  file.managed:
  - source: salt://collectd/files/filters.conf
  - template: jinja
  - user: root
  - group: root
  - mode: 660
  - watch_in:
    - service: collectd_service
  - require:
    - file: collectd_client_conf_dir
  - require_in:
    - file: collectd_client_conf_dir_clean

/etc/collectd/thresholds.conf:
  file.managed:
  - source: salt://collectd/files/thresholds.conf
  - template: jinja
  - user: root
  - group: root
  - mode: 660
  - watch_in:
    - service: collectd_service
  - require:
    - file: collectd_client_conf_dir
  - require_in:
    - file: collectd_client_conf_dir_clean

{{ client.config_file }}:
  file.managed:
  - source: salt://collectd/files/collectd.conf
  - template: jinja
  - user: root
  - group: root
  - mode: 640
  - defaults:
    service_grains: {{ service_grains|yaml }}
    remote_plugin: {{ remote_plugin|yaml }}
  - require:
    - file: collectd_client_conf_dir
  - require_in:
    - file: collectd_client_conf_dir_clean
  - watch_in:
    - service: collectd_service

{%- for backend_name, backend in client.backend.iteritems() %}

{{ client.config_dir }}/collectd_writer_{{ backend_name }}.conf:
  file.managed:
  - source: salt://collectd/files/backend/{{ backend.engine }}.conf
  - template: jinja
  - user: root
  - group: root
  - mode: 660
  - defaults:
    backend_name: "{{ backend_name }}"
  - require:
    - file: collectd_client_conf_dir
  - require_in:
    - file: collectd_client_conf_dir_clean
  - watch_in:
    - service: collectd_service

{%- endfor %}

collectd_service:
  service.running:
  - name: collectd
  - enable: true
  - require:
    - pkg: collectd_client_packages

{%- endif %}
