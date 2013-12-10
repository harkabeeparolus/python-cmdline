import sys
import os, os.path
import cmd, readline
import argparse
import tempfile
import shlex
import subprocess
import time

COMMANDARGS = 'command',
COMMANDKWARGS = {'help': 'command'}

ARGUMENTARGS = 'argument',
ARGUMENTKWARGS = {'help': 'arguments', 'nargs': '*'}

def _mkdo(cbk):
    def do(self, line):
        try:
            split = shlex.split(line)
            args = getattr(Cmdline, cbk + 'parser').parse_args(split)
        except SystemExit:
            return

        # Run command
        self.t0 = time.time()
        getattr(self, 'run_' + cbk)(args)
        if args.time:
            print "%.1f seconds" % (time.time() - self.t0)

        # Flush data to paging temporary file
        self.temp.flush()

        # Ring the bell
        if self.bell:
            print '\a\r',

    return do

def _mkcomplete():
    def complete(self, text, line, begidx, endidx):
        # TODO Option for directories?
        return _filecomp(text, line, begidx)

    return complete

def _filecomp(text, line, begidx):
    def _filetype(direc, e):
        if direc and direc != '/':
            direc = '%s/' % direc
        path = '%s%s' % (direc, e)

        return '%s/' % path if os.path.isdir(os.path.expanduser(path)) else path

    direc = os.path.dirname(text)

    return [_filetype(direc, e)
            for e in os.listdir(os.path.expanduser(direc if direc else '.'))
            if e.startswith(os.path.basename(text))]

class Cmdline(cmd.Cmd):
    def __init__(self, history=False, bell=False, timing=False):
        cmd.Cmd.__init__(self)

        self.bell = bell
        self.timing = timing

        # Create argument parsers and callbacks
        for cbk in [cbk[4:] for cbk in dir(self) if cbk.startswith('run_')]:
            # Create argument parser
            setattr(Cmdline, cbk + 'parser', argparse.ArgumentParser(prog=cbk))
            parser = getattr(Cmdline, cbk + 'parser')
            if self.timing:
                parser.add_argument('-t', '--time', action='store_true',
                                    help="measure time spent in operations")

            # Create help function
            if 'help_' + cbk not in dir(self):
                setattr(Cmdline, 'help_' + cbk,
                        getattr(Cmdline, cbk + 'parser').print_help)

            # Create do function
            setattr(Cmdline, 'do_' + cbk, _mkdo(cbk))

            # Create complete function
            if 'complete_' + cbk not in dir(self):
                setattr(Cmdline, 'complete_' + cbk, _mkcomplete())

        # Set prompt and title
        self.name = self.__class__.__name__.lower()
        self.prompt = self.name + '% '
        self.wintitle()

        # Create directory
        self.directory = os.path.expanduser('~/.%s' % self.name)
        if not os.path.lexists(self.directory):
            os.mkdir(self.directory)

        # Set up base argument parsers
        self.editparser.description = "Edit command line."
        self.editparser.add_argument(*COMMANDARGS, **COMMANDKWARGS)
        self.editparser.add_argument(*ARGUMENTARGS, **ARGUMENTKWARGS)

        self.pageparser.description = "Page output."

        self.EOFparser.description = "Exit. You could also use Ctrl-D."

        # Set page file name
        self.temp = tempfile.NamedTemporaryFile(prefix='page-',
                                                dir=self.directory)

        # History
        self.history = history
        histfile = self.directory + '/histfile'
        if self.history and os.path.exists(histfile):
            readline.read_history_file(histfile)

        # Setup completion
        readline.set_completer_delims(' \t\n')

    def wintitle(self):
        print "\033]0;%s\007\r" % self.name,

    def emptyline(self):
        pass

    def tempreset(self):
        '''
        Reset page temporary file
        '''

        self.temp.seek(0)
        self.temp.truncate()

    def precmd(self, line):

        readline.set_pre_input_hook()

        if self.history:
            readline.write_history_file(self.directory + '/histfile')

        return line

    def loop(self):
        while True:
            try:
                self.cmdloop()
            except KeyboardInterrupt:
                readline.set_pre_input_hook()
                print

    def run_EOF(self, _):
        # For some reason the tempfile isn't closed with the object is detroyed
        self.temp.close()

        print
        sys.exit(0)

    def run_edit(self, args):
        '''
        Edit command line
        '''

        # Open command line in editor
        tmpw = tempfile.NamedTemporaryFile(prefix='edit-', dir=self.directory)
        print >> tmpw, ' '.join([args.command] + args.argument)
        tmpw.flush()
        subprocess.call(['vim', '-n', '+set titlestring=' + self.name,
                         tmpw.name])
        self.wintitle()

        # Read edited command line
        tmpr = open(tmpw.name)
        line = tmpr.read().strip() # Can't cope with any trailing newline

        def hook():
            '''
            Insert text in command line
            '''

            readline.insert_text(line)
            readline.redisplay()

        readline.set_pre_input_hook(hook)

    def complete_edit(self, text, line, begidx, endidx):
        '''
        Complete command for Vim editing
        '''

        return [cmd[3:] for cmd in dir(self)
                if cmd.startswith('do_') and cmd[3:].startswith(text)]

    def run_page(self, args):
        '''
        Page output
        '''

        subprocess.call(['vim', '-n', '+set nowrap titlestring=' + self.name,
                         self.temp.name])
        self.wintitle()
