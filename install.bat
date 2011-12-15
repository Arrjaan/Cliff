@echo off 

echo -- Cliff Server installation -- 
echo.
echo.
echo Editing configuation files...
echo.
php install.php
echo.
echo.
echo Installing Apache Service...
echo.
sc create Apache2.2 binpath= "%cd%\httpd\bin\httpd.exe -k runservice" start= auto
sc start Apache2.2
echo Installing MySQL Service...
echo.
sc create MySQL binpath= "%cd%\mysql\bin\mysqld --defaults-file=%cd%\mysql\my.ini MySQL" start= auto
sc start MySQL
echo Installing FTP Service...
echo.
"%cd%/ftp/FileZilla Server.exe" /install auto
"%cd%/ftp/FileZilla Server.exe" /servicename FTP
"%cd%/ftp/FileZilla Server.exe" /start
echo.
echo.
echo Adding PHP directory to PATH variable...
SET PATH=%CD%\php;%PATH%
echo Adding Perl directory to PATH variable...
SET PATH=%CD%\perl\bin;%PATH%
echo.
echo Done!

pause