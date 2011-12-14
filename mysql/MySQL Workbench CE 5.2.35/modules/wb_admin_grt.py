# Copyright (c) 2009, 2010, Oracle and/or its affiliates. All rights reserved.
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

from wb import DefineModule
import grt
import os
import tempfile
import time

from mforms import Utilities, AppView, newSectionBox, App
import mforms

import wb_admin_main
import wb_admin_utils
import wba_ssh_ui
import wb_admin_ssh
import wb_admin_control
from wb_server_control import PasswordHandler
from wb_server_control import ServerProfile
from db_utils import MySQLConnection, MySQLError
from wb_common import OperationCancelledError, InvalidPasswordError, dprint_ex
from wb_server_management import local_run_cmd, local_get_cmd_output

# define this Python module as a GRT module
ModuleInfo = DefineModule(name= "WbAdmin", author= "Oracle Corp.", version="2.0")

class DBError(Exception):
    pass

tab_references = []

#===============================================================================
#
#===============================================================================
class AdministratorTab(AppView):
    #top_box holds all sections
    top_vbox = None
    monitor = None
    configuration = None
    ctrl_be = None

    #---------------------------------------------------------------------------
    def __init__(self, server_instance_settings):
        AppView.__init__(self, False, "admin", True)

        server_profile = ServerProfile(server_instance_settings, False)

        self.ctrl_be = wb_admin_control.WbAdminControl(server_profile, 
                        connect_sql=True)

        self.ctrl_be.init()

        version = self.ctrl_be.get_server_version()
        if type(version) is tuple:
          valid_versions = ((4,0), (4,1), (5,0), (5,1), (5,2), (5,4), (5,5), (5,6), (6,0))
          if version[:2] not in valid_versions:
            print version, "UNSUPPORTED"
          else:
            dprint_ex("Server version %s is supported" % str(version))

        self.on_close(wb_admin_utils.weakcb(self, "handle_on_close"))

        # Create sections and add them to the admin page.
        self.configuration = wb_admin_main.WbAdminMainView(server_profile, self.ctrl_be, self.monitor)
        self.add(self.configuration, True, True)
        #section = self.add_section("Configuration", False, False)
        #section.set_content(self.configuration)

    #---------------------------------------------------------------------------
    def handle_on_close(self):
        App.get().set_status_text("Closing Administator.")
        self.configuration.shutdown()
        self.ctrl_be.shutdown()
        tab_references.remove(self)
        return True

    #---------------------------------------------------------------------------
    def wait_server_check(self, timeout):
        # wait for the server status check to be performed until the given timeout
        t = time.time()
        while self.ctrl_be.is_server_running() and time.time() - t < timeout:
            time.sleep(0.5)

    #---------------------------------------------------------------------------
    def add_section(self, label_text, is_content_expandable, header_mode):
        section = newSectionBox(is_content_expandable, label_text, header_mode)
        section.set_name(label_text)
        self.add(section, not is_content_expandable, True)
        return section


