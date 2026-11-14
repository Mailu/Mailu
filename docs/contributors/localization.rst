I18N and L10N
=============

You can contribute translations of Mailu's administration and sign-in interfaces
by editing the translation files in this repository and opening a pull request.
You do not need to run a mail server to edit or check a translation.

Where to find the files
-----------------------

The files are under ``core/admin`` in a checkout of the Mailu repository:

- ``messages.pot`` is the translation template. It contains the source strings
  extracted from the Python code and HTML templates, without translations.
- ``mailu/translations/<locale>/LC_MESSAGES/messages.po`` contains the editable
  translations for one language. For example, French is in
  ``mailu/translations/fr/LC_MESSAGES/messages.po`` and Hebrew is in
  ``mailu/translations/he/LC_MESSAGES/messages.po``.
- ``babel.cfg`` tells Babel which source files to extract messages from.
- ``messages.mo`` files are compiled catalogs used at runtime. They are ignored
  by Git; do not include them in your contribution.

These catalogs cover the Mailu admin application. Webmail applications such as
Roundcube have their own translations, maintained separately.

Translate an existing language
------------------------------

Fork the Mailu repository, clone your fork, and create a branch based on
``master`` as described in :doc:`environment` and :doc:`workflow`.

Open the ``messages.po`` file for your language in `Poedit`_ or another gettext
translation editor. A text editor also works: each ``msgid`` is a source string
and its ``msgstr`` is the translation. Edit ``msgstr``, leaving ``msgid`` and
source references unchanged. For example:

.. code-block:: po

   msgid "Sign in"
   msgstr "Se connecter"

Translate missing entries and review entries marked ``fuzzy`` (shown as needing
review in Poedit). A fuzzy translation is a suggestion, not a confirmed
translation; check it and remove the fuzzy flag only when it is correct.
Untranslated and fuzzy entries normally fall back to the source text.

Keep substitution placeholders such as ``%(email)s`` or ``%s`` intact, and
preserve any required HTML tags. For plural entries, fill in all plural forms
required by the language rather than replacing the entry with a single string.
The catalog header records the language and plural rules; let your translation
editor manage these fields and update translator information as appropriate.

To pick up newer source strings in Poedit, use its option to update the catalog
from a POT file and select ``core/admin/messages.pot``. The command-line
equivalent is documented below. Updating against a POT file only adds strings
already present in that template; it does not extract new strings from code.

.. _Poedit: https://poedit.net/

Command-line tools
------------------

Mailu uses Babel to extract messages, update catalogs, and compile translations.
For translation work, install Babel and Jinja2 in a Python virtual environment.
From the repository root:

.. code-block:: bash

   python3 -m venv .venv
   . .venv/bin/activate
   python -m pip install Babel Jinja2
   cd core/admin

All ``pybabel`` commands below run from ``core/admin`` with that environment
activated.

Refresh the template and an existing catalog
--------------------------------------------

If you need strings that have been added to the code since the last template
update, first regenerate ``messages.pot``:

.. code-block:: bash

   pybabel extract -F babel.cfg -k lazy_gettext -o messages.pot mailu

Then merge the template into your language's catalog, replacing ``fr`` with
the existing locale directory name:

.. code-block:: bash

   pybabel update -i messages.pot -d mailu/translations -l fr

This preserves existing translations, adds missing entries, and may mark changed
entries as fuzzy. Review those entries in your editor. For a translation-only
contribution, update only the language you are working on to avoid unrelated
changes to other catalogs.

Template extraction and catalog updates are explicit steps. The admin image
build compiles the checked-in catalogs, but does not extract new strings, update
PO files, or translate them automatically. Contributors changing source strings
should also follow :doc:`memo`.

Add a new language
------------------

Check ``mailu/translations`` first to avoid creating a second catalog for an
existing language. Choose a Babel locale identifier, such as ``fi`` for Finnish
or a language/territory identifier where appropriate. Use underscores in locale
identifiers, following the existing directory names.

Refresh the template as described above, then initialize the new catalog. For
example, to add Finnish:

.. code-block:: bash

   pybabel init -i messages.pot -d mailu/translations -l fi

This creates ``mailu/translations/fi/LC_MESSAGES/messages.po`` with the language's
plural rules. Open it in your editor and translate the entries. Use ``init``
only for a new language; use ``update`` for an existing catalog.

Check and preview your translation
----------------------------------

Compile the catalog to check for errors, including invalid placeholders:

.. code-block:: bash

   pybabel compile -d mailu/translations -l fr --statistics

Replace ``fr`` with your locale and fix any errors reported. Compilation does
not check the meaning or layout of a translation, so review the text as well.
Do not use ``--use-fuzzy`` to hide unfinished review work.

To preview the interface, use the admin development environment described in
:doc:`environment`, or build and run an admin image from your checkout in a
test deployment. The admin image compiles the catalogs during its build. If
you edit PO files in a running development environment, compile the catalogs
there and restart the admin application to reload cached translations.

Choose your language from the interface's language menu and check the affected
pages. Mailu discovers languages from compiled catalogs at application startup;
adding a catalog does not require maintaining a separate list of languages.
The browser's preferred languages are used when no supported language has been
selected in the session.

Submit your contribution
------------------------

Review ``git diff`` and ``git status``, commit your changes, push your branch
to your fork, and open a pull request against ``Mailu/Mailu``'s ``master`` branch.
Include the edited or new ``messages.po`` file and, if you regenerated it, the
``messages.pot`` template. Do not submit compiled ``messages.mo`` files or your
virtual environment.

In the pull request, name the language, summarize what you translated, and say
whether compilation succeeded and whether you checked the interface. Partial
translations are welcome; you do not have to translate the entire catalog to
contribute. See :doc:`workflow` for the general contribution process.
