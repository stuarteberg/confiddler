.. confiddler documentation master file, created by
   sphinx-quickstart on Thu Dec 20 19:06:15 2018.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

.. |br| raw:: html

   <br />

confiddler
==========

``confiddler`` has tools to help you define and load YAML configuration files.


Here's the basic idea:

1. Define your config file structure with a JSON schema.
   (See `json-schema.org <https://json-schema.org>`_ or
   `jsonschema <http://python-jsonschema.readthedocs.org>`_).



2. Help your users get started by showing them a **default config file** which is:
   
   - auto-generated from your defaults, and 
   - auto-commented with your schema ``description``.


3. Load a user's config file with :py:func:`confiddler.load_config()`, which will:

     - validate it against your schema
     - auto-inject default values for any settings the user omitted

See the :ref:`Quickstart <quickstart>` for a short example.


Install
-------

.. code-block:: bash

    conda install -c flyem-forge confiddler


Contents
--------

.. toctree::
   :maxdepth: 2

   quickstart
   core

