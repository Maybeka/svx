from svx.cli import main as cli_main


def main() -> None:
    cli_main(
        [
            "svtypes-gen",
            "--module",
            "examples.milestone_5_existing_env.tests.types",
            "--channel-helpers",
        ]
    )


if __name__ == "__main__":
    main()
