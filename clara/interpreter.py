'''
Common interpreter stuff
'''

# Python imports
import time

from copy import deepcopy

# clara imports
from .common import UnknownLanguage
from .model import Program, VAR_IN, VAR_OUT, VAR_RET, VAR_COND
from .model import prime, unprime, isprimed


class RuntimeErr(Exception):
    pass


class UndefValue(object):

    def __eq__(self, other):
        return isinstance(other, UndefValue)

    def __repr__(self):
        return '<undef>'

    
def isundef(x):
    return isinstance(x, UndefValue)


class Interpreter(object):

    DEFAULT_RETURN = UndefValue()

    def __init__(self, timeout=5, entryfnc='main'):
        self.timeout = timeout
        self.starttime = None
        self.entryfnc = entryfnc

        self.fnc = None
        self.loc = None

        self.trace = []

        self.prog = None

    def getfnc(self, name):

        return self.prog.getfnc(name)

    def run(self, prog, mem=None, ins=None, args=None, entryfnc=None):

        if not isinstance(prog, Program):
            raise Exception("Expected Program, for '%s'" % (prog,))

        self.prog = prog

        # Get function
        entryfnc = entryfnc or self.entryfnc
        try:
            fnc = prog.getfnc(entryfnc)
        except KeyError:
            raise RuntimeErr("Unknown function: '%s'" % (entryfnc,))

        # Init memory
        if mem is None:
            mem = dict()

        # Init trace
        self.trace = []
        
        # Set inputs
        if ins:
            mem[VAR_IN] = list(ins)
        # Set output
        if VAR_OUT not in mem:
            mem[VAR_OUT] = ''
        # Set var
        mem[VAR_RET] = UndefValue()

        # Init all vars to Undef
        for (var, _) in list(fnc.types.items()):
            if var not in mem:
                mem[var] = UndefValue()

        # Set args for the function
        if args:
            if len(args) != len(fnc.params):
                raise RuntimeErr(
                    "Wrong number of args: expected %s, got %s" % (
                        len(fnc.params), len(args)))
            for (var, t), a in zip(fnc.params, args):
                mem[var] = self.convert(a, t)

        self.starttime = time.time()

        res = self.execute(fnc, mem)
        self.prog = None
        return res

    def execute(self, obj, mem):

        # Check for timeout
        if self.timeout and self.starttime \
           and (time.time() - self.starttime > self.timeout):
            raise RuntimeErr(
                'Timeout (%.3f)' % (round(time.time() - self.starttime, 3),))
        
        # Get name of the object to be executed
        name = obj.__class__.__name__
        meth = getattr(self, 'execute_%s' % (name,))

        try:
            return meth(obj, mem)
        except (OverflowError, ZeroDivisionError, AttributeError,
                TypeError, IndexError, RuntimeError, ValueError, KeyError) as ex:
            raise RuntimeErr("Exception '%s' on execution of '%s'" % (
                ex, obj))
                
    def execute_Function(self, fnc, mem):

        self.fnc = fnc.name
        self.loc = fnc.initloc

        while True:

            # Execute all exprs
            for (var, expr) in fnc.exprs(self.loc):
                
                val = self.execute(expr, mem)
                
                if var == VAR_COND:
                    val = not not val
                    
                varp = prime(var)
                vtype = (fnc.rettype if var == VAR_RET
                         else (fnc.gettype(var) or '*'))
                mem[varp] = self.convert(val, vtype)

                if var == VAR_RET and not isundef(val):
                    break

            # Save memory
            (newmem, mem) = self.procmem(mem)
            self.trace.append((self.fnc, self.loc, mem))
            mem = newmem

            # Check return
            if not isundef(mem.get(VAR_RET, UndefValue())):
                break

            # Find new location
            numtrans = fnc.numtrans(self.loc)
            if numtrans == 0:  # Done
                break
            
            elif numtrans == 1:  # Trivially choose True
                self.loc = fnc.trans(self.loc, True)

            else:
                self.loc = fnc.trans(self.loc, mem.get(VAR_COND))

        return self.trace

    def procmem(self, mem):
        newmem = dict()

        for var, val in list(mem.items()):
            if isprimed(var):
                var = unprime(var)
                newmem[var] = deepcopy(val)
            else:
                varp = prime(var)
                if varp not in mem:
                    newmem[var] = deepcopy(val)
                    mem[varp] = deepcopy(val)

        return newmem, mem

    def execute_Op(self, op, mem):

        if op.name in self.UNARY_OPS:
            if len(op.args) != 1 and op.name not in self.BINARY_OPS:
                raise RuntimeError(
                    "Got <>1 args for binary op in '%s'" % (op,))
            if len(op.args) == 1:
                return self.execute_UnaryOp(op.name, op.args[0], mem)

        if op.name in self.BINARY_OPS:
            if len(op.args) != 2:
                raise RuntimeError(
                    "Got <>2 args for binary op in '%s'" % (op,))
            return self.execute_BinaryOp(op.name, op.args[0], op.args[1], mem)

        if op.name == '[]':
            return self.execute_ArrayIndex(op, mem)
                
        meth = getattr(self, 'execute_%s' % (op.name,))
        return meth(op, mem)

    def execute_Var(self, v, mem):
        return mem.get(v.tostr(), UndefValue())

    def execute_ListHead(self, l, mem):

        t = l.args[0].value
        l = self.execute(l.args[1], mem)

        if isinstance(l, list):
            if len(l) > 0:
                return self.convert(l[0], t)
            elif len(l) == 0:
                return UndefValue()

        raise RuntimeErr("ListHead on '%s'" % (l,))

    def execute_ListTail(self, l, mem):

        l = self.execute(l.args[0], mem)

        if isinstance(l, list):
            if len(l) > 0:
                return list(l[1:])
            elif len(l) == 0:
                return []

        raise RuntimeErr("ListTail on '%s'" % (l,))

    def execute_StrAppend(self, a, mem):

        return ''.join([str(self.execute(x, mem)) for x in a.args])

    def execute_StrFormat(self, f, mem):

        fmt = self.execute(f.args[0], mem)
        if not isinstance(fmt, str):
            raise RuntimeErr("Expected 'str' for format, got '%s'" % (fmt,))
        
        args = [self.execute(x, mem) for x in f.args[1:]]

        return fmt % tuple(args)

    def execute_ite(self, ite, mem):

        cond = not not self.execute(ite.args[0], mem)

        if cond:
            return self.execute(ite.args[1], mem)
        else:
            return self.execute(ite.args[2], mem)

    def execute_FuncCall(self, f, mem):
        name = f.args[0].name
        try:
            fnc = self.getfnc(name)
        except KeyError:
            raise RuntimeErr("Unknown function: '%s'" % (name,))

        args = [self.execute(x, mem) for x in f.args[1:]]

        newmem = {
            VAR_IN: mem.get(VAR_IN, UndefValue()),
            VAR_OUT: mem.get(VAR_OUT, UndefValue()),
        }

        if len(fnc.params) != len(args):
            raise RuntimeErr("Wrong number of args: expected %s, got %s" % (
                len(fnc.params), len(args)
            ))
        for (var, _), arg in zip(fnc.params, args):
            newmem[var] = deepcopy(arg)

        oldfnc = self.fnc
        oldloc = self.loc
        trace = self.execute(fnc, newmem)
        self.fnc = oldfnc
        self.loc = oldloc
        
        return trace[-1][2].get(prime(VAR_RET), self.DEFAULT_RETURN)

        
INTERPRETERS = {}


def addlanginter(lang, inter):
    INTERPRETERS[lang] = inter


def getlanginter(lang):
    if lang in INTERPRETERS:
        return INTERPRETERS[lang]
    raise UnknownLanguage("No interpreter for language: '%s'" % (lang,))
