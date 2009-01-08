def with_color(str, fg, bg=49):
    '''Given foreground/background ANSI color codes, return a string that,
    when printed, will format the supplied string using the supplied colors.
    '''
    return "\x1b[%dm\x1b[%dm%s\x1b[39m\x1b[49m" % (fg,bg,str)

def B(str):
    '''Returns a string that, when printed, will display the supplied string
    in ANSI bold.
    '''
    return "\x1b[1m%s\x1b[22m" % str

def r(str): return with_color(str, 31) # Red
def g(str): return with_color(str, 32) # Green
def y(str): return with_color(str, 33) # Yellow
def b(str): return with_color(str, 34) # Blue
def m(str): return with_color(str, 35) # Magenta
def c(str): return with_color(str, 36) # Cyan
def w(str): return with_color(str, 37) # White

#following from Python cookbook, #475186
def has_colors(stream):
    '''Returns boolean indicating whether or not the supplied stream supports
    ANSI color.
    '''
    if not hasattr(stream, "isatty"):
        return False
    if not stream.isatty():
        return False # auto color only on TTYs
    try:
        import curses
        curses.setupterm()
        return curses.tigetnum("colors") > 2
    except:
        # guess false in case of error
        return False