#-------------------------------------------------------------------------------
def do_open_administrator(server_instance):
    validate_setting(server_instance.serverInfo, "sys.usesudo", norm_to_switch, None)#"Server profile has no indication of sudo usage")
    validate_setting(server_instance.serverInfo, "sys.usesudostatus", norm_to_switch, None)

    if server_instance.serverInfo["sys.system"] != "Windows":
      #validate_setting(server_instance.serverInfo, "sys.sudo", make_str_existing, "Server profile has no privileges elevation command defined")

      #if server_instance.serverInfo.has_key("sys.sudo") and server_instance.serverInfo["sys.sudo"].strip(" \r\t\n") == "":
      #  Utilities.show_warning("WB Administrator", "Server profile has empty privileges elevation command defined. Some functionality maybe unavailable", "OK", "", "")
      try:
        if not server_instance.serverInfo["sys.sudo"]:
          # don't break settings that were working perfectly before, assume a valid default
          server_instance.serverInfo["sys.sudo"] = "/usr/bin/sudo -p EnterPasswordHere /bin/bash -c"
      except:
        server_instance.serverInfo["sys.sudo"] = "/usr/bin/sudo -p EnterPasswordHere /bin/bash -c"

    app = App.get()
    try:
      adminTab = AdministratorTab(server_instance)
    except wb_admin_ssh.ConnectionError, exc:
      Utilities.show_error("Error Connecting to Server (%s@%s)" % (server_instance.loginInfo["ssh.userName"], server_instance.loginInfo["ssh.hostName"]), str(exc), "OK", "", "")
      app.set_status_text("Could not Open WB Admin")
      return None
    except MySQLError, exc:
      if exc.message:
        Utilities.show_error("Error Connecting to MySQL Server (%s)" % exc.location, str(exc), "OK", "", "")
      app.set_status_text("Could not Open WB Admin")
      return None
    except OperationCancelledError, exc:
        app.set_status_text("Cancelled (%s)"%exc)
        return None
    except Exception, exc:
        import traceback
        traceback.print_exc()
        Utilities.show_error("Error Starting Workbench Administrator", "%s: %s" % (type(exc).__name__, exc), "OK", "", "")
        app.set_status_text("Could not Open WB Admin")
        return None
    
    version = adminTab.ctrl_be.get_server_version()
    if version and version[0] < 5:
      Utilities.show_error("Unsupported Server Version", "The version of the server you're trying to connect to is %i.%i, which is not supported by Workbench."%version[:2],
                          "Close", "Ignore", "")
      app.set_status_text("Could not Open WB Admin")
      return None
    
    app.dock_view(adminTab, "maintab")
    app.set_view_title(adminTab, "Admin (%s)" % (server_instance.name))

    tab_references.append(adminTab)

    app.set_status_text("WB Admin Opened")

    dprint_ex(1, "Completed")
    return adminTab


#-------------------------------------------------------------------------------
def validate_setting(settings, option, norm_cb, msg):
  if settings.has_key(option):
    if norm_cb is not None:
      norm_cb(settings, option)
  else:
    if msg is not None:
      Utilities.show_warning("WB Administartor", msg, "OK", "", "")
    norm_cb(settings, option)

#-------------------------------------------------------------------------------
def norm_to_switch(settings, option):
  value = 0
  if settings.has_key(option):
    value = settings[option]
    if value > 0:
      value = 1
    else:
      value = 0

  settings[option] = value

#-------------------------------------------------------------------------------
def make_str_existing(settings, option):
  if not settings.has_key(option):
    settings[option] = ""

#-------------------------------------------------------------------------------
@ModuleInfo.plugin("wb.admin.open", type="standalone", caption= "Initialize WB Admin",  pluginMenu= "Administrator")
@ModuleInfo.export(grt.INT, grt.classes.db_mgmt_ServerInstance)
def openAdministrator(server_instance):
    do_open_administrator(server_instance)
    return 1


# this shouldn't be exported as a plugin... and besides it crashes
#@ModuleInfo.plugin("wb.admin.filterDebugger", type="standalone", caption= "Test filters",  pluginMenu= "Utilities")
@ModuleInfo.export(grt.INT, grt.DICT, grt.DICT)
def openFilterDebugger(loginInfo, serverInfo):
    wb_admin_control.run_filter_debugger(loginInfo, serverInfo)
    return 1

@ModuleInfo.plugin("wb.admin.listServices", type="standalone")
@ModuleInfo.export(grt.STRING, grt.DICT)
def listWindowsServices(server_instance):
    return wb_admin_utils.list_windows_services(server_instance)

#@ModuleInfo.plugin("wb.admin.remoteFileSelector", type="standalone")
@ModuleInfo.export(grt.STRING, grt.classes.db_mgmt_ServerInstance)
def openRemoteFileSelector(serverInstance):
    profile = ServerProfile(serverInstance)
    return wba_ssh_ui.remote_file_selector(profile, PasswordHandler(profile))


