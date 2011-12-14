sc stop %1
ping 127.0.0.1 -n 15 -w 1000 > nul
sc start %1