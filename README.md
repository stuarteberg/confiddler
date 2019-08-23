confiddler
==========

Schema-checked YAML config files, with default values for missing fields.


[![Travis CI Status](https://travis-ci.com/stuarteberg/confiddler.svg?branch=master)](https://travis-ci.com/stuarteberg/confiddler)
[![Codecov Status](https://codecov.io/gh/stuarteberg/confiddler/branch/master/graph/badge.svg)](https://codecov.io/gh/stuarteberg/confiddler)
[![Documentation Status](https://readthedocs.org/projects/confiddler/badge/?version=latest)](https://confiddler.readthedocs.io/en/latest/?badge=latest)


The Basic Idea
--------------

1. Define your config file structure with a JSON schema.
   (See `json-schema.org <https://json-schema.org>`_ or
   `jsonschema <http://python-jsonschema.readthedocs.org>`_).


2. Help your users get started by showing them a **default config file** which is:
   
   - auto-generated from your defaults, and 
   - auto-commented with your schema ``description``.


3. Load a user's config file with :py:func:`confiddler.load_config()`, which will:

     - validate it against your schema
     - auto-inject default values for any settings the user omitted


Quickstart
----------

Define your schema

```python
>>> from confiddler import dump_default_config, load_config

>>> schema = {
      "description": "Settings for a robot vacuum cleaner",
      "properties": {
        "speed": {
          "description": "Speed of the robot (1-10)",
          "type": "number",
          "minValue": 1,
          "maxValue": 10,
          "default": 1
        },
        "movement": {
          "description": "Movement strategy: random, raster, or spiral",
          "type": "string",
          "enum": ["random", "raster", "spiral"],
          "default": "random"
        }
      }
    }
```

Show your user the default config.

```python
>>> dump_default_config(schema, sys.stdout, 'yaml')
speed: 1
movement: random

>>> dump_default_config(schema, sys.stdout, 'yaml-with-comments')
#
# Settings for a robot vacuum cleaner
#

# Speed of the robot (1-10)
speed: 1

# Movement strategy: random, raster, or spiral
movement: random
```

Load your user's config.

```yaml
# my-robot-config.yaml

speed: 2

# (Other settings omitted -- will be set as default.)
```

```python
>>> load_config('my-robot-config.yaml', schema, inject_defaults=True)
{'speed': 2, 'movement': 'random'}
```
