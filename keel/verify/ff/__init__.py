"""Importing this package registers every fitness function it contains."""

from keel.verify.ff import pointer_integrity as pointer_integrity  # noqa: F401
from keel.verify.ff import secrets as secrets  # noqa: F401
from keel.verify.ff import sensitive_data as sensitive_data  # noqa: F401
from keel.verify.ff import unsafe_tool_calls as unsafe_tool_calls  # noqa: F401
