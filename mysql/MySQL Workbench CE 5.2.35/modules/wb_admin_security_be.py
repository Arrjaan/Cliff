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

import grt
from grt import modules
from db_utils import QueryError, escape_sql_string
from wb_common import dprint_ex, PermissionDeniedError
from grt import modules;

import hashlib
def make_scrambled_password(pwd):
    ret = hashlib.sha1(pwd).digest()
    ret = hashlib.sha1(ret).hexdigest()
    return "*" + ret.upper()


class WBSecurityValidationError(Exception):
    pass


LIST_ACCOUNTS_QUERY = "SELECT User, Host FROM mysql.user ORDER BY User"
LIST_SCHEMAS_QUERY = "SHOW DATABASES"

GET_ACCOUNT_QUERY = "SELECT * FROM mysql.user WHERE User='%(user)s' AND Host='%(host)s'"

GET_ACCOUNT_SCHEMA_PRIVS_QUERY = "SELECT * FROM mysql.db WHERE User='%(user)s'"

GET_ACCOUNT_MYSQL_TABLE_PRIVS_QUERY = "SELECT * FROM mysql.tables_priv WHERE Host='%(host)s' AND User='%(user)s' AND Db='mysql'"
#GET_ACCOUNT_IS_TABLE_PRIVS_QUERY = "SELECT * FROM mysql.tables_priv WHERE Host='%(host)s' AND User='%(user)s' AND Db='information_schema'"

UPDATE_ACCOUNT_QUERY = "UPDATE mysql.user SET %(assignments)s WHERE User='%(old_user)s' AND Host='%(old_host)s'"
CREATE_USER_QUERY = "CREATE USER '%(user)s'@'%(host)s' identified by password '%(password)s'"
CREATE_USER_QUERY_PLUGIN = "CREATE USER '%(user)s' IDENTIFIED WITH '%(auth_plugin)s' AS '%(auth_string)s'"
#INSERT_ACCOUNT_QUERY = "INSERT INTO mysql.user (User, Host, Password, %(field_names)s) VALUES ('%(user)s', '%(host)s', PASSWORD('%(password)s'), %(field_values)s)"
#INSERT_ACCOUNT_QUERY_NO_PASSWORD = "INSERT INTO mysql.user (User, Host, Password, %(field_names)s) VALUES ('%(user)s', '%(host)s', '', %(field_values)s)"

DELETE_SCHEMA_PRIV = "DELETE FROM mysql.db WHERE User='%(user)s'"
INSERT_SCHEMA_PRIV = "INSERT INTO mysql.db (User, Host, Db, %(priv_names)s) VALUES ('%(user)s', '%(host)s', '%(db)s', %(priv_values)s)"

FLUSH_PRIVILEGES = "FLUSH PRIVILEGES"

REVOKE_ALL = "REVOKE ALL PRIVILEGES, GRANT OPTION FROM '%(user)s'@'%(host)s'"
REMOVE_USER = "DROP USER '%(user)s'@'%(host)s'"

