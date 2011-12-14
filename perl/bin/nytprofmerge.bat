@rem = '--*-Perl-*--
@echo off
if "%OS%" == "Windows_NT" goto WinNT
perl -x -S "%0" %1 %2 %3 %4 %5 %6 %7 %8 %9
goto endofperl
:WinNT
perl -x -S %0 %*
if NOT "%COMSPEC%" == "%SystemRoot%\system32\cmd.exe" goto endofperl
if %errorlevel% == 9009 echo You do not have Perl in your PATH.
if errorlevel 1 goto script_failed_so_exit_with_non_zero_val 2>nul
goto endofperl
@rem ';
#!/usr/bin/perl
#line 15
##########################################################
# This script is part of the Devel::NYTProf distribution
#
# Copyright, contact and other information can be found
# at the bottom of this file, or by going to:
# http://search.cpan.org/dist/Devel-NYTProf/
#
##########################################################
# $Id$
##########################################################

use warnings;
use strict;

use Devel::NYTProf::Core;
require Devel::NYTProf::FileHandle;
require Devel::NYTProf::Data;
use List::Util qw(min);

our $VERSION = '4.06';
    
if ($VERSION != $Devel::NYTProf::Core::VERSION) {
    die "$0 version '$VERSION' doesn't match version '$Devel::NYTProf::Core::VERSION' of $INC{'Devel/NYTProf/Core.pm'}\n";
}

use Getopt::Long;
use Carp;

my $opt_out = 'nytprof-merged.out';

GetOptions(
    'out|o=s'   => \$opt_out,
    'help|h'    => \&usage,
    'verbose|v' => \my $opt_verbose,
) or usage();


print "Writing $opt_out\n" if $opt_verbose;
my $out = Devel::NYTProf::FileHandle::open($opt_out, "wb")
    or die "Error opening $opt_out: $!\n";

