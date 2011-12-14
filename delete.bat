@echo off 

echo Removing Apache Service...
sc stop Apache2.2
sc delete Apache2.2
echo Removing MySQL Service...
sc stop MySQL
sc delete MySQL
echo Removing FTP Service...
"%cd%/ftp/FileZilla Server.exe" /stop 
"%cd%/ftp/FileZilla Server.exe" /uninstall 
echo Done!

pause