def selectServer(title):
    window = mforms.Form(None)
    window.set_title(title)
    box = mforms.newBox(False)
    window.set_content(box)
    
    box.set_padding(12)
    box.set_spacing(12)
    
    label = mforms.newLabel()
    label.set_text("Select Server to Connect to:")
    box.add(label, False, True)
    
    listbox = mforms.newListBox(False)
    box.add(listbox, True, True)
    listbox.show();

    for inst in grt.root.wb.rdbmsMgmt.storedInstances:
      listbox.add_item(inst.name)
    
    bbox = mforms.newBox(True)
    box.add(bbox, False, True)
    
    bbox.set_spacing(8)
    
    ok = mforms.newButton()
    ok.set_text("OK")
    bbox.add_end(ok, False, True)

    cancel = mforms.newButton()
    cancel.set_text("Cancel")
    bbox.add_end(cancel, False, True)
    
    window.set_size(400, 300)
    window.center()
    
    if window.run_modal(ok, cancel):
      i = listbox.get_selected_index()
      if i >= 0:
          return grt.root.wb.rdbmsMgmt.storedInstances[i]
    return None
        


@ModuleInfo.plugin("wb.admin.dumpManager", type="standalone", caption= "Open Database Export/Import Manager",  pluginMenu= "Administrator")
@ModuleInfo.export(grt.INT)
def openExportImport():
    server = selectServer("Import/Export MySQL Data")
    if server:
        tab = do_open_administrator(server)
        if tab:   
            tab.wait_server_check(4)
            tab.configuration.switch_to("DATA EXPORT / RESTORE", "Data Export and Restore")
            return 1
    return 0



@ModuleInfo.plugin("wb.admin.securityManager", type="standalone", caption= "Open Security Manager",  pluginMenu= "Administrator")
@ModuleInfo.export(grt.INT)
def openSecurityManager():
    server = selectServer("Security Manager")
    if server:
        tab = do_open_administrator(server)
        if tab:
            tab.wait_server_check(4)
            tab.configuration.switch_to("SECURITY", "Users and Privileges")
            return 1
    return 0

@ModuleInfo.plugin("wb.admin.placeholder", type="standalone", caption= "Open Administrator",  pluginMenu= "Administrator")
@ModuleInfo.export(grt.INT)
def tmpAdministratorShortcut():
    server = selectServer("Server Administration")
    if server:
        tab = do_open_administrator(server)
    return 1

#-------------------------------------------------------------------------------
@ModuleInfo.export(grt.INT, grt.STRING)
def testAdministrator(what):
  import wb_admin_test
  wb_admin_test.run()
  import sys
  sys.exit(0) # TODO return code here
  return 1


def check_if_config_file_has_section(config_file, section):
    for line in config_file:
        if line.strip() == "[%s]"%section:
	    return True
    return False


test_ssh_connection = None
test_ssh_connection_is_windows = None

