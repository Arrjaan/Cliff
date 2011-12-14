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

 # import platform before paramiko to avoid random import error in osx 10.6
import platform
try:
  platform.system()
except IOError, err:
  if err.errno == 4:
      print "platform.system() exception detected, trying workaround..."
      # random bizarre platform.system() bug detected, try again after 3s
      import time
      time.sleep(3)
      platform.system()

import os
import errno
import stat
#import mforms
import time
import traceback

from wb_common import PermissionDeniedError, InvalidPasswordError, OperationCancelledError, dprint_ex


try:
    import paramiko
    import socket
except:
    traceback.print_exc()
    # temporary workaround
    paramiko = None
    socket = None

if paramiko and paramiko.__version_info__[1] in (7,) and paramiko.__version_info__[2] in (4,5,6):
    from paramiko.message import Message
    from paramiko.common import *
    from paramiko.channel import Channel
    from paramiko.ssh_exception import SSHException, BadAuthenticationType, ChannelException
    import threading
    OPEN_CHANNEL_TIMEOUT = 15

    def wba_open_channel(self, kind, dest_addr=None, src_addr=None, timeout = None):
        chan = None
        if not self.active:
            # don't bother trying to allocate a channel
            return None
        self.lock.acquire()
        try:
            chanid = self._next_channel()
            m = Message()
            m.add_byte(chr(MSG_CHANNEL_OPEN))
            m.add_string(kind)
            m.add_int(chanid)
            m.add_int(self.window_size)
            m.add_int(self.max_packet_size)
            if (kind == 'forwarded-tcpip') or (kind == 'direct-tcpip'):
                m.add_string(dest_addr[0])
                m.add_int(dest_addr[1])
                m.add_string(src_addr[0])
                m.add_int(src_addr[1])
            elif kind == 'x11':
                m.add_string(src_addr[0])
                m.add_int(src_addr[1])
            chan = Channel(chanid)
            self._channels.put(chanid, chan)
            self.channel_events[chanid] = event = threading.Event()
            self.channels_seen[chanid] = True
            chan._set_transport(self)
            chan._set_window(self.window_size, self.max_packet_size)
        finally:
            self.lock.release()
        self._send_user_message(m)
        ts = time.time() + OPEN_CHANNEL_TIMEOUT if (timeout is None) else timeout
        while True:
            event.wait(0.1);
            if not self.active:
                e = self.get_exception()
                if e is None:
                    e = SSHException('Unable to open channel.')
                raise e
            if event.isSet():
                break
            if time.time() > ts:
              chan.close()
              chan = None  # TODO: Check if clean up from self._channels is needed
              event.clear()
              self._channels.delete(chanid)
              if chanid in self.channel_events:
                del self.channel_events[chanid]
              raise IOError("open channel timeout")
        chan = self._channels.get(chanid)
        if chan is not None:
            return chan
        e = self.get_exception()
        if e is None:
            e = SSHException('Unable to open channel.')
        raise e

    paramiko.Transport.open_channel = wba_open_channel
else:
  print "Warning! Can't use connect with timeout in paramiko", paramiko and paramiko.__version__

#===============================================================================
class ConnectionError(Exception):
  pass
  

#===============================================================================
class SSHDownException(Exception):
  pass

#===============================================================================
#
#===============================================================================
class WbAdminSFTP:
  def __init__(self, sftp):
    self.sftp = sftp

  #-----------------------------------------------------------------------------
  def pwd(self):
    ret = None
    if self.sftp:
      try:
        ret = self.sftp.getcwd()

        if ret is None:
          self.sftp.chdir(".")
          ret = self.sftp.getcwd()

        if ret is None:
          ret = ''
      except IOError, e:
        print e

    return ret

  #-----------------------------------------------------------------------------
  def ls(self, path):
    ret = ((),())
    if self.sftp:
      fnames = ()
      fattrs = ()
      try:
        fnames = self.sftp.listdir(path)
        fattrs = self.sftp.listdir_attr(path)
      except IOError, e:
        if e.errno == errno.ENOENT and path.strip(" \r\t\n") == ".":
          raise
        ret = (('Failed to read directory content',),())

      if len(fnames) > 0 and len(fnames) == len(fattrs):
        dirs = []
        rest = []
        for i in range(0, len(fnames)):
          attr = fattrs[i]
          if stat.S_ISDIR(attr.st_mode):
            dirs.append((attr.filename))
          elif stat.S_ISREG(attr.st_mode):
            rest.append((attr.filename))
          else:
            rest.append((attr.filename))

        dirs.sort()
        rest.sort()
        ret = (tuple(dirs), tuple(rest))
    return ret

  #-----------------------------------------------------------------------------
  def cd(self, path):
    ret = False
    if self.sftp:
      try:
        self.sftp.chdir(path)
        ret = True
      except IOError, e:
        ret = False

    return ret

  #-----------------------------------------------------------------------------
  def close(self):
    if self.sftp:
      self.sftp.close()