PrivilegeInfo = {
"Select_priv": ("SELECT", "The SELECT privilege enables you to select rows from tables in a database.\nSELECT statements require the SELECT privilege only if they actually retrieve rows from a table. Some SELECT statements do not access tables and can be executed without permission for any database"),
"Insert_priv": ("INSERT", "The INSERT privilege enables rows to be inserted into tables in a database.\nINSERT is also required for the ANALYZE TABLE, OPTIMIZE TABLE, and REPAIR TABLE table-maintenance statements."),
"Update_priv": ("UPDATE", "The UPDATE privilege enables rows to be updated in tables in a database."),
"Delete_priv": ("DELETE", "The DELETE privilege enables rows to be deleted from tables in a database."),
"Create_priv": ("CREATE", "The CREATE privilege enables creation of new databases and tables."),
"Drop_priv": ("DROP", """The DROP privilege enables you to drop (remove) existing databases, tables, and views.
Beginning with MySQL 5.1.10, the DROP privilege is also required in order to use the statement ALTER TABLE ... DROP PARTITION on a partitioned table.
Beginning with MySQL 5.1.16, the DROP privilege is required for TRUNCATE TABLE (before that, TRUNCATE TABLE requires the DELETE privilege).
If you grant the DROP privilege for the mysql database to a user, that user can drop the database in which the MySQL access privileges are stored."""),
"Reload_priv": ("RELOAD", "The RELOAD privilege enables use of the FLUSH statement.\nIt also enables mysqladmin commands that are equivalent to FLUSH operations:\nflush-hosts, flush-logs, flush-privileges, flush-status, flush-tables, flush-threads, refresh, and reload."),
"Event_priv": ("EVENT", "The EVENT privilege is required to create, alter, or drop events for the Event Scheduler. This privilege was added in MySQL 5.1.6."),
"Shutdown_priv": ("SHUTDOWN", "The SHUTDOWN privilege enables use of the mysqladmin shutdown command. There is no corresponding SQL statement."),
"Process_priv": ("PROCESS", "The PROCESS privilege pertains to display of information about the threads executing within the server\n(that is, information about the statements being executed by sessions).\nThe privilege enables use of SHOW PROCESSLIST or mysqladmin processlist to see threads belonging to other accounts; you can always see your own threads."),
"File_priv": ("FILE", """The FILE privilege gives you permission to read and write files on the server host using the 
LOAD DATA INFILE and SELECT ... INTO OUTFILE statements and the LOAD_FILE() function. A user who has the FILE privilege
can read any file on the server host that is either world-readable or readable by the MySQL server. 
(This implies the user can read any file in any database directory, because the server can access any of those files.) 
The FILE privilege also enables the user to create new files in any directory where the MySQL server has write access.
As a security measure, the server will not overwrite existing files."""),
"Grant_priv": ("GRANT OPTION", "The GRANT OPTION privilege enables you to give to other users or remove from other users those privileges that you yourself possess."),
"References_priv": ("REFERENCES", "The REFERENCES privilege currently is unused."),
"Index_priv": ("INDEX", "The INDEX privilege enables you to create or drop (remove) indexes.\nINDEX applies to existing tables. If you have the CREATE privilege for a table, you can include index definitions in the CREATE TABLE statement."),
"Alter_priv": ("ALTER", "The ALTER privilege enables use of ALTER TABLE to change the structure of or rename tables.\n(ALTER TABLE also requires the INSERT and CREATE privileges.)"),
"Show_db_priv": ("SHOW DATABASES", """The SHOW DATABASES privilege enables the account to see database names by issuing the
SHOW DATABASE statement. Accounts that do not have this privilege see only databases for which
they have some privileges, and cannot use the statement at all if the server was started with
the --skip-show-database option. Note that any global privilege is a privilege for the database."""),
"Trigger_priv": ("TRIGGER", "The TRIGGER privilege enables you to create and drop triggers.\nYou must have this privilege for a table to create or drop triggers for that table. This privilege was added in MySQL 5.1.6. (Prior to MySQL 5.1.6, trigger operations required the SUPER privilege.)"),
"Super_priv": ("SUPER", """The SUPER privilege enables an account to use CHANGE MASTER TO, KILL or
mysqladmin kill to kill threads belonging to other accounts (you can always kill your own threads),
PURGE BINARY LOGS, configuration changes via SET GLOBAL to modify global system variables, 
the mysqladmin debug command, enabling or disabling logging, performing updates even if the read_only
system variable is enabled, starting and stopping replication on slave servers, and allows you to
connect (once) even if the connection limit controlled by the max_connections system variable is reached."""),
"Create_tmp_table_priv": ("CREATE TEMPORARY TABLES", "The CREATE TEMPORARY TABLES privilege enables the use of the keyword TEMPORARY in CREATE TABLE statements."),
"Lock_tables_priv": ("LOCK TABLES", "The LOCK TABLES privilege enables the use of explicit LOCK TABLES statements to lock tables for which you have the SELECT privilege.\nThis includes the use of write locks, which prevents other sessions from reading the locked table."),
"Execute_priv": ("EXECUTE", "The EXECUTE privilege is required to execute stored routines (procedures and functions)."),
"Repl_slave_priv": ("REPLICATION SLAVE", "The REPLICATION SLAVE privilege should be granted to accounts that are used\nby slave servers to connect to the current server as their master.\nWithout this privilege, the slave cannot request updates that have been made to databases on the master server."),
"Repl_client_priv": ("REPLICATION CLIENT", "The REPLICATION CLIENT privilege enables the use of SHOW MASTER STATUS and SHOW SLAVE STATUS"),
"Create_view_priv": ("CREATE VIEW", "The CREATE VIEW privilege enables use of CREATE VIEW."),
"Show_view_priv": ("SHOW VIEW", "The SHOW VIEW privilege enables use of SHOW CREATE VIEW."),
"Create_routine_priv": ("CREATE ROUTINE", "The CREATE ROUTINE privilege is needed to create stored routines (procedures and functions)."),
"Alter_routine_priv": ("ALTER ROUTINE", "The ALTER ROUTINE privilege is needed to alter or drop stored routines (procedures and functions)."),
"Create_user_priv": ("CREATE USER", "The CREATE USER privilege enables use of CREATE USER, DROP USER, RENAME USER, and REVOKE ALL PRIVILEGES."),
"Create_tablespace_priv": ("CREATE TABLESPACE", "The CREATE TABLESPACE privilege is needed to create, alter, or drop tablespaces and log file groups."),

# custom stuff
#"IS_monitor_attr" : ("* INFO SCHEMA monitoring", ""),
"Routine_manage_attr" : ("* Modify Routines", ""),
#"IS_read_all_attr" : ("* SELECT access to INFO SCHEMA", ""),
"User_manage_attr" : ("* Modify Access Control", ""),
#"IS_monitor_innodb_attr" : ("* InnoDB monitoring in INFO SCHEMA", "")
}


