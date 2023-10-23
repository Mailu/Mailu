Before requesting a pull
========================

Update translations
-------------------

Mailu uses Babel for internationalization and localization. Before any
of your work is merged, you must make sure that your strings are internationalized
using Babel.

If you used ``_``, ``trans`` blocks and other Babel syntax in your code, run the
following command to update the POT file:

.. code-block:: bash

  pybabel extract -F babel.cfg -k lazy_gettext -o messages.pot mailu

The, update the translations:

.. code-block:: bash

  pybabel update -i messages.pot -d mailu/translations

Please resolve fuzzy strings to the best of your knowledge.

Update information files
------------------------

If you added a feature or fixed a bug or committed anything that is worth mentioning
for the next upgrade, add it in the ``CHANGELOG.md`` file.

Also, if you would like to be mentioned by name or add a comment in ``AUTHORS.md``,
feel free to do so.