#===============================================================================
#
#===============================================================================
class WbAdminSSH:
  def wrapped_connect(self, settings, password_delegate):
    assert hasattr(password_delegate, "get_password_for")
    assert hasattr(password_delegate, "reset_password_for")
  
    dprint_ex(2, "Enter")
    self.client = None

    #loginInfo = settings.loginInfo
    #serverInfo = settings.serverInfo

    print type(settings)
    host = settings.ssh_hostname #loginInfo['ssh.hostName']
    usekey = settings.ssh_usekey #int(loginInfo['ssh.useKey'])
    pwd = None # It is ok to keep pwd set to None even if we have it in server settings
               # it will be retrived later
    port = settings.ssh_port#loginInfo['ssh.port']

    if usekey == 1:
      # We need to check if keyfile needs password. For some reason paramiko does not always
      # throw exception to request password
      key_filename = settings.ssh_key #loginInfo['ssh.key']
      f = None
      try:
        f = open(key_filename, 'r')
      except IOError, e:
        f = None # set file handle to None indicating that open failed

      keycont = None # Will hold contents of the keyfile
      if f is not None:
        keycont = f.read()
        f.close()
      else:
        usekey = 0 # Reset usekey to 0 so paramiko will not use non-existent key file
        key_filename = None

      accepted = None

      if usekey == 0:
        # We need password for password ssh auth as keyfile is missing. Retrieve password or ask for it
        pwd = password_delegate.get_password_for("ssh")
        #accepted, pwd = mforms.Utilities.find_or_ask_for_password("SSH key file missing. Remote SSH Login (%s)" % serverInfo['sys.system'], "ssh@%s:%s" % (host,port or 22), loginInfo['ssh.userName'], False)
      elif keycont is not None:
        if 'ENCRYPTED' in keycont:
          # Retrieve password or ask for it
          try:
              pwd = password_delegate.get_password_for("sshkey")
          except OperationCancelledError, exc:
              # SSH key usage cancelled, just login normally
              usekey = 0
              pwd = password_delegate.get_password_for("ssh")
          #accepted, pwd = mforms.Utilities.find_or_ask_for_password("Unlock SSH Private Key", "ssh_keyfile@%s"%key_filename, loginInfo['ssh.userName'], False)
        #else:
        #  accepted = True

      #if not accepted:
      #  raise OperationCancelledError("Cancelled key password input")

      try:
          self.connect(host, port, settings.ssh_username, pwd, usekey, key_filename)
      except InvalidPasswordError, exc:
          if usekey:
              password_delegate.reset_password_for("sshkey")
          else:
              password_delegate.reset_password_for("ssh")
          raise exc
    else:
      #if pwd is None:
      #  accepted, pwd = mforms.Utilities.find_or_ask_for_password("Remote SSH Login (%s)" % serverInfo['sys.system'], "ssh@%s:%s" % (host,port or 22), loginInfo['ssh.userName'], False)
      pwd = password_delegate.get_password_for("ssh")

      #if accepted:
      try:
          self.connect(host, port, settings.ssh_username, pwd, None, None)
      except InvalidPasswordError, exc:
          password_delegate.reset_password_for("ssh")
      #else:
      #  raise OperationCancelledError("Cancelled login")
    dprint_ex(2, "Leave")

  def connect(self, host, port, user, pwd, usekey = 0, key = None):
    if port == None or port == 0:
      port = 22

    if not paramiko:
        raise Exception("One of the modules necessary for SSH base administration could not be imported.") 

    if key and key.startswith("~"):
      key = os.path.expanduser(key)

    self.client = paramiko.SSHClient()
    if usekey:
      self.client.load_system_host_keys()

    # TODO: Check if file with 
    self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
      if 'timeout' in paramiko.SSHClient.connect.func_code.co_varnames:
        self.client.connect(hostname = host, port = int(port), username = user, password = pwd, pkey = None, key_filename = key, timeout = 10)
      else:
        self.client.connect(hostname = host, port = int(port), username = user, password = pwd, pkey = None, key_filename = key)
      dprint_ex(1, "Connected via ssh to ", host, " client = ", self.client)
    except socket.error, exc:
      self.client = None
      raise SSHDownException()
      #if exc.args[0] == 61: # connection refused
      #  raise ConnectionError("Could not establish SSH connection: %r.\nMake sure the SSH daemon is running and is accessible." % exc)
      #else:
      #  raise ConnectionError("Could not establish SSH connection: %r.\nMake sure the SSH daemon is running and is accessible." % exc)
    except paramiko.PasswordRequiredException, exc:
      if pwd is not None:
        raise ConnectionError("Could not unlock private keys. %s" % exc)
      else:
        raise exc
    except paramiko.SSHException, exc:
      raise ConnectionError("Could not establish SSH connection: %s." % exc)
    except Exception, exc:
      raise ConnectionError("Could not establish SSH connection. %s." % exc)

  def is_connected(self):
    return self.client is not None

  def file_exists(self, path):
    ret = False
    if self.client is None:
      raise Exception("wb_admin_ssh: SSH client not connected. file_exists failed")

    sftp = self.client.open_sftp()
    try:
      sftp.stat(path)
      ret = True
      sftp.close()
    except IOError, e:
      sftp.close()
      ret = False
    except:
      sftp.close()
      raise

    return ret

  def stat(self, path):
    ret = None
    sftp = self.client.open_sftp()
    try:
      ret = sftp.stat(path)
      sftp.close()
    except IOError, e:
      ret = None
      sftp.close()
    except:
      ret = None
      sftp.close()
      
    return ret

  def get(self, source, dest):
    if source is not None:
      source = source.strip("'\"")

    ret = False
    try:
      sftp = self.client.open_sftp()
      sftp.get(source, dest)
      ret = True
      sftp.close()
    except IOError, e:
      print "WbAdminSSH.get of file '" + source + "' failed: " + str(e)

    return ret
    
  def get_contents(self, path): # raises IOError
    sftp = self.client.open_sftp()

    # test if sftp session is ok. I get a EACCES doing anything after sftp session is open with freesshd
    try:
      sftp.chdir(".")
    except IOError, exc:
      sftp.close()
      if exc.errno == errno.EACCES:    
          raise PermissionDeniedError("Permission denied opening SFTP session. Please ensure the ssh account is correctly setup.")
      raise exc
    
    try:
      f = sftp.file(path, "r")
    except IOError, exc:
      sftp.close()
      if exc.errno == errno.EACCES:
        raise PermissionDeniedError("Permission denied opening remote file %s for reading: %s" % (path, exc))
      raise exc
    ret = f.read()
    f.close()
    sftp.close()
    return ret

  def set_contents(self, path, data): # raises IOError
    sftp = self.client.open_sftp()
    try:
      f = sftp.file(path, "w")
      f.chmod(stat.S_IREAD | stat.S_IWRITE)
    except IOError, exc:
      sftp.close()
      if exc.errno == errno.EACCES:
        raise PermissionDeniedError("Permission denied opening remote file %s for writing: %s" % (path, exc))
      raise exc
    ret = f.write(data)
    f.close()
    sftp.close()
    return ret

  def put(self, source, dest):
    ret = False
    try:
      sftp = self.client.open_sftp()
      sftp.put(source, dest)
      ret = True
      sftp.close()
    except:
      print "WbAdminSSH.put failed"

    return ret

  def exec_cmd(self, cmd, as_admin = 0, admin_password = None, output_handler = None, read_size = 128, get_channel_cb = None):
    dprint_ex(3, "Enter cmd = ", cmd)
    out = ""
    ret = None
    # For some reason we have bool in pwd
    if type(admin_password) is unicode:
      admin_password = admin_password.encode("utf8")

    if type(admin_password) is not str:
      admin_password = None

    if self.client is not None:
      bufsize = -1
      transport = self.client.get_transport()
      chan = None
      try:
        chan = transport.open_session() # There should be timeout someday. The patch was sent.
        if chan:
          chan.setblocking(True)
          chan.settimeout(10)
          if as_admin:
            chan.get_pty()

          #print "Executing '%s' over ssh" % cmd

          chan.exec_command(cmd)

          stdin = chan.makefile('wb', bufsize)
          stdout = chan.makefile('rb', bufsize)
          stderr = chan.makefile_stderr('rb', bufsize)

          if get_channel_cb is not None:
            dprint_ex(3, "Getting channel via passed cb", get_channel_cb)
            get_channel_cb(chan)

          # There can be possible long delay if command executed expects password
          # and the password is None
          if (as_admin and admin_password is not None):
            time.sleep(1)
            dprint_ex(3, "Sending password")
            try:
              stdin.write(admin_password+"\n")
              stdin.flush()
            except socket.error, e:
              es = str(e)
              if not('ocket' in es and 'closed' in es):
                raise

          def reader(self, ssh_session):
            out = ""
            loop = True
            while loop:
              try:
                chunk = ssh_session.recv(read_size)
                if chunk is not None and chunk != "":
                  out += chunk
                else:
                  loop = False
              except socket.timeout:
                loop = False

            return out

          out = ""

          if output_handler is None:
            out = reader(self, chan)
          else:
            output_handler(chan)

          if chan.exit_status_ready():
            ret = chan.recv_exit_status()
          else:
            dprint_ex(1, "Read from the peer is done, but status code is not available")

      except paramiko.SSHException, e:
        if chan and chan.recv_ready():
          out = chan.recv(128)
        print out
        print "SSHException in SSH:", str(e)
        traceback.print_exc()
      except Exception, e:
        if chan and chan.recv_ready():
          out = chan.recv(128)
        print out
        # A "socket closed" exception happens sometimes when sending the password, for some reason.
        # Not sure, but it could be that the command was accepted without a password (maye sudo doing internal
        # password caching for some time). Until that is investigated, exceptions shouldn't bubble up
        print "Exception in SSH:", str(e)
        traceback.print_exc()
      except:
        print "Unknown exception in ssh"

      if chan is not None:
        chan.close()

    if out is not None and admin_password is not None:
      out = out.replace(admin_password, "")
    dprint_ex(5, "SSH.exec_cmd(cmd =", cmd, ", output =", out, ". Retcode =", ret, ")")
    return (out, ret)

  def getftp(self):
    self.sftp = WbAdminSFTP(self.client.open_sftp())
    return self.sftp

  def close(self):
    dprint_ex(2, " ")
    if self.client is not None:
      self.client.close()


