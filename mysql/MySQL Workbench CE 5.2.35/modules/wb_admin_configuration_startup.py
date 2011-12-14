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

from mforms import newButton, newPanel, newLabel, newBox, newCheckBox, newTable, newTextBox, newImageBox, Utilities
import mforms

from wb_common import dprint_ex
import datetime
from wb_admin_utils import no_remote_admin_warning_label

class WbAdminConfigurationStartup(mforms.Box):
    long_status_msg = None
    short_status_msg = None
    start_stop_btn = None
    startup_msgs_log = None
    is_server_running_prev_check = None
    copy_to_clipboard_button = None
    clear_messages_button = None
    ui_created = False

    #---------------------------------------------------------------------------
    def print_output(self, text):
      ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S - ")
      self.startup_msgs_log.append_text_with_encoding(ts + text + "\n", self.ctrl_be.server_helper.cmd_output_encoding)

    #---------------------------------------------------------------------------
    def __init__(self, ctrl_be, server_profile, main_view):
        mforms.Box.__init__(self, False)
        self.main_view = main_view
        self.ctrl_be = ctrl_be
        self.server_profile = server_profile
        self.main_view.add_content_page(self, "MANAGEMENT", "Startup / Shutdown", "admin_start_stop_win")

    #---------------------------------------------------------------------------
    @property
    def server_profile(self):
        return self.ctrl_be.server_profile

    #---------------------------------------------------------------------------
    @property
    def server_control(self):
        return self.ctrl_be.server_control

    #---------------------------------------------------------------------------
    def create_ui(self):
        self.suspend_layout()

        if not self.server_profile.admin_enabled:
            self.add(no_remote_admin_warning_label(self.server_profile), False, True)
            self.resume_layout()
            return

        self.main_view.ui_profile.apply_style(self, 'page')
        self.set_padding(8) # TODO check padding

        # Top layout structure.
        content = newBox(False)
        self.add(content, True, True)

        # A spacer at the bottom of the page.
        spacer = newBox(True)
        spacer.set_size(-1, 40)
        self.add(spacer, False, True)

        # Left pane (start/stop).
        heading = newLabel("Database Server Status")
        heading.set_style(mforms.BoldStyle)
        content.add(heading, False, True)

        left_pane = newBox(False)
        left_pane.set_spacing(8)

        self.long_status_msg = newLabel("The database server is stopped")
        self.long_status_msg.set_style(mforms.SmallStyle)
        left_pane.add(self.long_status_msg, False, True)

        status_message_part = newLabel("The database server instance is ")
        self.short_status_msg = newLabel("...")
        self.short_status_msg.set_color("#DD0000")

        self.start_stop_btn = newButton()
        self.start_stop_btn.set_text("Start server")
        self.start_stop_btn.add_clicked_callback(self.start_stop_clicked)

        start_stop_hbox = newBox(True)
        start_stop_hbox.add(status_message_part, False, True)
        start_stop_hbox.add(self.short_status_msg, False, True)
        start_stop_hbox.add(newLabel("  "), False, False)
        start_stop_hbox.add(self.start_stop_btn, False, False)
        left_pane.add(start_stop_hbox, False, False)

        left_pane.add(self.long_status_msg, False, False)
        left_pane.add(start_stop_hbox, False, False)

        description = newLabel("If you stop the server, you and your applications will not be able to use the Database and all current connections will be closed")
        description.set_style(mforms.SmallStyle)
        left_pane.add(description, False, False)

        separator = newImageBox()
        separator.set_image("options-horizontal-separator.png")
        left_pane.add(separator, False, True)

        auto_start_checkbox = newCheckBox()
        auto_start_checkbox.set_text("Automatically Start Database Server on Startup")
        auto_start_checkbox.set_active(True)

        description = newLabel("You may select to have the Database server start automatically whenever the computer starts up.")
        description.set_style(mforms.SmallStyle)
        description.set_wrap_text(True)

        content.add(left_pane, False, True)

        # Right pane (log).
        heading = newLabel("Startup Message Log")
        heading.set_style(mforms.BoldStyle)
        content.add(heading, False, True)

        right_pane = newBox(False)    
        right_pane.set_spacing(8)

        self.startup_msgs_log = newTextBox(mforms.BothScrollBars)
        self.startup_msgs_log.set_read_only(True)
        right_pane.add(self.startup_msgs_log, True, True)

        button_box = newBox(True)
        self.refresh_button = newButton()
        self.refresh_button.set_text("Refresh Status")
        self.refresh_button.add_clicked_callback(lambda:self.refresh(2))
        button_box.add(self.refresh_button, False, False)

        self.copy_to_clipboard_button = newButton()
        self.copy_to_clipboard_button.set_size(150, -1)
        self.copy_to_clipboard_button.set_text("Copy to Clipboard")
        self.copy_to_clipboard_button.add_clicked_callback(self.copy_to_clipboard)
        button_box.add_end(self.copy_to_clipboard_button, False, False)

        self.clear_messages_button = newButton()
        self.clear_messages_button.set_size(150, -1)
        self.clear_messages_button.set_text("Clear Messages")
        self.clear_messages_button.add_clicked_callback(self.clear_messages)
        button_box.add_end(self.clear_messages_button, False, False)
        right_pane.add(button_box, False, True)

        content.add(right_pane, True, True)

        self.resume_layout()

        self.ctrl_be.add_me_for_event("server_started", self)
        self.ctrl_be.add_me_for_event("server_stopped", self)

    #---------------------------------------------------------------------------
    def page_activated(self):
        self.main_view.set_content_label(" Startup / Shutdown")
        if not self.ui_created:
            self.create_ui()
            self.ui_created = True
        if self.server_control:
            self.server_control.set_output_handler(self.print_output)
        self.refresh()

    #---------------------------------------------------------------------------
    def server_started_event(self):
      dprint_ex(2, "Handling server start event in start/stop page")
      self.ctrl_be.uitask(self.update_ui, "running")

    #---------------------------------------------------------------------------
    def server_stopped_event(self):
      dprint_ex(2, "Handling server stop event in start/stop page")
      self.ctrl_be.uitask(self.update_ui, "stopped")

    #---------------------------------------------------------------------------
    def update_ui(self, server_status):
      dprint_ex(2, "Enter. server_status =", server_status)

      if not self.server_profile.admin_enabled:
        return

      self.is_server_running_prev_check = server_status
      if server_status in ("running", "starting"):
        if server_status == "starting":
          self.long_status_msg.set_text("The database server is starting...")
          self.start_stop_btn.set_enabled(False)
          self.short_status_msg.set_color("#DDCC00")
        else:
          self.start_stop_btn.set_enabled(True)
          self.short_status_msg.set_color("#00DD00")
          self.long_status_msg.set_text("The database server is started and ready for client connections. To shut the Server down, use the \"Stop Server\" button")
        self.short_status_msg.set_text(server_status)
        self.start_stop_btn.set_text("Stop Server")
      elif server_status in ("stopped", "stopping"):
        if server_status == "stopping":
          self.long_status_msg.set_text("The database server is stopping...")
          self.start_stop_btn.set_enabled(False)
          self.short_status_msg.set_color("#DDCC00")
        else:
          self.start_stop_btn.set_enabled(True)
          self.short_status_msg.set_color("#DD0000")
          self.long_status_msg.set_text("The database server is stopped. To start the Server, use the \"Start Server\" button")
        self.short_status_msg.set_text(server_status)
        self.start_stop_btn.set_text("Start Server")
      else:
        self.long_status_msg.set_text("The state of the database server could not be determined, please verify server profile settings.")
        self.short_status_msg.set_text("unknown")
        self.short_status_msg.set_color("#FF0000")
        self.start_stop_btn.set_text("Start Server")
        self.start_stop_btn.set_enabled(False)

      dprint_ex(2, "Leave")

    #---------------------------------------------------------------------------
    def start_stop_clicked(self):
        status = self.ctrl_be.is_server_running(verbose=1)
        # Check if server was started/stoped from outside
        if self.is_server_running_prev_check == status:
            if status == "running":
                self.start_stop_btn.set_enabled(False)
                self.refresh_button.set_enabled(False)

                try:
                    if self.server_control and not self.server_control.stop_async(self.async_stop_callback):
                        self.start_stop_btn.set_enabled(True)
                        self.refresh_button.set_enabled(True)
                        return
                except Exception, exc:
                    self.start_stop_btn.set_enabled(True)
                    self.refresh_button.set_enabled(True)
                    Utilities.show_error("Stop Server",
                              "An error occurred while attempting to stop the server.%s %s\n" % (type(exc).__name__, exc),
                              "OK", "", "")
                    return
            elif status == "stopped":
                self.start_stop_btn.set_enabled(False)
                self.refresh_button.set_enabled(False)

                try:
                    if self.server_control and not self.server_control.start_async(self.async_start_callback):
                        self.start_stop_btn.set_enabled(True)
                        self.refresh_button.set_enabled(True)
                        return
                except Exception, exc:
                    self.start_stop_btn.set_enabled(True)
                    self.refresh_button.set_enabled(True)
                    Utilities.show_error("Stop Server",
                              "An error occurred while attempting to stop the server.%s %s\n" % (type(exc).__name__, exc),
                              "OK", "", "")
                    return

            elif status == "stopping":
                self.print_output("Server is stopping, please wait...")
            elif status == "starting":
                self.print_output("Server is starting, please wait...")
            else:
                self.print_output("Unable to detect server status.")
            self.refresh()

    #---------------------------------------------------------------------------
    def async_stop_callback(self, status):
        self.ctrl_be.uitask(self.async_stop_finished, status)

    #---------------------------------------------------------------------------
    def async_stop_finished(self, status): # status can be one of success, bad_password or error message
        if status == "success":
            self.print_output("Server stop done.")
        elif status == "bad_password":
            r = Utilities.show_error("Stop Server",
                              "A permission error occurred while attempting to stop the server.\n"
                              "Administrator password was possibly wrong.",
                              "Retry", "Cancel", "")
            if r == mforms.ResultOk:
                pass
            else:
                self.print_output("Could not stop server. Permission denied")
        else:
            self.print_output("Could not stop server: %s" % (status or "unknown error"))
            Utilities.show_error("Could not stop server", str(status), "OK", "", "")
        self.refresh()
        self.refresh_button.set_enabled(True)
        self.start_stop_btn.set_enabled(True)

    #---------------------------------------------------------------------------
    def async_start_callback(self, status):
        self.ctrl_be.uitask(self.async_start_finished, status)

    #---------------------------------------------------------------------------
    def async_start_finished(self, status):
        if status == "success":
            self.print_output("Server start done.")
        elif status == "bad_password":
            r = Utilities.show_error("Start Server",
                              "A permission error occurred while attempting to start the server.\n"
                              "Administrator password was possibly wrong.",
                              "Retry", "Cancel", "")
            if r == mforms.ResultOk:
                pass
            else:
                self.print_output("Could not stop server. Permission denied")
        else:
            self.print_output("Could not start server: %s" % (status or "unknown error"))
            Utilities.show_error("Could not start server", str(status), "OK", "", "")
        self.refresh()
        self.refresh_button.set_enabled(True)
        self.start_stop_btn.set_enabled(True)

    #---------------------------------------------------------------------------
    def refresh(self, verbose=1):
      self.is_server_running_prev_check = self.ctrl_be.is_server_running(verbose=verbose, force_process_check=True)
      self.update_ui(self.is_server_running_prev_check)

    #---------------------------------------------------------------------------
    def copy_to_clipboard(self):
      Utilities.set_clipboard_text(self.startup_msgs_log.get_string_value())

    #---------------------------------------------------------------------------
    def clear_messages(self):
      self.startup_msgs_log.clear()