@ModuleInfo.export(grt.STRING, grt.STRING, grt.classes.db_mgmt_ServerInstance)
def testInstanceSettingByName(what, server_instance):
    global test_ssh_connection
    print "What", what
    profile = ServerProfile(server_instance)

    if what == "connect_to_host":
        if test_ssh_connection:
            test_ssh_connection = None

        print "Connecting to %s" % profile.ssh_hostname

        try:
            test_ssh_connection = wb_admin_control.WbAdminControl(profile, connect_sql=False)
            test_ssh_connection.init()
            grt.send_info("connected.")
        except Exception, exc:
          import traceback
          traceback.print_exc()
          return "ERROR "+str(exc)
        except:
          print "Unknown error"
          return "ERROR"

        if not test_ssh_connection.is_ssh_connected():
            test_ssh_connection = None
            return "ERROR Error connecting to host"

        result, rc = test_ssh_connection.execute_filtered_command("uname", False)
        if rc != 0:
            # error calling uname, possibly windows
            result, rc = test_ssh_connection.execute_filtered_command("ver", False)
            test_ssh_connection_is_windows = True
        else:
            test_ssh_connection_is_windows = False
        print "OK, Operating System is '%s'" % result.strip()
        if not result:
            return "ERROR"

        return "OK"

    elif what == "disconnect":
        if test_ssh_connection:
            test_ssh_connection = None
        return "OK"
    
    elif what == "check_privileges":
        return "ERROR"
    
    elif what in ("find_config_file", "check_config_path", "check_config_section"):
        config_file = profile.config_file_path
        print "Check if %s exists in remote host" % config_file
        if not test_ssh_connection.ssh.file_exists(config_file):
          return "ERROR File %s doesn't exist" % config_file
        else:
          print "File was found in expected location"
        
        if what == "check_config_path":
          return "OK"

        section = profile.config_file_section
        cfg_file_content = ""
        print "Check if %s section exists in %s" % (section, config_file)
        try:
          #local_file = test_ssh_connection.fetch_file(config_file)
          cfg_file_content = test_ssh_connection.server_helper.get_file_content(path=config_file, as_admin=False, admin_password=False)
        except Exception, exc:
          return "ERROR "+str(exc)

        if ("[" + section + "]") in cfg_file_content:
          return "OK"
        return "ERROR Couldn't find section %s in the remote config file %s" % (section, config_file)

    elif what in ("find_config_file/local", "check_config_path/local", "check_config_section/local"):
        config_file = profile.config_file_path
        config_file = wb_admin_control.WbAdminControl(profile, connect_sql=False).expand_path_variables(config_file)
        print "Check if %s can be accessed" % config_file
        if os.path.exists(config_file):
          print "File was found at the expected location"
        else:
          return "ERROR File %s doesn't exist" % config_file

        if what == "check_config_path/local":
          return "OK"

        section = profile.config_file_section
        print "Check if section for instance %s exists in %s" % (section, config_file)
        if check_if_config_file_has_section(open(config_file, "r"), section):
          print "[%s] section found in configuration file" % section
          return "OK"
        return "ERROR Couldn't find section [%s] in the config file %s" % (section, config_file)

    elif what == "find_error_files":
        return "ERROR"
      
    elif what == "check_admin_commands":
        path = profile.start_server_cmd
        cmd_start= None
        if path.startswith("/"):
            cmd_start = path.split()[0]
            if not test_ssh_connection.ssh.file_exists(cmd_start):
                return "ERROR %s is invalid" % path

        path = profile.stop_server_cmd
        if path.startswith("/"):
            cmd = path.split()[0]
            if cmd != cmd_start and not test_ssh_connection.ssh.file_exists(cmd):
                return "ERROR %s is invalid" % path

        command = profile.check_server_status_cmd
        print "Checking command '%s'" % command
        #rc = test_ssh_connection.is_running()
        rc = test_ssh_connection.server_control.get_status()
        print "Server detected as %s" % (rc and "running" or "stopped"), 

        return "OK"

    elif what == "check_admin_commands/local":
        path = profile.start_server_cmd
        cmd_start= None
        if path.startswith("/"):
            cmd_start = path.split()[0]
            if not os.path.exists(cmd_start):
                return "ERROR %s is invalid" % path

        path = profile.stop_server_cmd
        if path.startswith("/"):
            cmd = path.split()[0]
            if cmd != cmd_start and not os.path.exists(cmd):
                return "ERROR %s is invalid" % path

        command = profile.check_server_status_cmd
        print "Checking command '%s'" % command
        result, rc = local_get_cmd_output(command, 0, None)
        print "Server detected as %s" % (result and "running" or "stopped")

        return "OK "+(result and "running" or "stopped")

    return "ERROR bad command"


@ModuleInfo.export(grt.DICT, grt.classes.db_mgmt_ServerInstance)
def detectInstanceSettings(server_instance):    
    #form = Form()
    
    #form.run(None, None)
    
    return {}



@ModuleInfo.export(grt.INT, grt.classes.db_mgmt_ServerInstance)
def testInstanceSettings(server_instance):
    return 0

