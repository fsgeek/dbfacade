#!/usr/bin/env python3
"""
Pre-commit hook to check for blanket exception handlers.

This hook looks for 'except Exception:' or 'except:' patterns which are generally
discouraged in favor of more specific exception handling.
"""

import argparse
import ast
import re
import sys
from typing import List, Optional, Set, Tuple


class BlanketExceptionVisitor(ast.NodeVisitor):
    """AST visitor to find blanket exception handlers."""

    def __init__(self) -> None:
        self.blanket_exceptions: List[Tuple[int, str]] = []

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        """Visit exception handler nodes and check for blanket exceptions."""
        # Check for bare except: clause
        if node.type is None:
            self.blanket_exceptions.append(
                (node.lineno, "Bare except clause found. Use specific exceptions instead.")
            )
        # Check for except Exception: clause
        elif isinstance(node.type, ast.Name) and node.type.id == "Exception":
            self.blanket_exceptions.append(
                (
                    node.lineno,
                    "Blanket 'except Exception:' found. Use specific exceptions instead.",
                )
            )
        # Check for except (Exception): clause
        elif isinstance(node.type, ast.Tuple):
            exception_names = []
            for elt in node.type.elts:
                if isinstance(elt, ast.Name):
                    exception_names.append(elt.id)

            if "Exception" in exception_names or "BaseException" in exception_names:
                self.blanket_exceptions.append(
                    (
                        node.lineno,
                        f"Exception tuple contains too-generic exceptions: {', '.join(exception_names)}",
                    )
                )

        # Continue visiting children
        self.generic_visit(node)

    def check_exit_calls(self, node: ast.Expr) -> None:
        """Check if the exception handler has sys.exit() calls to enforce fail-stop."""
        # Implementation would check if there's a sys.exit() call
        # This is a simplified version
        pass


def check_file(filename: str) -> List[Tuple[int, str]]:
    """Check a file for blanket exception handlers."""
    with open(filename, "r", encoding="utf-8") as file:
        content = file.read()

    try:
        tree = ast.parse(content)
        visitor = BlanketExceptionVisitor()
        visitor.visit(tree)
        return visitor.blanket_exceptions
    except SyntaxError as e:
        return [(e.lineno or 0, f"SyntaxError: {str(e)}")]


def main() -> int:
    """Main function to check files for blanket exception handlers."""
    parser = argparse.ArgumentParser()
    parser.add_argument("filenames", nargs="*", help="Filenames to check")
    args = parser.parse_args()

    exit_code = 0
    for filename in args.filenames:
        if not filename.endswith(".py"):
            continue

        issues = check_file(filename)
        for line, message in issues:
            print(f"{filename}:{line}: {message}")
            exit_code = 1

    return exit_code


if __name__ == "__main__":
    sys.exit(main())