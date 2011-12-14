#!/usr/bin/python

from thread import start_new_thread

from random import randint
import socket
import select
import sys
import time
import paramiko
from Queue import Queue

SSH_PORT = 22
REMOTE_PORT = 3306

TunnelSerial = 1

# timeout for closing an unused tunnel
TUNNEL_TIMEOUT = 60

# paramiko 1.6 didn't have this class
if hasattr(paramiko, "WarningPolicy"):
    WarningPolicy = paramiko.WarningPolicy
else:
    class WarningPolicy(paramiko.MissingHostKeyPolicy):
        def missing_host_key(self, client, hostname, key):
            print 'WARNING: Unknown %s host key for %s: %s' % (key.get_name(), hostname, hexlify(key.get_fingerprint()))


class Tunnel:
    def __init__(self, q, tunnel_manager, server, username, target, threaded=True):
        global TunnelSerial

        self.tunnel_manager = tunnel_manager

        self.local_port = None
        self.listen_sock = None
        self.q = q
        self.server = server
        self.username = username
        self.target = target
        self.id = TunnelSerial
        self.shutdown = False
        self.connecting = False
        self.error = None
        self.threaded = threaded
        TunnelSerial += 1
        
        self.num_clients = 1
        self.client = None
        self.connections = []


    def match(self, server, username, target):
        return self.server == server and self.username == username and self.target == target


    def start(self, password, keyfile):
        self.listen_sock = socket.socket()
        # pick a random port number
        while True:
            self.local_port = randint(1024, 65535)
            try:
                self.listen_sock.bind(("127.0.0.1", self.local_port))
                self.listen_sock.listen(2)
                break
            except socket.error, exc:
                print exc,self.local_port
                err, msg = exc.args
                if err == 22:
                    continue # retry
                raise exc

        self.connecting = True
        if self.threaded:
            print "Starting thread..."
            start_new_thread(self._threadloop, (password, keyfile))
            print "Thread started"
        else:
            self._threadloop(password, keyfile)
        return self.local_port


    def respond(self, msgtype, msg):
        print self.local_port, msgtype,msg
        if self.q:
            self.q.put("%s %s %s"%(self.local_port, msgtype, msg))


    def _connect_ssh(self, password, keyfile):
        self.client = paramiko.SSHClient()
        self.client.load_system_host_keys()
        self.client.set_missing_host_key_policy(WarningPolicy())

        try:
            self.client.connect(self.server[0], self.server[1], username=self.username, key_filename=keyfile, password=password)
            return True
        except paramiko.PasswordRequiredException, exc:
            print "Password required: %r" % exc
            self.respond("ERROR", "Authentication error: %r" % exc)
        except paramiko.AuthenticationException, exc:
            print "Bad password: %r" % exc
            self.respond("ERROR", "Authentication error: %r" % exc)
        except Exception, e:
            self.error = str(e)
            self.respond("ERROR", "Failed to connect to %s:%d: %r" % (self.server[0], self.server[1], e))            
        return False


    def close(self):
        self.respond("INFO", "Closing tunnel")
        self.shutdown = True
        self.listen_sock.close()
        
        for con in self.connections[:]:
            con.close()

        self.client.close()


    def _threadloop(self, password, keyfile):
        try:
            self._actual_work(password, keyfile)
        except Exception, e:
            self.respond("INFO", "Internal error in tunnel manager: %r" % e)
            import traceback
            traceback.print_exc()
    
    def _actual_work(self, password, keyfile):
        if keyfile:
            self.respond("INFO", "Connecting to SSH server at %s:%s using key %s..."%(self.server[0],self.server[1],keyfile))
        else:
            self.respond("INFO", "Connecting to SSH server at %s:%s..."%(self.server[0],self.server[1]))
        if not self._connect_ssh(password, keyfile):
            self.connecting = False
            self.listen_sock.close()
            self.shutdown = True
        else:
            self.respond("INFO", "Connection opened")
        del password
        self.connecting = False

        while not self.shutdown:
            try:
                socks = [self.listen_sock]
                for sock, chan in self.connections:
                    socks.append(sock)
                    socks.append(chan)

                r, w, x = select.select(socks, [], [], TUNNEL_TIMEOUT)
            except Exception, e:
                if not self.shutdown:
                    self.respond("ERROR", "Error while forwarding data: %r"%e)
                break

            if not r and len(socks) <= 1:
                print "Closing tunnel to %s:%s from inactivity..." % (self.server[0],self.server[1])
                break
                

            if self.listen_sock in r:
                print "New client connection"
                self.accept_client()
            
            closed = []
            for sock, chan in self.connections:
                if sock in r:
                    data = sock.recv(1024)
                    if not data:
                        closed.append((sock, chan))
                    else:
                        chan.send(data)

                if chan in r:
                    data = chan.recv(1024)
                    if not data:
                        closed.append((sock, chan))
                    else:
                        sock.send(data)

            for item in set(closed):
                sock, chan = item
                try:
                    sock.close()
                except:
                    pass
                try:
                    chan.close()
                except:
                    pass
                print "Client for %s disconnected" % self.local_port
                self.connections.remove(item)

        for sock, chan in self.connections:
            try:
                sock.close()
            except:
                pass
            try:
                chan.close()
            except:
                pass
        
        self.listen_sock.close()
        del self.tunnel_manager.tunnel_by_port[self.local_port]
        


    def accept_client(self):
        try:
            local_sock, peeraddr = self.listen_sock.accept()
        except Exception, e:
            self.respond("ERROR", "Error accepting new tunnel client: %r"%e)
            return
        print "client connection established"

        transport = self.client.get_transport()

        try:
            sshchan = transport.open_channel('direct-tcpip', self.target, local_sock.getpeername())
        except Exception, e:
            self.error = 'Remote connection to %s:%d failed: %r' % (self.target[0], self.target[1], e)
            self.respond("ERROR", 'Remote connection to %s:%d failed: %r' % (self.target[0], self.target[1], e))
            local_sock.close()
            return

        if sshchan is None:
            self.error = 'Remote connection to %s:%d was rejected by the SSH server.' % (self.target[0], self.target[1])
            self.respond("ERROR", 'Remote connection to %s:%d was rejected by the SSH server.' % (self.target[0], self.target[1]))
            local_sock.close()
            return

        self.respond("INFO", 'Tunnel now open %r -> %r -> %r' % (local_sock.getpeername(), sshchan.getpeername(), self.target))

        self.connections.append((local_sock, sshchan))




