'''
Common parser stuff
'''

import re

# clara lib imports
from .common import UnknownLanguage
from .model import Program, Function, Expr, Op, Var, Const, VAR_COND, VAR_RET


class NotSupported(Exception):
    '''
    Exception denoting that the code being parsed contains unsupported
    elements.
    '''

    def __init__(self, msg, line=None):
        self.line = line
        super(NotSupported, self).__init__(msg)

        
class ParseError(Exception):
    '''
    Exception denoting that the code cannot be parsed because syntax errors.
    '''

    def __init__(self, msg, line=None):
        super(ParseError, self).__init__(msg)


class Parser(object):
    '''
    Common stuff for parser for any language
    '''

    def __init__(self, optifs=True, postprocess=True, nobcs=False,
                 slice=False):
        
        self.prog = Program()

        self.fncs = {}
        self.fncsl = []
        self.fnc = None
        self.loc = None

        self.optifs = optifs
        self.postproc = postprocess
        self.slice = slice

        self.loops = []

        self.cnt = 0

        self.warns = []

        self.hasbcs = False
        self.nobcs = nobcs

    def newcnt(self):
        self.cnt += 1
        return self.cnt

    def ssavar(self, var):
        return '%s_&%d&' % (var, self.newcnt())

    def addwarn(self, msg, *args):
        if args:
            msg %= args
        self.prog.addwarn(str(msg))

    def rmemptyfncs(self):
        '''
        Removes empty functions, i.e., declarations only
        '''

        for fnc in self.prog.getfncs():
            if fnc.initloc is None:
                self.prog.rmfnc(fnc.name)

    def rmunreachlocs(self, fnc):
        '''
        Removes unreachable locations from the graph
        '''

        visited = set()
        tovisit = [fnc.initloc]

        while len(tovisit) > 0:
            loc = tovisit.pop()
            if loc in visited:
                continue
            visited.add(loc)

            l1 = fnc.trans(loc, True)
            if l1:
                tovisit.append(l1)
            l2 = fnc.trans(loc, False)
            if l2:
                tovisit.append(l2)

        for loc in fnc.locs():
            if loc not in visited:
                fnc.rmloc(loc)

    def ssa(self, fnc):
        '''
        Converts exprs of each loc to SSA form
        '''

        for loc in fnc.locs():

            # Find last appearance of each var
            last = {}
            for i, (var, _) in enumerate(fnc.exprs(loc)):
                last[var] = i

            # Replace non-last appearance by a fresh var
            m = {}
            exprs = []
            for i, (var, expr) in enumerate(fnc.exprs(loc)):
                
                for v1, v2 in list(m.items()):
                    expr = expr.replace(v1, Var(v2))

                if var == VAR_RET:
                    newvar = var
                else:
                    if last[var] > i:
                        newvar = m[var] = self.ssavar(var)
                    else:
                        m.pop(var, None)
                        newvar = var

                if var != newvar:
                    expr.original = (var, self.cnt)

                exprs.append((newvar, expr))

            fnc.replaceexprs(loc, exprs)

    def rmtmp(self, fnc):
        '''
        Removes (merges) "tmp" or SSA-generated assignments
        '''

        for loc in fnc.locs():

            m = {}
            exprs = []
            primed = set([])
            lastret = None

            # Remember "real" vars and replace temps
            for var, expr in fnc.exprs(loc):

                #expr.statement = True
                
                expr.prime(primed)
                
                for v, e in list(m.items()):
                    expr = expr.replace(v, e)

                    if isinstance(expr, Op) and expr.name == 'ite':
                        expr.args[0].original = None
                        expr.args[1].original = None
                        expr.args[2].original = None

                if var.endswith('&'):
                    m[var] = expr

                else:
                    if var == VAR_RET:
                        lastret = len(exprs)
                        
                    exprs.append((var, expr))
                    
                    if var != VAR_RET:
                        primed.add(var)

            # "Merge" return stmts
            nexprs = []
            retexpr = None
            retcond = None
            for i, (var, expr) in enumerate(exprs):
                if var == VAR_RET:
                    tmpretcond = self.getretcond(expr)
                    if tmpretcond is True or retcond is None:
                        retcond = tmpretcond
                    elif tmpretcond is not None and retcond is not True:
                        retcond = Op(self.OROP, retcond, tmpretcond)
                    if retexpr:
                        retexpr = retexpr.replace(VAR_RET, expr)
                    else:
                        retexpr = expr

                    if i == lastret:
                        nexprs.append((var, retexpr))
                        
                else:
                    if retcond is True:
                        continue
                    elif retcond:
                        expr = Op('ite', Op(self.NOTOP, retcond),
                                  expr, Var(var))
                    nexprs.append((var, expr))

            fnc.replaceexprs(loc, nexprs)

    def getretcond(self, expr):
        if isinstance(expr, Op) and expr.name == 'ite':
            icond = expr.args[0]
            ct = self.getretcond(expr.args[1])
            cf = self.getretcond(expr.args[2])
            cond = []
            if ct is None and cf is None:
                return None
            if ct is True and cf is True:
                return True
            if ct:
                if ct is True:
                    cond.append(icond.copy())
                else:
                    cond.append(Op(self.ANDOP, icond.copy(), ct.copy()))
            if cf:
                nicond = Op(self.NOTOP, icond)
                if cf is True:
                    cond.append(nicond.copy())
                else:
                    cond.append(Op(self.ANDOP, nicond.copy(), cf.copy()))
            if len(cond) == 1:
                return cond[0]
            else:
                return Op(self.OROP, cond[0], cond[1])
            
        elif isinstance(expr, Var) and expr.name == VAR_RET:
            return None
        
        else:
            return True

    def postprocess(self):

        if not self.postproc:
            return

        self.rmemptyfncs()
        for fnc in list(self.prog.fncs.values()):
            self.rmunreachlocs(fnc)
            self.ssa(fnc)
            self.rmtmp(fnc)

    def visit(self, node, name=None):

        # Skip None-node
        if node is None:
            return

        # Name of the node class
        if name is None:
            name = node.__class__.__name__

        # Get method
        meth = getattr(self, 'visit_%s' % (name,), None)
        if meth is None:
            raise NotSupported("Unimplemented visitor: '%s'%s" % (name,
                               " (%s)" % node.value if hasattr(node, "value") else ""))

        # Call visitor method
        return meth(node)

    def visit_expr(self, node, allowlist=False, allownone=False):
        res = self.visit(node)

        if isinstance(res, list) and allowlist:
            ok = True
            for r in res:
                if not isinstance(r, Expr):
                    ok = False
                    break
            if ok:
                return res

        if res and not isinstance(res, Expr):
            raise ParseError("Expected expression, got '%s'" % (res,),
                             line=node.coord.line)

        if (not res) and (not allownone):
            if node:
                self.addwarn("Expression expected at line %s" % (
                    node.coord.line,))
            else:
                self.addwarn("Expression expected")
            res = Const('?')

        return res

    def visit_if(self, node, cond, true, false):

        # Add condition (with new location)
        preloc = self.loc
        condloc = self.addloc('the condition of the if-statement at line %d' % (
            self.getline(cond)
        ))
        condexpr = self.visit_expr(cond, allowlist=True)
        if isinstance(condexpr, list):
            condexpr = self.expr_list_and(condexpr)
        self.addexpr(VAR_COND, condexpr)
        
        # Add true loc
        trueline = self.getline(true) or self.getline(node)
        trueloc = self.addloc('inside the if-branch starting at line %d' % (
            trueline))
        self.visit(true)
        afterloc1 = self.loc

        afterloc = self.addloc('after the if-statement beginning at line %s' % (
            self.getline(node)
        ))

        # Add (general) transitions
        self.addtrans(preloc, True, condloc)
        self.addtrans(condloc, True, trueloc)
        self.addtrans(afterloc1, True, afterloc)

        # Add false loc
        if false:
            falseloc = self.addloc('inside the else-branch starting at line %d' % (
                self.getline(false)))
            self.visit(false)
            afterloc2 = self.loc

            self.addtrans(condloc, False, falseloc)
            self.addtrans(afterloc2, True, afterloc)

        else:
            self.addtrans(condloc, False, afterloc)
            falseloc = None

        # "Loop-less" if-statement
        if trueloc == afterloc1 and ((not false) or falseloc == afterloc2):
            if self.optifs:
                self.optimizeif(preloc, condexpr, trueloc, falseloc)
                return

        self.loc = afterloc

    def optimizeif(self, preloc, condexpr, trueloc, falseloc):
        '''
        Optimized "simple" or "loop-less" if statement
        '''

        # Remove unneded part of the graph
        self.fnc.rmtrans(preloc, True)
        self.loc = preloc

        # Keep track of assigned vars
        varss = set()
        varsl = []
        mt = {}
        mf = {}

        # Add exprs from branches
        def addvars(loc, m):
            for (var, expr) in self.fnc.exprs(loc):
                newvar = self.ssavar(var)

                if var not in varss:
                    varss.add(var)
                    varsl.append(var)

                # Replace vars mapped so far
                for (v1, v2) in list(m.items()):
                    expr = expr.replace(v1, Var(v2))
                expr.original = (var, self.cnt)
                self.addexpr(newvar, expr)

                # Remember replacement
                m[var] = newvar

        addvars(trueloc, mt)
        if falseloc is not None:
            addvars(falseloc, mf)

        # Add condition
        condvar = self.ssavar('$cond')
        self.addexpr(condvar, condexpr.copy())

        # Merge branches
        for var in varsl:
            self.addexpr(var, Op('ite', Var(condvar),
                                 Var(mt.get(var, var)), Var(mf.get(var, var))))

    def expr_list_and(self, exprs):

        if len(exprs) == 0:
            return None
            
        else:
            newexpr = exprs[0]
            for expr in exprs[1:]:
                newexpr = Op('&&', newexpr, expr, line=expr.line)
            return newexpr

    def visit_loop(self, node, init, cond, next, body, do, name, prebody=None):
        
        # Visit init stmts
        if init:
            self.visit(init)

        # Add condition (with new location)
        preloc = self.loc
        if isinstance(cond, Expr):
            condexpr = cond
        else:
            condexpr = self.visit_expr(cond, allowlist=True)
            if isinstance(condexpr, list):
                condexpr = self.expr_list_and(condexpr)
                
        if not condexpr:
            condexpr = Const('1')
        condloc = self.addloc("the condition of the '%s' loop at line %s" % (
            name, condexpr.line or self.getline(node)))
        self.addexpr(VAR_COND, condexpr)

        # Add exit loc
        exitloc = self.addloc("*after* the '%s' loop starting at line %d" % (
            name, self.getline(node)
        ))

        # Add next loc
        if next:
            nextloc = self.addloc("update of the '%s' loop at line %d" % (
                name, self.getline(next)
            ))
            self.visit(next)
        else:
            nextloc = None

        # Add body with (new location)
        bodyloc = self.addloc("inside the body of the '%s' loop beginning at line %d" % (
            name, self.getline(body) or self.getline(node)
        ))
        self.addloop((condloc, exitloc, nextloc))
        if prebody:
            for x in prebody:
                self.addexpr(*x)
        self.visit(body)
        self.poploop()
        afterloc = self.loc

        # Connect transitions
        self.addtrans(preloc, True, bodyloc if do else condloc)
        self.addtrans(condloc, True, bodyloc)
        self.addtrans(condloc, False, exitloc)
        if nextloc:
            self.addtrans(afterloc, True, nextloc)
            self.addtrans(nextloc, True, condloc)
        else:
            self.addtrans(afterloc, True, condloc)

        self.loc = exitloc

    def addfnc(self, name, params, rettype):
        if self.fnc:
            self.fncsl.append((self.fnc, self.loc))
        self.fnc = Function(name, params, rettype)
        self.fncs[name] = self.fnc
        self.prog.addfnc(self.fnc)

    def endfnc(self):
        if self.fncsl:
            self.fnc, self.loc = self.fncsl.pop()
        else:
            self.fnc = None
            self.loc = None

    def addloc(self, desc):
        assert (self.fnc), 'No active fnc!'
        self.loc = self.fnc.addloc(desc=desc)
        return self.loc

    def addexpr(self, name, expr, loc=None, idx=None):
        assert (self.fnc), 'No active fnc!'
        if not loc:
            loc = self.loc
        self.fnc.addexpr(loc, name, expr, idx=idx)

    def numexprs(self, loc=None):
        assert (self.fnc), 'No active fnc!'
        if not loc:
            loc = self.loc
        return self.fnc.numexprs(loc)

    def rmlastexprs(self, loc=None, num=1):
        assert (self.fnc), 'No active fnc!'
        if not loc:
            loc = self.loc
        self.fnc.rmlastexprs(loc, num)
    
    def addtrans(self, loc1, cond, loc2):
        assert (self.fnc), 'No active fnc!'
        self.fnc.addtrans(loc1, cond, loc2)

    def addtype(self, var, type, skiponexist=True):
        assert (self.fnc), 'No active fnc!'
        self.fnc.addtype(var, type, skiponexist)

    def hasvar(self, var):
        assert (self.fnc), 'No active fnc'
        return self.fnc.gettype(var) is not None

    def addloop(self, l):
        self.loops.append(l)

    def poploop(self):
        return self.loops.pop()

    def lastloop(self):
        return self.loops[-1] if len(self.loops) else None

    def isfncname(self, name):
        return name in self.fncs

    @classmethod
    def parse_code(cls, code, *args, **kwargs):
        parser = cls(*args, **kwargs)
        parser.parse(code)
        parser.postprocess()
        if parser.slice:
            parser.prog.slice()
        return parser.prog

    
PARSERS = {}


def addlangparser(lang, parser):
    PARSERS[lang] = parser

    
def getlangparser(lang):
    if lang in PARSERS:
        return PARSERS[lang]
    raise UnknownLanguage("No parser for language: '%s'" % (lang,))
