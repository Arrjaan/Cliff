# Copyright (c) 2007, 2011, Oracle and/or its affiliates. All rights reserved.
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

from mforms import newBox, newLabel, newButton, newTextEntry, newTreeView, newTable, newRadioButton, newListBox, newSelector, newPanel, newTabView, Utilities, newCheckBox, newImageBox, App
import mforms
import re
import getpass

from wb_admin_utils import not_running_warning_label
from wb_admin_security_be import AdminSecurity, PrivilegeInfo, SecurityAdminRoles, WBSecurityValidationError
from wb_common import PermissionDeniedError


SCHEMA_OBJECT_RIGHTS = [
"Select_priv",
"Insert_priv",
"Update_priv",
"Delete_priv",
"Execute_priv",
"Show_view_priv",
]

SCHEMA_DDL_RIGHTS = [
"Create_priv",
"Alter_priv",
"References_priv",
"Index_priv",
"Create_view_priv", 
"Create_routine_priv",
"Alter_routine_priv",
"Drop_priv",
"Trigger_priv"
]

SCHEMA_OTHER_RIGHTS = [
"Grant_priv",
"Create_tmp_table_priv",
"Lock_tables_priv",
]


AUTHENTICATION_PLUGIN_TYPES = {
None : {"name" : "Standard", 
        "auth_string_label": "",
        "enable_host": True,
        "enable_password" : True,
        },
"authentication_windows" : { "name": "Windows Native",
        "auth_string_label": "Supply the Windows username and/or group names that are allowed to use this account, separated by a comma (,)\nThis account will be usable by these users whenever they are logged into Windows, without additional passwords.\nExample: Administrator, %s" % (getpass.getuser() or "joe"),
        "enable_host": False,
        "enable_password" : False
        },
"authentication_pam" : {"name": "PAM",
        "auth_string_label": "Syntax: <pam_service_name>[,<group_name1>=<sql_user_name1>  [,<group_name2>=<sql_user_name2> ...]]\nSee documentation for details.",
        "enable_host": False,
        "enable_password" : False
        },
"*" : {"name": None,
        "auth_string_label": "See the plugin documentation for valid values and details.",
        "enable_host": True,
        "enable_password" : True
        }
}

def rLabel(text):
    l = newLabel(text)
    l.set_text_align(mforms.MiddleRight)
    return l

def dLabel(text):
    l = newLabel(text)
    l.set_style(mforms.SmallHelpTextStyle)
    return l
    
    
class AddSchemaPrivilegeForm(mforms.Form):
    def __init__(self, secman, user=""):
        mforms.Form.__init__(self, None, mforms.FormResizable | mforms.FormMinimizable)

        self.set_title("New Schema Privilege Definition")

        self.secman = secman

        box = newBox(False)
        box.set_padding(12)
        box.set_spacing(8)
        self.set_content(box)
        
        label = newLabel()
        label.set_text("Select the Host and the Schema for which the user '%s'\nwill have the privileges you want to define."%user)
        box.add(label, False, True)
        
        panel = newPanel(mforms.TitledBoxPanel)
        panel.set_title("Host")
        box.add(panel, False, True)
        table = newTable()
        panel.add(table)
        table.set_padding(8)
        table.set_row_count(3)
        table.set_column_count(3)
        table.set_row_spacing(8)
        
        self.host1 = newRadioButton(mforms.RadioButton.new_id())
        self.host1.set_active(True)
        self.host1.add_clicked_callback(self.host_radio_changed)
        self.host1.set_text("Any Host (%)")
        table.add(self.host1, 0, 1, 0, 1, mforms.HFillFlag)
        
        self.host2 = newRadioButton(self.host1.group_id())
        self.host2.set_text("Hosts matching pattern or name:")
        self.host2.add_clicked_callback(self.host_radio_changed)
        table.add(self.host2, 0, 1, 1, 2, mforms.HFillFlag)
        
        self.host2entry = newTextEntry()
        table.add(self.host2entry, 1, 2, 1, 2, mforms.HFillFlag|mforms.HExpandFlag)
                
        self.host3 = newRadioButton(self.host1.group_id())
        self.host3.set_text("Selected host:")
        self.host3.add_clicked_callback(self.host_radio_changed)
        table.add(self.host3, 0, 1, 2, 3, mforms.HFillFlag)
        
        self.host3sel = newSelector()
        table.add(self.host3sel, 1, 2, 2, 3, mforms.HFillFlag|mforms.HExpandFlag)
        
        hosts = [h for u,h in secman.account_names if u == user]
        self.host3sel.add_items(hosts)
        

        panel = newPanel(mforms.TitledBoxPanel)
        panel.set_title("Schema")
        box.add(panel, True, True)
        table = newTable()
        panel.add(table)
        table.set_padding(8)
        table.set_row_count(3)
        table.set_column_count(3)
        table.set_row_spacing(8)
        
        self.schema1 = newRadioButton(mforms.RadioButton.new_id())
        self.schema1.set_active(True)
        self.schema1.add_clicked_callback(self.schema_radio_changed)
        self.schema1.set_text("Any Schema (%)")
        table.add(self.schema1, 0, 1, 0, 1, mforms.HFillFlag)
        
        self.schema2 = newRadioButton(self.schema1.group_id())
        self.schema2.add_clicked_callback(self.schema_radio_changed)
        self.schema2.set_text("Schemas matching pattern or name:")
        table.add(self.schema2, 0, 1, 1, 2, mforms.HFillFlag)
        
        self.schema2entry = newTextEntry()
        table.add(self.schema2entry, 1, 2, 1, 2, mforms.HFillFlag|mforms.HExpandFlag)
                
        self.schema3 = newRadioButton(self.schema1.group_id())
        self.schema3.add_clicked_callback(self.schema_radio_changed)
        self.schema3.set_text("Selected schema:")
        table.add(self.schema3, 0, 1, 2, 3, mforms.HFillFlag)
        
        self.schema3sel = newListBox(False)
        table.add(self.schema3sel, 1, 2, 2, 3, mforms.HFillFlag|mforms.HExpandFlag|mforms.VFillFlag|mforms.VExpandFlag)
        self.schema3sel.add_items(self.secman.schema_names)

        bbox = newBox(True)
        box.add(bbox, False, True)

        bbox.set_spacing(8)

        self.ok = newButton()
        self.ok.set_text("OK")
        bbox.add_end(self.ok, False, True)

        self.cancel = newButton()
        self.cancel.set_text("Cancel")
        bbox.add_end(self.cancel, False, True)
        
        self.set_size(450, 500)
    
        self.host_radio_changed()
        self.schema_radio_changed()
    
        self.center()


    def host_radio_changed(self):
        self.host2entry.set_enabled(self.host2.get_active())
        self.host3sel.set_enabled(self.host3.get_active())


    def schema_radio_changed(self):
        self.schema2entry.set_enabled(self.schema2.get_active())
        self.schema3sel.set_enabled(self.schema3.get_active())

    
    def run(self):
        if self.run_modal(self.ok, self.cancel):
            if self.host1.get_active():
                host = "%"
            elif self.host2.get_active():
                host = self.host2entry.get_string_value()
            else:
                host = self.host3sel.get_string_value()

            if self.schema1.get_active():
                schema = "%"
            elif self.schema2.get_active():
                schema = self.schema2entry.get_string_value()
            else:
                schema = self.schema3sel.get_string_value()

            return host, schema

        return None, None


