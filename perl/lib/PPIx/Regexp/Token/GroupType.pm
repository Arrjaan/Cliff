=head1 NAME

PPIx::Regexp::Token::GroupType - Represent a grouping parenthesis type.

=head1 SYNOPSIS

 use PPIx::Regexp::Dumper;
 PPIx::Regexp::Dumper->new( 'qr{(?i:foo)}smx' )
     ->print();

=head1 INHERITANCE

C<PPIx::Regexp::Token::GroupType> is a
L<PPIx::Regexp::Token|PPIx::Regexp::Token>.

C<PPIx::Regexp::Token::GroupType> is the parent of
L<PPIx::Regexp::Token::GroupType::Assertion|PPIx::Regexp::Token::GroupType::Assertion>,
L<PPIx::Regexp::Token::GroupType::BranchReset|PPIx::Regexp::Token::GroupType::BranchReset>,
L<PPIx::Regexp::Token::GroupType::Code|PPIx::Regexp::Token::GroupType::Code>,
L<PPIx::Regexp::Token::GroupType::Modifier|PPIx::Regexp::Token::GroupType::Modifier>,
L<PPIx::Regexp::Token::GroupType::NamedCapture|PPIx::Regexp::Token::GroupType::NamedCapture>,
L<PPIx::Regexp::Token::GroupType::Subexpression|PPIx::Regexp::Token::GroupType::Subexpression>
and
L<PPIx::Regexp::Token::GroupType::Switch|PPIx::Regexp::Token::GroupType::Switch>.

=head1 DESCRIPTION

This class represents any of the magic sequences of characters that can
follow an open parenthesis. This particular class is intended to be
abstract.

=head1 METHODS

This class provides no public methods beyond those provided by its
superclass.

=cut

package PPIx::Regexp::Token::GroupType;

use strict;
use warnings;

use base qw{ PPIx::Regexp::Token };

our $VERSION = '0.021';

# Return true if the token can be quantified, and false otherwise
sub can_be_quantified { return };

=begin comment

sub __PPIX_TOKENIZER__regexp {
    my ( $class, $tokenizer, $character ) = @_;

    return $character eq 'x' ? 1 : 0;
}

=end comment

=cut

1;

__END__

=head1 SUPPORT

Support is by the author. Please file bug reports at
L<http://rt.cpan.org>, or in electronic mail to the author.

=head1 AUTHOR

Thomas R. Wyant, III F<wyant at cpan dot org>

=head1 COPYRIGHT AND LICENSE

Copyright (C) 2009-2011 by Thomas R. Wyant, III

This program is free software; you can redistribute it and/or modify it
under the same terms as Perl 5.10.0. For more details, see the full text
of the licenses in the directory LICENSES.

This program is distributed in the hope that it will be useful, but
without any warranty; without even the implied warranty of
merchantability or fitness for a particular purpose.

=cut

# ex: set textwidth=72 :
