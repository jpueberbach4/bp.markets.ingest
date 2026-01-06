import argparse
import sys

class CustomArgumentParser(argparse.ArgumentParser):
    """
    Custom ArgumentParser that prints the help message on error.
    """
    def error(self, message: str):
        sys.stderr.write(f"{message}\n\n")
        self.print_help(sys.stderr)
        sys.exit(2)