#############################

class SecurityAccount(mforms.Box):
    def __init__(self, owner):
        mforms.Box.__init__(self, False)
        self.set_managed()
        self.owner = owner

        self._selected_user = None
        self._selected_user_original = None
        self.valid = False

        self.suspend_layout()
        self.set_padding(8)
        self.set_spacing(8)

        top_box = newBox(True)
        top_box.set_spacing(8)
        self.add(top_box, True, True)

        bottom_box = newBox(True)
        bottom_box.set_spacing(8)

        self.add_button = newButton()
        self.add_button.set_text("Add Account")
        bottom_box.add(self.add_button, False, True)
        self.add_button.add_clicked_callback(self.add_account)

        self.dup_button = newButton()
        self.dup_button.set_text("Duplicate")
        #bottom_box.add(self.dup_button, False, True)
        self.dup_button.add_clicked_callback(self.dup_account)

        self.del_button = newButton()
        self.del_button.set_text("Remove")
        bottom_box.add(self.del_button, False, True)
        self.del_button.add_clicked_callback(self.del_account)

        self.refresh_button = newButton()
        self.refresh_button.set_text("Refresh")
        self.refresh_button.add_clicked_callback(self.owner.refresh)
        bottom_box.add_end(self.refresh_button, False, True)

        self.save_button = newButton()
        self.save_button.set_text("Apply")
        bottom_box.add_end(self.save_button, False, True)
        self.save_button.add_clicked_callback(self.commit)

        self.revert_button = newButton()
        self.revert_button.set_text("Revert")
        bottom_box.add_end(self.revert_button, False, True)        
        self.revert_button.add_clicked_callback(self.revert)

        self.revoke_all_button = newButton()
        self.revoke_all_button.set_text("Revoke All Privileges")
        bottom_box.add_end(self.revoke_all_button, False, True)        
        self.revoke_all_button.add_clicked_callback(self.revoke_all)
        self.revoke_all_button.set_tooltip("Immediately remove all privileges from the account, from every object at all levels.\nThe account itself will be left untouched and logins will still be possible.")
            
        self.add(bottom_box, False, True)

        account_list_box = newBox(False)
        account_list_box.set_spacing(8)
        account_list_box.set_size(220, -1)
        top_box.add(account_list_box, False, True)
    
        label = newLabel("User Accounts")
        account_list_box.add(label, False, True)

        #searchbox = TextEntry(SearchEntry)
        #account_list_box.add(searchbox, False, True)

        self.user_list = newTreeView(mforms.TreeDefault)
        self.user_list.add_column(mforms.StringColumnType, "User", 80, False)
        self.user_list.add_column(mforms.StringColumnType, "From Host", 120, False)
        self.user_list.end_columns()
        self.user_list.add_changed_callback(self.user_selected)
        self.user_list.set_allow_sorting(True)
        account_list_box.add(self.user_list, True, True)


        self.content_box = abox = newBox(False)
        abox.set_spacing(8)
        top_box.add(abox, True, True)
    
        self.account_label = newLabel("Select an account to edit or click Add Account to create a new one")
        self.account_label.set_style(mforms.BoldStyle)
        
        abox.add(self.account_label, False, True)

 
        tabView = newTabView(False)
        abox.add(tabView, True, True)
        
        ##
        vbox = newBox(False)
        vbox.set_spacing(12)
        vbox.set_padding(12)
        tabView.add_page(vbox, "Login")

        table = newTable()
        vbox.add(table, False, True)
                        
        table.set_row_count(7)
        table.set_column_count(3)
        table.set_row_spacing(8)
        table.set_column_spacing(8)
        
        self.username = newTextEntry()
        self.username.set_size(150, -1)
        self.username.add_changed_callback(self.set_dirty)
        self.username.set_max_length(16) # max username length for mysql 
        self.password = newTextEntry(mforms.PasswordEntry)
        self.password.set_size(150, -1)
        self.password.add_changed_callback(self.set_dirty)
        self.confirm = newTextEntry(mforms.PasswordEntry)
        self.confirm.set_size(150, -1)
        self.confirm.add_changed_callback(self.set_dirty)
        
        self.hostlimithost = newTextEntry()
        self.hostlimithost.add_changed_callback(self.validate_hostlimithost)
        
        table.add(rLabel("Login Name:"), 0, 1, 0, 1, mforms.HFillFlag)
        table.add(self.username, 1, 2, 0, 1, mforms.HFillFlag)
        table.add(dLabel("You may create multiple accounts with the same name\nto connect from different hosts."), 2, 3, 0, 1, mforms.HFillFlag|mforms.HExpandFlag)

        self.has_extra_plugins = len([p for p in self.active_plugins if p not in ("mysql_native_password", "mysql_old_password")]) > 0

        if self.has_extra_plugins:
            self.auth_type_label = rLabel("Authentication Type:")
            table.add(self.auth_type_label, 0, 1, 1, 2, mforms.HFillFlag)
            self.auth_type_sel = newSelector()
            table.add(self.auth_type_sel, 1, 2, 1, 2, mforms.HFillFlag|mforms.HExpandFlag)
            table.add(dLabel("\nFor the standard password and/or host based authentication,\nselect 'Standard'.\n"), 2, 3, 1, 2, mforms.HFillFlag)
            self.auth_type_sel.add_changed_callback(self.auth_type_changed)
            self.auth_type_list = []
            for plugin in [None] + self.active_plugins:
                if plugin in ("mysql_native_password", "mysql_old_password"):
                    continue
                if AUTHENTICATION_PLUGIN_TYPES.has_key(plugin):
                    self.auth_type_sel.add_item(AUTHENTICATION_PLUGIN_TYPES[plugin]["name"])
                else:
                    self.auth_type_sel.add_item(plugin)
                self.auth_type_list.append(plugin)
        else:
            self.auth_type_list = None
            self.auth_string_param = None

        self.auth_type_password_labels = []
        def add(label, l = self.auth_type_password_labels):
            l.append(label)
            return label

        table.add(add(rLabel("Limit Connectivity to Hosts Matching:")), 0, 1, 2, 3, mforms.HFillFlag)
        table.add(self.hostlimithost, 1, 2, 2, 3, mforms.HFillFlag)
        self.hostlimit_box = newBox(True)
        self.hostlimithost_valid_icon = newImageBox()
        self.hostlimit_box.add(self.hostlimithost_valid_icon, False, False)
        self.hostlimit_box.add(add(dLabel("% and _ wildcards may be used")), True, True)
        table.add(self.hostlimit_box, 2, 3, 2, 3, mforms.HFillFlag|mforms.HExpandFlag)
        
        table.add(add(rLabel("Password:")), 0, 1, 3, 4, mforms.HFillFlag)
        table.add(self.password, 1, 2, 3, 4, mforms.HFillFlag)
        table.add(add(dLabel("Type a password to reset it.")), 2, 3, 3, 4, mforms.HFillFlag|mforms.HExpandFlag)
        table.add(add(rLabel("Confirm Password:")), 0, 1, 4, 5, mforms.HFillFlag)
        table.add(self.confirm, 1, 2, 4, 5, mforms.HFillFlag)
        table.add(add(dLabel("Enter password again to confirm.")), 2, 3, 4, 5, mforms.HFillFlag|mforms.HExpandFlag)

        table.add(newLabel(""), 1, 2, 5, 6, mforms.HFillFlag)

        if self.has_extra_plugins:
            self.auth_string_param = newTextEntry()
            self.auth_string_param.add_changed_callback(self.set_dirty)
            self.auth_string_label = rLabel("Authentication String:")
            table.add(self.auth_string_label, 0, 1, 6, 7, mforms.HFillFlag)
            table.add(self.auth_string_param, 1, 2, 6, 7, mforms.HFillFlag|mforms.HExpandFlag)
            table.add(dLabel("Authentication plugin specific parameters."), 2, 3, 6, 7, mforms.HFillFlag)
            self.auth_string_help = newLabel("")
            vbox.add(self.auth_string_help, False, True)

        ####
        
        box = newBox(False)
        tabView.add_page(box, "Administrative Roles")
        
        lbox = newBox(True)
        box.add(lbox, True, True)
        lbox.set_spacing(12)
        lbox.set_padding(12)

        self.role_list = newTreeView(mforms.TreeDefault)
        self.role_list.add_column(mforms.CheckColumnType, "", 30, True)
        self.role_list.add_column(mforms.StringColumnType, "Role", 150, False)
        self.role_list.add_column(mforms.StringColumnType, "Description", 300, False)
        self.role_list.end_columns()
        lbox.add(self.role_list, True, True)
        self.role_list.set_cell_edited_callback(self.role_list_toggled)

        self.role_priv_list = newTreeView(mforms.TreeDefault)
        self.role_priv_list.add_column(mforms.StringColumnType, "Global Privileges Assigned to User", 200, False)
        self.role_priv_list.end_columns()
        self.role_priv_list.set_size(220, -1)
        self.role_priv_list.set_allow_sorting(True)
        lbox.add(self.role_priv_list, False, True)

        self.role_list.clear_rows()
        for name, desc, privs in SecurityAdminRoles:
            row = self.role_list.add_row()
            self.role_list.set_bool(row, 0, False)
            self.role_list.set_string(row, 1, name)
            self.role_list.set_string(row, 2, desc)

        ###
        table = newTable()
        tabView.add_page(table, "Account Limits")

        table.set_padding(12)
        table.set_column_spacing(8)
        table.set_row_spacing(8)
        table.set_row_count(4)
        table.set_column_count(3)
                
        table.add(rLabel("Max. Queries:"), 0, 1, 0, 1, 0)
        self.max_questions = newTextEntry()
        self.max_questions.set_size(60, -1)
        self.max_questions.add_changed_callback(self.set_dirty)
        table.add(self.max_questions, 1, 2, 0, 1, mforms.HFillFlag)
        table.add(dLabel("Number of queries the account can execute within one hour."), 2, 3, 0, 1, mforms.HFillFlag|mforms.HExpandFlag)
        
        table.add(rLabel("Max. Updates:"), 0, 1, 1, 2, 0)
        self.max_updates = newTextEntry()
        self.max_updates.set_size(60, -1)
        self.max_updates.add_changed_callback(self.set_dirty)
        table.add(self.max_updates, 1, 2, 1, 2, mforms.HFillFlag)
        table.add(dLabel("Number of updates the account can execute within one hour."), 2, 3, 1, 2, mforms.HFillFlag|mforms.HExpandFlag)

        table.add(rLabel("Max. Connections:"), 0, 1, 2, 3, 0)
        self.max_connections = newTextEntry()
        self.max_connections.set_size(60, -1)
        self.max_connections.add_changed_callback(self.set_dirty)
        table.add(self.max_connections, 1, 2, 2, 3, mforms.HFillFlag)
        table.add(dLabel("The number of times the account can connect to the server per hour."), 2, 3, 2, 3, mforms.HFillFlag|mforms.HExpandFlag)
        
        table.add(rLabel("Concurrent Connections:"), 0, 1, 3, 4, 0)
        self.max_uconnections = newTextEntry()
        self.max_uconnections.set_size(60, -1)
        self.max_uconnections.add_changed_callback(self.set_dirty)
        table.add(self.max_uconnections, 1, 2, 3, 4, mforms.HFillFlag)
        table.add(dLabel("The number of simultaneous connections to the server the account can have."), 2, 3, 3, 4, mforms.HFillFlag|mforms.HExpandFlag)

        self.resume_layout()

        self.user_selected()

    @property
    def active_plugins(self):
        return [name for name, ptype in self.owner.ctrl_be.server_active_plugins if ptype == "AUTHENTICATION"]

    def selected_plugin_type(self):
        if self.auth_type_list:
            return self.auth_type_list[max(self.auth_type_sel.get_selected_index(), 0)]
        return None

    def update_enable_state_for_auth_type(self, auth_type):
        info = AUTHENTICATION_PLUGIN_TYPES.get(auth_type)
        if not info:
            info = AUTHENTICATION_PLUGIN_TYPES["*"]

        if info:
            self.password.set_enabled(info["enable_password"])
            self.confirm.set_enabled(info["enable_password"])
            self.hostlimithost.set_enabled(info["enable_host"])

            if self.auth_string_param:
                self.auth_string_help.set_text(info["auth_string_label"])

                if auth_type is None:
                    self.auth_string_label.set_enabled(False)
                    self.auth_string_param.set_enabled(False)
                    for label in self.auth_type_password_labels:
                        label.set_enabled(True)
                else:
                    self.auth_string_label.set_enabled(True)
                    self.auth_string_param.set_enabled(True)
                    for label in self.auth_type_password_labels:
                        label.set_enabled(False)


    def set_hostlimithost(self, value):
        self.hostlimithost.set_value(value)
        self.validate_hostlimithost()


    def auth_type_changed(self):
        if not self.has_extra_plugins:
            return

        auth_type = self.selected_plugin_type()
        self.update_enable_state_for_auth_type(auth_type)

        info = AUTHENTICATION_PLUGIN_TYPES.get(auth_type)
        if not info:
            info = AUTHENTICATION_PLUGIN_TYPES["*"]

        if info:
            if not info["enable_password"]:
                self.password.set_value("")
                self.confirm.set_value("")

            if not info["enable_host"]:
                self.set_hostlimithost("%")

            if auth_type is None and self.auth_string_param:
                self.auth_string_param.set_value("")

        self.set_dirty()


    def role_list_toggled(self, row, col, value):
        if self._selected_user:
            self.role_list.set_int(row, col, int(value))

            role = self.role_list.get_string(row, 1)
            self._selected_user.toggle_role(role, value == "1")

            roles = self._selected_user.admin_roles
            for i in range(self.role_list.count()):
                self.role_list.set_bool(i, 0, self.role_list.get_string(i, 1) in roles)
            
            self.set_dirty()
            
            self.refresh_priv_list()
        
                
    def host_limit_clicked(self):
        self.hostlimithost.set_enabled(self.hostlimit.get_active())
        self.set_dirty()
        

    def user_selected(self):
        sel = self.user_list.get_selected()

        self._selected_user = None
        self._selected_user_original = None
        self.show_user(None)

        self.dup_button.set_enabled(False)
        self.del_button.set_enabled(False)
        
        self.refresh_priv_list()

        if sel >= 0:
            user, host = eval(self.user_list.get_row_tag(sel))
            self.account_label.set_text("Details for account %s@%s" % (user, host))

            user_info = self.owner.secman.async_get_account(self.show_user, user, host)
        else:
            self.account_label.set_text("Select an account to edit or click Add Account to create a new one")


    def show_user(self, user):
        sel = self.user_list.get_selected()
        if sel < 0 and user:
            return
        if user and eval(self.user_list.get_row_tag(sel))[0] != user.username:
            return

        self.content_box.set_enabled(user != None)
        self.revoke_all_button.set_enabled(user != None and user.is_commited)
        self.unset_dirty()

        self._selected_user = user
        self._selected_user_original = user and user.snapshot_for_revert()

        if user:
            self.dup_button.set_enabled(True)
            self.del_button.set_enabled(True)

            self.username.set_value(user.username)
            self.password.set_value("")
            self.confirm.set_value("")

            self.set_hostlimithost(user.host)
            
            if self.auth_type_list:
                try:
                    index = self.auth_type_list.index(user.auth_plugin or None)
                except ValueError, x:
                    mforms.Utilities.show_warning("Invalid Authentication Plugin", 
                              "User %s has plugin type %s, which is not listed as a known authentication plugin by the server." % (user.formatted_name(), user.auth_plugin), 
                              "OK", "", "")
                    return

                self.auth_type_sel.set_selected(index)
                # changing auth type not supported atm
                self.auth_type_sel.set_enabled(not user.is_commited)
                self.auth_string_param.set_value(user.auth_string or "")
                self.update_enable_state_for_auth_type(user.auth_plugin or None)

            self.max_questions.set_value(str(user.max_questions))
            self.max_updates.set_value(str(user.max_updates))
            self.max_connections.set_value(str(user.max_connections))
            self.max_uconnections.set_value(str(user.max_user_connections))
            
            roles = user.admin_roles
            for i in range(self.role_list.count()):
                self.role_list.set_bool(i, 0, self.role_list.get_string(i, 1) in roles)
            
            self.refresh_priv_list()
        else:
            self.username.set_value("")
            self.password.set_value("")
            self.confirm.set_value("")
            
            self.set_hostlimithost("")

            if self.auth_string_param:
                self.auth_string_param.set_value("")

            self.max_questions.set_value("")
            self.max_updates.set_value("")
            self.max_connections.set_value("")
            self.max_uconnections.set_value("")
            
            for i in range(self.role_list.count()):
                self.role_list.set_bool(i, 0, False)
    
    
    def add_account(self):
        account = self.owner.secman.create_account()
        self.refresh()
        self.user_list.set_selected(len(self.owner.secman.account_names)-1)
        self.user_selected()
        self.set_dirty()


    def dup_account(self):
        if self._selected_user:
            account = self.owner.secman.copy_account(self._selected_user)
            self.refresh()
            self.user_list.set_selected(len(self.owner.secman.account_names)-1)
            self.user_selected()


    def del_account(self):
        if self._selected_user:
            if not self._selected_user.is_commited or Utilities.show_message("Remove Account",
                  "The account '%s' will be permanently removed. Please confirm."%(self._selected_user.formatted_name()),
                  "Remove", "Cancel", "") == mforms.ResultOk:
                the_name = self._selected_user.formatted_name()
                self.owner.secman.delete_account(self._selected_user)
                self._selected_user = None
                self._selected_user_original = None
                self.refresh()
                self.user_selected()
                mforms.App.get().set_status_text("Account '%s' was deleted" % the_name)


    def refresh(self):
        selected_row = None
        
        su = self._selected_user
        suo = self._selected_user_original
        self.user_list.freeze_refresh()
        self.user_list.clear_rows()
        self._selected_user = su
        self._selected_user_original = suo
        for user, host in self.owner.secman.account_names:
            row = self.user_list.add_row()
            self.user_list.set_string(row, 0, user or "<anonymous>")
            self.user_list.set_string(row, 1, host)
            self.user_list.set_row_tag(row, repr((user, host)))
            if self._selected_user and (user == self._selected_user.username and host == self._selected_user.host):
                selected_row = row
        
        if selected_row is not None:
            self.user_list.set_selected(selected_row)
            self.user_selected()
        self.user_list.thaw_refresh()

    def refresh_priv_list(self):
        self.role_priv_list.freeze_refresh()
        self.role_priv_list.clear_rows()
        if self._selected_user:
            privs = self._selected_user.raw_privilege_names
            privs.sort()
            for priv in privs:
                row = self.role_priv_list.add_row()
                self.role_priv_list.set_string(row, 0, priv)
        self.role_priv_list.thaw_refresh()

    def validate_hostlimithost(self):
        host = self.hostlimithost.get_string_value()
        self.valid_name = False
        if len(host) <= 255:
            if host[-1:] == ".":
                host = host[:-1]
            allowed = re.compile("(?!-)[_%A-Z\d-]{1,63}(?<!-)$", re.IGNORECASE)
            self.valid_name = all(allowed.match(x) for x in host.split("."))

        if self.valid_name:
            #self.set_dirty()
            self.hostlimithost_valid_icon.show(False)
        else:
            #self.unset_dirty()
            self.hostlimithost_valid_icon.set_image("mini_error.png")
            self.hostlimithost_valid_icon.show()
            self.hostlimithost_valid_icon.set_tooltip("Host name contains incorrect characters")

    def set_dirty(self):
        self.save_button.set_enabled(True)
        self.revert_button.set_enabled(True)
        self.user_list.set_enabled(False)


    def unset_dirty(self):
        self.save_button.set_enabled(False)
        self.revert_button.set_enabled(False)
        self.user_list.set_enabled(True)
  
  
    def revoke_all(self):
        if self._selected_user:
            if Utilities.show_message("Revoke All Privileges", 
                  "Please confirm revokation of all privileges for the account '%s'@'%s'.\nNote: the account itself will be maintained."%(self._selected_user.username, self._selected_user.host),
                  "Revoke", "Cancel", "") == mforms.ResultOk:
                self._selected_user.revoke_all()
                self._selected_user.load(self._selected_user.username, self._selected_user.host)
                self.show_user(self._selected_user)


    def revert(self):
        if self._selected_user_original:
            self.show_user(self.owner.secman.revert_account(self._selected_user, self._selected_user_original))
        if not self._selected_user.is_commited:
            self.owner.secman.delete_account(self._selected_user)
        self.refresh()
    
    
    def commit(self):
        if self._selected_user:
            username = self.username.get_string_value()
            host = self.hostlimithost.get_string_value()
            
            is_new_user = not self._selected_user.is_commited
            
            password_unneeded = False
            if self.has_extra_plugins and not AUTHENTICATION_PLUGIN_TYPES[self.selected_plugin_type()]["enable_password"]:
                password_unneeded = True
            if is_new_user and not self.password.get_string_value() and not password_unneeded:
                if Utilities.show_warning("Save Account Changes",
                        "It is a security hazard to create an account with no password.\nPlease confirm creation of '%s'@'%s' with no password."%(username, host),
                        "Create", "Cancel", "") != mforms.ResultOk:
                    return

            self._selected_user.username = self.username.get_string_value()
            self._selected_user.password = self.password.get_string_value()
            self._selected_user.confirm_password = self.confirm.get_string_value()
            #if self.hostlimit.get_active():
            self._selected_user.host = self.hostlimithost.get_string_value()
           # else:
           #     self._selected_user.host = "%"

            self._selected_user.max_questions = int(self.max_questions.get_string_value())
            self._selected_user.max_updates = int(self.max_updates.get_string_value())
            self._selected_user.max_connections = int(self.max_connections.get_string_value())
            self._selected_user.max_user_connections = int(self.max_uconnections.get_string_value())

            if is_new_user and self.has_extra_plugins:
                self._selected_user.auth_plugin = self.selected_plugin_type()

            if self._selected_user.auth_plugin:
                self._selected_user.auth_string = self.auth_string_param.get_string_value()

            try:
                self._selected_user.save()
            except WBSecurityValidationError, exc:
                Utilities.show_error("Save Account Changes",
                      str(exc), "OK", "", "")
                return
            except PermissionDeniedError, exc:
                Utilities.show_error("Save Account Changes",
                      str(exc), "OK", "", "")
                return
            
            the_name = self._selected_user.formatted_name()
            
            self._selected_user.load(self._selected_user.username, self._selected_user.host)
            self.owner.refresh()
            
            if is_new_user:
                mforms.App.get().set_status_text("Created account '%s'" % the_name)
            else:
                mforms.App.get().set_status_text("Updated account '%s'" % the_name)

