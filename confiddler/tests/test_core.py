from io import StringIO

import pytest
from ruamel.yaml import YAML

from confiddler import load_config, emit_defaults, validate

yaml = YAML()
yaml.default_flow_style = False


def test_load_empty():
    f = StringIO('{}')
    cfg = load_config(f, {})
    assert cfg == {}


def test_validate():
    schema = {
        'mystring': {
            'type': 'string'
        }
    }
    
    data = {"mystring": "Test"}

    f = StringIO()
    yaml.dump(data, f)
    f.seek(0)
    
    cfg = load_config(f, schema)
    assert cfg['mystring'] == 'Test'


def test_emit_defaults():
    schema = {
        'type': 'object',
        'properties': {
            'mystring': {
                'type': 'string',
                'default': 'DEFAULT'
            },
            'mynumber': {
                'type': 'number',
                'default': 42
            }
        },
        'default': {}
    }
    
    defaults = emit_defaults(schema)
    assert defaults == { 'mystring': 'DEFAULT',
                         'mynumber': 42 }

    # Make sure defaults still validate
    # (despite being yaml CommentedMap or whatever)
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


def test_inject_default():
    schema = {
        'type': 'object',
        'properties': {
            'mystring': {
                'type': 'string',
                'default': 'DEFAULT'
            },
            'mynumber': {
                'type': 'number',
                'default': 42
            }
        },
        'default': {}
    }

    data = {'mynumber': 10}

    f = StringIO()
    yaml.dump(data, f)
    f.seek(0)
    
    cfg = load_config(f, schema)
    assert cfg['mystring'] == 'DEFAULT'
    validate(cfg, schema)


if __name__ == "__main__":
    pytest.main(['-s', '--tb=native', '--pyargs', 'confiddler.tests.test_core'])
