import argparse
import sys


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the munshi command.

    Returns:
        The configured parser.
    """
    parser = argparse.ArgumentParser(prog="munshi", description="Your daily work register.")
    sub = parser.add_subparsers(dest="command", required=True)
    doctor = sub.add_parser("doctor", help="Check the setup.")
    doctor.add_argument("--demo", action="store_true", help="Use the demo home.")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the munshi command line.

    Args:
        argv: Arguments without the program name; defaults to sys.argv.

    Returns:
        The process exit code.
    """
    args = build_parser().parse_args(argv)
    if args.command == "doctor":
        print(f"✓ Python {sys.version.split()[0]}")
    return 0
