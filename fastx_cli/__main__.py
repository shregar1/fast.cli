"""Support ``python -m fastx_cli`` (PEP 338).

When the interpreter executes the package as a script, :pep:`338` loads this
module and runs the ``if __name__ == "__main__"`` block. We delegate to
:func:`fastx_cli.app.main` so behaviour matches the ``fast-cli`` console script.
"""

from fastx_cli.app import main

if __name__ == "__main__":
    main()
