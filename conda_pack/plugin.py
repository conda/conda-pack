import conda.plugins

from conda_pack.cli import main


@conda.plugins.hookimpl
def conda_subcommands():
    yield conda.plugins.CondaSubcommand(
        name="pack",
        action=main,
        summary="Package an existing conda environment into an archive file.",
    )
