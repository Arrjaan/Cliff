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

import shutil
import platform
import os
import errno
import threading
import stat
import tempfile
default_sudo_prefix       = '/usr/bin/sudo -p EnterPasswordHere'

from wb_common import dprint_ex, splitpath
from wb_admin_ssh import WbAdminSSH

from wb_common import InvalidPathError, InvalidPasswordError, PermissionDeniedError

class wbaOS:
  unknown = "unknown"
  windows = "windows"
  linux   = "linux"
  darwin  = "darwin"

  def __setattr__(self, name, value):
      raise NotImplementedError



def quote_path(path):
    if path.startswith("~/"):
        # be careful to not quote shell special chars
        return '~/"%s"' % path[2:]
    else:
        return '"%s"' % path.replace('"', r'\"')

def quote_path_win(path):
    return '"%s"' % path.replace("/", "\\").replace('"', r'\"')


def wrap_for_sudo(command, sudo_prefix):
    if not command:
        raise Exception("Empty command passed to execution routine")
    if not sudo_prefix:
        sudo_prefix = default_sudo_prefix
    if '/bin/sh' in sudo_prefix or '/bin/bash' in sudo_prefix:
        command = sudo_prefix + " \"" + command.replace('\\', '\\\\').replace('"', r'\"') + "\""
    else:
        command = sudo_prefix + " /bin/sh -c \"" + command.replace('\\', '\\\\').replace('"', r'\"') + "\""
    return command

###



class SSH(WbAdminSSH):
  def __init__(self, profile, password_delegate):
    self.mtx = threading.Lock()
    self.wrapped_connect(profile, password_delegate)

  def __del__(self):
    dprint_ex(2, "Closing SSH connection")
    self.close()
  
  def get_contents(self, filename):
    self.mtx.acquire()
    try:
      ret = WbAdminSSH.get_contents(self, filename)
    finally:
      self.mtx.release()
    return ret

  def set_contents(self, filename, data):
    self.mtx.acquire()
    try:
      ret = WbAdminSSH.set_contents(self, filename, data)
    finally:
      self.mtx.release()
    return ret

  def exec_cmd(self, cmd, as_admin = 0, admin_password = None, output_handler = None, read_size = 128, get_channel_cb = None):
    output   = None
    retcode  = None

    self.mtx.acquire()
    dprint_ex(3, "cmd = ", cmd, ", sudo = ", as_admin)
    try:
      (output, retcode) = WbAdminSSH.exec_cmd(self, cmd, 
                                      as_admin=as_admin, 
                                      admin_password=admin_password, 
                                      output_handler=output_handler,
                                      read_size = read_size,
                                      get_channel_cb = get_channel_cb)
      dprint_ex(3, "Done cmd = ", cmd)
    finally:
      self.mtx.release()
    
    return (output, retcode)


##===================================================================================================
## Local command execution
def local_run_cmd_linux(command, as_admin=False, admin_password=None, sudo_prefix=default_sudo_prefix, output_handler=None):
    # pexpect used only in linux
    import pexpect
    
    # wrap cmd
    if as_admin:
        command = wrap_for_sudo(command, sudo_prefix)

    script = command.strip(" ")
    if script is None or len(script) == 0:
        return None

    temp_file = tempfile.NamedTemporaryFile()

    script = script + " > " + temp_file.name + " 2>&1; echo CMDRESULT$? >> " + temp_file.name

    result = None

    if "'" in script:
      print "' found in script", script
      raise Exception("WBA: Internal error, unexpected character in script to be executed")

    if not as_admin:
      result = pexpect.run("/bin/bash -c '" + script + "'", withexitstatus=True)
    else:
      child = pexpect.spawn("/bin/bash -c '" + script + "'") # script should already have sudo prefix
      try:
          child.expect('assword', timeout=10)
          if admin_password is not None:
              child.write(admin_password + '\n')
          else:
              child.write("\n");
      except pexpect.TIMEOUT:
          #though we are not able to get the expected output, the password is fed anyway
          if admin_password is not None:
            child.write(admin_password + '\n')
          else:
            child.write("\n")
      except pexpect.EOF:
          #Nothing we can do, client is terminatd for some reason, try to read anything available
          dprint_ex(2,"Pipe from sudo is closed.", script)

      text = ""

      if child.isalive():
          should_quit_read_loop = False
          while not should_quit_read_loop and child.isalive():
              try:
                  current_text = child.read_nonblocking(256, 30)
                  if current_text.find('EnterPasswordHere') >= 0:
                    try:
                      child.close()
                    except:
                      pass
                    temp_file.close()
                    raise InvalidPasswordError("Incorrect password for sudo")
                  else:
                    text += current_text
              except pexpect.TIMEOUT:
                  pass
              except pexpect.EOF:
                  should_quit_read_loop = True
      else:
          #Try to read
          text = child.read()

      child.close();

    text = temp_file.read()
    temp_file.close()

    idx = text.rfind("CMDRESULT")
    if (idx != -1):
      retcode = int(text[idx+9:].strip(" \r\t\n"))
      if output_handler:
        output_handler(text[0:idx])
      result = retcode

    return result


