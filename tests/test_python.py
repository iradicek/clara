"""
Some basic (regression) Python tests
"""

from utils import get_full_data_filename, parse_file

from clara.interpreter import getlanginter
from clara.model import VAR_RET, prime, Const
from clara.parser import getlangparser

def test_list_comp():
    f = get_full_data_filename("comp.py")
    parser = getlangparser("py")
    inter = getlanginter("py")

    m = parse_file(f, parser)
    inter = inter(entryfnc="main")

    ios = [
        ([], []),
        ([1], [2]),
        ([1,2,3], [2,3,4])
    ]

    retvar = prime(VAR_RET)

    for i, o in ios:
        trace = inter.run(m, args=[i])
        print(trace)
        value = trace[-1][2][retvar]
        assert value == o

def test_consts():
    f = get_full_data_filename("named_consts.py")
    parser = getlangparser("py")
    m = parse_file(f, parser)
    main = m.getfnc("main")
    loc = list(main.locs())[0]

    def check_expr(e, v):
        assert isinstance(e, Const)
        assert e.value == v

    consts = [
        ("v1", "\"Hello world\""),
        ("v2", "42"),
        ("v3", "42.333"),
        ("v4", "True"),
        ("v5", "False"),
        ("v6", "None")
    ]

    for var, val in consts:
        check_expr(main.getexpr(loc, var), val)


