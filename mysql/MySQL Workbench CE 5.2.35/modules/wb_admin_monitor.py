# Copyright (c) 2007, 2010, Oracle and/or its affiliates. All rights reserved.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; version 2 of the
# License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA
# 02110-1301  USA

from mforms import newWidgetContainer, newServerInfoWidget, newWidgetSeparator, newBarGraphWidget, newHeartbeatWidget, newLineDiagramWidget
import mforms

import wba_monitor_be

class WbAdminMonitor(mforms.Box):
    mon_be      = None
    ctrl_be          = None
    server_info      = None
    cpu_usage        = None
    memory           = None
    heartbeat        = None
    connection_usage = None
    traffic          = None
    hitrate          = None
    key_efficiency   = None

    widgets = None

    def __init__(self, server_profile, ctrl_be):
        mforms.Box.__init__(self, True)
        
        self.widgets = {}
        
        self.server_profile = server_profile
        self.set_managed()

        self.suspend_layout()

        self.set_size(-1, 91)
        self.ctrl_be = ctrl_be

        # Info.
        info_box = newWidgetContainer("INFO")
        self.add(info_box, False, True)

        self.server_info = newServerInfoWidget()
        self.server_info.set_server_status(-1)
        host_name = None
        if server_profile.db_connection_params:
            if server_profile.db_connection_params.driver.name == "MysqlNativeSocket":
                host_name = "localhost"
            else:
                host_name = server_profile.db_connection_params.parameterValues["hostName"]
        if not host_name:
            host_name = u"Not Set"

        self.server_info.set_server_info(unicode(server_profile.name), host_name, self.ctrl_be.raw_version)

        info_box.add_widget(self.server_info, False)

        separator = newWidgetSeparator()
        separator.set_size(8, -1)
        self.add(separator, False, True)
        
        # System.
        system_box = newWidgetContainer("SYSTEM")
        self.cpu_usage = newBarGraphWidget()
        if self.server_profile.target_is_windows:
          self.ctrl_be.uitask(self.cpu_usage.set_description, "CPU: --")
        else:
          self.ctrl_be.uitask(self.cpu_usage.set_description, "Load: --")
        system_box.add_widget(self.cpu_usage, False)

        if self.server_profile.target_is_windows:
          self.widgets['get_cpu_info'] = (self.cpu_usage, lambda x: "CPU: " + str(int(x*100)) + "%", None)
        else:
          self.cpu_usage.enable_auto_scale(True)
          self.widgets['get_cpu_info'] = (self.cpu_usage, lambda x: "Load: " + str(x), None)

        self.memory = newBarGraphWidget()
        system_box.add_widget(self.memory, False)
        self.ctrl_be.uitask(self.memory.set_description, "Mem: --")

        def mem_label(x):
          up = self.memory.get_upper_range()
          x = int(x/up*100)
          s = "Mem: " + str(x) + "%"
          return s

        self.widgets['get_mem_info'] = (self.memory, lambda x: mem_label(x), lambda x: (self.memory.get_upper_range() - x))

        #self.heartbeat = newHeartbeatWidget()
        #self.heartbeat.set_size(142, -1)
        #system_box.add_widget(self.heartbeat, False)
        #self.heartbeat.set_description("Server Health: -")

        self.add(system_box, False, True);

        separator = newWidgetSeparator()
        separator.set_size(8, -1)
        self.add(separator, False, True)

        sql = {}
        # Server health.
        health= newWidgetContainer("SERVER HEALTH")
        self.connection_usage= newLineDiagramWidget()
        self.connection_usage.set_size(110, -1)
        self.ctrl_be.uitask(self.connection_usage.set_description, "Connection Usage: --")
        self.connection_usage.enable_auto_scale(True)
        self.connection_usage.set_thresholds([0.0], [10.0, 50.0, 100.0, 500.0, 1000.0])
        health.add_widget(self.connection_usage, True)
        self.widgets['get_connections'] = (self.connection_usage, lambda x: "Connection Usage: " + str(int(x)), None);
        sql['get_connections'] = {'query' : ("Threads_connected",), 'min' : 0, 'max' : 10, 'calc' : None}

        self.traffic= newLineDiagramWidget()
        self.traffic.set_size(110, -1)
        self.ctrl_be.uitask(self.traffic.set_description, "Traffic: --")
        self.traffic.enable_auto_scale(True)
        self.traffic.set_thresholds([0.0], [100000.0, 1000000.0, 10000000.0, 100000000.0])
        health.add_widget(self.traffic, True)
        self.widgets['get_traffic'] = (self.traffic, lambda x: "Traffic: " + self.format_value(x), None);

        self.last_traffic = 0
        sql['get_traffic'] = {'query' : ("Bytes_sent",), 'min' : 0, 'max' : 100, 'calc' : self.calc_traffic}

        self.hitrate= newLineDiagramWidget()
        self.hitrate.set_size(110, -1)
        self.ctrl_be.uitask(self.hitrate.set_description, "Query Cache Hitrate: --")
        health.add_widget(self.hitrate, True)
        self.widgets['get_hitrate'] = (self.hitrate, lambda x: "Query Cache Hitrate: " + ("%.2f" % x) + "%", None);
        sql['get_hitrate'] = {'query' : ("Qcache_hits", "Qcache_inserts", "Qcache_not_cached"), 'min' : 0, 'max' : 100, 'calc' : self.calc_hitrate}

        self.key_efficiency= newLineDiagramWidget()
        self.key_efficiency.set_size(110, -1)
        self.ctrl_be.uitask(self.key_efficiency.set_description, "Key Efficiency: --")
        health.add_widget(self.key_efficiency, True)
        self.widgets['get_key_efficiency'] = (self.key_efficiency, lambda x: "Key Efficiency: " + ("%.2f" % x) + "%", None);
        sql['get_key_efficiency'] = {'query' : ("Key_reads","Key_read_requests"), 'min' : 0, 'max' : 100, 'calc' : self.calc_key_efficiency}

        self.add(health, True, True)

        self.resume_layout()

        self.mon_be = wba_monitor_be.WBAdminMonitorBE(3, server_profile, ctrl_be, self.widgets, sql)
        if not self.server_profile.target_is_windows:
          mem = self.mon_be.run('get_mem_total')
          if mem is not None:
            mem = mem.strip(" \r\t\n.,:;")
        else:
          mem = 100

        if mem != "" and mem is not None:
          try:
              self.memory.set_value_range(0, float(mem))
          except ValueError, exc:
              print "Error parsing output of get_mem_total: '%s'"%mem

        #disk = self.mon_be.run('get_disk_total')
        #if disk is not None:
        #  disk = disk.strip(" \r\t\n.,:;")
        #if disk != "" and disk is not None:
        #  pass

    def calc_traffic(self, x):
        tx = int(x[0])
        ret = tx - self.last_traffic
        self.last_traffic = tx
        return ret

    def calc_key_efficiency(self, (key_reads, key_read_requests)):
        key_read_requests = float(key_read_requests)
        if key_read_requests == 0.0:
          return 0
        return 100 - (float(key_reads) / key_read_requests * 100)

    def calc_hitrate(self, (hits, inserts, not_cached)):
        hits = float(hits)
        inserts = int(inserts)
        not_cached = int(not_cached)
        t = hits + inserts + not_cached
        if t == 0:
          return 0
        return (hits/t)*100

    def refresh_status(self, status):
      if status == "running":
        self.server_info.set_server_status(1)
      elif status == "stopped":
        self.server_info.set_server_status(0)
      
    def format_value(self, value):
      if value < 1024:
        return str(value) + " B/s"
      else:
        if value < 1024 * 1024:
          return "%.2f KB/s" % (value / 1024)
        else:
          return "%.2f MB/s" % (value / 1024 / 1024)