def local_run_cmd_windows(command, as_admin=False, admin_password=None, sudo_prefix=None, output_handler=None):
    # wrap cmd
    command = "cmd.exe /C " + command

    out_str =""
    retcode = 1

    if as_admin:
      try:
        from ctypes import c_int, WINFUNCTYPE, windll
        from ctypes.wintypes import HWND, LPCSTR, UINT
        prototype = WINFUNCTYPE(c_int, HWND, LPCSTR, LPCSTR, LPCSTR, LPCSTR, UINT)
        scriptparts = command.partition(" ")
        cmdname = scriptparts[0]
        cmdparams = scriptparts[2]
        paramflags = (1, "hwnd", 0), (1, "operation", "runas"), (1, "file", cmdname), (1, "params", cmdparams), (1, "dir", None), (1, "showcmd", 0)
        SHellExecute = prototype(("ShellExecuteA", windll.shell32), paramflags)
        ret = SHellExecute()
        # > 32 is OK, < 32 is error code
        retcode = 1
        if ret > 32:
          retcode = 0
        else:
          if ret == 0:
            dprint_ex(1, "Out of memory executing %s" % command)
          else:
            dprint_ex(1, "Error %i executing %s" % (ret, command))
        return retcode
      except:
        import traceback
        traceback.print_exc()
    else:
      try:
        stdin, stdout, stderr = os.popen3(command)
        out = stdout.read()
        if not out: out = ""
        err = stderr.read()
        if not err: err = ""
        out_str = out + err
        retcode = stdout.close() # this doesn't really work, it will return None
        stderr.close()
        stdin.close()
      except Exception, exc:
        import traceback
        traceback.print_exc()
        retcode = 1
        out_str = "Internal error: %s"%exc
    if retcode != 1:
      retcode = 0

    if output_handler:
        output_handler(out_str)
    return retcode


if platform.system() == "Windows":
  local_run_cmd = local_run_cmd_windows
else:
  local_run_cmd = local_run_cmd_linux

def local_get_cmd_output(command, as_admin=False, admin_password=None):
    output = []
    output_handler = lambda line, l=output: l.append(line)
    rc = local_run_cmd(command=command, as_admin=as_admin, admin_password=admin_password, sudo_prefix=None, output_handler=output_handler)
    return ("\n".join(output), rc)

##===================================================================================================
## Process Execution


_process_ops_classes = []


class ProcessOpsBase:
    cmd_output_encoding = ""
    
    def __init__(self, **kwargs):
        pass
    
    def post_init(self):
        pass
    
    def expand_path_variables(self, path):
        return path

    def get_cmd_output(self, command, as_admin=False, admin_password=None):
        output = []
        output_handler = lambda line, l=output: l.append(line)
        rc = self.exec_cmd(command, as_admin, admin_password, output_handler)
        return ("\n".join(output), rc)


class ProcessOpsNope(ProcessOpsBase):
    @classmethod
    def match(cls, (host, target, connect)):
        return connect == 'none'

    def expand_path_variables(self, path):
        return path

    def exec_cmd(self, command, as_admin=False, admin_password=None, output_handler=None):
        return None

    def get_cmd_output(self, command, as_admin=False, admin_password=None):
        return ("", None)

_process_ops_classes.append(ProcessOpsNope)


class ProcessOpsLinuxLocal(ProcessOpsBase):
    @classmethod
    def match(cls, (host, target, connect)):
        return connect == 'local' and (host in (wbaOS.linux, wbaOS.darwin) and target in (wbaOS.linux, wbaOS.darwin))

    def __init__(self, **kwargs):
        ProcessOpsBase.__init__(self, **kwargs)
        self.sudo_prefix= kwargs.get("sudo_prefix", default_sudo_prefix)

    def exec_cmd(self, command, as_admin=False, admin_password=None, output_handler=None):
        return local_run_cmd_linux(command, as_admin, admin_password, self.sudo_prefix, output_handler)

_process_ops_classes.append(ProcessOpsLinuxLocal)