# === Unit tests ===
if __name__ == "__main__":
  #import threading
  import time

  class Settings:
    def __init__(self):
      self.loginInfo = {}
      self.serverInfo = {}

      self.loginInfo['ssh.hostName'] = ''
      self.loginInfo['ssh.useKey']   = 0
      self.loginInfo['ssh.userName'] = ''
      self.loginInfo['ssh.port'] = ''

  settings = Settings()
  
  class Delegate:
      def get_password_for(self, what):
          return ""
      
      def reset_password_for(self, what):
          return ""

  wbassh = WbAdminSSH()
  wbassh.wrapped_connect(settings, Delegate())
  ftp = wbassh.getftp()

  print ftp.pwd()
  print ftp.ls('.')
  ftp.cd('OpenVPN')
  print ftp.pwd()
  print ftp.ls('.')

  wbassh.close()
  quit()

  class Test:
    def __init__(self):
      self.chan = None
      self.running = [True]

    def save_channel(self, c):
      print "Saving channel", c
      self.chan = c

    def cpu(self, text):
      text = text.strip(" \r\t\n")
      value = None
      try:
        value = int(text)
      except ValueError:
        value = None
      if value is not None:
        print "CPU", value

    def mem(self, text):
      text = text.strip(" \r\t\n")
      value = None
      try:
        value = int(text)
      except ValueError:
        value = None
      if value is not None:
        print "Mem", value

    def reader(self, ssh_session):
      what = ""
      out = ""
      timeouts = 12
      while self.running[0]: # running is passed in list via "refernce"
        try:
          ch = ssh_session.recv(1)
          timeouts = 12
          if ch == "C":
            what = self.cpu
          elif ch == "M":
            what = self.mem
          elif ch == "\r" or ch == "\n":
            if what is not None:
              what(out)
            what = None
            out = ""
            pass
          elif ch in "0123456789. ":
            out += ch
          else:
            what = None
            out = ""
        except socket.timeout:
          timeouts -= 1
          if timeouts <= 0:
            ssh_session.close()
            raise Exception("Can't read from remote Windows script")




  ts = Test()

  t = threading.Thread(target = wbassh.exec_cmd, args=("cmd /C cscript //NoLogo \"C:\Program Files\MySQL\MySQL Server 5.1\mysql_system_status.vbs\" /DoStdIn", None, False, ts.reader, 1, ts.save_channel))
  t.setDaemon(True)
  t.start()

  time.sleep(10)

  t.join()
  wbassh.close()
