'''
Simple Python interface for lpsolve
'''

from array import array
from cpython cimport array as c_array
from libc.stdio cimport stdout, stderr


from clara cimport lpsolve

EQ = lpsolve.EQ
LE = lpsolve.LE
GE = lpsolve.GE
TIMEOUT = lpsolve.TIMEOUT
SUBOPTIMAL = lpsolve.SUBOPTIMAL
NUMFAILURE = lpsolve.NUMFAILURE

cdef class LpModel:
  cdef lpsolve.lprec* _lprec

  def __cinit__(self, int rows=0, int cols=0):
      self._lprec = lpsolve.make_lp(rows, cols)
      if self._lprec is NULL:
          raise Exception('Could not create a new LP model')
      self.setouttostderr()

  def settimeout(self, long secs):
      lpsolve.set_timeout(self._lprec, secs)

  def setverbose(self, int verbose):
      lpsolve.set_verbose(self._lprec, verbose)
      
  def setouttostderr(self):
      lpsolve.set_outputstream(self._lprec, stderr)

  def setouttostdout(self):
      lpsolve.set_outputstream(self._lprec, stdout)

  def setaddrowmode(self, bint turnon):
      return lpsolve.set_add_rowmode(self._lprec, turnon)

  def setint(self, int column, bint isint):
      lpsolve.set_int(self._lprec, column, isint)

  def setupbo(self, int column, double value):
      lpsolve.set_upbo(self._lprec, column, value)

  def setpresolve(self, int do_presolve, int maxloops):
      lpsolve.set_presolve(self._lprec, do_presolve, maxloops)
      
  def getpresolveloops(self):
      return lpsolve.get_presolveloops(self._lprec)

  def setbbrule(self, int bb_rule):
      lpsolve.set_bb_rule(self._lprec, bb_rule)

  def setscaling(self, int scalemode):
      lpsolve.set_scaling(self._lprec, scalemode)

  def setbinary(self, int column, char must_be_bin):
      return lpsolve.set_binary(self._lprec, column, must_be_bin)

  def addconstraint(self, row, int ctype, double rh):
      cdef c_array.array a = array('d', [0] + row)
      lpsolve.add_constraint(self._lprec, a.data.as_doubles, ctype, rh)

  def addconstraintex(self, dict values, int ctype, double rh):
      cdef count = len(values)
      cdef c_array.array row = array('d')
      cdef c_array.array colno = array('i')

      for col, val in values.items():
          row.append(float(val))
          colno.append(col + 1)

      return lpsolve.add_constraintex(self._lprec, count, row.data.as_doubles,
                                      colno.data.as_ints, ctype, rh)

  def setobjfnex(self, dict values):
      cdef count = len(values)
      cdef c_array.array row = array('d')
      cdef c_array.array colno = array('i')

      for col, val in values.items():
          row.append(float(val))
          colno.append(col + 1)

      return lpsolve.set_obj_fnex(self._lprec, count, row.data.as_doubles,
                                  colno.data.as_ints)

  def setrh(self, int row, double value):
      return lpsolve.set_rh(self._lprec, row, value)

  def addSOS(self, str name, int sostype, int priority, list sosvars):
      cdef count = len(sosvars)
      cdef c_array.array svars = array('i')
      cdef c_array.array aname = array('c')

      for v in sosvars:
          svars.append(int(v))

      for c in name:
          aname.append(c)
          
      return lpsolve.add_SOS(self._lprec, aname.data.as_chars, sostype, priority, count,
                             svars.data.as_ints, NULL)

  def getvariables(self):
      cdef double* vars
      cdef int n = lpsolve.get_Ncolumns(self._lprec)
      lpsolve.get_ptr_variables(self._lprec, &vars)
      return [vars[i] for i in xrange(n)]

  def solve(self):
      return lpsolve.solve(self._lprec)

  def printlp(self):
      lpsolve.print_lp(self._lprec)

  def printsolution(self, int cols):
      lpsolve.print_solution(self._lprec, cols)

  def __dealloc__(self):
      if self._lprec is not NULL:
          lpsolve.delete_lp(self._lprec)
