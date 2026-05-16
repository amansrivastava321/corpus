"""CLI entry point — called by `corpus` console script."""

from corpus.cli.main import cli


def main() -> None:
    cli(auto_envvar_prefix="CORPUS")
