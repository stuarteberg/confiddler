from io import StringIO
from collections import UserDict, UserList

import numpy as np

import confiddler.json as json

def test():
    """
    Our drop-in json replacement can encode custom
    mappings and sequences, and also numpy arrays.
    """
    d = UserDict()
    d['l'] = UserList([1,2,3])
    d['a'] = np.arange(5)
    
    d['o'] = {}
    
    f = StringIO()
    json.dump(d, f)
    f.seek(0)
    
    assert json.load(f) == {'l': [1,2,3], 'a': [0,1,2,3,4], 'o': {}}

    s = json.dumps(d)
    assert json.loads(s) == {'l': [1,2,3], 'a': [0,1,2,3,4], 'o': {}}


if __name__ == "__main__":
    import pytest
    pytest.main(['-s', '--tb=native', '--pyargs', 'confiddler.tests.test_json'])
