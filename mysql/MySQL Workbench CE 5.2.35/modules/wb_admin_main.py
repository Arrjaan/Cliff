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

import platform
import threading
import time

from mforms import App, Utilities, newBox, newPanel, newButton, newLabel, newTabView, newTabSwitcher, newTextEntry, newSelector
from mforms import newTaskSidebar
import mforms

import wb_admin_monitor

from wb_admin_configuration_startup import WbAdminConfigurationStartup
from wb_admin_config_file_ui import WbAdminConfigFileUI
from wb_admin_connections import WbAdminConnections
from wb_admin_variables import WbAdminVariables
from wb_admin_security import WbAdminSecurity
from wb_admin_logs import WbAdminLogs
from wb_admin_export import WbAdminExport
from wb_admin_utils import MySQLConnection, MySQLError, weakcb, no_remote_admin_warning_label, dprint_ex
from wb_server_management import wbaOS
from wb_admin_ui_profile import UIProfile

import new

#-------------------------------------------------------------------------------
#def add_top_spacer(panel):
#    box = newBox(False)
#    spacer = newPanel(mforms.TransparentPanel)
#    spacer.set_size(100, 10)
#    box.add(spacer, False, True)
#    box.add(panel, True, True)
#    return box

#-------------------------------------------------------------------------------
def newHeaderLabel(text):
    widget = newPanel(mforms.StyledHeaderPanel)
    label = newLabel(text)
    widget.add(label)
    widget.set_text  = new.instancemethod(mforms.Label.set_text,  label, mforms.Label)
    widget.set_color = new.instancemethod(mforms.Label.set_color, label, mforms.Label)
    widget.set_style = new.instancemethod(mforms.Label.set_style, label, mforms.Label)
    widget.set_text_align = new.instancemethod(mforms.Label.set_text_align, label, mforms.Label)
    return widget


#===============================================================================
#
#===============================================================================
class ServerStatusPage(mforms.Box):
    status      = None
    connections = None

    #---------------------------------------------------------------------------
    def __init__(self, server_profile, ctrl_be, main_view):
        mforms.Box.__init__(self, False) # Make vertical box
        main_view.ui_profile.apply_style(self, 'page')
        self.set_managed()

        self.ctrl_be = ctrl_be
        self.main_view = main_view

        self.status = wb_admin_monitor.WbAdminMonitor(server_profile, self.ctrl_be)
        self.add(self.status, False, False)

        vbox = newBox(False)
        vbox.set_spacing(2)
        label = newLabel("CONNECTIONS")#newHeaderLabel(" Connections")
        main_view.ui_profile.apply_style(label, 'subsection-label')
        vbox.add(label, False, False)

        self.connections = WbAdminConnections(server_profile, self.ctrl_be)
        main_view.ui_profile.apply_style(self.connections, "page")
        vbox.add(self.connections, True, True)

        self.add(vbox, True, True)

        self.main_view.add_content_page(self, "MANAGEMENT", "Server Status", "admin_server_status_win")

    #---------------------------------------------------------------------------
    def refresh(self, status):
        self.status.refresh_status(status)
        if status and self.connections:
          self.connections.refresh_mt(self.ctrl_be)

    #---------------------------------------------------------------------------
    def page_activated(self):
        self.main_view.set_content_label(" Server Status")
        self.connections.page_activated()

    #---------------------------------------------------------------------------
    def page_deactivated(self):
        self.connections.page_deactivated()


