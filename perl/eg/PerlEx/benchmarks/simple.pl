#!perl -w
use CGI; my $cgi = new CGI;
my $counter = $cgi->param('counter');
if ($counter < 1) { $counter = 1; }
my $next = $counter + 1;

my $url = "simple.pl?counter=$next";
if ($next > 100) {
	$url = "frame_done.plex?runs=100";
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

