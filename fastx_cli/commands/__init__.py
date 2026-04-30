"""Click command groups and registration helpers.

The root :class:`click.Group` is defined in :mod:`fastx_cli.app`. Subpackages
here each expose either:

* A :class:`click.Group` (e.g. ``db_group``, ``add_group``) added via
  :meth:`click.Group.add_command`, or
* A ``register_*`` function that attaches commands to the root group inside a
  closure (e.g. :func:`fastx_cli.commands.generate_cmd.register_generate_commands`).

Keeping commands split by domain keeps import times lower for users who only
invoke a subset of subcommands and clarifies ownership for maintenance.
"""