#############################


class SecuritySchemaPrivileges(mforms.Box):
    def __init__(self, owner):
        mforms.Box.__init__(self, True)
        self.set_managed()
        self.owner = owner
        
        self._selected_user = None
        self._selected_user_original = None
      
        self.suspend_layout()
        self.set_spacing(8)
        self.set_padding(8)
        
        schema_list_box = newBox(False)
        schema_list_box.set_spacing(8)
        schema_list_box.set_size(150, -1)
        self.add(schema_list_box, False, True)
    
        #searchbox = TextEntry(SearchEntry)
        #schema_list_box.add(searchbox, False, True)

        self.user_list = newTreeView(mforms.TreeDefault)
        self.user_list.add_column(mforms.StringColumnType, "Users", 140, False)
        self.user_list.end_columns()
        self.user_list.add_changed_callback(self.user_selected)
        self.user_list.set_allow_sorting(True)
        schema_list_box.add(self.user_list, True, True)

        self.schema_rights_checks = {}

        self.content_box = priv_vbox = newBox(False)
        priv_vbox.set_spacing(8)
        self.add(priv_vbox, True, True)
        
        priv_vbox.add(newLabel("Select a user and pick the privileges it has for a given Schema and Host combination."), False, True)
        
        self.privs_list = newTreeView(mforms.TreeDefault)
        self.privs_list.add_column(mforms.StringColumnType, "Host", 100, True)
        self.privs_list.add_column(mforms.StringColumnType, "Schema", 100, True)
        self.privs_list.add_column(mforms.StringColumnType, "Privileges", 800, False)
        self.privs_list.end_columns()
        self.privs_list.add_changed_callback(self.schema_priv_selected)

        priv_vbox.add(self.privs_list, True, True)
        
        bbox = newBox(True)
        bbox.set_spacing(8)

        bbox.add(dLabel("Schema and Host fields may use % and _ wildcards. The server will match specific entries before wildcarded ones."), False, True)

        self.add_entry_button = newButton()
        self.add_entry_button.set_text("Add Entry...")
        bbox.add_end(self.add_entry_button, False, True)        
        self.add_entry_button.add_clicked_callback(self.add_entry)
        
        self.del_entry_button = newButton()
        self.del_entry_button.set_text("Delete Entry")
        bbox.add_end(self.del_entry_button, False, True)
        self.del_entry_button.add_clicked_callback(self.del_entry)
    
        priv_vbox.add(bbox, False, True)

        self.schema_priv_label = newLabel("")
        priv_vbox.add(self.schema_priv_label, False, True)

        hbox = newBox(True)
        hbox.set_homogeneous(True)
        hbox.set_spacing(8)
        priv_vbox.add(hbox, False, True)

        self.schema_object_privs_panel = panel = newPanel(mforms.TitledBoxPanel)
        panel.set_title("Object Rights")
        box = newBox(False)
        box.set_padding(8)
        for name in SCHEMA_OBJECT_RIGHTS:
            cb = newCheckBox()
            label, desc = PrivilegeInfo.get(name, ("", None))
            cb.set_text(label)
            if desc:
                cb.set_tooltip(desc)
            cb.add_clicked_callback(self.schema_priv_checked)
            box.add(cb, False, False)
            self.schema_rights_checks[name] = cb
        panel.add(box)        
        hbox.add(panel, False, True)

        self.schema_ddl_privs_panel = panel = newPanel(mforms.TitledBoxPanel)
        panel.set_title("DDL Rights")
        box = newBox(False)
        box.set_padding(8)
        for name in SCHEMA_DDL_RIGHTS:
            cb = newCheckBox()
            label, desc = PrivilegeInfo.get(name, ("", None))
            cb.set_text(label)
            if desc:
                cb.set_tooltip(desc)
            cb.add_clicked_callback(self.schema_priv_checked)
            box.add(cb, False, False)
            self.schema_rights_checks[name] = cb
        panel.add(box)
        hbox.add(panel, False, True)

        self.schema_other_privs_panel = panel = newPanel(mforms.TitledBoxPanel)
        panel.set_title("Other Rights")
        box = newBox(False)
        box.set_padding(8)
        for name in SCHEMA_OTHER_RIGHTS:
            cb = newCheckBox()
            label, desc = PrivilegeInfo.get(name, ("", None))
            cb.set_text(label)
            if desc:
                cb.set_tooltip(desc)
            cb.add_clicked_callback(self.schema_priv_checked)
            box.add(cb, False, False)
            self.schema_rights_checks[name] = cb
        panel.add(box)
        hbox.add(panel, False, True)


        bottom_box = newBox(True)
        bottom_box.set_spacing(8)

        if 0:
            img = newImageBox()
            if App.get().get_resource_path("task_warning_mac.png"):
                img.set_image("task_warning_mac.png")
            else:
                img.set_image("task_warning.png")
            bottom_box.add(img, False, True)
            bottom_box.add(dLabel("There are %i schema privilege entries for accounts that don't exist"), False, True)
            purge = newButton()
            purge.set_text("Purge")
            bottom_box.add(purge, False, True)


        self.grant_all = newButton()
        self.grant_all.set_text('Select "ALL"')
        bottom_box.add(self.grant_all, False, True)
        self.grant_all.add_clicked_callback(self.grant_all_schema_privs)

        self.revoke_all = newButton()
        self.revoke_all.set_text("Unselect All")
        bottom_box.add(self.revoke_all, False, True)
        self.revoke_all.add_clicked_callback(self.revoke_all_schema_privs)

        self.save_button = newButton()
        self.save_button.set_text("Save Changes")
        bottom_box.add_end(self.save_button, False, True)        
        self.save_button.add_clicked_callback(self.commit)
                
        self.revert_button = newButton()
        self.revert_button.set_text("Revert")
        bottom_box.add_end(self.revert_button, False, True)
        self.revert_button.add_clicked_callback(self.revert)
    
        priv_vbox.add(bottom_box, False, True)

        self.resume_layout()


    ####

    def set_dirty(self):
        self.save_button.set_enabled(True)
        self.revert_button.set_enabled(True)
        self.user_list.set_enabled(False)


    def unset_dirty(self):
        self.save_button.set_enabled(False)
        self.revert_button.set_enabled(False)
        self.user_list.set_enabled(True)


    def schema_priv_checked(self):
        privs = []
        for name, cb in self.schema_rights_checks.iteritems():
            if cb.get_active():
                privs.append(name)
        sel = self.privs_list.get_selected()
        if sel >= 0:
            self._selected_user.entries[sel].privileges = set(privs)
            
            plist = [PrivilegeInfo.get(p, " ")[0] for p in privs]
            plist.sort()
            self.privs_list.set_string(sel, 2, ", ".join(plist) or "none")
        self.set_dirty()


    def add_entry(self):
        if not self._selected_user:
            return
        addform = AddSchemaPrivilegeForm(self.owner.secman, self._selected_user.username)

        host, schema = addform.run()
        if host is not None and schema is not None:
            entry = self._selected_user.add_entry(host, schema, set())

            self.refresh_entry_list(self._selected_user)
            self.show_privileges(entry)

            self.privs_list.set_selected(len(self._selected_user.entries)-1)
            self.schema_priv_selected()

            self.set_dirty()
  

    def del_entry(self):
        sel = self.privs_list.get_selected()
        if sel < 0:
            return
        del self._selected_user.entries[sel]
        self.privs_list.delete_row(sel)
        self.schema_priv_selected()
        self.set_dirty()



    def user_selected(self):
        sel = self.user_list.get_selected()

        self._selected_user = None
        self._selected_user_original = None
        self.show_user(None)

        self.add_entry_button.set_enabled(False)
        self.add_entry_button.set_enabled(False)
        
        self.show_privileges(None)

        if sel >= 0:
            user = self.user_list.get_row_tag(sel)
            self.owner.secman.async_get_user_schema_privs(self.show_user, user)


    def schema_priv_selected(self):
        sel = self.privs_list.get_selected()
        if sel < 0 or not self._selected_user:
            self.show_privileges(None)
        else:
            entry = self._selected_user.entries[sel]
            self.show_privileges(entry)


    def grant_all_schema_privs(self):
        for name, cb in self.schema_rights_checks.iteritems():
            if name != "Grant_priv":
                cb.set_active(True)
            else:
                cb.set_active(False)
        self.schema_priv_checked()
        self.set_dirty()


    def revoke_all_schema_privs(self):
        for cb in self.schema_rights_checks.itervalues():
            cb.set_active(False)
        self.schema_priv_checked()
        self.set_dirty()


    def show_user(self, user):
        # make sure that the info is not outdated
        sel = self.user_list.get_selected()
        if sel < 0 and user:
            return
        if user and user.username != self.user_list.get_row_tag(sel):
            return

        self._selected_user = user
        self._selected_user_original = user and user.snapshot_for_revert()

        self.content_box.set_enabled(user != None)

        self.unset_dirty()
    
        self.refresh_entry_list(user)

        if user is not None:
            self.add_entry_button.set_enabled(True)
            self.del_entry_button.set_enabled(False)            

        self.show_privileges(None)
    
    
    def refresh_entry_list(self, user):
        self.privs_list.clear_rows()
        for entry in user and user.entries or []:
            row = self.privs_list.add_row()
            self.privs_list.set_string(row, 0, entry.host)
            self.privs_list.set_string(row, 1, entry.db)
            plist = [PrivilegeInfo.get(p, " ")[0] for p in entry.privileges]
            plist.sort()
            self.privs_list.set_string(row, 2, ", ".join(plist) or "none")

    
    
    def show_privileges(self, entry):
        self.schema_object_privs_panel.set_enabled(entry != None)
        self.schema_ddl_privs_panel.set_enabled(entry != None)
        self.schema_other_privs_panel.set_enabled(entry != None)

        if entry:
            db, host, privs = entry.db, entry.host, entry.privileges

            text = "The user '%s', " % self._selected_user.username
            if '_' in host or '%' in host:
                if host == '%':
                    text += "when connecting from any host, "
                else:
                    text += "when connecting from hosts matching '%s', " % host
            else:
                text += "when connecting from the host '%s', " % host
            if '_' in db or '%' in db:
                if db == '%':
                    text += "will have the following access rights to any schemas':"
                else:
                    text += "will have the following access rights to schemas matching '%s':" % db
            else:
                text += "will have the following access rights to the schema '%s':" % db
            self.schema_priv_label.set_text(text)
        
            self.del_entry_button.set_enabled(True)

            self.grant_all.set_enabled(True)
            self.revoke_all.set_enabled(True)

            for priv, check in self.schema_rights_checks.iteritems():
                check.set_active(priv in privs)
        else:
            self.schema_priv_label.set_text("")
            self.del_entry_button.set_enabled(False)

            self.grant_all.set_enabled(False)
            self.revoke_all.set_enabled(False)

            for priv, check in self.schema_rights_checks.iteritems():
                check.set_active(False)


    def refresh(self):
        self.user_list.clear_rows()
        for user in set([a[0] for a in self.owner.secman.account_names]):
            row = self.user_list.add_row()
            self.user_list.set_string(row, 0, user or "<anonymous>")
            self.user_list.set_row_tag(row, user)

        self.show_user(None)


    def revert(self):
        if self._selected_user_original:
            self.show_user(self.owner.secman.revert_user_schema_privs(self._selected_user, self._selected_user_original))


    def commit(self):
        if self._selected_user:       
            try:
                self._selected_user.save()
            except PermissionDeniedError, exc:
                Utilities.show_error("Save Account Changes",
                      str(exc), "OK", "", "")
                return
            self.unset_dirty()




