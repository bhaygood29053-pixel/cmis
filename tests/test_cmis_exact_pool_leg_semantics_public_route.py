import unittest

from liquidity_scout.providers.x1 import prove_exact_pool_leg_semantics


class ExactPoolLegSemanticsPublicRouteTests(unittest.TestCase):
    def test_public_export_routes_to_v14104(self):
        self.assertEqual(
            prove_exact_pool_leg_semantics.__module__,
            "liquidity_scout.providers.x1.exact_pool_leg_semantics_v14104",
        )


if __name__ == "__main__":
    unittest.main()