class ProcessOpsLinuxRemote(ProcessOpsBase):
    @classmethod
    def match(cls, (host, target, connect)):
        # host doesn't matter
        return connect == 'ssh' and target in (wbaOS.linux, wbaOS.darwin)

    def __init__(self, **kwargs): # Here should be at least commented list of args
        ProcessOpsBase.__init__(self, **kwargs)
        
        self.sudo_prefix= kwargs.get("sudo_prefix", default_sudo_prefix)
        self.ssh = kwargs["ssh"]

    def exec_cmd(self, command, as_admin=False, admin_password=None, output_handler=None):
        #if not self.ssh:
        #    raise Exception("No SSH session active")

        if as_admin:
            command = wrap_for_sudo(command, self.sudo_prefix)

        def ssh_output_handler(ssh_channel, handler):
            import socket
            loop = True
            while loop:
              try:
                chunk = ssh_channel.recv(128)
                if chunk is not None and chunk != "":
                  handler(chunk)
                else:
                  loop = False
              except socket.timeout:
                loop = False

        if output_handler:
          handler = lambda chan, h=output_handler: ssh_output_handler(chan, h)
        else:
          handler = None

        if self.ssh:
          # output_handler taken by ssh.exec_cmd is different from the one used elsewhere
          dummy_text, ret = self.ssh.exec_cmd(command, 
                  as_admin=as_admin, admin_password=admin_password, 
                  output_handler=handler)
        else:
          ret = 1
          if output_handler:
            output_handler("No SSH connection is active")
          else:
            print("No SSH connection is active")

        return ret

_process_ops_classes.append(ProcessOpsLinuxRemote)




WIN_REG_QUERY_PROGRAMFILES = 'reg query HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion /v "ProgramFilesDir"'
WIN_REG_QUERY_PROGRAMFILES_x86 = 'reg query HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion /v "ProgramFilesDir (x86)"'

WIN_PROGRAM_FILES_VAR = "%ProgramFiles%"
WIN_PROGRAM_FILES_X86_VAR = "%ProgramFiles(x86)%"
WIN_PROGRAM_FILES_X64_VAR = "%ProgramW6432%"


class ProcessOpsWindowsLocal(ProcessOpsBase):
    @classmethod
    def match(cls, (host, target, connect)):
        return (host == wbaOS.windows and target == wbaOS.windows and connect in ('wmi', 'local'))

    def __init__(self, **kwargs):
        ProcessOpsBase.__init__(self, **kwargs)
        self.target_shell_variables = {}
        
    def post_init(self):
        self.fetch_windows_shell_info()
        
    def exec_cmd(self, command, as_admin, admin_password, output_handler=None):
        return local_run_cmd_windows(command, as_admin, admin_password, None, output_handler)

    def expand_path_variables(self, path):
      """
      Expand some special variables in the path, such as %ProgramFiles% and %ProgramFiles(x86)% in 
      Windows. Uses self.target_shell_variables for the substitutions, which should have been
      filled when the ssh connection to the remote host was made.
      """
      for k, v in self.target_shell_variables.iteritems():
          path = path.replace(k, v)
      return path

    def fetch_windows_shell_info(self):
        # get some info from the remote shell
        result, code = self.get_cmd_output("chcp.com")
        if code == 0:
            result = result.strip(" .\r\n").split()
            if len(result) > 0:
                self.cmd_output_encoding = "cp" + result[-1]
        else:
            print "WARNING: Unable to determine codepage from shell: %s"%result

        result, code = self.get_cmd_output("echo %PROCESSOR_ARCHITECTURE%")
        if result:
            result = result.strip()
        ProgramFilesVar = None
        x86var = None
        if result != "x86":#we are on x64 win in x64 mode
            x86var = WIN_PROGRAM_FILES_X86_VAR
            ProgramFilesVar = WIN_PROGRAM_FILES_VAR
        else:
            result, code = self.get_cmd_output("echo %PROCESSOR_ARCHITEW6432%")
            if result:
                result = result.strip()
            if result == "%PROCESSOR_ARCHITEW6432%":#we are on win 32
                x86var = WIN_PROGRAM_FILES_VAR
                ProgramFilesVar = WIN_PROGRAM_FILES_VAR
            else:#32bit app on x64 win
                x86var = WIN_PROGRAM_FILES_VAR
                ProgramFilesVar = WIN_PROGRAM_FILES_X64_VAR

        result, code = self.get_cmd_output("echo "+ ProgramFilesVar)
        if code == 0:
            self.target_shell_variables["%ProgramFiles%"] = result.strip("\r\n")
            if ProgramFilesVar != "%ProgramFiles%":
                self.target_shell_variables[ProgramFilesVar] = result.strip("\r\n")
        else:
            print "WARNING: Unable to fetch ProgramFiles value in Windows machine: %s"%result

        # this one only exists in 64bit windows
        result, code = self.get_cmd_output("echo "+ x86var)
        if code == 0:
            self.target_shell_variables["%ProgramFiles(x86)%"] = result.strip("\r\n")
        else:
            print "WARNING: Unable to fetch ProgramFiles(x86) value in local Windows machine: %s"%result
        
        dprint_ex(1, "Encoding: %s, Shell Variables: %s" % (self.cmd_output_encoding, self.target_shell_variables))