## Special Tables

# information_schema tables are free for all to see

AdminAttributes = {
#             Db, Tables, Db Privileges
#"IS_monitor_attr" : ("information_schema", 
#              ["statistics", "engines", "plugins", "partitions", "files", "processlist", "global_status",
#              "session_status", "global_variables", "session_variables", "profiling"], 
#              ["Select_priv"],  None, None),
"Routine_manage_attr" : ("mysql",
              ["proc", "func", "event"],
              ["Insert", "Select", "Update", "Delete"],
              "GRANT INSERT, SELECT, UPDATE, DELETE ON TABLE mysql.%(table)s TO '%(user)s'@'%(host)s'",
              "REVOKE INSERT, SELECT, UPDATE, DELETE ON TABLE mysql.%(table)s FROM '%(user)s'@'%(host)s'"),
#"IS_read_all_attr" : ("information_schema", 
#              ["*"], 
#              ["Select_priv"]),
"User_manage_attr" : ("mysql", 
              ["columns_priv", "db", "host", "procs_priv", "tables_priv", "user"],
              ["Select", "Insert", "Update", "Delete"],
              "GRANT INSERT, SELECT, UPDATE, DELETE ON TABLE mysql.%(table)s TO '%(user)s'@'%(host)s'",
              "REVOKE INSERT, SELECT, UPDATE, DELETE ON TABLE mysql.%(table)s FROM '%(user)s'@'%(host)s'"),
#"IS_monitor_innodb_attr" : ("information_schema", 
#              [],  # InnoDB_* (5.4+ only)
#              ["Select_priv"]),
}


# Administrative Roles available for selection. Add your custom roles here.
# Format is ("NameOfTheRole", "description", [list,of,privileges]) 
# For a list of available privileges, look at the mysql.user table
SecurityAdminRoles = [
("DBA", "grants the rights to perform all tasks", 
    PrivilegeInfo.keys()),
("MaintenanceAdmin", "grants rights needed to maintain server", 
    ["Event_priv", "Reload_priv", "Show_db_priv", "Shutdown_priv", "Super_priv"]), # , "IS_monitor_attr" File_priv?
("ProcessAdmin", "rights needed to assess, monitor, and kill any user process running in server",
    ["Reload_priv", "Super_priv"]),#, "IS_monitor_attr"
("UserAdmin", "grants rights to create users logins and reset passwords", 
    ["Create_user_priv", "Reload_priv"]),
("SecurityAdmin", "rights to manage logins and grant and revoke server and database level permission", 
    ["Grant_priv", "Create_user_priv", "Reload_priv", "Show_db_priv", "User_manage_attr"]),
("MonitorAdmin", "minimum set of rights needed to monitor server", 
    ["Process_priv"]), #"IS_monitor_attr", "IS_monitor_innodb_attr"
("DBManager", "grants full rights on all databases",
    ["Create_priv", "Drop_priv", "Grant_priv", "Event_priv", "Alter_priv", "Delete_priv", 
    "Index_priv", "Insert_priv", "Select_priv", "Update_priv", "Create_tmp_table_priv", "Lock_tables_priv",
    "Trigger_priv", "Create_view_priv", "Show_view_priv", "Create_routine_priv", "Alter_routine_priv", "Show_db_priv"]),
("DBDesigner", "rights to create and reverse engineer any dabase schema", 
    ["Create_priv", "Alter_priv", "Index_priv", "Trigger_priv", "Create_view_priv",
    "Show_view_priv", "Create_routine_priv", "Alter_routine_priv", "Show_db_priv", "Routine_manage_attr"]),#, "IS_read_all_attr"
("ReplicationAdmin", "rights needed to setup and manage replication", 
    ["Repl_client_priv", "Repl_slave_priv", "Super_priv"]),
("BackupAdmin", "minimal rights needed to backup any database", 
    ["Event_priv", "Select_priv", "Lock_tables_priv", "Show_db_priv"])
]



