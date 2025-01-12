"""
monobit.figlet - FIGlet .flf format

(c) 2021 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""

import logging
from typing import NamedTuple

from ..matrix import to_text
from ..storage import loaders, savers
from ..streams import FileFormatError
from ..font import Font
from ..glyph import Glyph
from ..struct import Props, reverse_dict
from ..taggers import extend_string, tagmaps
from ..label import Codepoint


# note that we won't be able to use the "subcharacters" that are the defining feature of FIGlet
# as we only work with monochrome bitmaps



##############################################################################
# interface


@loaders.register('flf', magic=(b'flf2a',), name='figlet')
def load_flf(instream, where=None, *, ink:str=''):
    """Load font from a FIGlet .flf file."""
    flf_glyphs, flf_props, comments = _read_flf(instream.text, ink=ink)
    logging.info('figlet properties:')
    for line in str(flf_props).splitlines():
        logging.info('    ' + line)
    glyphs, props = _convert_from_flf(flf_glyphs, flf_props)
    logging.info('yaff properties:')
    for line in str(props).splitlines():
        logging.info('    ' + line)
    return Font(glyphs, properties=vars(props), comments=comments)

@savers.register(linked=load_flf)
def save_flf(fonts, outstream, where=None):
    """Write fonts to a FIGlet .flf file."""
    if len(fonts) > 1:
        raise FileFormatError('Can only save one font to .flf file.')
    font, = fonts
    flf_glyphs, flf_props, comments = _convert_to_flf(font)
    logging.info('figlet properties:')
    for line in str(flf_props).splitlines():
        logging.info('    ' + line)
    _write_flf(outstream.text, flf_glyphs, flf_props, comments)


##############################################################################
# structure definitions

_ENCODING = 'unicode'
_CODEPOINTS = list(range(32, 127)) + [196, 214, 220, 228, 246, 252, 223]

_DIRECTIONS = {
    '0': 'left-to-right',
    '1': 'right-to-left'
}

_SIGNATURE = 'flf2a'

# http://www.jave.de/docs/figfont.txt
#
# >          flf2a$ 6 5 20 15 3 0 143 229    NOTE: The first five characters in
# >            |  | | | |  |  | |  |   |     the entire file must be "flf2a".
# >           /  /  | | |  |  | |  |   \
# >  Signature  /  /  | |  |  | |   \   Codetag_Count
# >    Hardblank  /  /  |  |  |  \   Full_Layout*
# >         Height  /   |  |   \  Print_Direction
# >         Baseline   /    \   Comment_Lines
# >          Max_Length      Old_Layout*

class _FLF_HEADER(NamedTuple):
    signature_hardblank: str
    height: int
    baseline: int
    max_length: int
    old_layout: int
    comment_lines: int
    print_direction: int = 0
    full_layout: int = 0
    codetag_count: int = 0



##############################################################################
# loader

def _read_flf(instream, ink=None):
    """Read font from a FIGlet .flf file."""
    props = _read_props(instream)
    comments = _read_comments(instream, props)
    glyphs = _read_glyphs(instream, props, ink=ink)
    return glyphs, props, comments

def _read_props(instream):
    """Read .flf property header."""
    header = _FLF_HEADER(*instream.readline().strip().split())
    if not header.signature_hardblank.startswith(_SIGNATURE):
        raise FileFormatError('Not a FIGlet .flf file: does not start with `flf2a` signature.')
    return Props(
        hardblank = header.signature_hardblank[-1],
        **header._asdict()
    )

def _read_comments(instream, props):
    """Parse comments at start."""
    return '\n'.join(
        line.rstrip()
        for _, line in zip(range(int(props.comment_lines)), instream)
    )

def _read_glyphs(instream, props, ink=''):
    """Parse glyphs."""
    # glyphs in default repertoire
    glyphs = [_read_glyph(instream, props, codepoint=_i) for _i in _CODEPOINTS]
    # code-tagged glyphs
    for line in instream:
        line = line.rstrip()
        # codepoint, unicode name label
        codepoint, _, tag = line.partition(' ')
        glyphs.append(_read_glyph(instream, props, codepoint=int(codepoint, 0), tag=tag, ink=ink))
    return glyphs

def _read_glyph(instream, props, codepoint, tag='', ink=''):
    glyph_lines = [_line.rstrip() for _, _line, in zip(range(int(props.height)), instream)]
    # > In most FIGfonts, the endmark character is either "@" or "#".  The FIGdriver
    # > will eliminate the last block of consecutive equal characters from each line
    # > of sub-characters when the font is read in.  By convention, the last line of
    # > a FIGcharacter has two endmarks, while all the rest have one. This makes it
    # > easy to see where FIGcharacters begin and end.  No line should have more
    # > than two endmarks.
    glyph_lines = [_line.rstrip(_line[-1]) for _line in glyph_lines]
    # check number of characters excluding spaces
    paper = [' ', props.hardblank]
    charset = set(''.join(glyph_lines)) - set(paper)
    # if multiple characters per glyph found, ink characters must be specified explicitly
    if len(charset) > 1:
        if not ink:
            raise FileFormatError(
                'Multiple ink characters not supported: '
                f'encountered {list(charset)}.'
            )
        else:
            paper += list(charset - set(ink))
    return Glyph.from_matrix(glyph_lines, paper=paper).modify(
        codepoint=codepoint, tags=[tag]
    )

def _convert_from_flf(glyphs, props):
    """Convert figlet glyphs and properties to monobit."""
    descent = int(props.height)-int(props.baseline)
    properties = Props(
        descent=descent,
        offset=(0, -descent),
        ascent=int(props.baseline),
        direction=_DIRECTIONS[props.print_direction],
        encoding=_ENCODING,
        default_char=0,
    )
    # keep uninterpreted parameters in namespace
    properties.figlet = Props(
        old_layout=props.old_layout,
        full_layout=props.full_layout,
    )
    return glyphs, properties


##############################################################################
# saver

def _convert_to_flf(font, hardblank='$'):
    """Convert monobit glyphs and properties to figlet."""
    # convert to unicode
    font = font.set_properties(encoding=_ENCODING)
    # count glyphs outside the default set
    # we can only encode glyphs that have chars
    # latin-1 codepoints, so we can just use chr()
    flf_chars = tuple(chr(_cp) for _cp in _CODEPOINTS)
    coded_chars = set(font.get_chars()) - set(flf_chars)
    # get length of global comment
    comments = font.get_comments()
    # construct flf properties
    props = Props(
        signature_hardblank=_SIGNATURE + hardblank,
        height=font.pixel_size,
        baseline=font.ascent,
        # > The Max_Length parameter is the maximum length of any line describing a
        # > FIGcharacter.  This is usually the width of the widest FIGcharacter, plus 2
        # > (to accommodate endmarks as described later.)
        max_length=2 + max(_g.advance for _g in font.glyphs),
        # layout parameters - keep to default, there is not much we can sensibly do
        old_layout=0,
        comment_lines=len(comments.splitlines()),
        # > The Print_Direction parameter tells which direction the font is to be
        # > printed by default.  A value of 0 means left-to-right, and 1 means
        # > right-to-left.  If this parameter is absent, 0 (left-to-right) is assumed.
        print_direction=reverse_dict(_DIRECTIONS)[font.direction],
        # layout parameters - keep to default, there is not much we can sensibly do
        full_layout=0,
        codetag_count = len(coded_chars)
    )
    # keep namespace properties
    try:
        figprops = Props.from_str(font.figlet)
    except AttributeError:
        pass
    else:
        try:
            props.old_layout = figprops.old_layout
        except AttributeError as e:
            pass
        try:
            props.full_layout = figprops.full_layout
        except AttributeError as e:
            pass
    # first get glyphs in default repertoire
    # fill missing glyphs with empties
    glyphs = [font.get_glyph(_chr, missing='empty') for _chr in flf_chars]
    # code-tagged glyphs
    glyphs.extend(font.get_glyph(_chr) for _chr in coded_chars)
    # map default glyph to codepoint zero
    # > If a FIGcharacter with code 0 is present, it is treated
    # > specially.  It is a FIGfont's "missing character".  Whenever
    # > the FIGdriver is told to print a character which doesn't exist
    # > in the current FIGfont, it will print FIGcharacter 0.  If there
    # > is no FIGcharacter 0, nothing will be printed.
    glyphs.append(font.get_default_glyph().modify(codepoint=0))
    # expand glyphs by bearings
    glyphs = [
        _g.expand(
            left=max(0, font.offset.x + _g.offset.x),
            bottom=max(0, font.offset.y + _g.offset.y),
            right=max(0, font.tracking + _g.tracking),
            # include leading; ensure glyphs are equal height
            top=max(0, font.line_height - _g.height - max(0, font.offset.y + _g.offset.y)),
        )
        for _g in glyphs
    ]
    return glyphs, props, comments

def _write_flf(outstream, flf_glyphs, flf_props, comments, ink='#', paper=' ', hardblank='$'):
    """Write out a figlet font file."""
    # header
    header = _FLF_HEADER(**vars(flf_props))
    outstream.write(' '.join(str(_elem) for _elem in header) + '\n')
    # global comment
    outstream.write(comments + '\n')
    # use hardblank for space char (first char)
    outstream.write(_format_glyph(flf_glyphs[0], ink=ink, paper=hardblank))
    for glyph in flf_glyphs[1:len(_CODEPOINTS)]:
        outstream.write(_format_glyph(glyph, ink=ink, paper=paper))
    for glyph in flf_glyphs[len(_CODEPOINTS):]:
        tag = glyph.tags[0] if glyph.tags else tagmaps['unicode'].get_tag(glyph)
        outstream.write('{} {}\n'.format(Codepoint(glyph.codepoint), tag))
        outstream.write(_format_glyph(glyph, ink=ink, paper=paper))


def _format_glyph(glyph, ink='#', paper=' ', end='@'):
    lines = [
        f'{_line}{end}'
        for _line in to_text(glyph.as_matrix(), ink=ink, paper=paper).splitlines()
    ]
    if lines:
        lines[-1] += end + '\n'
    return '\n'.join(lines)