_process_ops_classes.append(ProcessOpsWindowsLocal)


class ProcessOpsWindowsRemoteSSH(ProcessOpsWindowsLocal):
    @classmethod
    def match(cls, (host, target, connect)):
        # host doesn't matter
        return (target == wbaOS.windows and connect == 'ssh')

    def __init__(self, **kwargs):
        ProcessOpsWindowsLocal.__init__(self, **kwargs)

        self.ssh = kwargs["ssh"]


    def post_init(self):
        if self.ssh:
            self.fetch_windows_shell_info()


    def exec_cmd(self, command, as_admin=False, admin_password=None, output_handler=None):
        command = "cmd.exe /c " + command
    
        if not self.ssh:
            raise Exception("No SSH session active")

        def ssh_output_handler(ssh_channel, handler):
            import socket
            loop = True
            while loop:
              try:
                chunk = ssh_channel.recv(128)
                if chunk is not None and chunk != "":
                  handler(chunk)
                else:
                  loop = False
              except socket.timeout:
                loop = False

        if output_handler:
          handler = lambda chan, h=output_handler: ssh_output_handler(chan, h)
        else:
          handler = None

        # output_handler taken by ssh.exec_cmd is different from the one used elsewhere
        dummy_text, ret = self.ssh.exec_cmd(command, 
                as_admin=as_admin, admin_password=admin_password, 
                output_handler=handler)
        return ret


        

_process_ops_classes.append(ProcessOpsWindowsRemoteSSH)



##===================================================================================================
## File Operations 

_file_ops_classes = []

class FileOpsNope:
    @classmethod
    def match(cls, target_os, connection_method):
        return connection_method == "none"

    def __init__(self, process_ops, ssh = None):
        pass

    def save_file_content(self, filename, content, as_admin = False, admin_password = None):
        pass

    def save_file_content_and_backup(self, filename, content, backup_extension, as_admin = False, admin_password = None):
        pass

    def get_file_content(self, filename, as_admin = False, admin_password = None):
        return ""

    def _copy_file(self, source, dest, as_admin = False, admin_password = None): # not used externally
        pass

    def is_dir_writable(self, path):
        return False

    # Return format is list of entries in dir (directories go first, each dir name is follwoed by /)
    def listdir(self, path): # base operation to build file_exists and remote file selector
        return []

_file_ops_classes.append(FileOpsNope)


