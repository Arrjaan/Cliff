@echo off 
sc config Apache2.2 start= auto
sc config MySQL start= auto
sc start Apache2.2
sc start MySQL
start http://localhost/#server

