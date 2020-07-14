'''
Python parser
'''

# Python imports
import ast

from itertools import chain

# clara lib imports
from .model import Var, Const, Op, Expr, VAR_RET, VAR_OUT
from .parser import Parser, ParseError, addlangparser, NotSupported, ParseError


class PyParser(Parser):

    # Supported methods with side effects.
    # These are allowed as standalone expressions.
    # During parsing, we currently can't check for types,
    # so this is done in the interpreter.
    ATTR_FNCS = ['append', 'extend', 'insert', 'remove', 'pop', 'sort',
                 'reverse', 'clear', 'popitem', 'update']
    BUILTIN_FNCS = [
        'input', 'float', 'int', 'bool', 'str', 'list', 'dict',
        'set', 'tuple', 'round', 'pow', 'sum', 'range', 'xrange', 'len',
        'reversed', 'enumerate', 'abs', 'max', 'min', 'type', 'zip', 'map',
        'isinstance']
    UNSUPPORTED_BUILTIN_FNCS = ['eval', 'iter']
    CONSTS = ['True', 'False', 'None', 'list', 'tuple', 'int', 'dict',
              'float', 'bool']
    MODULE_NAMES = ['math', 'string', 'm']

    NOTOP = 'Not'
    OROP = 'Or'
    ANDOP = 'And'

    BOUND_VARS = []

    def __init__(self, *args, **kwargs):
        super(PyParser, self).__init__(*args, **kwargs)
        
        self.hiddenvarcnt = 0

    def parse(self, code):

        # Get AST
        try:
            pyast = ast.parse(code, mode='exec')
        except (SyntaxError, IndentationError) as e:
            raise ParseError(str(e))
        
        self.visit(pyast)

    def visit_Module(self, node):
        '''
        Creates functions from a module
        '''
        funcdefs = list([x for x in node.body if isinstance(x, ast.FunctionDef)])
        for func in funcdefs:

            args = [(arg.arg, '*') for arg in func.args.args]
            self.addfnc(func.name, args, '*')
            
            for arg, t in args:
                self.addtype(arg, t)

            self.addloc(
                desc="around the beginning of function '%s'" % func.name)
                
            for b in func.body:
                self.visit(b)

            self.endfnc()

    # Methods for visiting literals

    def visit_Constant(self, node):
        if isinstance(node.value, str):
            return self.visit(node, "Str")
        elif isinstance(node.value, bytes):
            return self.visit(node, "Bytes")
        elif isinstance(node.value, bool):
            return self.visit(node, "NameConstant")
        elif node.value is Ellipsis:
            return self.visit(node, "Ellipsis")
        elif isinstance(node.value, (int, float)):
            return self.visit(node, "Num")
        else:
            raise NotSupported("Unimplemented Constant visitor for '%s'" % (node.value,))

    def visit_Num(self, node):
        if type(node.n) in (int, float, int, complex):
            return Const(str(node.n), line=node.lineno)
        else:
            raise NotSupported(
                'Type {} not supported'.format(type(node.n).__name__),
                line=node.lineno)

    def visit_Str(self, node):
        return Const('"{}"'.format(node.s), line=node.lineno)

    def visit_List(self, node):
        elts = list(map(self.visit_expr, node.elts))
        return Op('ListInit', *elts, line=node.lineno)

    def visit_Set(self, node):
        elts = list(map(self.visit_expr, node.elts))
        return Op('SetInit', *elts, line=node.lineno)

    def visit_Dict(self, node):
        keys = list(map(self.visit_expr, node.keys))
        vals = list(map(self.visit_expr, node.values))
        args = list(chain(*list(zip(keys, vals))))
        return Op('DictInit', *args, line=node.lineno)

    def visit_Tuple(self, node):
        elts = list(map(self.visit, node.elts))
        return Op('TupleInit', *elts, line=node.lineno)

    # Methods for Variables

    def visit_Name(self, node):
        try:
            bindx = self.BOUND_VARS.index(node.id)
            return Op('BoundVar', Const(str(bindx)), line=node.lineno)
        except ValueError:
            pass
        if node.id in self.CONSTS and not self.hasvar(node.id):
            return Const(node.id)
        if (node.id not in self.MODULE_NAMES):
            #and not self.isfncname(node.id)):
            self.addtype(node.id, '*')
        return Var(node.id)

    # Methods for Expressions

    def visit_Expr(self, node):
        '''
        Expressions need to be handled depending on their type.
        Method calls like str.lower() can be ignored
        (Strings are immutable), while
        calls like list.append() must be handled.
        '''
        if isinstance(node.value, ast.Call):
            if isinstance(node.value.func, ast.Name):
                self.warns.append('Ignored call to {} at line {}'.format(
                    node.value.func.id, node.lineno))
                
            elif isinstance(node.value.func, ast.Attribute):
                if node.value.func.attr in self.ATTR_FNCS:
                    call = self.visit_expr(node.value)
                    
                    if isinstance(call, Op) and call.name == 'ignore_none':
                        call = call.args[0]
                        
                    if isinstance(node.value.func.value, ast.Subscript):
                        var = self.visit_expr(node.value.func.value.value)
                        index = self.visit_expr(node.value.func.value.slice)
                        expr = Op('AssignElement', var, index, call,
                                  line=node.lineno)
                        if isinstance(var, Var):
                            self.addexpr(var.name, expr)
                        else:
                            raise NotSupported("Non-name element assignment",
                                               line=node.lineno)
                        
                    elif isinstance(node.value.func.value, ast.Name):
                        var = self.visit(node.value.func.value)
                        if isinstance(var, Var):
                            # Skip assignment of 'pop' function
                            if node.value.func.attr != 'pop':
                                self.addexpr(var.name, call)
                        else:
                            raise NotSupported("Non-name call",
                                               line=node.lineno)
                        
                    else:
                        raise NotSupported(
                            'Call to {}'.format(
                                node.value.func.__class__.__name__),
                            line=node.lineno)
                else:
                    self.warns.append('Ignored call to {} at line {}'.format(
                        node.value.func.attr, node.lineno))
            else:
                raise NotSupported(
                    'Call to {}'.format(
                        node.value.func.__class__.__name__),
                    line=node.lineno)

        elif isinstance(node.value, (ast.Num, ast.Str, ast.List, ast.Tuple,
                                     ast.Dict)):
            # Happily ignore these side-effect free statements
            pass
        else:
            self.warns.append('Ignored Expr of type {} at line {}'.format(
                node.value.__class__.__name__, node.lineno))

    def visit_BoolOp(self, node):
        func = node.op.__class__.__name__
        val_model = list(map(self.visit_expr, node.values))

        expr = Op(func, val_model[0], val_model[1], line=val_model[1].line)

        for v in val_model[2:]:
            expr = Op(func, expr, v, line=v.line)

        return expr

    def visit_BinOp(self, node):
        func = node.op.__class__.__name__
        left = self.visit_expr(node.left)
        right = self.visit_expr(node.right)

        return Op(func, left, right, line=node.lineno)

    def visit_UnaryOp(self, node):
        func = node.op.__class__.__name__
        operand = self.visit(node.operand)

        return Op(func, operand, line=node.lineno)

    def visit_Compare(self, node):
        comps_model = list(map(self.visit, node.comparators))
        ops_model = [x.__class__.__name__ for x in node.ops]

        left = self.visit_expr(node.left)
        right = comps_model[0]
        op = ops_model[0]

        expr = Op(op, left, right, line=right.line)

        left = right
        for op, right in zip(ops_model[1:], comps_model[1:]):
            expr = Op('And', expr, Op(op, left, right, line=right.line),
                      line=right.line)
            left = right

        return expr

    def visit_IfExp(self, node):
        test_model = self.visit_expr(node.test)
        body_model = self.visit_expr(node.body)
        else_model = self.visit_expr(node.orelse)

        return Op('ite', test_model, body_model, else_model, line=node.lineno)

    def visit_Attribute(self, node):
        value = self.visit(node.value)
        return Op('GetAttr', value, Const(node.attr), line=node.lineno)

    def visit_Assert(self, node):
        pass

    # Methods for Subscripts

    def visit_Slice(self, node):
        args = []
        if node.lower is None:
            args.append(Const('None'))
        else:
            args.append(self.visit_expr(node.lower))
        if node.upper is None:
            args.append(Const('None'))
        else:
            args.append(self.visit_expr(node.upper))
        if node.step is None:
            args.append(Const('None'))
        else:
            args.append(self.visit_expr(node.step))
        return Op('Slice', *args)

    def visit_ExtSlice(self, node):
        dims = list(map(self.visit_expr, node.dims))
        return Op('TupleInit', *dims)

    def visit_Subscript(self, node):
        val = self.visit_expr(node.value)
        return Op('GetElement', val, self.visit_expr(node.slice),
                  line=node.lineno)

    def visit_Index(self, node):
        return self.visit(node.value)

    # Methods for Statements

    def visit_list(self, node):
        for child in node:
            self.visit(child)

    def visit_Delete(self, node):
        if len(node.targets) > 1:
            raise NotSupported('Multiple delete targets')
        target = self.visit(node.targets[0])

        if isinstance(target, Op):
            if target.name == 'GetElement':
                if isinstance(target.args[0], Var):
                    if len(target.args) != 2:
                        raise NotSupported('Delete target with %d args' % (
                            len(target.args,)))
                    delexpr = Op('Delete', *target.args, line=node.lineno)
                    self.addexpr(target.args[0].name, delexpr)
                else:
                    raise NotSupported('Delete target not Var, but %s' % (
                        target.args[0].__class__
                    ))
            else:
                raise NotSupported('Delete target op: %s' % (target.name,))
        else:
            raise NotSupported('Delete target: %s' % (target.__class__,))
    
    def visit_Assign(self, node):
        if len(node.targets) != 1:
            raise NotSupported('Only single assignments allowed')
        
        target = node.targets[0]

        right = self.visit_expr(node.value)

        # Assignment to a variable
        if isinstance(target, ast.Name):
            self.addtype(target.id, '*')
            self.addexpr(target.id, right)

        # Assignment to indexed element
        elif isinstance(target, ast.Subscript):
            if isinstance(target.slice, ast.Index):
                var = Var(target.value.id)
                self.addtype(target.value.id, '*')
                index = self.visit_expr(target.slice.value)
                
                self.addexpr(target.value.id,
                             Op('AssignElement', var, index, right,
                                line=right.line))
                
            else:
                raise NotSupported(
                    'Subscript assignments only allowed to Indices',
                    line=node.lineno)

        # Assignment to a tuple
        elif isinstance(target, ast.Tuple):
            targets = list(map(self.visit_expr, target.elts))
            for i, target in enumerate(targets):
                expr = Op('GetElement', right.copy(), Const(str(i)),
                          line=right.line)
                if isinstance(target, Var):
                    self.addexpr(target.name, expr)
                else:
                    raise NotSupported("Tuple non-var assignment",
                                       line=target.line)
                
        else:
            raise NotSupported(
                'Assignments to {} not supported'.format(
                    target.__class__.__name__),
                line=node.lineno)

    def visit_AugAssign(self, node):

        op = node.op.__class__.__name__

        # For some reason concatenation of lists and tuples works in Python
        # if it is done with += instead of +, so hacking this distinction
        if op == 'Add':
            op = 'AssAdd'
        
        # Aug assign to a name
        if isinstance(node.target, ast.Name):
            target = Var(node.target.id)
            self.addtype(node.target.id, '*')
            value = self.visit_expr(node.value)
            rhs = Op(op, target, value,
                     line=node.lineno)
            self.addexpr(target.name, rhs)

        # Aug assign to a index
        elif isinstance(node.target, ast.Subscript):
            if isinstance(node.target.slice, ast.Index):
                var = Var(node.target.value.id)
                right = self.visit_expr(node.value)
                index = self.visit_expr(node.target.slice.value)
                rhs = Op(op, self.visit(node.target),
                         right, line=node.lineno)
                self.addexpr(var.name, Op('AssignElement', var, index, rhs,
                                          line=node.lineno))
                
            else:
                raise NotSupported(
                    'Subscript assignments only allowed to Indices',
                    line=node.lineno)
        else:
            raise NotSupported(
                'Assignments to {} not supported'.format(
                    node.target.__class__.__name__),
                line=node.lineno)

    def visit_Print(self, node):
        '''
        Only used in Python 2.x, ignores destination and newline
        '''
        values_model = list(map(self.visit_expr, node.values))
        expr = Op('StrAppend', Var(VAR_OUT), *values_model, line=node.lineno)
        self.addexpr(VAR_OUT, expr)
    
    def visit_Call(self, node):
        if len(node.keywords) > 0:
            raise NotSupported(
                'keyword arguments not supported',
                line=node.lineno)

        if isinstance(node.func, ast.Name):
            if node.func.id in self.BUILTIN_FNCS:
                fncname = node.func.id
                args = list(map(self.visit_expr, node.args))
                return Op(fncname, *args, line=node.lineno)
            elif node.func.id in self.UNSUPPORTED_BUILTIN_FNCS:
                raise NotSupported("builtin: '%s'" % (node.func.id,))
            else:
                fnc = Var(node.func.id)
                args = list(map(self.visit_expr, node.args))
                return Op('FuncCall', fnc, *args, line=node.lineno)

        elif isinstance(node.func, ast.Num):
            num = self.visit_expr(node.func)
            self.addwarn("Call to a number '%s' on line %s ignored",
                         num, num.line)
            return Const('?')

        elif isinstance(node.func, ast.Attribute):            
            attr = node.func.attr
            val = self.visit_expr(node.func.value)
            args = list(map(self.visit_expr, node.args))
            if (isinstance(val, Var) and val.name in self.MODULE_NAMES
                and not self.hasvar(val.name)):

                # A bit of hack...
                if val.name == 'm':
                    val.name = 'math'
                    
                return Op('%s_%s' % (val, attr), *args, line=node.lineno)
            if attr == 'pop':
                if isinstance(val, Var):
                    popvar = self.ssavar('pop#')
                    self.addexpr(popvar, Op(attr, val, *args,
                                            line=node.lineno))
                    self.addexpr(val.name, Op('GetElement', Var(popvar),
                                              Const('0')))
                    return Op('GetElement', Var(popvar), Const('1'))
                else:
                    raise NotSupported('Pop to a non-name list')
            elif attr == 'len':
                # we don't distinguish between a.len() and len(a), but the
                # former is a mistake, so we convert it to something that
                # will produce runtime error - this should be handled
                # in some other way
                return Op('attr_len', val, *args, line=node.lineno)

            op = Op(attr, val, *args, line=node.lineno)

            # Results of (side-effect) attr functions are None,
            # so the result should be ignored, but we want to keep it
            # syntatically
            if attr in self.ATTR_FNCS:
                op = Op('ignore_none', op, line=op.line)

            return op
        
        else:
            raise NotSupported(
                'Call of {} not supported'.format(
                    node.func.__class__.__name__),
                line=node.lineno)

    # Methods for Imports

    def visit_Import(self, node):
        '''
        Imports are ignored
        '''
        self.addwarn('Import at line {} ignored'.format(node.lineno))

    def visit_ImportFrom(self, node):
        '''
        Imports are ignored
        '''
        self.addwarn('ImportFrom at line {} ignored'.format(node.lineno))

    def visit_If(self, node):
        self.visit_if(node, node.test, node.body, node.orelse)

    def visit_While(self, node):

        if node.orelse:
            raise NotSupported("While-Else not supported",
                               line=self.getline(node.orelse))
        
        self.visit_loop(node, None, node.test, None, node.body, False, 'while')

    def visit_For(self, node):
        
        if node.orelse:
            raise NotSupported("For-Else not supported",
                               line=self.getline(node.orelse))
        
        # Iterated expression
        it = self.visit_expr(node.iter)

        # Targets of iteration
        if isinstance(node.target, ast.Name):
            self.addtype(node.target.id, '*')
            targets = [self.visit_expr(node.target)]
        elif isinstance(node.target, ast.Tuple):
            for el in node.target.elts:
                if isinstance(el, ast.Name):
                    self.addtype(el.id, '*')
            targets = list(map(self.visit_expr, node.target.elts))
        else:
            raise NotSupported(
                'For loop with {} as target'.format(
                    node.target.__class__.__name__),
                line=node.lineno)

        hiddenvar = self.hiddenvarcnt
        self.hiddenvarcnt += 1

        # Set up the iterated variable
        iter_name = 'iter#{}'.format(hiddenvar)
        it_var = Var(iter_name)
        self.addtype(iter_name, '*')

        # Set up the iteration index
        ind_name = 'ind#{}'.format(hiddenvar)
        ind_var = Var(ind_name)
        self.addtype(ind_name, 'int')

        # Add assignments to iterators
        self.addexpr(it_var.name, it)
        self.addexpr(ind_var.name, Const(str(0), line=node.lineno))

        # Condition is ind_var < len(iter_var)
        cond = Op('Lt', ind_var.copy(), Op('len', it_var.copy()),
                  line=node.iter.lineno)
                  
        # Assignments to iterated variable(s)
        prebody = []
        el = Op('GetElement', it_var.copy(), ind_var.copy(),
                line=node.target.lineno)
        if len(targets) == 1:
            prebody.append((targets[0].name, el.copy()))
        else:
            for i, t in enumerate(targets):
                eli = Op('GetElement', el.copy(), Const(str(i)),
                         line=node.target.lineno)
                prebody.append((t.name, eli))
        
        # Add index variable increment
        prebody.append((ind_var.name,
                        Op('Add', ind_var.copy(), Const(str(1)),
                           line=node.iter.lineno)))

        self.visit_loop(node, None, cond, None, node.body, False, 'for',
                        prebody=prebody)

    def visit_Break(self, node):
        if self.nobcs:
            return
        
        # Find loop
        lastloop = self.lastloop()
        if not lastloop:
            self.addexpr(VAR_RET, Const('break_outside_loop'))
            self.addwarn("'break' outside loop at line %s", node.lineno)
            return

        # Add new location and jump to exit location
        self.hasbcs = True
        preloc = self.loc
        self.loc = self.addloc(
            desc="after 'break' statement at line %s" % (
                node.lineno,))
        self.addtrans(preloc, True, lastloop[1])

    def visit_Continue(self, node):
        if self.nobcs:
            return

        # Find loop
        lastloop = self.lastloop()
        if not lastloop:
            self.addwarn("'continue' outside loop at line %s", node.lineno)
            return

        # Add new location and jump to condition location
        self.hasbcs = True
        preloc = self.loc
        self.loc = self.addloc(
            desc="after 'continue' statement at line %s" % (
                node.lineno,))
        self.addtrans(preloc, True, lastloop[0])

    def visit_Return(self, node):
        if node.value is None:
            ret = Const('None', line=node.lineno)
        else:
            ret = self.visit_expr(node.value)

        self.addexpr(VAR_RET, ret)

    def visit_Pass(self, node):
        pass

    # Comprehension methods

    def visit_GeneratorExp(self, node):
        return self.visit_ListComp(node)
    
    def visit_comprehension(self, node):

        # elt is an expression generating elements
        # generators is a comprehension object

        if len(node.generators) != 1:
            raise NotSupported("Only one generator supported",
                               line=node.lineno)

        gen = node.generators[0]

        iter = self.visit(gen.iter)

        bounds = self.BOUND_VARS
        self.BOUND_VARS = []
        target = self.listofnames(gen.target)
        tlen = Const(str(len(target)))
        self.BOUND_VARS = bounds

        bound_len = len(target)
        self.BOUND_VARS = list(target) + self.BOUND_VARS

        if gen.ifs is None or len(gen.ifs) == 0:
            ifs = Const('True')
        elif len(gen.ifs) == 1:
            ifs = self.visit_expr(gen.ifs[0])
        else:
            raise NotSupported("Comprehension multiple ifs")

        if isinstance(node, ast.DictComp):
            key = self.visit_expr(node.key)
            value = self.visit_expr(node.value)
            op = Op(node.__class__.__name__, tlen, key, value, iter, ifs)
        else:
            elt = self.visit_expr(node.elt)
            op = Op(node.__class__.__name__, tlen, elt, iter, ifs)

        self.BOUND_VARS = self.BOUND_VARS[bound_len:]

        return op

    def visit_ListComp(self, node):
        return self.visit_comprehension(node)
    
        # elt = self.visit_expr(node.elt)

        # if len(node.generators) != 1:
        #     raise NotSupported("Only one generator supported",
        #                        line=node.lineno)
        
        # gen = self.visit_expr(node.generators[0])

        # return Op('ListComp', elt, gen, line=node.lineno)

    def visit_SetComp(self, node):
        return self.visit_comprehension(node)
    
        # elt = self.visit_expr(node.elt)

        # if len(node.generators) != 1:
        #     raise NotSupported("Only one generator supported",
        #                        line=node.lineno)
        
        # gen = self.visit_expr(node.generators[0])

        # return Op('SetComp', elt, gen, line=node.lineno)

    def visit_DictComp(self, node):
        return self.visit_comprehension(node)
    
        # key = self.visit_expr(node.key)
        # value = self.visit_expr(node.value)
        
        # if len(node.generators) != 1:
        #     raise NotSupported("Only one generator supported",
        #                        line=node.lineno)
        
        # gen = self.visit_expr(node.generators[0])

        # return Op('DictComp', key, value, gen, line=node.lineno)

    def visit_Global(self, node):
        # ignore
        pass

    # Auxiliary methods

    def listofnames(self, node):

        if isinstance(node, ast.Name):
            return [node.id]

        if isinstance(node, ast.Tuple):
            names = []
            for arg in node.elts:
                if isinstance(arg, ast.Name):
                    names.append(arg.id)
                else:
                    raise NotSupported("Comprehension: not a list of names")
            return names

        raise NotSupported("Comprehension: not a list of names")
    
    def getline(self, node):
        if isinstance(node, list):
            if len(node):
                return self.getline(node[0])
            else:
                return
        return node.lineno

addlangparser('py', PyParser)