#===============================================================================
# The local file ops are context free, meaning that they
# do not need active shell session to work on
# local  all  plain
#   save_file_content  - python
#   get_file_content   - python
#   copy_file          - python
#   get_dir_access     - python (returns either rw or ro or none)
#   listdir            - python
# local  all  sudo derives from local-all-plain
#   save_file_content  - shell
#   get_file_content   - python (maybe sudo if file is 0600)
#   copy_file          - shell
#   get_dir_access     - python (returns either rw or ro or none)
#   listdir            - python/shell(for ro-dirs)
class FileOpsLocalUnix:
    @classmethod
    def match(cls, target_os, connection_method):
        return connection_method == "local" and target_os in (wbaOS.linux, wbaOS.darwin)

    process_ops = None
    def __init__(self, process_ops, ssh=None):
        self.process_ops = process_ops
        self.tempdir = os.path.expanduser('~')

    # content must be a string
    def save_file_content(self, filename, content, as_admin = False, admin_password = None):
        self.save_file_content_and_backup(filename, content, None, as_admin, admin_password)


    def save_file_content_and_backup(self, filename, content, backup_extension, as_admin = False, admin_password = None):
        dprint_ex(1, "Saving file %s with backup (sudo=%s)" %  (filename, as_admin))
        if as_admin:
            # The delete argument is only available starting from py 2.6 (NamedTemporaryFile deletes files on close in all cases, unless you pass delete=False)
            tmp = tempfile.NamedTemporaryFile(dir=self.tempdir)
            tmp_name = tmp.name
            try:
                dprint_ex(1, "Writing file contents to tmp file %s" % tmp_name)
                tmp.write(content)
                tmp.flush()
                if backup_extension and os.path.exists(filename):
                    dprint_ex(1, "Creating backup of %s to %s" % (filename, filename+backup_extension))
                    self._copy_file(source = filename, dest = filename + backup_extension, 
                                    as_admin = as_admin, admin_password = admin_password)

                dprint_ex(1, "Copying over tmp file to final filename using sudo: %s -> %s" % (tmp_name, filename))
                self._copy_file(source = tmp_name, dest = filename, as_admin = as_admin, admin_password = admin_password)
                dprint_ex(1, "Done")
                tmp.close()
            except Exception, exc:
                dprint_ex(1, str(exc))
                if tmp:
                  tmp.close()
                raise
        else:
            target_dir = splitpath(filename)[0]
            
            if not os.path.exists(target_dir):
                dprint_ex(1, "Target directory %s does not exist" % target_dir)
                raise InvalidPathError("The directory %s does not exist" % target_dir)
            
            if not self.is_dir_writable(target_dir):
                dprint_ex(1, "Target directory %s is not writable" % target_dir)
                raise PermissionDeniedError("Cannot write to target directory")
            
            if os.path.exists(filename) and backup_extension:
                dprint_ex(1, "Target file %s exists, creating backup" % filename)
                # backup config file
                self._copy_file(filename, filename+backup_extension)            
            try:
                f = open(filename, 'w')
            except OSError, err:
                if err.errno == errno.EACCES:
                    raise PermissionDeniedError("Could not open file %s for writing" % filename)
                raise err
            f.write(content)
            f.close()


    # UseCase: If get_file_content fails with exception of access, try sudo
    def get_file_content(self, filename, as_admin = False, admin_password = None):
        cont = []
        if as_admin:
            # TODO: Implement
            raise NotImplementedError
        else:
            try:
                f = open(filename, 'r')
            except OSError, e:
                if e.errno == errno.EACCES:
                    raise PermissionDeniedError("Can't open file '%s'"%filename)
                raise e
            cont = f.read()
            f.close()
        return cont


    def _copy_file(self, source, dest, as_admin = False, admin_password = None): # not used externally
        if not as_admin:
            try:
                shutil.copy(source, dest)
            except OSError, e:
                if e.errno == errno.EACCES:
                    raise PermissionDeniedError("Can't copy %s to %s" % (source, dest))
                elif e.errno == errno.ENOENT:
                    raise InvalidPathError("File not found: %s" % source)
                raise
        else:
            output = []
            res = self.process_ops.exec_cmd("/bin/cp " + quote_path(source) + " " + quote_path(dest),
                          as_admin   = True,
                          admin_password = admin_password,
                          output_handler = lambda line, l= output: l.append(line)
                         )
            
            if res != 0:
                output = "\n".join(output)
                

                # TODO: Add handling of errors

    def is_dir_writable(self, path):
        ret = False
        
        try:
            dirlist = os.listdir(path)
            filename = '~wba_write_test'
            cnt = 1
            while True:
                if filename + str(cnt) not in dirlist:
                    break
            cnt += 1
            filename = os.path.join(path, filename + str(cnt))
            fp = open(filename, 'w')
            fp.close()
            os.remove(filename)
            ret = True
        except (IOError, OSError), e:
            ret = False
            dprint_ex(1, "code=",e.errno)
        
        return ret

    # Return format is list of entries in dir (directories go first, each dir name is follwoed by /)
    def listdir(self, path): # base operation to build file_exists and remote file selector
        dirlist = []
        try:
            _path = path
            dlist = os.listdir(_path)
            mod = ""
            for item in dlist:
                _path = os.path.join(path, item)
                item_stat = os.stat(_path)
                if stat.S_ISDIR(item_stat):
                    dirlist.insert(0, item + '/')
                elif stat.S_ISREG(item_stat) or stat.S_ISLNK(item_stat):
                    dirlist.append(item)
        except OSError, e:
            if e.errno == errno.EACCES:
              raise PermissionDeniedError("Permission denied accessing %s" % _path)
            elif e.errno == errno.ENOENT:
              raise InvalidPathError("Path not found: %s" % _path)
            raise
        return dirlist

_file_ops_classes.append(FileOpsLocalUnix)



