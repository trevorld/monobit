"""
monobit.operations - manipulate glyphs

(c) 2019 Rob Hagemans
licence: https://opensource.org/licenses/MIT
"""


def mirror(glyphs):
    """Reverse pixels horizontally."""
    return {
        _key: [_row[::-1] for _row in _char]
        for _key, _char in glyphs.items()
    }

def flip(glyphs):
    """Reverse pixels vertically."""
    return {
        _key: _char[::-1]
        for _key, _char in glyphs.items()
    }

def transpose(glyphs):
    """Transpose glyphs."""
    return {
        _key: [list(_x) for _x in zip(*_char)]
        for _key, _char in glyphs.items()
    }

def rotate(glyphs, turns):
    """Rotate by 90-degree turns; positive is clockwise."""
    turns %= 4
    if turns == 3:
        return flip(transpose(glyphs))
    elif turns == 2:
        return flip(mirror(glyphs))
    elif turns == 1:
        return mirror(transpose(glyphs))
    return glyphs

def invert(glyphs):
    """Reverse video."""
    return {
        _key: [[(not _col) for _col in _row] for _row in _char]
        for _key, _char in glyphs.items()
    }

def crop(glyphs, left=0, top=0, right=0, bottom=0):
    """Crop glyphs, inclusive bounds."""
    return {
        _key: [
            _row[left : (-right if right else None)]
            for _row in _char[top : (-bottom if bottom else None)]
        ]
        for _key, _char in glyphs.items()
    }

def expand(glyphs, left=0, top=0, right=0, bottom=0):
    """Add empty space."""
    return {
        _key: (
            [[False] * (left + len(_char[0]) + right)] * top
            + [
                [False] * left + _row + [False] * right
                for _row in _char
            ]
            + [[False] * (left + len(_char[0]) + right)] * bottom
        )
        for _key, _char in glyphs.items()
    }

def stretch(glyphs, factor_x=1, factor_y=1):
    """Repeat rows and/or columns."""
    # vertical stretch
    glyphs = {
        _key: [_row for _row in _char for _ in range(factor_y)]
        for _key, _char in glyphs.items()
    }
    # horizontal stretch
    glyphs = {
        _key: [
            [_col for _col in _row for _ in range(factor_x)]
            for _row in _char
        ]
        for _key, _char in glyphs.items()
    }
    return glyphs

def shrink(glyphs, factor_x=1, factor_y=1, force=False):
    """Remove rows and/or columns."""
    # vertical shrink
    shrunk_glyphs = {
        _key: _char[::factor_y]
        for _key, _char in glyphs.items()
    }
    if not force:
        # check we're not throwing away stuff
        for offs in range(1, factor_y):
            alt = {
                _key: _char[offs::factor_y]
                for _key, _char in glyphs.items()
            }
            if shrunk_glyphs != alt:
                nomatch = [
                    hex(_key) for _key, _glyph in shrunk_glyphs.items()
                    if _glyph != alt[_key]
                ]
                raise ValueError("can't shrink without loss: {}".format(nomatch))
    # horizontal stretch
    glyphs = {
        _key: [_row[::factor_x] for _row in _char]
        for _key, _char in shrunk_glyphs.items()
    }
    return glyphs