# for sorting tuples containing host, db, user entries in the same order as the server
def get_acl_sort(tup):
    order = 0

    wild_pos = 0
    chars = 0
    for t in tup:
        if type(t) is not str:
            continue
        for i in range(len(t)):
            c = t[i]
            if c == "\\":
                pass
            elif c == "%" or c == "_":
                wild_pos = i
                break
            chars = 128
        order = (order << 8) + (wild_pos and min(wild_pos, 127) or chars)
    return order


def acl_compare(t1, t2):
    return get_acl_sort(t1) - get_acl_sort(t2)


class AdminSecurity:
    def __init__(self, ctrl_be):
        self.ctrl_be = ctrl_be
        self._accounts = []
        self._schema_names = []
        self._account_info_cache = {}
        self._schema_privileges_cache = {}

        self.has_plugin = False
        self.has_authentication_string = False
        self.has_max_user_connections = False
        self.schema_privilege_names = []
        self.global_privilege_names = []
        self.user_table_fields = []


    def get_valid_privileges(self):
        # self.global_privilege_names - column names from user table
        # PrivilegeInfo: map of user table's column name to privilege and its description
        privs = []
        for name in self.global_privilege_names:
            (priv, desc) = PrivilegeInfo.get(name, (None, None))
            if priv:
                privs.append(priv)

        return privs

    def async_refresh(self, callback):
        # get list of privileges that actually exist
        if not self.schema_privilege_names:
            try:
              result = self.ctrl_be.exec_query("DESCRIBE mysql.db")
            except QueryError, e:
              if e.error == 1142:
                raise PermissionDeniedError("Please make sure the used account has rights to the MySQL grant tables.\n%s"%e)
              raise e

            if result is not None:
              while result.nextRow():
                field= result.stringByName("Field")
                if field.endswith("_priv"):
                  self.schema_privilege_names.append(field)

        if not self.user_table_fields:
            try:
              result = self.ctrl_be.exec_query("DESCRIBE mysql.user")
            except QueryError, e:
              if e.error == 1142:
                raise PermissionDeniedError("Please make sure the used account has rights to the MySQL grant tables.\n%s"%e)
              raise e

            if result is not None:
              while result.nextRow():
                field= result.stringByName("Field")
                self.user_table_fields.append(field)
                if field.endswith("_priv"):
                  self.global_privilege_names.append(field)
                if field == "max_user_connections":
                  self.has_max_user_connections = True
                if field == "plugin":
                  self.has_plugin = True
                if field == "authentication_string":
                  self.has_authentication_string = True

        # get list of schema names
        schema_names = []
        try:
          result = self.ctrl_be.exec_query(LIST_SCHEMAS_QUERY)
        except QueryError, e:
          if e.error == 1142:
            raise PermissionDeniedError("Please make sure the used account has rights to the MySQL grant tables.\n%s"%e)
          raise e
        except Exception, e:
          raise Exception("Error querying security information: %s" % e)

        if result is not None:
          while result.nextRow():
            name = result.stringByName("Database")
            schema_names.append(name)

        schema_names.sort()
        self._schema_names = schema_names

        # get list of account names from User table
        accounts = []
        try:
          result = self.ctrl_be.exec_query(LIST_ACCOUNTS_QUERY)
        except Exception, e:
          raise Exception("Error querying security information: %s" % e)

        if result:
          while result.nextRow():
            user = result.stringByName("User")
            host = result.stringByName("Host")
            accounts.append((user, host))

        # Sort list of accounts by User and Host
        # User is sorted alphabetically, Host is sorted by specificity in addition to alpha
        # (most specific items first)

        accounts.sort(acl_compare)

        self._accounts = accounts
        self._account_info_cache = {}
        self._schema_privileges_by_user = {}

        callback()

    
    @property
    def schema_names(self):
        return self._schema_names

    @property
    def account_names(self):
        return self._accounts


    def delete_account(self, acct):
        if acct.is_commited:
            query = REMOVE_USER % {"user":escape_sql_string(acct.username), "host":escape_sql_string(acct.host)}
            self.ctrl_be.exec_sql(query)

            self.ctrl_be.exec_sql(FLUSH_PRIVILEGES)
    
        del self._account_info_cache[acct.username+"@"+acct.host]
        self._accounts.remove((acct.username, acct.host))


    def revert_account(self, account, backup):
        i = self._accounts.index((account.username, account.host))
        self._accounts[i] = ((backup.username, backup.host))
        del self._account_info_cache[account.username+"@"+account.host]
        self._account_info_cache[backup.username+"@"+backup.host] = backup
        
        return backup


    def copy_account(self, account):
        copy = account.copy()
        copy.is_commited = False
        self._account_info_cache[copy.username+"@"+copy.host] = copy
        self._accounts.append((copy.username, copy.host))
        return copy


    def create_account(self):
        acct = AdminAccount(self)
        acct.username = "newuser"
        acct.host = "%"
        self._account_info_cache[acct.username+"@"+acct.host] = acct
        self._accounts.append((acct.username, acct.host))
        return acct


    def async_get_account(self, callback, name, host):
        key = name+"@"+host

        if self._account_info_cache.has_key(key):
            callback(self._account_info_cache[key])
            return
        
        account = AdminAccount(self)
        account.load(name, host)

        self._account_info_cache[key] = account
  
        callback(account)



    def revert_user_schema_privs(self, privs, backup):
        del self._schema_privileges_cache[privs.username]
        self._schema_privileges_cache[backup.username] = backup
        
        return backup


    def async_get_user_schema_privs(self, callback, user):
        if self._schema_privileges_cache.has_key(user):
            callback(self._schema_privileges_cache[user])
            return

        privileges = AdminUserDbPrivs(self)
        privileges.load(user)
        
        self._schema_privileges_cache[user] = privileges
        
        callback(privileges)
    