#===============================================================================
class FileOpsLocalWindows(FileOpsLocalUnix): # Used for remote as well, if not using sftp
    @classmethod
    def match(cls, target_os, connection_method):
        return connection_method in ("local", "wmi") and target_os == wbaOS.windows


    def __init__(self, process_ops, ssh=None):
        FileOpsLocalUnix.__init__(self, process_ops, ssh)
        
        tempdir, rc= self.process_ops.get_cmd_output("echo %temp%")
        if tempdir and tempdir.strip():
            self.tempdir = tempdir.strip()
    
    def save_file_content_and_backup(self, filename, content, backup_extension, as_admin = False, admin_password = None):
        dprint_ex(1, "Saving file %s with backup (sudo=%s)" %  (filename, as_admin))
        if as_admin:
            tmp_name = self.tempdir+"\\wbfilesavetmp"
            tmp = open(tmp_name, "w+b")
            try:
                dprint_ex(1, "Writing file contents to tmp file %s" % tmp_name)
                tmp.write(content)
                tmp.close()

                if backup_extension and os.path.exists(filename):
                    #dprint_ex(1, "Creating backup of %s to %s" % (filename, filename+backup_extension))
                    #self._copy_file(source = filename, dest = filename + backup_extension, 
                    #                as_admin = as_admin, admin_password = admin_password)
                    
                    # Create backup and copy over file to final destination in a single command
                    # This is done because running copy twice, would bring up the UAC dialog twice
                    
                    script = "copy /Y %s %s && copy /Y %s %s" % (quote_path_win(filename), quote_path_win(filename + backup_extension),
                                                                 quote_path_win(tmp_name), quote_path_win(filename))
                    dprint_ex(1, "Creating backup and commiting tmp file: %s" % script)
                    output = []
                    res = self.process_ops.exec_cmd(script, 
                          as_admin   = True,
                          admin_password = admin_password,
                          output_handler = lambda line, l= output: l.append(line)
                         )
                    if res != 0:
                        output = "\n".join(output)
                        raise RuntimeError("Error while executing '%s'. Output = '%s'"%(script, output))
                else:
                    dprint_ex(1, "Copying over tmp file to final filename using sudo: %s -> %s" % (tmp_name, filename))
                    self._copy_file(source = tmp_name, dest = filename, as_admin = as_admin, admin_password = admin_password)
                
                
                dprint_ex(1, "Delete tmp file %s" % tmp_name)
                # delete tmp file
                
                ## BIZARRE STUFF GOING ON HERE
                # commenting out the following line, will make something in committing config file change fail
                # even tho the copies happen before this line.. wtf
               # os.remove(tmp_name)
                
                dprint_ex(1, "Done.")
            except Exception, exc:
                dprint_ex(1, str(exc))
                if tmp:
                  tmp.close()
                raise
        else:
            FileOpsLocalUnix.save_file_content_and_backup(self, filename, content, backup_extension, as_admin, admin_password)

    # UseCase: If get_file_content fails with exception of access, try sudo
    def get_file_content(self, filename, as_admin = False, admin_password = None):
        if as_admin:
            # TODO: Implement
            raise NotImplementedError
        else:
            return FileOpsLocalUnix.get_file_content(self, filename, as_admin, admin_password)


    def _copy_file(self, source, dest, as_admin = False, admin_password = None): # not used externally, but in superclass
       if not as_admin:
            try:
                shutil.copyfile(source, dest)
            except OSError, e:
                if e.errno == errno.EACCES:
                    raise PermissionDeniedError("Can't copy %s to %s" % (source, dest))
                elif e.errno == errno.ENOENT:
                    raise InvalidPathError("File not found: %s" % source)
                raise
       else:
            output = []
            res = self.process_ops.exec_cmd("copy /Y " + quote_path_win(source) + " " + quote_path_win(dest), 
                          as_admin   = True,
                          admin_password = admin_password,
                          output_handler = lambda line, l= output: l.append(line)
                         )
            if res != 0:
                output = "\n".join(output)
                raise RuntimeError("Error copying file %s to %s\n%s" % (source, dest, output.strip()))

    #def listdir(self, path) - derived from FileOpsLocalUnix


_file_ops_classes.append(FileOpsLocalWindows)

