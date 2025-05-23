"""Tests for the metaregistry."""

import unittest

import rdflib

import bioregistry
from bioregistry import manager
from bioregistry.export.rdf_export import metaresource_to_rdf_str
from bioregistry.schema import Registry


class TestMetaregistry(unittest.TestCase):
    """Tests for the metaregistry."""

    def setUp(self) -> None:
        """Set up the test case."""
        self.manager = bioregistry.manager

    def test_minimum_metadata(self):
        """Test the metaregistry entries have a minimum amount of data."""
        for metaprefix, registry in self.manager.metaregistry.items():
            self.assertIsInstance(registry, Registry)
            external_prefixes = set(self.manager.get_registry_invmap(metaprefix))
            with self.subTest(metaprefix=metaprefix):
                self.assertIsNotNone(registry.name)
                self.assertIsNotNone(registry.homepage)
                self.assertIsNotNone(registry.example)
                if metaprefix != "bioregistry" and external_prefixes:
                    self.assertIn(
                        registry.example,
                        external_prefixes,
                        msg="Examples should be external-registry specific and mapped",
                    )
                self.assertIsNotNone(registry.description)
                self.assertIsNotNone(registry.contact)
                self.assertIsNotNone(registry.license, msg=f"Contact: {registry.contact}")
                self.assertNotEqual("FIXME", registry.contact.name)
                if "support" not in registry.contact.name.lower():
                    self.assertIsNotNone(registry.contact.orcid)
                    self.assertIsNotNone(registry.contact.github)

                if registry.provider_uri_format:
                    self.assertIsNotNone(registry.provider_uri_format)
                    self.assertIn("$1", registry.provider_uri_format)

                if (
                    # Missing URI format string
                    not registry.provider_uri_format
                    # Unresolved overlap in Bioregistry
                    or metaprefix in bioregistry.read_registry()
                    # Has URI format string, but not in proper form
                    or (
                        registry.provider_uri_format
                        and not registry.provider_uri_format.endswith("$1")
                    )
                ):
                    self.assertIsNotNone(registry.bioregistry_prefix)

                if registry.bioregistry_prefix:
                    self.assertEqual(
                        bioregistry.normalize_prefix(registry.bioregistry_prefix),
                        registry.bioregistry_prefix,
                        msg="link from metaregistry to bioregistry must use canonical prefix",
                    )
                    resource = bioregistry.get_resource(registry.bioregistry_prefix)
                    self.assertIsNotNone(resource)
                    self.assertIsNotNone(
                        resource.get_uri_format(),
                        msg=f"corresponding registry entry ({registry.bioregistry_prefix})"
                        f" is missing a uri_format",
                    )

                # When a registry is a resolver, it means it
                # can resolve entries (prefixes) + identifiers
                if registry.resolver_uri_format:
                    self.assertIn("$1", registry.resolver_uri_format)
                    self.assertIn("$2", registry.resolver_uri_format)
                    self.assertIsNotNone(registry.resolver_type)
                    self.assertIn(registry.resolver_type, {"lookup", "resolver"})

                invalid_keys = set(registry.model_dump()).difference(Registry.model_fields)
                self.assertEqual(set(), invalid_keys, msg="invalid metadata")
                self.assertIsNotNone(registry.qualities)
                self.assertIsInstance(registry.qualities.bulk_data, bool)

                if registry.governance.public_version_controlled_data:
                    self.assertIsNotNone(registry.governance.data_repository)
                    self.assertIsNotNone(registry.governance.issue_tracker)

    def test_get_registry(self):
        """Test getting a registry."""
        self.assertIsNone(bioregistry.get_registry("nope"))
        self.assertIsNone(bioregistry.get_registry_name("nope"))
        self.assertIsNone(bioregistry.get_registry_homepage("nope"))
        self.assertIsNone(bioregistry.get_registry_provider_uri_format("nope", ...))
        self.assertIsNone(bioregistry.get_registry_example("nope"))
        self.assertIsNone(bioregistry.get_registry_description("nope"))

        metaprefix = "uniprot"
        registry = bioregistry.get_registry(metaprefix)
        self.assertIsInstance(registry, Registry)
        self.assertEqual(metaprefix, registry.prefix)

        self.assertEqual(registry.description, bioregistry.get_registry_description(metaprefix))

        homepage = "https://www.uniprot.org/database/"
        self.assertEqual(homepage, registry.homepage)
        self.assertEqual(homepage, bioregistry.get_registry_homepage(metaprefix))

        name = "UniProt Cross-ref database"
        self.assertEqual(name, registry.name)
        self.assertEqual(name, bioregistry.get_registry_name(metaprefix))

        example = "DB-0174"
        self.assertEqual(example, registry.example)
        self.assertEqual(example, bioregistry.get_registry_example(metaprefix))

        url = bioregistry.get_registry_provider_uri_format(metaprefix, example)
        self.assertEqual("https://www.uniprot.org/database/DB-0174", url)

    def test_resolver(self):
        """Test generating resolver URLs."""
        # Can't resolve since nope isn't a valid registry
        self.assertIsNone(bioregistry.get_registry_uri("nope", "chebi", "1234"))
        # Can't resolve since GO isn't a resolver
        self.assertIsNone(bioregistry.get_registry_uri("go", "chebi", "1234"))

        url = bioregistry.get_registry_uri("bioregistry", "chebi", "1234")
        self.assertEqual("https://bioregistry.io/chebi:1234", url)

    def test_get_rdf(self):
        """Test conversion to RDF."""
        registry = self.manager.metaregistry["uniprot"]
        s = metaresource_to_rdf_str(registry, manager=manager)
        self.assertIsInstance(s, str)
        g = rdflib.Graph()
        g.parse(data=s)

    def test_corresponding(self):
        """Test data corresponds between the registry and metaregistry."""
        for metaprefix, registry in self.manager.metaregistry.items():
            if registry.bioregistry_prefix:
                resource = self.manager.registry[registry.bioregistry_prefix]
            elif metaprefix in self.manager.registry:
                resource = self.manager.registry[metaprefix]
            else:
                continue

            # Test pattern
            pattern = resource.get_pattern()
            if pattern is None:
                continue
            with self.subTest(metaprefix=metaprefix):
                self.assertRegex(registry.example, pattern)

            # Test URI format string
            if registry.provider_uri_format:
                uri_formats = resource.get_uri_formats()
                self.assertLess(0, len(uri_formats))
                self.assertIn(registry.provider_uri_format, uri_formats)
