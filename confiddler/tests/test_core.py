import copy
import textwrap
import tempfile
from io import StringIO

import pytest
from ruamel.yaml import YAML

from confiddler import (load_config, emit_defaults, validate, dump_default_config,
                        flow_style, ValidationError, convert_to_base_types, dump_config)

yaml = YAML()
yaml.default_flow_style = False

TEST_SCHEMA = {
        'type': 'object',
        'required': ['mystring', 'mynumber'],
        'default': {},
        'properties': {
            'mystring': {
                'type': 'string',
                'default': 'DEFAULT'
            },
            'mynumber': {
                'type': 'number',
                'default': 42
            },
            'myobject': {
                'type': 'object',
                'default': {'inner-string': 'INNER_DEFAULT'}
            }
        }
    }


def test_load_empty():
    f = StringIO('{}')
    cfg = load_config(f, {})
    assert cfg == {}


def test_validate():
    schema = {
        'properties': {
            'mystring': {
                'type': 'string'
            }
        }
    }
    
    data = {"mystring": "Test"}

    f = StringIO()
    yaml.dump(data, f)
    f.seek(0)
    
    cfg = load_config(f, schema)
    assert cfg['mystring'] == 'Test'


def test_failed_validate():
    schema = {
        'properties': {
            'mystring': {
                'type': 'string'
            }
        }
    }
    
    data = {"mystring": 123}

    f = StringIO()
    yaml.dump(data, f)
    f.seek(0)

    with pytest.raises(ValidationError):
        load_config(f, schema)


def test_missing_required_property_with_default():
    schema = {
        'required': ['mystring'],
        'properties': {
            'mystring': {
                'type': 'string',
                'default': 'DEFAULT'
            }
        }
    }
    
    data = {}

    f = StringIO()
    yaml.dump(data, f)
    f.seek(0)

    cfg = load_config(f, schema)
    assert cfg['mystring'] == "DEFAULT"
    

def test_missing_required_property_no_default():
    schema = {
        'required': ['mystring'],
        'properties': {
            'mystring': {
                'type': 'string',
                
                # NO DEFAULT -- really required
                #'default': 'DEFAULT'
            }
        }
    }
    
    data = {}

    f = StringIO()
    yaml.dump(data, f)
    f.seek(0)

    with pytest.raises(ValidationError):
        load_config(f, schema)


def test_load_list():
    """
    Make sure lists can be loaded properly
    (e.g. that it isn't overwritten with the default, etc.)
    """
    schema = copy.deepcopy(TEST_SCHEMA)
    schema['properties']['mylist'] = {
        'type': 'array',
        'items': {'type': 'string'},
        'default': []
    }
    
    data = {'mylist': ['a', 'b', 'c']}

    f = StringIO()
    yaml.dump(data, f)
    f.seek(0)
    
    cfg = load_config(f, schema)
    assert cfg['mylist'] == list('abc')


def test_emit_defaults():
    schema = copy.deepcopy(TEST_SCHEMA)
    defaults = emit_defaults(schema)
    assert defaults == { 'mystring': 'DEFAULT',
                         'mynumber': 42,
                         'myobject': {'inner-string': 'INNER_DEFAULT'} }

    # Make sure defaults still validate
    # (despite being yaml CommentedMap or whatever)
    validate(defaults, schema)


def test_dump_default_config():
    schema = copy.deepcopy(TEST_SCHEMA)
    defaults = emit_defaults(schema)
    
    # To file object
    f = StringIO()
    dump_default_config(schema, f)
    f.seek(0)
    
    assert yaml.load(f) == defaults

    # To string
    s = dump_default_config(schema)
    assert s == f.getvalue()
    
    

def test_emit_incomplete_defaults():
    schema = copy.deepcopy(TEST_SCHEMA)
    
    # Delete the default for 'mynumber'
    del schema['properties']['mynumber']['default']
    
    defaults = emit_defaults(schema)
    assert defaults == { 'mystring': 'DEFAULT',
                         'mynumber': '{{NO_DEFAULT}}',
                         'myobject': {'inner-string': 'INNER_DEFAULT'} }

    # The '{{NO_DEFAULT}}' setting doesn't validate.
    # That's okay.
    with pytest.raises(ValidationError):
        validate(defaults, schema)