#===============================================================================
# This remote file ops are shell dependent, they must be
# given active ssh connection, possibly, as argument 
# remote unix sudo/non-sudo
#   save_file_content  - shell
#   get_file_content   - shell
#   copy_file          - shell
#   get_dir_access     - shell(returns either rw or ro or none)
#   listdir            - shell(for ro-dirs)
class FileOpsRemoteUnix:
    @classmethod
    def match(cls, target_os, connection_method):
        return connection_method == "ssh" and target_os in (wbaOS.linux, wbaOS.darwin)

    def __init__(self, process_ops, ssh):
        self.process_ops = process_ops
        self.ssh = ssh

    # UseCase: If get_file_content fails with exception of access, try sudo
    def get_file_content(self, filename, as_admin = False, admin_password = None): # may raise IOError
        if self.ssh:
          if as_admin:
              #TODO
              raise Exception("Read file as admin not supported")
          else:
              try:
                  return self.ssh.get_contents(filename)
              except IOError, exc:
                  if exc.errno == errno.EACCES:
                      raise PermissionDeniedError("Permission denied attempting to read file %s" % filename)
        else:
            print "Attempt to read remote file with no ssh session"
            import traceback
            traceback.print_stack()
            raise Exception("Cannot read remote file without an SSH session")
        return None

    #-----------------------------------------------------------------------------
    def save_file_content(self, filename, content, as_admin = False, admin_password = None):
        self.save_file_content_and_backup(filename, content, None, as_admin, admin_password)

    #-----------------------------------------------------------------------------
    def save_file_content_and_backup(self, path, content, backup_extension, as_admin = False, admin_password = None):
        # Check if dir, where config file will be stored is writable
        dirname, filename = splitpath(path)

        if not as_admin and not self.is_dir_writable(dirname.strip(" \r\t\n")):
            raise PermissionDeniedError("Cannot write to directory %s" % dirname)

        if self.ssh is not None:
            ## Get home dir for using as tmpdir
            homedir, status = self.process_ops.get_cmd_output("echo ~")
            if type(homedir) is unicode:
                homedir = homedir.encode("utf8")
            if type(homedir) is str:
                homedir = homedir.strip(" \r\t\n")
            else:
                homedir = None
            dprint_ex(2, "Got home dir", homedir)

            if not homedir:
                raise Exception("Unable to get path for remote home directory")

            tmpfilename = homedir + "/.wba.temp"

            dprint_ex(1, "Remotely writing contents to temporary file %s" % tmpfilename)
            dprint_ex(3, content)
            self.ssh.set_contents(tmpfilename, content)

            if backup_extension:
                dprint_ex(1, "Backing up %s" % path)
                backup_cmd = "/bin/cp " + quote_path(path) + " " + quote_path(path+backup_extension)
                self.process_ops.exec_cmd(backup_cmd, as_admin, admin_password)

            copy_to_dest = "/bin/cp " + quote_path(tmpfilename) + " " + quote_path(path)
            delete_tmp = "/bin/rm " + quote_path(tmpfilename)
            dprint_ex(1, "Copying file to final destination: %s" % copy_to_dest)
            self.process_ops.exec_cmd(copy_to_dest, as_admin, admin_password)
            dprint_ex(1, "Deleting tmp file: %s" % delete_tmp)
            self.process_ops.exec_cmd(delete_tmp)
        else:
            raise Exception("No SSH session active, cannot save file remotely")



    def is_dir_writable(self, path):
        target_path = quote_path(path + "/workbench-temp-file")
        result = self.process_ops.exec_cmd("touch " + target_path)
        ret = (result == 0)
        if ret:
            result = self.process_ops.exec_cmd("rm " + target_path)
        return ret


    def listdir(self, path): # base operation to build file_exists and remote file selector
        (output, status) = self.process_ops.exec_cmd('/bin/ls -1 -p')
        dlist = []
        if status == 0:
            raw_list = output.split('\n')
            for item in raw_list:
                if item[-1:] == '/':
                    dlist.insert(0, item)
                else:
                    dlist.append(item)
        return dlist

_file_ops_classes.append(FileOpsRemoteUnix)


#===============================================================================
# remote win sudo/non-sudo
#   save_file_content  - sftp
#   get_file_content   - sftp
#   copy_file          - sftp
#   get_dir_access     - sftp(returns either rw or ro or none)
#   listdir            - sftp(for ro-dirs)
class FileOpsRemoteWindows(FileOpsRemoteUnix):
    @classmethod
    def match(cls, target_os, connection_method):
        return connection_method == "ssh" and target_os == wbaOS.windows

    def __init__(self, process_ops, ssh):
        FileOpsRemoteUnix.__init__(self, process_ops, ssh)
        self.process_ops = process_ops
        self.ssh = ssh

    def save_file_content_and_backup(self, path, content, backup_extension, as_admin = False, admin_password = None):
        # Check if dir, where config file will be stored is writable
        dirname, filename = splitpath(path)

        if not as_admin and not self.is_dir_writable(dirname.strip(" \r\t\n")):
            raise PermissionDeniedError("Cannot write to directory %s" % dirname)

        if self.ssh is not None:
            ## Get temp dir for using as tmpdir
            tmpdir, status = self.process_ops.get_cmd_output("echo %temp%")
            if type(tmpdir) is unicode:
                tmpdir = tmpdir.encode("utf8")
            if type(tmpdir) is str:
                tmpdir = tmpdir.strip(" \r\t\n")
                if tmpdir[1] == ":":
                    tmpdir = tmpdir[2:]
                else:
                    dprint_ex(1,"Temp directory path '" + tmpdir + " is not in expected form. The expected for is something like 'C:\\Windows\\Temp'")
                    tmpdir = None
                dprint_ex(2, "Got temp dir", tmpdir)
            else:
                tmpdir = None
            
            if not tmpdir:
                tmpdir = dirname

            tmpfilename = tmpdir + r"\workbench-temp-file.ini"

            dprint_ex(1, "Remotely writing contents to temporary file %s" % tmpfilename)
            dprint_ex(1, content)
            self.ssh.set_contents(tmpfilename, content)

            if backup_extension:
                dprint_ex(1, "Backing up %s" % path)
                backup_cmd = "copy /y " + quote_path_win(path) + " " + quote_path_win(path+backup_extension)
                msg, code = self.process_ops.get_cmd_output(backup_cmd)
                if code != 0:
                    print backup_cmd, "->", msg
                    raise RuntimeError("Error backing up file: %s" % msg)

            copy_to_dest = "copy /y " + quote_path_win(tmpfilename) + " " + quote_path_win(path)
            delete_tmp = "del " + quote_path_win(tmpfilename)
            dprint_ex(1, "Copying file to final destination: %s" % copy_to_dest)
            msg, code = self.process_ops.get_cmd_output(copy_to_dest)
            if code != 0:
                print copy_to_dest, "->", msg
                raise RuntimeError("Error copying temporary file over destination file: %s\n%s to %s" % (msg, tmpfilename, path))
            dprint_ex(1, "Deleting tmp file: %s" % delete_tmp)
            msg, code = self.process_ops.get_cmd_output(delete_tmp)
            if code != 0:
                print "Could not delete temporary file %s: %s" % (tmpfilename, msg)
        else:
            raise Exception("No SSH session active, cannot save file remotely")

    # UseCase: If get_file_content fails with exception of access, try sudo
    def get_file_content(self, filename, as_admin = False, admin_password = None):
        if self.ssh:
            # Supposedly in Windows, sshd account has admin privileges, so as_admin can be ignored
            try:
                return self.ssh.get_contents(filename)
            except IOError, exc:
                if exc.errno == errno.EACCES:
                    raise PermissionDeniedError("Permission denied attempting to read file %s" % filename)
        else:
            print "Attempt to read remote file with no ssh session"
            import traceback
            traceback.print_stack()
            raise Exception("Cannot read remote file without an SSH session")

    def is_dir_writable(self, path):
        msg, code = self.process_ops.get_cmd_output('echo 1 > ' + quote_path(path + "/wba_tmp_file.bak"))
        ret = (code == 0)
        if ret:
            msg, code = self.process_ops.get_cmd_output('del ' + quote_path(path + "/wba_tmp_file.bak"))
        return ret

    def listdir(self, path): # base operation to build file_exists and remote file selector
        sftp = self.ssh.getftp()
        (dirs, files) = sftp.ls(path)
        ret = []
        for d in dirs:
            ret.append(d + "/")
        return tuple(ret + list(files))