#===============================================================================
#
#===============================================================================
class WbAdminMainView(mforms.Box):
    last_server_status = None

    def __init__(self, server_profile, ctrl_be, monitor):
        mforms.Box.__init__(self, True) # True - vertical layout
        self.tasks_side                 = newTaskSidebar()
        self.content_box                = newBox(False)

        self.tasks_side.set_selection_color(mforms.SystemHighlight)

        self.tabs                       = []
        self.name2page                  = {}
        self.config_ui                  = None
        self.closing                    = False
        self.tabview                    = newTabView(True)
        self.ctrl_be                    = ctrl_be
        self.old_active_tab             = None
        self.server_profile             = server_profile

        self.refresh_tasks_sleep_time   = 2

        self.ui_profile = UIProfile(server_profile)

        # Setup self
        self.set_managed()
        self.ui_profile.apply_style(self, "main")

        if server_profile.host_os == wbaOS.windows:
            side_panel = newPanel(mforms.StyledHeaderPanel)
            side_panel.set_title(" Task and Object Browser")
            side_panel.add(self.tasks_side)
            self.add(side_panel, False, True)

            self.content_panel = newPanel(mforms.StyledHeaderPanel)
            self.content_panel.set_title(" Task and Object Browser")
            self.content_panel.add(self.content_box)
            self.add(self.content_panel, True, True)
        else:
            vbox  = newBox(False)
            vbox.add(self.tasks_side, True, True)
            self.add(vbox, False, False)
            
            vbox  = newBox(False)
            self.content_label = newHeaderLabel("")
            self.ui_profile.apply_style(self.content_label, 'content-label')
            vbox.add(self.content_label, False, False)
            vbox.add(self.content_box, True, True)
            self.add(vbox, True, True)

        self.ctrl_be.add_me_for_event("server_started", self)
        self.ctrl_be.add_me_for_event("server_stopped", self)

        # Setup tasks sidebar
        self.fill_task_sidebar()
        self.tasks_side.add_on_section_command_callback(self.section_clicked)
        self.tasks_side.show()
        self.tasks_side.set_size(220, -1)

        # Setup content box
        self.content_box.add(self.tabview, True, True)

        # Create content pages
        self.server_status_page = ServerStatusPage(server_profile, ctrl_be, self)
        self.config_ui = WbAdminConfigFileUI(server_profile = server_profile, ctrl_be = ctrl_be, main_view = self)
        self.startup = WbAdminConfigurationStartup(ctrl_be, server_profile, self)
        self.security = WbAdminSecurity(self.ctrl_be, server_profile, self)
        self.variables = WbAdminVariables(self.ctrl_be, server_profile, self)
        self.logs = WbAdminLogs(self.ctrl_be, server_profile, self)
        self.dump = WbAdminExport(server_profile, self.ctrl_be, self)

        Utilities.add_timeout(0.5, weakcb(self, "timeout"))
        self.timeout_thread = threading.Thread(target = self.refresh_tasks_thread)
        self.timeout_thread.setDaemon(True)
        self.timeout_thread.start()
        self.tabview.add_tab_changed_callback(self.tab_changed)

        self.timeout() # will call self.connect_mysql() and check if mysql is running

        self.ctrl_be.continue_events() # Process events which are queue during init
        dprint_ex(1, "WBA init complete")

        self.tasks_side.select_entry("MANAGEMENT", "Server Status")
        self.server_status_page.page_activated()

    #---------------------------------------------------------------------------
    def set_content_label(self, text):
        if hasattr(self, "content_label"):
            self.content_label.set_text(text)
        else:
            self.content_panel.set_title(text)

    #---------------------------------------------------------------------------
    def add_taskbar_section(self, name):
        i = self.tasks_side.add_section(name)
        #self.sections_list.append(name)
        return i

    #---------------------------------------------------------------------------
    def fill_task_sidebar(self):
        self.add_taskbar_section("MANAGEMENT")
        self.add_taskbar_section("CONFIGURATION")
        self.add_taskbar_section("SECURITY")
        self.add_taskbar_section("DATA EXPORT / RESTORE")

    #---------------------------------------------------------------------------
    def section_clicked(self, section):
      i, content = self.name2page.get(section, (None, None))
      #print section, i, content
      if i is not None:
        self.tabview.set_active_tab(i)
        self.tab_changed()

    #---------------------------------------------------------------------------
    def switch_to(self, section, task):
      self.tasks_side.select_entry(section, task)
      self.tab_changed()

    #---------------------------------------------------------------------------
    def tab_changed(self):
      if self.old_active_tab and hasattr(self.old_active_tab, "page_deactivated"):
        self.old_active_tab.page_deactivated()

      i = self.tabview.get_active_tab()
      panel = self.tabs[i]
      if panel is not None:
        panel.page_activated()
      self.old_active_tab = panel

    #---------------------------------------------------------------------------
    def shutdown(self):
        dprint_ex(2, " closing")
        for tab in self.tabs:
            if hasattr(tab, "shutdown"):
                tab.shutdown()

        self.closing = True

    #---------------------------------------------------------------------------
    def shutdown_event(self):
        self.shutdown()

    #---------------------------------------------------------------------------
    def server_started_event(self):
      dprint_ex(1, "Handling start event")
      if len(self.tabs) > 0 and hasattr(self.tabs[0], 'print_output'):
        self.ctrl_be.uitask(self.tabs[0].print_output, "Server is running")
      ###self.connect_mysql()
      #if None == self.connect_mysql():
      self.refresh_tasks_sleep_time = 2
      dprint_ex(1, "Done handling start event")

    #---------------------------------------------------------------------------
    def server_stopped_event(self):
      dprint_ex(1, "Handling stop event")
      if len(self.tabs) > 0 and hasattr(self.tabs[0], "print_output"):
        self.ctrl_be.uitask(self.tabs[0].print_output, "Server is stopped")

      self.refresh_tasks_sleep_time = 3
      dprint_ex(1, "Done handling stop event")

    #---------------------------------------------------------------------------
    def refresh_tasks_thread(self):
      dprint_ex(2, "Enter")
      number_of_wakes_between_refreshes = 3
      cnt = 0

      only_status_check = 0

      while not self.closing:
        status = "unknown"

        try:
          status = self.ctrl_be.is_server_running(verbose=0)
        except Exception, exc:
          import traceback
          traceback.print_exc()
          print "exception getting server status: %s" % exc

        control_event = None
        if self.last_server_status != status:
          if status == "running":
            control_event = "server_started"
          elif status == "stopped":
            control_event = "server_stopped"

        if control_event:
          self.ctrl_be.event_from_main(control_event)

        dprint_ex(3, "server running", status, ", self.closing =", self.closing)
        if self.last_server_status != status or only_status_check == 0:
          dprint_ex(2, "Performing extra actions")
          if self.server_status_page:
            self.server_status_page.refresh(status)

        self.last_server_status = status


        time.sleep(self.refresh_tasks_sleep_time)
        cnt += 1
        only_status_check = cnt % number_of_wakes_between_refreshes

      dprint_ex(2, "Leave")

    #---------------------------------------------------------------------------
    def timeout(self):
      if not self.closing:
        self.ctrl_be.process_ui_task_queue()
      return not self.closing


    #---------------------------------------------------------------------------
    def add_content_page(self, content, section_name, item_name, icon_name_as_cmd, return_content_container = False):
        # strip _win prefix for osx icons, because we do not install _win icons in osx
        if self.server_profile.host_os == wbaOS.darwin:
            if icon_name_as_cmd[-4:] == "_win":
                icon_name_as_cmd = icon_name_as_cmd[:-4]

        container = content
        if return_content_container:
          container = newBox(False)
          container.add_end(content, True, True)

        self.tasks_side.add_section_entry(section_name, item_name, icon_name_as_cmd + ".png", icon_name_as_cmd, False)
        i = self.tabview.add_page(container, "")
        content.set_padding(8)
        self.tabs.append(content)
        self.name2page[icon_name_as_cmd] = (i, content)

        return container