def test_emit_defaults_with_comments():
    schema = {
        'type': 'object',
        'properties': {
            'mystring': {
                'description': 'MYSTRING_DESCRIPTION_TEXT',
                'type': 'string',
                'default': 'DEFAULT'
            },
            'mynumber': {
                'description': 'MYNUMBER_DESCRIPTION_TEXT',
                'type': 'number',
                'default': 42
            }
        },
        'default': {}
    }
    
    defaults = emit_defaults(schema, include_yaml_comments=True)
    assert defaults == { 'mystring': 'DEFAULT',
                         'mynumber': 42 }

    validate(defaults, schema)

    f = StringIO()
    yaml.dump(defaults, f)
    assert 'MYSTRING_DESCRIPTION_TEXT' in f.getvalue()
    assert 'MYNUMBER_DESCRIPTION_TEXT' in f.getvalue()


def test_emit_defaults_with_flow_style():
    schema = copy.deepcopy(TEST_SCHEMA)
    d = schema['properties']['myobject']['default']
    schema['properties']['myobject']['default'] = flow_style(d)

    defaults = emit_defaults(schema)
    assert defaults['myobject'].fa.flow_style()

    # Make sure defaults still validate
    # (despite being yaml CommentedMap or whatever)
    validate(defaults, schema)


def test_inject_default():
    schema = copy.deepcopy(TEST_SCHEMA)
    data = {'mynumber': 10}

    f = StringIO()
    yaml.dump(data, f)
    f.seek(0)
    
    cfg = load_config(f, schema)
    assert cfg['mystring'] == 'DEFAULT'
    assert cfg['myobject']['inner-string'] == 'INNER_DEFAULT'
    assert cfg['myobject'].from_default == True
    validate(cfg, schema)


def test_inject_default_array_item_objects():
    """
    Users can specify that items of an array should be objects,
    with a particular schema.  If that item schema specifies default properties,
    then those properties will be injected into any objects in the list (if the user ommitted them).
    
    The NUMBER of items must be chosen by the user,
    but the contents of the items is determined by the default schema.
    """
    schema = {
        'type': 'array',
        'items': {
            'type': 'object',
            'default': {},
            'properties': {
                'foo': {
                    'default': 'bar'
                    }
                }
            }
        }
    
    # The first object in this array is completely specified
    # by the user, but the remaining two will be "filled in"
    # with the defaults from the item schema.
    data = [{'foo': 'MYFOO'}, {}, {}]
    
    f = StringIO()
    yaml.dump(data, f)
    f.seek(0)
    
    cfg = load_config(f, schema)
    assert cfg == [{'foo': 'MYFOO'},
                   {'foo': 'bar'},
                   {'foo': 'bar'}]
    assert not cfg[0].from_default
    assert cfg[1].from_default
    assert cfg[2].from_default


def test_load_from_path():
    d = tempfile.mkdtemp()
    config = {'mynumber': 99}
    path = f'{d}/test_load_from_path.yaml'
    with open(path, 'w') as f:
        yaml.dump(config, f)
    
    loaded = load_config(path, TEST_SCHEMA, True)
    assert loaded['mynumber'] == 99
    assert loaded['mystring'] == "DEFAULT"


def test_convert_to_base_types():
    d = yaml.load('{"a": [1,2,3], "b": {"x": 1, "y": 2}}')
    assert type(d) != dict
    assert type(d['a']) != list
    assert type(d['b']) != dict

    d2 = convert_to_base_types(d)
    assert type(d2) == dict
    assert type(d2['a']) == list
    assert type(d2['b']) == dict


def test_dump_config():
    data = {'a': flow_style([1,2,3])}
    dumped = dump_config(data)
    expected = textwrap.dedent("""\
        a: [1, 2, 3]
    """)
    assert dumped == expected

if __name__ == "__main__":
    pytest.main(['-s', '--tb=native', '--pyargs', 'confiddler.tests.test_core'])