class AdminUserDbPrivEntry:
    host = None
    db = None
    privileges = set()
    
    def __init__(self, host, db, privileges):
        assert type(privileges) == set
        self.host = host
        self.db = db
        self.privileges = privileges


    def copy(self):
        return AdminUserDbPrivEntry(self.host, self.db, self.privileges.copy())
    



class AdminUserDbPrivs:
    _owner = None
    username = None    
    entries = []
    _orig_entries = []

    def __init__(self, owner):
        self._owner = owner


    def copy(self):
        copy = AdminUserDbPrivs(self._owner)
        
        copy.username = self.username
        copy.entries = [e.copy() for e in self.entries]
        
        return copy

    def snapshot_for_revert(self):
        copy = self.copy()
        copy._orig_entries = self._orig_entries[:]
        return copy


    def add_entry(self, host, db, privileges):
        entry = AdminUserDbPrivEntry(host, db, privileges)
        self.entries.append(entry)
        return entry


    def load(self, username):
        # Schema privileges from Db table
        query = GET_ACCOUNT_SCHEMA_PRIVS_QUERY % {"user": escape_sql_string(username)}
        try:
            result = self._owner.ctrl_be.exec_query(query)
        except Exception, e:
            raise Exception("Error querying security information: %s" % e)

        self.username = username

        self.entries = []

        while result.nextRow():
            privs = set()
            for priv in self._owner.schema_privilege_names:
                value = result.stringByName(priv)
                if value == 'Y':
                    privs.add(priv)

            schema = result.stringByName("Db")
            host = result.stringByName("Host")
            
            self.entries.append(AdminUserDbPrivEntry(host, schema, privs))

        self.entries.sort(lambda a, b: acl_compare((a.host, a.db), (b.host, b.db)))
        self._orig_entries = [e.copy() for e in self.entries]

    
    def save(self):
        ##XXX begin transaction

        self._owner.ctrl_be.exec_sql(DELETE_SCHEMA_PRIV % {"user":escape_sql_string(self.username) if self.username else self.username})
        
        for entry in self.entries:
            fields = {"user":escape_sql_string(self.username), "host":entry.host, "db":entry.db}
            priv_names = []
            priv_values = []
            for priv in self._owner.schema_privilege_names:
                priv_names.append("%s" % priv)
                if priv in entry.privileges:
                  priv_values.append("'Y'")
                else:
                  priv_values.append("'N'")
                #priv_values.append("'Y'" if priv in entry.privileges else "'N'")
            fields["priv_names"] = ", ".join(priv_names)
            fields["priv_values"] = ", ".join(priv_values)
            self._owner.ctrl_be.exec_sql(INSERT_SCHEMA_PRIV % fields)
        
        ##XXX commit transaction

        self._owner.ctrl_be.exec_sql(FLUSH_PRIVILEGES)