_file_ops_classes.append(FileOpsRemoteWindows)


#===============================================================================
#
#===============================================================================
class ServerManagementHelper(object):
    def __init__(self, profile, ssh):
        self.tmp_files = [] # TODO: make sure the files will be deleted on exit
        
        self.profile = profile

        klass = None
        match_tuple = (profile.host_os, profile.target_os, profile.connect_method)
        for k in _process_ops_classes:
            if k.match(match_tuple):
                klass = k
                break
        if klass:
          self.shell = klass(sudo_prefix=profile.sudo_prefix, ssh=ssh)
          self.shell.post_init()
        else:
          raise Exception("Unsupported administration target type: %s"%str(match_tuple))

        klass = None
        for k in _file_ops_classes:
          if k.match(profile.target_os, profile.connect_method):
            klass = k
            break

        if klass:
          self.file = klass(self.shell, ssh=ssh)
        else:
          raise Exception("Unsupported administration target type: %s:%s" % (str(profile.target_os), str(profile.connect_method)))


    @property
    def cmd_output_encoding(self):
        if self.shell:
            return self.shell.cmd_output_encoding
        return ""

    #-----------------------------------------------------------------------------
    def is_dir_writable(self, path):
        return self.file.is_dir_writable(path)

    #-----------------------------------------------------------------------------
    def file_exists(self, path):
        return self.file.file_exists(path)

    #-----------------------------------------------------------------------------
    # Make sure that file is readable only by user!
    def make_local_tmpfile(self):
        # Here we create that file name blah-blah-blah
        # if total_success: 
        #   self.tmp_files.append(filename)
        raise NotImplementedError

    #-----------------------------------------------------------------------------
    def get_file_content(self, path, as_admin, admin_password):
        return self.file.get_file_content(path, as_admin=as_admin, admin_password=admin_password)

    #-----------------------------------------------------------------------------
    def set_file_content(self, path, contents, as_admin, admin_password):
        return self.file.save_file_content(path, contents, as_admin=as_admin, admin_password=admin_password)

    #-----------------------------------------------------------------------------
    def set_file_content_and_backup(self, path, contents, backup_extension, as_admin, admin_password):
        if type(contents) is unicode:
            contents = contents.encode("utf8")
        return self.file.save_file_content_and_backup(path, contents, backup_extension, as_admin=as_admin, admin_password=admin_password)

    #-----------------------------------------------------------------------------
    # Returns Status Code
    # Text Output is given to output_handler, if there is any
    def execute_command(self, command, as_admin=False, admin_password=None, output_handler=None):
        return self.shell.exec_cmd(command, as_admin, admin_password, output_handler)

