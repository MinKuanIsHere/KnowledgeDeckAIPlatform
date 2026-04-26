import asyncio
from typing import Annotated

import typer
from sqlalchemy import select

from app.db.base import async_session_factory
from app.db.models import User

app = typer.Typer(help="KnowledgeDeck admin CLI", no_args_is_help=True)


# Typer collapses single-command apps unless an explicit callback is registered;
# without this, `python -m app.cli create-user <name>` fails because the
# subcommand name becomes implicit. Registering a no-op callback keeps the
# multi-command group behavior so the subcommand name is required.
@app.callback()
def _main() -> None:
    """KnowledgeDeck admin CLI."""


async def _create_user(username: str, password: str) -> None:
    async with async_session_factory()() as session:
        existing = await session.scalar(select(User).where(User.username == username))
        if existing is not None:
            raise typer.BadParameter(f"user already exists: {username}")
        session.add(User(username=username, password=password))
        await session.commit()


@app.command("create-user")
def create_user(
    username: str,
    password: Annotated[
        str,
        typer.Option(
            prompt=True,
            hide_input=True,
            confirmation_prompt=True,
            help="Password for the new user. Will be prompted if omitted.",
        ),
    ],
) -> None:
    asyncio.run(_create_user(username, password))
    typer.echo(f"created user: {username}")


if __name__ == "__main__":
    app()
