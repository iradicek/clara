"""
Some basic (regression) Python tests
"""

from utils import get_full_data_filename, parse_file

from clara.interpreter import getlanginter
from clara.matching import Matching
from clara.model import VAR_RET, prime
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
