@echo off 

echo Installing Apache Service...
sc create Apache2.2 binpath= "C:\Myst\httpd\bin\httpd.exe -k runservice" start= auto
sc start Apache2.2
echo Installing MySQL Service...
sc create MySQL binpath= "C:\Myst\mysql\bin\mysqld --defaults-file=C:\Myst\mysql\my.ini MySQL" start= auto
sc start MySQL
echo Installing FTP Service...
"%cd%/ftp/FileZilla Server.exe" /install auto
"%cd%/ftp/FileZilla Server.exe" /servicename FTP
"%cd%/ftp/FileZilla Server.exe" /start
echo Adding PHP directory to PATH variable...
SET PATH=%CD%\php;%PATH%
echo Done!

pause