class TunnelManager:
    def __init__(self):
        self.tunnel_by_port = {}

        self.inpipe = sys.stdin
        self.outpipe = sys.stdout


    def lookup_tunnel(self, server, username, target):
        if type(server) == str:
            if ':' in server:
                server = server.split(":", 1)
                server = (server[0], int(server[1]))
            else:
                server = (server, SSH_PORT)
        if type(target) == str:
            if ':' in target:
                target = target.split(":", 1)
                target = (target[0], int(target[1]))
            else:
                target = (target, REMOTE_PORT)

        for port, tunnel in self.tunnel_by_port.iteritems():
            if tunnel.match(server, username, target):
                return tunnel.local_port
        return None

    def open_tunnel(self, server, username, password, keyfile, target):
        try:
            port = self.open_ssh(server, username, password, keyfile, target)
        except Exception, exc:
            import traceback
            traceback.print_exc()
            return (False, str(exc))
        return (True, port)
   
    def open_ssh(self, server, username, password, keyfile, target):
        if type(server) == str:
            if ':' in server:
                server = server.split(":", 1)
                server = (server[0], int(server[1]))
            else:
                server = (server, SSH_PORT)
        if type(target) == str:
            if ':' in target:
                target = target.split(":", 1)
                target = (target[0], int(target[1]))
            else:
                target = (target, REMOTE_PORT)
        if not password:
            password = ""
        if not keyfile:
            keyfile = None

        found = None
        for port, tunnel in self.tunnel_by_port.iteritems():
            if tunnel.match(server, username, target):
                found = tunnel
                break

        if not found:
            tunnel = Tunnel(Queue(), self, server, username, target)
            port = tunnel.start(password, keyfile)
            self.tunnel_by_port[port] = tunnel

            return port
        else:
            print "Reusing tunnel at port %i" % tunnel.local_port
            return tunnel.local_port


    def wait_connection(self, port):
        tunnel = self.tunnel_by_port[port]
        while tunnel.connecting and not tunnel.error:
            time.sleep(0.3)
        return tunnel.error


    def get_message(self, port):
        tunnel = self.tunnel_by_port[port]
        return tunnel.q.get(block=False)
        

    def close(self, port):
        pass
        # tunnels auto-close when inactive
        #tunnel = self.tunnel_by_port.get(port, None)
        #if tunnel:
        #    tunnel.num_clients -= 1
        #    if tunnel.num_clients == 0:
        #        tunnel.close()
        #        del self.tunnel_by_port[port]

    def send(self, code, arg=""):
        if arg:
            self.outpipe.write(code+" "+arg+"\n")
        else:
            self.outpipe.write(code+"\n")
        self.outpipe.flush()

    def shutdown(self):
        pass

    def wait_requests(self):
        #print "SSH Tunnel Manager started, waiting for requests..."
        self.send("READY")
        while True:
            request = self.inpipe.readline()
            if not request:
                #print "Exiting tunnel manager..."
                break
            try:
                cmd, args = eval(request, {}, {})
            except:
                print "Ignoring invalid request"
                self.send("ERROR", "Invalid request")
                continue
            if cmd == "LOOKUP":
                try:
                    port = self.lookup_tunnel(*args)
                    if port is not None:
                        self.send("OK", "%i"%port)
                    else:
                        self.send("ERROR", "not found")
                except Exception, exc:
                    self.send("ERROR", "%r"%exc)
            elif cmd == "OPENSSH":
                try:
                    port = self.open_ssh(*args)
                    self.send("OK", "%i"%port)
                except Exception, exc:
                    self.send("ERROR", "%r"%exc)
            elif cmd == "CLOSE":
                #self.close(args[0])
                self.send("OK")
            elif cmd == "WAIT":
                # wait for the SSH connection to be established
                error = self.wait_connection(args)
                if not error:
                    self.send("OK")
                else:
                    self.send("ERROR "+error)
            elif cmd == "MESSAGE":
                msg = self.get_message(args)
                if msg:
                    self.send(msg)
                else:
                    self.send("NONE")
            else:
                print "Invalid request %s"%request
                self.send("ERROR", "Invalid request")

"""
if "--single" in sys.argv:
    target = sys.argv[2]
    if "-pw" in sys.argv:
        password = sys.argv[sys.argv.index("-pw")+1]
    else:
        password = None
    if "-i" in sys.argv:
        keyfile = sys.argv[sys.argv.index("-i")+1]
    else:
        keyfile = None
    server = sys.argv[-1]

    tunnel = Tunnel(None, False)
    if "@" in server:
        username, server = server.split("@", 1)
    else:
        username = ""
    print "Starting tunnel..."
    if type(server) == str:
        if ':' in server:
            server = server.split(":", 1)
            server = (server[0], int(server[1]))
        else:
            server = (server, SSH_PORT)
    if type(target) == str:
        if ':' in target:
            target = target.split(":", 1)
            target = (target[0], int(target[1]))
        else:
            target = (target, REMOTE_PORT)
    
    tunnel.start(server, username, password or "", keyfile, target)

else:
    tm = TunnelManager()
    sys.stdout = sys.stderr
    try:
        tm.wait_requests()
    except KeyboardInterrupt, e:
	    pass

"""
