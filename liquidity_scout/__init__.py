"""Liquidity Scout core package.

The public CMIS source tree and the protected ``cmis-private-core`` wheel share
selected ``liquidity_scout`` package paths at runtime. Extend the package search
path so repository-owned public modules and installed protected modules compose
without copying private source back into the public checkout.
"""

from pkgutil import extend_path

__path__ = extend_path(__path__, __name__)
