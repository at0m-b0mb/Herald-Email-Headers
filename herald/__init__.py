"""Herald — read the headers.

An offline reader for e-mail headers: it reconstructs the path a message took,
reports the authentication the receiving server recorded, flags the tells of a
forgery, and grades what it finds — without ever claiming a message is safe.
"""

__version__ = "1.0.0"
__all__ = ["__version__"]
