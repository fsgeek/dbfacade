#!/usr/bin/env python3
"""
Pre-commit hook to check for potential semantic data leakage.

This hook looks for patterns that might indicate unprotected semantic field names
in database operations, logging, or error messages.
"""

import argparse
import ast
import os
import re
import sys
from typing import Dict, List, Optional, Set, Tuple


# Regular expression patterns for risky patterns
DIRECT_DB_PATTERNS = [
    r"db\.(?:aql\.)?execute\(\s*[\"'].*\bFILTER\s+doc\.([a-zA-Z0-9_]+)\b",  # Direct field access
    r"db\.(?:aql\.)?execute\(\s*[\"'].*\bSORT\s+doc\.([a-zA-Z0-9_]+)\b",     # Direct field sort
    r"db\.(?:aql\.)?execute\(\s*f[\"'].*\{([a-zA-Z0-9_]+)\}",                # String interpolation in AQL
]

LOG_PATTERNS = [
    r"log(?:ger|ging)?\.(?:debug|info|warning|error|critical)\(\s*f[\"'].*\{(\w+)\.[a-zA-Z0-9_]+\}",  # Logging direct object properties
]

DEV_MODE_PATTERNS = [
    r"if\s+(?:not\s+)?(?:os\.getenv\([\"']INDALEKO_MODE[\"']\)|DEV_MODE)\s*(?:==|!=)\s*[\"'](?:DEV|PROD)[\"']",  # Environment checks
]


class SemanticLeakageVisitor(ast.NodeVisitor):
    """AST visitor to find potential semantic data leakage."""

    def __init__(self) -> None:
        self.leakage_issues: List[Tuple[int, str]] = []
        
    def visit_Call(self, node: ast.Call) -> None:
        """Visit function call nodes to check for database operations."""
        # Check for direct database operations
        if isinstance(node.func, ast.Attribute):
            if hasattr(node.func, 'attr') and node.func.attr == 'execute':
                # Check if this is a database execute call
                if hasattr(node.func.value, 'attr') and node.func.value.attr in ('aql', 'db'):
                    # Check the query string
                    if node.args and isinstance(node.args[0], ast.Str):
                        query = node.args[0].s
                        # Check for direct field access in AQL
                        if re.search(r'\bdoc\.([a-zA-Z0-9_]+)\b', query):
                            self.leakage_issues.append(
                                (node.lineno, "Potential semantic leakage: direct field access in AQL query")
                            )
        
        # Check for logging of semantic data
        if isinstance(node.func, ast.Attribute) and hasattr(node.func, 'attr'):
            if node.func.attr in ('debug', 'info', 'warning', 'error', 'critical'):
                if hasattr(node.func.value, 'id') and node.func.value.id in ('logger', 'logging'):
                    # Check log message for direct attribute access
                    if node.args and isinstance(node.args[0], (ast.Str, ast.JoinedStr)):
                        # For f-strings, look for attribute access in the format specifiers
                        if isinstance(node.args[0], ast.JoinedStr):
                            for value in node.args[0].values:
                                if isinstance(value, ast.FormattedValue):
                                    if isinstance(value.value, ast.Attribute):
                                        self.leakage_issues.append(
                                            (node.lineno, "Potential semantic leakage: direct attribute access in logs")
                                        )
        
        self.generic_visit(node)
    
    def visit_Attribute(self, node: ast.Attribute) -> None:
        """Visit attribute access to check for direct field access."""
        # Check if this is direct access to a model attribute outside of dev mode
        # This is a simplified check - would need context to be more accurate
        if isinstance(node.value, ast.Name) and not node.attr.startswith('_'):
            # We would need context to know if this is a model instance
            pass
            
        self.generic_visit(node)


def check_file(filename: str) -> List[Tuple[int, str]]:
    """Check a file for potential semantic data leakage."""
    with open(filename, "r", encoding="utf-8") as file:
        content = file.read()
    
    issues = []
    
    # Check using AST for more accurate detection
    try:
        tree = ast.parse(content)
        visitor = SemanticLeakageVisitor()
        visitor.visit(tree)
        issues.extend(visitor.leakage_issues)
    except SyntaxError as e:
        issues.append((e.lineno or 0, f"SyntaxError: {str(e)}"))
    
    # Additional regex-based checks
    lines = content.split('\n')
    for i, line in enumerate(lines, 1):
        # Check for direct database field access
        for pattern in DIRECT_DB_PATTERNS:
            matches = re.search(pattern, line)
            if matches:
                field = matches.group(1)
                if not field.startswith('_'):  # Skip internal fields
                    issues.append((i, f"Potential semantic leakage: direct field name '{field}' in database operation"))
        
        # Check for logging of sensitive data
        for pattern in LOG_PATTERNS:
            matches = re.search(pattern, line)
            if matches:
                var = matches.group(1)
                issues.append((i, f"Potential semantic leakage: direct object attribute from '{var}' in log message"))
    
    # De-duplicate issues by line
    unique_issues = {}
    for line, message in issues:
        if line not in unique_issues:
            unique_issues[line] = message
    
    return [(line, message) for line, message in unique_issues.items()]


def main() -> int:
    """Main function to check files for semantic data leakage."""
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