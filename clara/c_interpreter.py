'''
C interpreter
'''

# Python imports
import math
import sys

# clara imports
from .interpreter import Interpreter, addlanginter, RuntimeErr, UndefValue


def libcall(*args):
    '''
    Decorator for library calls
    - args is a list of types of arguments
    '''

    def dec(fun):  # fun - is an original function to call

        # Wrapper instead of real function (calls real function inside)
        def wrap(self, f, mem):
            
            # First check number of arguments
            if len(args) != len(f.args):
                raise RuntimeErr("Expected '%d' args in '%s', got '%d'" % (
                    len(args), f.name, len(f.args)))
            
            # Evaluate args
            fargs = [self.execute(x, mem) for x in f.args]

            # Convert args
            nargs = []
            for a, t in zip(fargs, args):
                nargs.append(self.convert(a, t))

            # Call original function
            return fun(self, *nargs)
                
        return wrap
    
    return dec


class CInterpreter(Interpreter):

    BINARY_OPS = {'+', '-', '*', '/', '%', '<', '<=', '>', '>=', '==', '!=',
                  '^', '&', '!', '&&', '||'}

    UNARY_OPS = {'!', '-', '+'}

    def execute_Const(self, c, mem):

        # Undef
        if c.value == '?':
            return UndefValue

        # EOF
        if c.value == 'EOF':
            return -1

        # String
        if len(c.value) >= 2 and c.value[0] == c.value[-1] == '"':
            return str(c.value[1:-1])

        # Char
        if len(c.value) >= 3 and c.value[0] == c.value[-1] == "'":
            try:
                ch = c.value[1:-1].decode('string_escape')
                if len(ch) == 1:
                    return ord(ch)
            except ValueError:
                pass
            
        # Integer
        try:
            return int(c.value)
        except ValueError:
            pass

        # Float
        try:
            return float(c.value)
        except ValueError:
            pass

        assert False, 'Unknown constant: %s' % (c.value,)

    def execute_UnaryOp(self, op, x, mem):

        x = self.tonumeric(self.execute(x, mem))

        if op == '-':
            res = -x
        elif op == '+':
            res = +x
        elif op == '!':
            res = not x
        else:
            assert False, "Unknown unary op: '%s'" % (op,)

        return self.tonumeric(res)

    def execute_BinaryOp(self, op, x, y, mem):

        x = self.tonumeric(self.execute(x, mem))

        # Special case for short-circut
        if op in ['&&', '||']:

            if op == '||' and x:
                return x

            if op == '&&' and (not x):
                return 0
                
            return self.tonumeric(self.execute(y, mem))

        y = self.tonumeric(self.execute(y, mem))

        x, y = self.togreater(x, y)
        
        if op == '+':
            res = x + y
        elif op == '-':
            res = x - y
        elif op == '*':
            res = x * y
        elif op == '/':
            res = x / y
        elif op == '%':
            res = x % y
        elif op == '==':
            res = x == y
        elif op == '!=':
            res = x != y
        elif op == '<':
            res = x < y
        elif op == '<=':
            res = x <= y
        elif op == '>':
            res = x > y
        elif op == '>=':
            res = x >= y
        elif op == '^':
            res = x ^ y
        elif op == '&':
            res = x & y
        elif op == '|':
            res = x | y
        else:
            assert False, 'Unknown binary op: %s' % (op,)

        return res

    def execute_cast(self, c, mem):

        t = c.args[0].value
        x = self.execute(c.args[1], mem)

        return self.convert(x, t)

    def execute_ArrayCreate(self, ac, mem):
        x = int(self.tonumeric(self.execute(ac.args[0], mem)))
        return [None for _ in range(x)]

    def execute_ArrayInit(self, ai, mem):
        return [self.execute(x, mem) for x in ai.args]

    def execute_ArrayAssign(self, aa, mem):

        a = self.execute(aa.args[0], mem)
        if not isinstance(a, list):
            raise RuntimeErr("Expected 'list', got '%s'" % (a,))
        a = list(a)
        
        i = int(self.tonumeric(self.execute(aa.args[1], mem)))
        if i < 0 or i >= len(a):
            raise RuntimeErr("Array index out of bounds: %d" % (i,))

        v = self.execute(aa.args[2], mem)

        a[i] = v

        return a

    def execute_ArrayIndex(self, ai, mem):

        a = self.execute(ai.args[0], mem)
        if not isinstance(a, list):
            raise RuntimeErr("Expected 'list', for '%s'" % (a,))
        
        i = int(self.tonumeric(self.execute(ai.args[1], mem)))
        if i < 0 or i >= len(a):
            raise RuntimeErr("Array index out of bounds: %d" % (i,))

        return a[i]

    @libcall('float')
    def execute_floor(self, x):
        return math.floor(x)

    @libcall('float')
    def execute_ceil(self, x):
        return math.ceil(x)

    @libcall('float', 'float')
    def execute_pow(self, x, y):
        return math.pow(x, y)

    @libcall('float')
    def execute_sqrt(self, x):
        return math.sqrt(x)

    @libcall('float')
    def execute_log(self, x):
        return math.log(x)

    @libcall('float')
    def execute_abs(self, x):
        return abs(x)

    @libcall('float')
    def execute_log2(self, x):
        return math.log(x, 2)

    @libcall('float')
    def execute_log10(self, x):
        return math.log(x, 10)

    @libcall('float')
    def execute_exp(self, x):
        return math.exp(x)

    def execute_scanf(self, f, mem):
        return sum(map(lambda x: len(str(x)), filter(lambda x: not isinstance(x, UndefValue), [self.execute_Var(arg, mem) for arg in f.args])))

    def tonumeric(self, v):

        if v in [True, False]:
            return 1 if v else 0

        if not isinstance(v, (int, float)):
            raise RuntimeErr("Non-numeric value: '%s'" % (v,))

        return v

    def togreater(self, x, y):

        if isinstance(x, float):
            return x, float(y)

        if isinstance(y, float):
            return float(x), y

        return x, y

    def convert(self, val, t):

        if isinstance(val, UndefValue):
            return val

        if t == 'int':
            if val in [True, False]:
                val = 1 if val else 0
            return int(val)

        if t == 'float':
            if val in [True, False]:
                val = 1.0 if val else 0.0
            return float(val)

        if t == 'char':
            if val in [True, False]:
                val = 1 if val else 0
            return int(val) % 128

        if t.endswith('[]'):
            st = t[:-2]
            if isinstance(val, list):
                return [x if x is None else self.convert(x, st) for x in val]
            raise RuntimeErr("Expected list, got '%s'" % (val,))

        return val

addlanginter('c', CInterpreter)