class AdminAccount:
    _owner = None
    
    _orig_username = None
    _orig_host = None
    _orig_password = None
    _orig_auth_string = None
    username = None
    password = None
    confirm_password = None
    host = None
    
    max_questions = 0
    max_updates = 0
    max_connections = 0
    max_user_connections = 0
    auth_plugin = None
    auth_string = None
    
    _global_privs = set()
    _orig_global_privs = set()

    is_commited = False # False means that account was not pushed to mysql server
    
    def __init__(self, owner):
        self._owner = owner

    def formatted_name(self):
        if self.host is not None:
            return "%s@%s" % (self.username, self.host)
        else:
            return self.username

    def copy(self):
        copy = AdminAccount(self._owner)
        copy.username = self.username
        copy.password = None
        copy.confirm_password = None
        copy.host = self.host
        copy.max_questions = self.max_questions
        copy.max_updates = self.max_updates
        copy.max_connections = self.max_connections
        copy.max_user_connections = self.max_user_connections
        copy.auth_plugin = self.auth_plugin
        copy.auth_string = self.auth_string
        copy.is_commited = self.is_commited
        copy._global_privs = self._global_privs.copy()
        return copy
    
    def snapshot_for_revert(self):
        copy = self.copy()
        copy._orig_username = self._orig_username
        copy._orig_password = self._orig_password
        copy._orig_auth_string = self._orig_auth_string
        copy._orig_host = self._orig_host
        return copy

    def toggle_role(self, role, flag):
        def privs_for_role(role):
            for rname, rdesc, rprivs in SecurityAdminRoles:
                if rname == role:
                    return rprivs
            return []

        privs = privs_for_role(role)
        if privs:
            if flag:
                self._global_privs = self._global_privs.union(set(privs))
            else:
                self._global_privs = self._global_privs.difference(set(privs))

            # check what roles are left and then reapply them so that there are no leftover privs
            admin_roles = self.admin_roles
            self._global_privs = set()
            for role in admin_roles:
                self._global_privs = self._global_privs.union(set(privs_for_role(role)))


    @property
    def admin_roles(self):
        roles = []
        for rname, rdesc, rprivs in SecurityAdminRoles:
            if set(rprivs).issubset(self._global_privs):
                roles.append(rname)

        return roles


    @property
    def raw_privilege_names(self):
        return [PrivilegeInfo.get(p, [p])[0] for p in self._global_privs]


    def revoke_all(self):
        command = REVOKE_ALL % {"user":escape_sql_string(self.username),"host":self.host}
        self._owner.ctrl_be.exec_sql(command)


    def save(self):
        if self.password != self.confirm_password:
            raise WBSecurityValidationError("The new password and its confirmation don't match. Please re-enter them.")

        #if not self.username:
        #    raise WBSecurityValidationError("Username must not be blank")

        if not self.host:
            raise WBSecurityValidationError("Host name must not be blank")

        # check if username + host is duplicated
        if self.is_commited and (self.username != self._orig_username or self.host != self._orig_host):
            if (self.username, self.host) in self._owner.account_names:
                raise WBSecurityValidationError("The '%s' account already exists and cannot be saved." % (self.formatted_name()))
        elif not self.is_commited:
            if self._owner.account_names.count((self.username, self.host)) > 1:
                raise WBSecurityValidationError("The '%s' account already exists and cannot be saved." % (self.formatted_name()))

        fields = {
            "old_user" : escape_sql_string(self._orig_username) if self._orig_username else self._orig_username,
            "old_host" : escape_sql_string(self._orig_host) if self._orig_host else self._orig_host,
            "user" : escape_sql_string(self.username) or "NULL",
            "host" : escape_sql_string(self.host) or "",
            "password" : escape_sql_string(self.password or self._orig_password or ""),
            "auth_plugin" : escape_sql_string(self.auth_plugin) if self.auth_plugin else None,
            "auth_string" : escape_sql_string(self.auth_string) if self.auth_string else None
        }

        if self.is_commited:
            assert self._orig_username is not None and self._orig_host is not None
            assignments = []
            for priv in self._owner.global_privilege_names:
                if priv in self._global_privs:
                  assignments.append("%s='%s'" % (priv, 'Y'))
                else:
                  assignments.append("%s='%s'" % (priv, 'N'))

            for limit in ["max_questions", "max_updates", "max_connections"] + (self._owner.has_max_user_connections and ["max_user_connections"] or []):
                assignments.append("%s='%s'" % (limit, getattr(self, limit)))

            if self._orig_username != self.username:
                assignments.append("User='%s'"%escape_sql_string(self.username))
            if self.auth_plugin:
                if self._orig_auth_string != self.auth_string:
                    assignments.append("authentication_string='%s'" % escape_sql_string(self.auth_string))
            else:
                if self._orig_host != self.host:
                    assignments.append("Host='%s'"%escape_sql_string(self.host))
                if self.password:
                    assignments.append("Password=password('%s')"%escape_sql_string(self.password))

            fields["assignments"] = ", ".join(assignments)

            query = UPDATE_ACCOUNT_QUERY % fields

            try:
                result = self._owner.ctrl_be.exec_sql(query)
            except QueryError, e:
                if e.error == 1142:
                    raise Exception("Error updating account %s@%s: Insufficient rights to perform operation"%(self.username, self.host))
                else:
                    raise Exception("Error updating account %s@%s: %s"%(self.username, self.host, e))
            except Exception, e:
                raise Exception("Error updating account %s@%s: %s"%(self.username, self.host, e))

            self._owner.ctrl_be.exec_sql(FLUSH_PRIVILEGES)
        else:
            # Account was nost saved yet
            def run_query(query):
                result = None
                try:
                    result = self._owner.ctrl_be.exec_sql(query)
                except QueryError, e:
                    if e.error == 1142:
                        raise Exception("Error creating account %s@%s: Insufficient rights to perform operation"%(self.username, self.host))
                    else:
                        raise Exception("Error creating account %s@%s: %s"%(self.username, self.host, e))
                except Exception, e:
                    raise Exception("Error creating account %s@%s: %s"%(self.username, self.host, e))
                return result

            raw_pwd = fields['password']
            fields['password'] = make_scrambled_password(raw_pwd)
            if self.auth_plugin:
                create_query = CREATE_USER_QUERY_PLUGIN % fields
            else:
                create_query = CREATE_USER_QUERY % fields
            run_query(create_query)

            fields['password'] = raw_pwd

            names = ["MAX_QUERIES_PER_HOUR", "MAX_UPDATES_PER_HOUR", "MAX_CONNECTIONS_PER_HOUR"] + (self._owner.has_max_user_connections and ["MAX_USER_CONNECTIONS"] or [])
            values = [str(s) for s in [self.max_questions, self.max_updates, self.max_connections] + (self._owner.has_max_user_connections and [self.max_user_connections] or [])]

            grants = []

            valid_privs = self._owner.get_valid_privileges()
            for priv_field_name in self._global_privs:
                (grant_priv_type, description) = PrivilegeInfo.get(priv_field_name, (None,None))
                if grant_priv_type == 'GRANT OPTION':
                    # these will be glued to 'GRANT OPTION' below at 'for name, value...
                    names.append("GRANT") 
                    values.append("OPTION")
                elif grant_priv_type and (grant_priv_type[0] != '*'):
                    if grant_priv_type in valid_privs:
                        grants.append(grant_priv_type)

            if len(grants) == 0:
              grants.append("USAGE")

            fields["grants"] = ", ".join(grants)

            grant_query = "GRANT %(grants)s ON *.* TO '%(user)s'@'%(host)s' with " % fields

            for name, value in zip(names, values):
              if value:
                grant_query += "%s %s "%(name, str(value))

            run_query(grant_query)

        new_attrs = set([p for p in self._global_privs if p.endswith("_attr")])
        old_attrs = set([p for p in self._orig_global_privs if p.endswith("_attr")])


        def grant_special(priv):
            db, tables, privs, grant, revoke = AdminAttributes[priv]
            if "%(table)s" in grant:
                for table in tables:
                    query = grant % {"table":table, "user":self.username, "host":self.host}
                    self._owner.ctrl_be.exec_sql(query)
            else:
                query = grant % {"table":table, "user":self.username, "host":self.host}
                self._owner.ctrl_be.exec_sql(query)

        def revoke_special(priv):
            db, tables, privs, grant, revoke = AdminAttributes[priv]
            if "%(table)s" in revoke:
                for table in tables:
                    query = revoke % {"table":table, "user":self.username, "host":self.host}
                    self._owner.ctrl_be.exec_sql(query)
            else:
                query = grant % {"table":table, "user":self.username, "host":self.host}
                self._owner.ctrl_be.exec_sql(query)

        # check for newly granted special privs
        for priv in new_attrs.difference(old_attrs):
            grant_special(priv)

        # check for revoked special privs
        for priv in old_attrs.difference(new_attrs):
            revoke_special(priv)

        self._owner.ctrl_be.exec_sql(FLUSH_PRIVILEGES)

        self.is_commited = True


    def load(self, username, hostname):
        self.is_commited = True
        # Basic stuff from User table
        query = GET_ACCOUNT_QUERY % {"user":escape_sql_string(username),"host":escape_sql_string(hostname)}
        try:
            result = self._owner.ctrl_be.exec_query(query)
        except Exception, e:
            raise Exception("Error querying security information: %s" % e)

        if not result.nextRow():
            raise Exception("Could not load account information for %s@%s"%(username,hostname))

        self.username = result.stringByName("User")
        self.host = result.stringByName("Host")
        
        self._orig_password = result.stringByName("Password")
        self._orig_username = self.username
        self._orig_host = self.host
        self._orig_auth_string = self.auth_string
        
        self.max_questions = result.intByName("max_questions")
        self.max_updates = result.intByName("max_updates")
        self.max_connections = result.intByName("max_connections")
        if self._owner.has_max_user_connections:
            self.max_user_connections = result.intByName("max_user_connections")
        if self._owner.has_plugin:
            self.auth_plugin = result.stringByName("plugin")
        if self._owner.has_authentication_string:
            self.auth_string = result.stringByName("authentication_string")
        
        self._global_privs = set()
        for priv in self._owner.global_privilege_names:
            if result.stringByName(priv) == 'Y':
                self._global_privs.add(priv)


        """ not necessary, IS is accessible to all
        # privs from information_schema tables
        query = GET_ACCOUNT_IS_TABLE_PRIVS_QUERY % {"user":username,"host":hostname}
        result = modules.DbMySQLQuery.executeQuery(self._owner._connection, query)
        if result < 0:
            raise Exception("Error querying information_schema table: "+modules.DbMySQLQuery.lastError())

        try:
            is_privs = []
            while modules.DbMySQLQuery.resultNextRow(result):
                table = result.stringByName("Table_name")
                table_privs = result.stringByName("Table_priv")
                is_privs.append((table, table_priv and table_privs.split(",") or []))
        finally:
            modules.DbMySQLQuery.closeResult(result)
        """

        # privs from mysql tables
        query = GET_ACCOUNT_MYSQL_TABLE_PRIVS_QUERY % {"user":escape_sql_string(username),"host":escape_sql_string(hostname)}
        try:
            result = self._owner.ctrl_be.exec_query(query)
        except Exception, e:
            raise Exception("Error querying mysql table: %s" % e)

        mysql_privs = {}
        while result.nextRow():
            table = result.stringByName("Table_name")
            table_privs = result.stringByName("Table_priv")
            mysql_privs[table] = table_privs and table_privs.split(",") or []

        # interpret the privileges
        for name, (db, tables, required_privs, grant, revoke) in AdminAttributes.items():
            if db == "mysql":
                ok = True
                for table in tables:
                    if not mysql_privs.has_key(table):
                        ok = False
                        break
                    if not set(required_privs).issubset(set(mysql_privs[table])):
                        ok= False
                        break
                if ok:
                    self._global_privs.add(name)

        self._orig_global_privs = self._global_privs.copy()




