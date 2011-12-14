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

import os
import weakref
import platform
import copy

from grt import modules
from mforms import Utilities, newLabel, newBox, newTextEntry, newTextBox, newButton, Form, newTreeView
import mforms

from db_utils import MySQLConnection, MySQLError
from wb_common import dprint_ex

#-------------------------------------------------------------------------------
def get_db_connection(server_instance_settings):
  if server_instance_settings.connection:
    db_connection = MySQLConnection(server_instance_settings.connection)
    ignore_error = False
    error_location = None
    the_error = None
    try:
      db_connection.connect()
    except MySQLError, exc:
     # errors that probably just mean the server is down can be ignored (ex 2013)
     # errors from incorrect connect parameters should raise an exception
     # ex 1045: bad password
      if exc.code in (1045,):
        raise exc
      elif exc.code in (2013,):
        ignore_error = True
      error_location = exc.location
      the_error = str(exc)

      if not ignore_error:
        if Utilities.show_warning("Could not connect to MySQL Server at %s" % error_location,
                "%s\nYou can continue but some functionality may be unavailable." % the_error,
                "Continue Anyway", "Cancel", "") != mforms.ResultOk:
          raise MySQLError("", 0, "")
    return db_connection
  else:
    Utilities.show_warning("WB Admin", "Server instance has no database connection specified.\nSome functionality will not be available.", "OK", "", "")


  return None




def weakcb(object, cbname):
    """Create a callback that holds a weak reference to the object. When passing a callback
    for mforms, use this to create a ref to it and prevent circular references that are never freed.
    """
    def call(ref, cbname):
        callback = getattr(ref(), cbname, None)
        if callback is None:
            print "Object has no callback %s"%cbname
        else:
            return callback()

    return lambda ref=weakref.ref(object): call(ref, cbname)


not_running_warning_label_text = "There is no connection to the MySQL Server.\nThis functionality requires an established connection to a running MySQL server to work."
def not_running_warning_label():
    warning = newLabel(not_running_warning_label_text)
    warning.set_style(mforms.BigStyle)
    warning.set_text_align(mforms.MiddleCenter)
    warning.show(False)
    return warning

def no_remote_admin_warning_label(server_instance_settings):
    if server_instance_settings.uses_ssh:
        warning = newLabel("There is no SSH connection to the server.\nTo use this functionality, the server where MySQL is located must have a SSH server running\nand you must provide its login information in the server profile.")
    else:
        if server_instance_settings.uses_wmi:
            warning = newLabel("There is no WMI connection to the server.\nTo use this functionality, the server where MySQL is located must be configured to use WMI\nand you must provide its login information in the server profile.")
        else:
            warning = newLabel("Remote Administration is disabled.\nTo use this functionality, the server where MySQL is located must either have an SSH server running\nor alternatively, if it is a Windows machine, must have WMI enabled.\nAdditionally you must enable remote administration in the server profile, providing login details for it.")
    warning.set_style(mforms.BigStyle)
    warning.set_text_align(mforms.MiddleCenter)
    return warning




def run_filter_debugger(loginInfo, serverInfo, build_filters, apply_filters):
  form = Form(None, mforms.FormSingleFrame)

  close = newButton()
  close.set_text("Close")
  test = newButton()
  test.set_text("Test")
  clr = newButton()
  clr.set_text("Clear output")
  button_box = newBox(True)
  button_box.set_spacing(8)
  button_box.add(close, False, True)
  button_box.add(clr, False, True)
  
  top_box = newBox(False)
  top_box.set_padding(12)
  top_box.set_spacing(8)

  panel_box = newBox(True)
  
  panel_box.set_spacing(12)
  panel_box.set_padding(8)

  input_area = newTextBox(mforms.BothScrollBars)
  input_box = newBox(False)
  input_box.add(newLabel("Input:"), False, True)
  input_box.add(input_area, True, True)

  output_area = newTextBox(mforms.BothScrollBars)
  output_box = newBox(False)
  output_box.add(newLabel("Output:"), False, True)
  output_box.add(output_area, True, True)

  panel_box.add(input_box, True, True)
  panel_box.add(output_box, True, True)

  filter_box = newBox(True)

  filter_lbl = newLabel("Filter:")
  filters = newTextEntry()

  filter_box.add(filter_lbl, False, True)
  filter_box.add(filters, True, True)
  filter_box.add(test, False, True)
  
  top_box.add(filter_box, False, True)
  top_box.add(panel_box, True, True)
  top_box.add(button_box, False, True)
  
  form.set_content(top_box)
  form.set_size(400, 400)

  def clr_action(output_area):
    output_area.clear()

  def close_action():
    form.close()

  def test_action(filters_entry, input_area, output_area, build_filters, apply_filters):
    (script, filters) = build_filters("dummy_executable | " + filters_entry.get_string_value())

    def add_text(x):
      output_area.append_text(x)

    (filtered_text, filters_code) = apply_filters(input_area.get_string_value(), filters, add_text)

    retcode = 0
    if filters_code is not None:
      if retcode is not None:
        retcode = int(retcode) and filters_code
      else:
        retcode = filters_code

    output_area.append_text("retcode = " + str(retcode) + "\n")

  close.add_clicked_callback(close_action)
  clr.add_clicked_callback(lambda : clr_action(output_area))
  test.add_clicked_callback(lambda : test_action(filters, input_area, output_area, build_filters, apply_filters))

  form.relayout()
  form.center()
  form.run_modal(close, None)

#==========================================================================
# Unit tests
#==========================================================================
