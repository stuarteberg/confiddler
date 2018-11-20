import collections

from json import (load, loads, JSONEncoder, JSONDecoder, JSONDecodeError, #@UnusedImport
                  dump as builtin_dump, dumps as builtin_dumps)

try:
    import numpy as np
    _numpy_loaded = True
except ImportError:
    _numpy_loaded = False


class ExtendedEncoder(JSONEncoder):
    """
    Encoder that handles objects that the built-in json library doesn't handle:
    
    - Numpy arrays and scalars are converted into their pure-python counterparts
      (No attempt is made to preserve bit-width information.)

    - All Mapping and Sequence types are converted to dict and list, respectively.
      (For example, ruamel.yaml.CommentedMap)
    
    Usage:
    
        >>> d = {"a": np.arange(3, dtype=np.uint32)}
        >>> json.dumps(d, cls=NumpyConvertingEncoder)
        '{"a": [0, 1, 2]}'
    """
    def default(self, o):
        if _numpy_loaded:
            if isinstance(o, (np.ndarray, np.number)):
                return o.tolist()
        if isinstance(o, collections.abc.Mapping) and not isinstance(o, dict):
            return {str(k):v for k,v in o.items()}
        if isinstance(o, collections.abc.Sequence) and not isinstance(o, (list, str, bytes)):
            return list(o)
        return super().default(o)


def dump(*args, **kwargs):
    """
    json.dump(), but using ExtendedEncoder, above.
    """
    if 'cls' not in kwargs:
        kwargs['cls'] = ExtendedEncoder
    return builtin_dump(*args, **kwargs)


def dumps(*args, **kwargs):
    """
    json.dumps(), but using ExtendedEncoder, above.
    """
    if 'cls' not in kwargs:
        kwargs['cls'] = ExtendedEncoder
    return builtin_dumps(*args, **kwargs)
