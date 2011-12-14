#!/usr/bin/perl -w
use strict;
use warnings;
use CGI;
use CGI::Carp 'fatalsToBrowser';
use DBI;
use File::Basename;

my $cgi = new CGI;

# a mess to get around lack of vars provided by iPlanet
(my $file = __FILE__) =~ s/\//\\/g;
my $directory = dirname($file);

# zip file at http://ftp.census.gov/geo/www/gazetteer/places.html
# Connect to database
my $user = "";
my $passwd = "";
my $dsn = "Provider=MSDASQL;Driver={Microsoft Text Driver (*.txt; *.csv)};DBQ=$directory";
my $dbh = DBI->connect( "dbi:ODBC:$dsn", $user, $passwd, {RaiseError => 1, PrintError => 1})
    or die $DBI::errstr;

my $counter = $cgi->param('counter') || 1;
if ($counter < 1) { $counter = 1; }
my $next = $counter + 1;
my $url = "zipcgi.pl?counter=$next";
if ($next > 25) {
    $url = "frame_done.plex?runs=25";
}

print "Content-Type: text/html\r\n\r\n";
print <<EOF;
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">

<HTML>
<HEAD>
	<TITLE>PerlEx Performance</TITLE>

<META HTTP-EQUIV="Pragma" CONTENT="no-cache">
<META HTTP-EQUIV="Refresh" CONTENT="0; URL=$url">
</HEAD>

<BODY bgcolor="00ff00">
<font face="verdana, arial, helvetica size="2">
<center>
<H1>
<font size="+9">$counter</font>
<p>
Perl CGI
<p>
</H1>
</center>
</font>
</BODY>
</HTML>

EOF

# Disconnect database connection
$dbh->disconnect;