my $sub_is_anon_in_eval = qr/__ANON__\[\(eval/;

my $next_fid = 1;
my %fid_to_file;
my %file_to_fid;
my %fids = (0 => 0);
# Similar, but with all evals folded too
my %fids_folded = (0 => 0);

my %eval_to_fid;

my $version;
my %seen_subs;
my %callers;
my %map_range;

my @pending_fids;
my %pending_subs;

sub _write_time_block_or_line {
    my ($tag, $ticks, $fid, $line, $block_line, $sub_line) = @_;

    confess("No mapping for $fid") unless defined $fids{$fid};
    $fid = $fids{$fid};
    # Is this a subroutine (re)defined in an eval?
    my $mapped_fid = $map_range{$fid}[$line];
    $fid = $mapped_fid if defined $mapped_fid;

    # XXX overflow isn't passed in or through
    if ($tag eq 'TIME_LINE') {
	$out->write_time_line($ticks, 0, $fid, $line);
    } else {
	$out->write_time_block($ticks, 0, $fid, $line, $block_line, $sub_line);
    }
}

# Croak if any of these attributes differ between profiles
my %identical = map {$_, 1}
    qw (PL_perldb clock_id nv_size perl_version
	ticks_per_sec xs_version);

# Effectively, these are global variables. Sorry.
my $input;
my %attributes;
my $deflating;

my %dispatcher =
    (
     '' => sub {
	 die "Unknown tag '$_[0]' in $input\n";
     },
     VERSION => sub {
	 my (undef, $major, $minor) = @_;
	 my $this_version = "$major $minor";
	 if($version) {
	     die "Incompatible version '$this_version' in $input, expected '$version'"
		 unless $this_version eq $version;
	 } else {
	     $version = $this_version;
	     $out->write_header($major, $minor);
	 }
     },
     COMMENT => sub {
	 my (undef, $text) = @_;
	 chomp $text; # Arguably this is a bug in the callback interface.
	 # This isn't true unless we enable compression ourselves, and if we
	 # do that, the low level code will write out a correct comment
	 # automatically.
	 return if $text =~ /\ACompressed at level \d with zlib [0-9.]+\z/;
	 $out->write_comment($text)
     },
     ATTRIBUTE => sub {
	 my (undef, $key, $value) = @_;
	 if ($identical{$key}) {
	     if (exists $attributes{$key}) {
		 if ($attributes{$key} ne $value) {
		     die ("In $input, attribute '$key' has value '$value', which differs from the previous value for that key, '$attributes{$key}'\n");
		 }
	     } else {
		 $attributes{$key} = $value;
		 $out->write_attribute($key, $value);
	     }
	 } else {
	     push @{$attributes{$key}}, $value;
	 }
     },

     START_DEFLATE => sub {
	 if (!$deflating && $out->can('start_deflate_write_tag_comment')) {
	     $out->start_deflate_write_tag_comment;
	     ++$deflating;
	 }
     },

     PID_START => sub {
	 my (undef, $pid, $parent, $time) = @_;
	 $out->write_process_start($pid, $parent, $time);
     },
     PID_END => sub {
	 my (undef, $pid, $time) = @_;
	 $out->write_process_end($pid, $time);
     },

     NEW_FID => sub {
	 my (undef, $fid, $eval_fid, $eval_line, $flags, $size, $mtime, $name) = @_;

	 return unless $pending_fids[$fid];
	 my ($new_fid, $new_eval_fid) = @{$pending_fids[$fid]};

	 $out->write_new_fid($new_fid, $new_eval_fid, $eval_line, $flags,
			     $size, $mtime, $name);
     },
     TIME_BLOCK => \&_write_time_block_or_line,
     TIME_LINE  => \&_write_time_block_or_line,

     DISCOUNT => sub {
	 $out->write_discount();
     },
     SUB_INFO => sub {
	 my (undef, $fid, $first_line, $last_line, $name) = @_;

	 my $output_fid = $pending_subs{"$fid,$first_line,$last_line,$name"};
	 return unless defined $output_fid;

	 $out->write_sub_info($output_fid, $name, $first_line, $last_line);
     },
     SUB_CALLERS => sub {
	 my (undef, $fid, $line, $count, $incl_time, $excl_time, $reci_time, $rec_depth, $called, $caller) = @_;
	 confess("No mapping for $fid") unless defined $fids{$fid};
	 $fid = $fids{$fid};
	 my $mapped_fid = $map_range{$fid}[$line];
	 $fid = $mapped_fid if defined $mapped_fid;

	 if ($callers{"$fid,$line"}{$called}{$caller}) {
	     my $sum = $callers{"$fid,$line"}{$called}{$caller};
	     $sum->{count} += $count;
	     $sum->{incl} += $incl_time;
	     $sum->{excl} += $excl_time;
	     $sum->{reci} += $reci_time;
	     $sum->{depth} = $rec_depth if $rec_depth > $sum->{depth};
	 } else {
	     # New;
	     $callers{"$fid,$line"}{$called}{$caller} =
		 {
		  depth => $rec_depth,
		  count => $count,
		  incl => $incl_time,
		  excl => $excl_time,
		  reci => $reci_time,
		 };
	 }
     },
     SRC_LINE => sub {
	 my (undef, $fid, $line, $text) = @_;
	 confess("No mapping for $fid") unless defined $fids{$fid};
	 $fid = $fids{$fid};
	 # Is this a subroutine (re)defined in an eval?
	 my $mapped_fid = $map_range{$fid}[$line];
	 $fid = $mapped_fid if defined $mapped_fid;
	 $out->write_src_line($fid, $line, $text);
     },
    );

foreach $input (@ARGV) {
    print "Reading $input...\n" if $opt_verbose;
    @pending_fids = ();
    %pending_subs = ();

    Devel::NYTProf::Data->new({filename => $input, callback => {
	NEW_FID => sub {
	    my (undef, $fid, $eval_fid, $eval_line, $flags, $size, $mtime, $name) = @_;
	    my ($new_fid, $new_eval_fid);
	    if($eval_fid) {
		# Generally, treat every eval as distinct, even at the same location
		$new_eval_fid = $fids{$eval_fid};
		confess("unknown eval_fid $eval_fid") unless defined $new_eval_fid;

		$new_fid = $next_fid++;
		$fids{$fid} = $new_fid;

		# But also track the first fid to be allocated at that line of the eval
		my $folded_fid = $fids_folded{$eval_fid};
		confess("unknown folded eval_fid $eval_fid") unless defined $folded_fid;

		my $corresponding_eval = $eval_to_fid{"$folded_fid,$eval_line"};
		if (!defined $corresponding_eval) {
		    # Not seen a fid generated in an eval at this location before
		    $eval_to_fid{"$folded_fid,$eval_line"} = $new_fid;
		    $fids_folded{$fid} = $new_fid;
		} else {
		    $fids_folded{$fid} = $corresponding_eval;
		}
	    } else {
		$new_eval_fid = $eval_fid;
		$new_fid = $file_to_fid{$name};

		if(defined $new_fid) {
		    $fids_folded{$fid} = $fids{$fid} = $new_fid;
		    return;
		}

		$new_fid = $next_fid++;
		$fids_folded{$fid} = $fids{$fid} = $new_fid;
		$file_to_fid{$name} = $new_fid;
	    }
	    $fid_to_file{$new_fid} = $name;
	    $pending_fids[$fid] = [$new_fid, $new_eval_fid];
	},
	SUB_INFO => sub {
	    my (undef, $fid, $first_line, $last_line, $name) = @_;
	    my $output_fid;
	    if ($name =~ $sub_is_anon_in_eval) {
		confess("No mapping for $fid") unless defined $fids{$fid};
		$output_fid = $fids{$fid};
		$seen_subs{"$output_fid,$name"} ||= "$first_line,$last_line";
	    } else {
		confess("No mapping for $fid") unless defined $fids_folded{$fid};
		my $folded = $fids_folded{$fid};
		my $seen = $seen_subs{"$folded,$name"};
		if (defined $seen && $seen ne "$first_line,$last_line") {
		    # Warn that we are not folding

		    # Carry on, and output a SUB_INFO block for this fid
		    $output_fid = $fid;
		} else {
		    # This subroutine has be (re)defined in two distinct
		    # evals, but appears to be identical. So for this lines
		    # range in the second eval, treat profiling data as if it
		    # came from the fid of the first eval, so that all calls
		    # to the sub are collated.

		    # Have to use the mapped fid as the key to this hash, as
		    # only the mapped fids are are unique
		    my $mapped_fid = $fids{$fid};
		    $map_range{$mapped_fid}[$_] = $folded
			for $first_line .. $last_line;

		    return if defined $seen;

		    $seen_subs{"$folded,$name"} = "$first_line,$last_line";
		    $output_fid = $folded;
		}
	    }
	    $pending_subs{"$fid,$first_line,$last_line,$name"} = $output_fid;
	}
    }});

    print "Re-reading $input...\n" if $opt_verbose;
    Devel::NYTProf::Data->new({filename => $input, callback => \%dispatcher});
}

print "Finalizing...\n" if $opt_verbose;
# Deterministic order is useful for testing.
foreach my $fid_line (sort keys %callers) {
    my ($fid, $line) = split ',', $fid_line;
    foreach my $called (sort keys %{$callers{$fid_line}}) {
	foreach my $caller (sort keys %{$callers{$fid_line}{$called}}) {
	    my $sum = $callers{$fid_line}{$called}{$caller};
	    $out->write_sub_callers($fid, $line, $caller, $sum->{count},
				    @{$sum}{qw(incl excl reci)},
				    $sum->{depth}, $called);
	}
    }
}

foreach my $key (sort grep {!$identical{$_}} keys %attributes) {
    my @values = @{$attributes{$key}};
    if ($key eq 'basetime') {
	my $value = min(@values);
	$out->write_attribute($key, $value);
    } elsif ($key eq 'application') {
	my %counts;
	$counts{$_}++ foreach @values;
	my @grouped;
	foreach my $prog (sort keys %counts) {
	    my $count = $counts{$prog};
	    push @grouped, $prog;
            $grouped[-1] .= " ($count runs)" if $count > 1;
	}
	my $last = pop @grouped;
	my $value = @grouped ? join (', ', @grouped) . " and $last" : $last;
	$out->write_attribute($key, $value);
    } else {
	warn "Unknown attribute $key\n";
	$out->write_attribute($key, $_) foreach @values;
    }
}

print "Done.\n" if $opt_verbose;
exit 0;

sub usage {
    print <<END;
usage: [perl] nytprofmerge [opts] nytprof-file [...]
 --out <file>,  -o <file>  Name of output file [default: $opt_out]
 --help,        -h         Print this message
 --verbose,     -v         Be more verbose

This script of part of the Devel::NYTProf distribution.
See http://search.cpan.org/dist/Devel-NYTProf/ for details and copyright.
END
    exit 1;
}

__END__

=head1 NAME

nytprofmerge - Reads multiple NYTProf profiles and outputs a merged one

=head1 SYNOPSIS

 $ nytprofmerge --out=nytprof-merged.out nytprof.out.*

 $ nytprofmerge nytprof.out.*

=head1 DESCRIPTION

Reads multiple profile data files generated by Devel::NYTProf and writes out
a new profile data file containing data merged from the original files.

C<nytprofmerge> is likely to produce garbage if the input profiles
aren't all profiles of exactly the same software.

C<nytprofmerge> is new and somewhat experimental. If it produces unexpected
results please produce a I<small> test case that demonstrates the problem and
let us know at L<http://groups.google.com/group/develnytprof-dev> - thanks!

=cut

__END__
:endofperl
