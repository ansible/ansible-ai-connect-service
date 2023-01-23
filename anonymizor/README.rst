==========
Anonymizor
==========


.. image:: https://img.shields.io/pypi/v/anonymizor.svg
        :target: https://pypi.python.org/pypi/anonymizor

.. image:: https://img.shields.io/travis/goneri/anonymizor.svg
        :target: https://travis-ci.com/goneri/anonymizor

.. image:: https://readthedocs.org/projects/anonymizor/badge/?version=latest
        :target: https://anonymizor.readthedocs.io/en/latest/?version=latest
        :alt: Documentation Status


.. image:: https://pyup.io/repos/github/goneri/anonymizor/shield.svg
     :target: https://pyup.io/repos/github/goneri/anonymizor/
     :alt: Updates



Library to clean up Ansible tasks from any Personally Identifiable Information (PII)


* Free software: Apache Software License 2.0
* Documentation: https://anonymizor.readthedocs.io.


Features
--------

.. code-block::

   $ python3
   Python 3.9.16 (main, Dec  7 2022, 00:00:00)
   [GCC 12.2.1 20221121 (Red Hat 12.2.1-4)] on linux
   Type "help", "copyright", "credits" or "license" for more information.
   >>> from anonymizor import anonymizor
   >>> example = ["- name: foo bar\n  email: my-email@address.com\n"]
   >>> anonymizor.anonymize_batch(example)
   ['- email: lucas27@example.com\n  name: foo bar\n']

Credits
-------

This package was created with Cookiecutter_ and the `audreyr/cookiecutter-pypackage`_ project template.

.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _`audreyr/cookiecutter-pypackage`: https://github.com/audreyr/cookiecutter-pypackage
