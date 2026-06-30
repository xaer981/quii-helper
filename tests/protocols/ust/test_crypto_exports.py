from quii_helper.protocols.ust import crypto


class UstCryptoExportsTests:
    def test_legacy_crypto_aggregator_imports_without_loading_assets(
        self,
    ) -> None:
        assert "load_p2p_crypto_tables" in crypto.__all__
        assert callable(crypto.load_p2p_crypto_tables)
        assert "P2P_SO_CANDIDATES" not in crypto.__all__