class WbAdminSecurity(mforms.Box):
    _schema_priv_entries = []
    ui_created = False

    def __init__(self, ctrl_be, server_profile, main_view):
        mforms.Box.__init__(self, False)
        main_view.ui_profile.apply_style(self, 'page')
        self.set_managed()
        self.ctrl_be = ctrl_be
        self.secman  = None
        self.main_view = main_view
        self.main_view.add_content_page(self, "SECURITY", "Users and Privileges", "admin_manage_privs_win")


    def create_ui(self):
        self.suspend_layout()

        self.warning = not_running_warning_label()
        self.add(self.warning, False, True)

        self.tabview = newTabView(False)
        self.add(self.tabview, True, True)
    
        self.account_tab = SecurityAccount(self)
        self.tabview.add_page(self.account_tab, "Server Access Management")

        self.schema_privs_tab = SecuritySchemaPrivileges(self)
        self.tabview.add_page(self.schema_privs_tab, "Schema Privileges")
        
        self.resume_layout()


    def update_ui(self):
        if self.ctrl_be.is_sql_connected():
            self.secman = AdminSecurity(self.ctrl_be)

            self.warning.show(False)
            self.tabview.show(True)
        else:
            self.secman = None

            self.warning.show(True)
            self.tabview.show(False)



    def page_activated(self):
        self.main_view.set_content_label(" Users and Privileges")
        if not self.ui_created:
            self.create_ui()
            self.ui_created = True
        self.update_ui()
        self.refresh()

      
    def refresh(self):
        if self.ctrl_be.is_sql_connected():
            try:
                self.secman.async_refresh(self.do_refresh)
            except PermissionDeniedError, e:
                Utilities.show_error("Access Denied", str(e), "OK", "", "")



    def do_refresh(self):
        self.account_tab.refresh()

        self.schema_privs_tab.refresh()

