"""Tests for BaseDataSource abstract base."""

import pytest

from app.integrations.base import BaseDataSource


class TestBaseDataSource:
    def test_cannot_instantiate_abstract(self):
        """BaseDataSource should not be instantiatable directly."""
        with pytest.raises(TypeError):
            BaseDataSource()  # type: ignore[abstract]

    def test_concrete_subclass(self):
        """A concrete subclass should work."""
        class ConcreteSource(BaseDataSource):
            @property
            def name(self) -> str:
                return "test"

            async def fetch(self, **kwargs):
                return []

        ds = ConcreteSource()
        assert ds.name == "test"
