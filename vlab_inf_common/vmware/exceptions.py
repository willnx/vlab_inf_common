# -*- coding: UTF-8 -*-
"""Custom exceptions"""

# The existing code base excepts ValueError to gracefully handle the failure.
# Subclassing that exception lets us raise unique errors, but not update a few
# dozen services. Cheesy, yeah. Lazy, a bit. Worth the tech debt? I think so.
class DeployFailure(ValueError):
    pass
