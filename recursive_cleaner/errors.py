"""Exception classes for the recursive cleaner pipeline."""


class CleanerError(Exception):
    """Base error for the pipeline"""


class ParseError(CleanerError):
    """XML or code extraction failed - retry with error feedback"""


class MaxIterationsError(CleanerError):
    """Chunk never marked clean - skip and continue"""


class OutputValidationError(CleanerError):
    """Generated output file has invalid Python syntax"""
