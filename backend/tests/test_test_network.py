"""Unit tests for TestRailwayNetwork factory methods."""

import pytest

from tests.helpers.railway_network import TestRailwayNetwork


class TestHubChildrenFactories:
    """Tests for hub children station factories."""

    @pytest.mark.parametrize(
        (
            "factory_method",
            "expected_tfl_id",
            "expected_name",
            "expected_lines",
            "expected_hub_naptan",
            "expected_hub_name",
        ),
        [
            (
                "create_parallel_north",
                TestRailwayNetwork.STATION_PARALLEL_NORTH,
                "North Interchange (Tube)",
                [TestRailwayNetwork.LINE_PARALLELLINE],
                TestRailwayNetwork.HUB_NORTH,
                TestRailwayNetwork.HUB_NORTH_NAME,
            ),
            (
                "create_hubnorth_overground",
                TestRailwayNetwork.STATION_HUBNORTH_OVERGROUND,
                "North Interchange (Overground)",
                [TestRailwayNetwork.LINE_ASYMMETRICLINE],
                TestRailwayNetwork.HUB_NORTH,
                TestRailwayNetwork.HUB_NORTH_NAME,
            ),
            (
                "create_hubnorth_elizabeth",
                TestRailwayNetwork.STATION_HUBNORTH_ELIZABETH,
                "North Interchange (Elizabeth line)",
                [TestRailwayNetwork.LINE_ELIZABETHLINE],
                TestRailwayNetwork.HUB_NORTH,
                TestRailwayNetwork.HUB_NORTH_NAME,
            ),
            (
                "create_hubnorth_bus",
                TestRailwayNetwork.STATION_HUBNORTH_BUS,
                "North Interchange (Bus)",
                [],  # No line - bus mode not in network
                TestRailwayNetwork.HUB_NORTH,
                TestRailwayNetwork.HUB_NORTH_NAME,
            ),
            (
                "create_fork_mid_1",
                TestRailwayNetwork.STATION_FORK_MID_1,
                "Central Hub (Tube)",
                [TestRailwayNetwork.LINE_FORKEDLINE],
                TestRailwayNetwork.HUB_CENTRAL,
                TestRailwayNetwork.HUB_CENTRAL_NAME,
            ),
            (
                "create_hubcentral_dlr",
                TestRailwayNetwork.STATION_HUBCENTRAL_DLR,
                "Central Hub (DLR)",
                [TestRailwayNetwork.LINE_2STOPLINE],
                TestRailwayNetwork.HUB_CENTRAL,
                TestRailwayNetwork.HUB_CENTRAL_NAME,
            ),
        ],
        ids=[
            "parallel-north",
            "hubnorth-overground",
            "hubnorth-elizabeth",
            "hubnorth-bus",
            "fork-mid-1",
            "hubcentral-dlr",
        ],
    )
    def test_hub_children(
        self,
        factory_method: str,
        expected_tfl_id: str,
        expected_name: str,
        expected_lines: list[str],
        expected_hub_naptan: str,
        expected_hub_name: str,
    ) -> None:
        """Test hub children stations have correct hub attributes."""
        station = getattr(TestRailwayNetwork, factory_method)()

        assert station.tfl_id == expected_tfl_id
        assert station.name == expected_name
        assert station.lines == expected_lines
        assert station.hub_naptan_code == expected_hub_naptan
        assert station.hub_common_name == expected_hub_name


class TestBranchJunctionFactories:
    """Tests for branch junction station factories (NOT hubs)."""

    @pytest.mark.parametrize(
        ("factory_method", "expected_tfl_id", "expected_name", "expected_lines"),
        [
            (
                "create_fork_junction",
                TestRailwayNetwork.STATION_FORK_JUNCTION,
                "Fork Junction",
                [TestRailwayNetwork.LINE_FORKEDLINE],
            ),
            (
                "create_parallel_split",
                TestRailwayNetwork.STATION_PARALLEL_SPLIT,
                "Parallel Split",
                [TestRailwayNetwork.LINE_PARALLELLINE],
            ),
            (
                "create_parallel_rejoin",
                TestRailwayNetwork.STATION_PARALLEL_REJOIN,
                "Parallel Rejoin",
                [TestRailwayNetwork.LINE_PARALLELLINE],
            ),
        ],
        ids=["fork-junction", "parallel-split", "parallel-rejoin"],
    )
    def test_branch_junctions(
        self,
        factory_method: str,
        expected_tfl_id: str,
        expected_name: str,
        expected_lines: list[str],
    ) -> None:
        """Test branch junction stations are NOT hubs."""
        station = getattr(TestRailwayNetwork, factory_method)()

        assert station.tfl_id == expected_tfl_id
        assert station.name == expected_name
        assert station.lines == expected_lines
        assert station.hub_naptan_code is None  # NOT a hub
        assert station.hub_common_name is None


class TestSharedStationFactory:
    """Tests for shared station factory (serves 3 lines, NOT a hub)."""

    def test_create_shared_station(self) -> None:
        """Test shared-station serves exactly 3 lines (NOT a hub)."""
        station = TestRailwayNetwork.create_shared_station()

        assert station.tfl_id == TestRailwayNetwork.STATION_SHARED_STATION
        assert station.name == "Shared Station"
        assert len(station.lines) == 3
        assert TestRailwayNetwork.LINE_SHAREDLINE_A in station.lines
        assert TestRailwayNetwork.LINE_SHAREDLINE_B in station.lines
        assert TestRailwayNetwork.LINE_SHAREDLINE_C in station.lines
        assert station.hub_naptan_code is None  # NOT a hub
        assert station.hub_common_name is None


class TestStandaloneStationFactories:
    """Tests for standalone station factories (non-hub stations)."""

    @pytest.mark.parametrize(
        ("factory_method", "expected_tfl_id", "expected_name", "expected_lines"),
        [
            # Forkedline stations
            (
                "create_west_fork_2",
                TestRailwayNetwork.STATION_WEST_FORK_2,
                "West Fork 2",
                [TestRailwayNetwork.LINE_FORKEDLINE],
            ),
            (
                "create_west_fork",
                TestRailwayNetwork.STATION_WEST_FORK,
                "West Fork",
                [TestRailwayNetwork.LINE_FORKEDLINE],
            ),
            (
                "create_east_fork_2",
                TestRailwayNetwork.STATION_EAST_FORK_2,
                "East Fork 2",
                [TestRailwayNetwork.LINE_FORKEDLINE],
            ),
            (
                "create_east_fork",
                TestRailwayNetwork.STATION_EAST_FORK,
                "East Fork",
                [TestRailwayNetwork.LINE_FORKEDLINE],
            ),
            (
                "create_fork_mid_2",
                TestRailwayNetwork.STATION_FORK_MID_2,
                "Fork Mid 2",
                [TestRailwayNetwork.LINE_FORKEDLINE],
            ),
            (
                "create_fork_south_end",
                TestRailwayNetwork.STATION_FORK_SOUTH_END,
                "Fork South End",
                [TestRailwayNetwork.LINE_FORKEDLINE],
            ),
            # Parallelline stations
            (
                "create_via_bank_1",
                TestRailwayNetwork.STATION_VIA_BANK_1,
                "Via Bank 1",
                [TestRailwayNetwork.LINE_PARALLELLINE],
            ),
            (
                "create_via_bank_2",
                TestRailwayNetwork.STATION_VIA_BANK_2,
                "Via Bank 2",
                [TestRailwayNetwork.LINE_PARALLELLINE],
            ),
            (
                "create_via_charing_1",
                TestRailwayNetwork.STATION_VIA_CHARING_1,
                "Via Charing 1",
                [TestRailwayNetwork.LINE_PARALLELLINE],
            ),
            (
                "create_via_charing_2",
                TestRailwayNetwork.STATION_VIA_CHARING_2,
                "Via Charing 2",
                [TestRailwayNetwork.LINE_PARALLELLINE],
            ),
            (
                "create_parallel_south",
                TestRailwayNetwork.STATION_PARALLEL_SOUTH,
                "Parallel South",
                [TestRailwayNetwork.LINE_PARALLELLINE],
            ),
            # Asymmetricline stations
            (
                "create_asym_west",
                TestRailwayNetwork.STATION_ASYM_WEST,
                "Asym West",
                [TestRailwayNetwork.LINE_ASYMMETRICLINE],
            ),
            (
                "create_asym_regular_1",
                TestRailwayNetwork.STATION_ASYM_REGULAR_1,
                "Asym Regular 1",
                [TestRailwayNetwork.LINE_ASYMMETRICLINE],
            ),
            (
                "create_asym_skip_station",
                TestRailwayNetwork.STATION_ASYM_SKIP_STATION,
                "Asym Skip Station",
                [TestRailwayNetwork.LINE_ASYMMETRICLINE],
            ),
            (
                "create_asym_regular_2",
                TestRailwayNetwork.STATION_ASYM_REGULAR_2,
                "Asym Regular 2",
                [TestRailwayNetwork.LINE_ASYMMETRICLINE],
            ),
            (
                "create_asym_east",
                TestRailwayNetwork.STATION_ASYM_EAST,
                "Asym East",
                [TestRailwayNetwork.LINE_ASYMMETRICLINE],
            ),
            # TwoStopline stations
            (
                "create_twostop_west",
                TestRailwayNetwork.STATION_TWOSTOP_WEST,
                "TwoStop West",
                [TestRailwayNetwork.LINE_2STOPLINE],
            ),
            (
                "create_twostop_east",
                TestRailwayNetwork.STATION_TWOSTOP_EAST,
                "TwoStop East",
                [TestRailwayNetwork.LINE_2STOPLINE],
            ),
            # SharedLine A stations
            (
                "create_shareda_1",
                TestRailwayNetwork.STATION_SHAREDA_1,
                "SharedA 1",
                [TestRailwayNetwork.LINE_SHAREDLINE_A],
            ),
            (
                "create_shareda_2",
                TestRailwayNetwork.STATION_SHAREDA_2,
                "SharedA 2",
                [TestRailwayNetwork.LINE_SHAREDLINE_A],
            ),
            (
                "create_shareda_4",
                TestRailwayNetwork.STATION_SHAREDA_4,
                "SharedA 4",
                [TestRailwayNetwork.LINE_SHAREDLINE_A],
            ),
            # SharedLine B stations
            (
                "create_sharedb_1",
                TestRailwayNetwork.STATION_SHAREDB_1,
                "SharedB 1",
                [TestRailwayNetwork.LINE_SHAREDLINE_B],
            ),
            (
                "create_sharedb_2",
                TestRailwayNetwork.STATION_SHAREDB_2,
                "SharedB 2",
                [TestRailwayNetwork.LINE_SHAREDLINE_B],
            ),
            (
                "create_sharedb_4",
                TestRailwayNetwork.STATION_SHAREDB_4,
                "SharedB 4",
                [TestRailwayNetwork.LINE_SHAREDLINE_B],
            ),
            # SharedLine C stations
            (
                "create_sharedc_1",
                TestRailwayNetwork.STATION_SHAREDC_1,
                "SharedC 1",
                [TestRailwayNetwork.LINE_SHAREDLINE_C],
            ),
            (
                "create_sharedc_2",
                TestRailwayNetwork.STATION_SHAREDC_2,
                "SharedC 2",
                [TestRailwayNetwork.LINE_SHAREDLINE_C],
            ),
            (
                "create_sharedc_4",
                TestRailwayNetwork.STATION_SHAREDC_4,
                "SharedC 4",
                [TestRailwayNetwork.LINE_SHAREDLINE_C],
            ),
            # Elizabethline stations
            (
                "create_elizabeth_west",
                TestRailwayNetwork.STATION_ELIZABETH_WEST,
                "Elizabeth West",
                [TestRailwayNetwork.LINE_ELIZABETHLINE],
            ),
            (
                "create_elizabeth_mid",
                TestRailwayNetwork.STATION_ELIZABETH_MID,
                "Elizabeth Mid",
                [TestRailwayNetwork.LINE_ELIZABETHLINE],
            ),
            (
                "create_elizabeth_east",
                TestRailwayNetwork.STATION_ELIZABETH_EAST,
                "Elizabeth East",
                [TestRailwayNetwork.LINE_ELIZABETHLINE],
            ),
        ],
        ids=[
            "west-fork-2",
            "west-fork",
            "east-fork-2",
            "east-fork",
            "fork-mid-2",
            "fork-south-end",
            "via-bank-1",
            "via-bank-2",
            "via-charing-1",
            "via-charing-2",
            "parallel-south",
            "asym-west",
            "asym-regular-1",
            "asym-skip-station",
            "asym-regular-2",
            "asym-east",
            "twostop-west",
            "twostop-east",
            "shareda-1",
            "shareda-2",
            "shareda-4",
            "sharedb-1",
            "sharedb-2",
            "sharedb-4",
            "sharedc-1",
            "sharedc-2",
            "sharedc-4",
            "elizabeth-west",
            "elizabeth-mid",
            "elizabeth-east",
        ],
    )
    def test_standalone_stations(
        self,
        factory_method: str,
        expected_tfl_id: str,
        expected_name: str,
        expected_lines: list[str],
    ) -> None:
        """Test standalone station factories have correct basic attributes."""
        station = getattr(TestRailwayNetwork, factory_method)()

        assert station.tfl_id == expected_tfl_id
        assert station.name == expected_name
        assert station.lines == expected_lines


class TestSimpleLineFactories:
    """Tests for line factory methods with simple route structures."""

    @pytest.mark.parametrize(
        (
            "factory_method",
            "expected_tfl_id",
            "expected_name",
            "expected_mode",
            "expected_route_count",
            "expected_route_names",
        ),
        [
            (
                "create_2stopline",
                TestRailwayNetwork.LINE_2STOPLINE,
                "2 Stop Line",
                "dlr",
                2,
                {"Eastbound", "Westbound"},
            ),
            (
                "create_sharedline_a",
                TestRailwayNetwork.LINE_SHAREDLINE_A,
                "SharedLine A",
                "tube",
                2,
                {"Eastbound", "Westbound"},
            ),
            (
                "create_sharedline_b",
                TestRailwayNetwork.LINE_SHAREDLINE_B,
                "SharedLine B",
                "tube",
                2,
                {"Eastbound", "Westbound"},
            ),
            (
                "create_sharedline_c",
                TestRailwayNetwork.LINE_SHAREDLINE_C,
                "SharedLine C",
                "tube",
                2,
                {"Eastbound", "Westbound"},
            ),
            (
                "create_asymmetricline",
                TestRailwayNetwork.LINE_ASYMMETRICLINE,
                "Asymmetric Line",
                "overground",
                2,
                {"Eastbound", "Westbound"},
            ),
            (
                "create_elizabethline",
                TestRailwayNetwork.LINE_ELIZABETHLINE,
                "Elizabeth Line",
                "elizabeth-line",
                2,
                {"Eastbound", "Westbound"},
            ),
        ],
        ids=[
            "2stopline",
            "sharedline-a",
            "sharedline-b",
            "sharedline-c",
            "asymmetricline",
            "elizabethline",
        ],
    )
    def test_simple_line_factories(
        self,
        factory_method: str,
        expected_tfl_id: str,
        expected_name: str,
        expected_mode: str,
        expected_route_count: int,
        expected_route_names: set[str],
    ) -> None:
        """Test line factories have correct basic attributes and route structure."""
        line = getattr(TestRailwayNetwork, factory_method)()

        assert line.tfl_id == expected_tfl_id
        assert line.name == expected_name
        assert line.mode == expected_mode
        assert line.route_variants is not None
        assert "routes" in line.route_variants
        assert len(line.route_variants["routes"]) == expected_route_count

        route_names = {route["name"] for route in line.route_variants["routes"]}
        assert route_names == expected_route_names


class TestComplexLineFactories:
    """Tests for line factories with complex route structures requiring detailed validation."""

    def test_create_forkedline(self) -> None:
        """Test forkedline (tube) factory."""
        line = TestRailwayNetwork.create_forkedline()

        assert line.tfl_id == TestRailwayNetwork.LINE_FORKEDLINE
        assert line.name == "Forked Line"
        assert line.mode == "tube"
        assert line.route_variants is not None
        assert "routes" in line.route_variants
        assert len(line.route_variants["routes"]) == 4  # 4 route variants (2 branches x 2 directions)

        # Verify route names
        assert line.route_variants is not None
        route_names = {route["name"] for route in line.route_variants["routes"]}
        assert route_names == {
            "West Branch Southbound",
            "West Branch Northbound",
            "East Branch Southbound",
            "East Branch Northbound",
        }

        # Verify West Branch Southbound sequence
        assert line.route_variants is not None
        west_sb = next(r for r in line.route_variants["routes"] if r["name"] == "West Branch Southbound")
        assert west_sb["stations"] == [
            TestRailwayNetwork.STATION_WEST_FORK_2,
            TestRailwayNetwork.STATION_WEST_FORK,
            TestRailwayNetwork.STATION_FORK_JUNCTION,
            TestRailwayNetwork.STATION_FORK_MID_1,
            TestRailwayNetwork.STATION_FORK_MID_2,
            TestRailwayNetwork.STATION_FORK_SOUTH_END,
        ]

        # Verify East Branch Southbound sequence
        assert line.route_variants is not None
        east_sb = next(r for r in line.route_variants["routes"] if r["name"] == "East Branch Southbound")
        assert east_sb["stations"] == [
            TestRailwayNetwork.STATION_EAST_FORK_2,
            TestRailwayNetwork.STATION_EAST_FORK,
            TestRailwayNetwork.STATION_FORK_JUNCTION,
            TestRailwayNetwork.STATION_FORK_MID_1,
            TestRailwayNetwork.STATION_FORK_MID_2,
            TestRailwayNetwork.STATION_FORK_SOUTH_END,
        ]

    def test_create_parallelline(self) -> None:
        """Test parallelline (tube) factory."""
        line = TestRailwayNetwork.create_parallelline()

        assert line.tfl_id == TestRailwayNetwork.LINE_PARALLELLINE
        assert line.name == "Parallel Line"
        assert line.mode == "tube"
        assert line.route_variants is not None
        assert "routes" in line.route_variants
        assert len(line.route_variants["routes"]) == 4  # 4 route variants (2 branches x 2 directions)

        # Verify route names
        assert line.route_variants is not None
        route_names = {route["name"] for route in line.route_variants["routes"]}
        assert route_names == {
            "Via Bank Southbound",
            "Via Bank Northbound",
            "Via Charing Southbound",
            "Via Charing Northbound",
        }

        # Verify Via Bank Southbound sequence
        assert line.route_variants is not None
        bank_sb = next(r for r in line.route_variants["routes"] if r["name"] == "Via Bank Southbound")
        assert bank_sb["stations"] == [
            TestRailwayNetwork.STATION_PARALLEL_NORTH,
            TestRailwayNetwork.STATION_PARALLEL_SPLIT,
            TestRailwayNetwork.STATION_VIA_BANK_1,
            TestRailwayNetwork.STATION_VIA_BANK_2,
            TestRailwayNetwork.STATION_PARALLEL_REJOIN,
            TestRailwayNetwork.STATION_PARALLEL_SOUTH,
        ]

        # Verify Via Charing Southbound sequence
        assert line.route_variants is not None
        charing_sb = next(r for r in line.route_variants["routes"] if r["name"] == "Via Charing Southbound")
        assert charing_sb["stations"] == [
            TestRailwayNetwork.STATION_PARALLEL_NORTH,
            TestRailwayNetwork.STATION_PARALLEL_SPLIT,
            TestRailwayNetwork.STATION_VIA_CHARING_1,
            TestRailwayNetwork.STATION_VIA_CHARING_2,
            TestRailwayNetwork.STATION_PARALLEL_REJOIN,
            TestRailwayNetwork.STATION_PARALLEL_SOUTH,
        ]


class TestLineRouteDetails:
    """Tests for specific line route details."""

    def test_2stopline_route_sequences(self) -> None:
        """Test 2stopline has correct station sequences."""
        line = TestRailwayNetwork.create_2stopline()

        assert line.route_variants is not None
        eastbound = next(r for r in line.route_variants["routes"] if r["name"] == "Eastbound")
        assert eastbound["stations"] == [
            TestRailwayNetwork.STATION_TWOSTOP_WEST,
            TestRailwayNetwork.STATION_TWOSTOP_EAST,
        ]

        assert line.route_variants is not None
        westbound = next(r for r in line.route_variants["routes"] if r["name"] == "Westbound")
        assert westbound["stations"] == [
            TestRailwayNetwork.STATION_TWOSTOP_EAST,
            TestRailwayNetwork.STATION_TWOSTOP_WEST,
        ]

    @pytest.mark.parametrize(
        ("factory_method", "station_1", "station_2", "station_4", "station_5"),
        [
            (
                "create_sharedline_a",
                TestRailwayNetwork.STATION_SHAREDA_1,
                TestRailwayNetwork.STATION_SHAREDA_2,
                TestRailwayNetwork.STATION_SHAREDA_4,
                TestRailwayNetwork.STATION_SHAREDA_5,
            ),
            (
                "create_sharedline_b",
                TestRailwayNetwork.STATION_SHAREDB_1,
                TestRailwayNetwork.STATION_SHAREDB_2,
                TestRailwayNetwork.STATION_SHAREDB_4,
                TestRailwayNetwork.STATION_SHAREDB_5,
            ),
            (
                "create_sharedline_c",
                TestRailwayNetwork.STATION_SHAREDC_1,
                TestRailwayNetwork.STATION_SHAREDC_2,
                TestRailwayNetwork.STATION_SHAREDC_4,
                TestRailwayNetwork.STATION_SHAREDC_5,
            ),
        ],
        ids=["sharedline-a", "sharedline-b", "sharedline-c"],
    )
    def test_sharedlines_include_shared_station(
        self,
        factory_method: str,
        station_1: str,
        station_2: str,
        station_4: str,
        station_5: str,
    ) -> None:
        """Test sharedlines include shared-station at position 3."""
        line = getattr(TestRailwayNetwork, factory_method)()

        assert line.route_variants is not None
        eastbound = next(r for r in line.route_variants["routes"] if r["name"] == "Eastbound")
        assert eastbound["stations"] == [
            station_1,
            station_2,
            TestRailwayNetwork.STATION_SHARED_STATION,
            station_4,
            station_5,
        ]

    def test_asymmetricline_route_sequences(self) -> None:
        """Test asymmetricline has different eastbound/westbound sequences."""
        line = TestRailwayNetwork.create_asymmetricline()

        # Verify Eastbound sequence (includes skip station)
        assert line.route_variants is not None
        eastbound = next(r for r in line.route_variants["routes"] if r["name"] == "Eastbound")
        assert eastbound["stations"] == [
            TestRailwayNetwork.STATION_ASYM_WEST,
            TestRailwayNetwork.STATION_ASYM_REGULAR_1,
            TestRailwayNetwork.STATION_ASYM_SKIP_STATION,  # Only in eastbound!
            TestRailwayNetwork.STATION_ASYM_REGULAR_2,
            TestRailwayNetwork.STATION_ASYM_EAST,
        ]

        # Verify Westbound sequence (SKIPS skip station)
        assert line.route_variants is not None
        westbound = next(r for r in line.route_variants["routes"] if r["name"] == "Westbound")
        assert westbound["stations"] == [
            TestRailwayNetwork.STATION_ASYM_EAST,
            TestRailwayNetwork.STATION_ASYM_REGULAR_2,
            TestRailwayNetwork.STATION_ASYM_REGULAR_1,
            TestRailwayNetwork.STATION_ASYM_WEST,
        ]
        assert TestRailwayNetwork.STATION_ASYM_SKIP_STATION not in westbound["stations"]

    def test_elizabethline_route_sequences(self) -> None:
        """Test elizabethline has correct station sequences."""
        line = TestRailwayNetwork.create_elizabethline()

        # Verify Eastbound sequence
        assert line.route_variants is not None
        eastbound = next(r for r in line.route_variants["routes"] if r["name"] == "Eastbound")
        assert eastbound["stations"] == [
            TestRailwayNetwork.STATION_ELIZABETH_WEST,
            TestRailwayNetwork.STATION_HUBNORTH_ELIZABETH,
            TestRailwayNetwork.STATION_ELIZABETH_MID,
            TestRailwayNetwork.STATION_ELIZABETH_EAST,
        ]

        # Verify Westbound sequence
        assert line.route_variants is not None
        westbound = next(r for r in line.route_variants["routes"] if r["name"] == "Westbound")
        assert westbound["stations"] == [
            TestRailwayNetwork.STATION_ELIZABETH_EAST,
            TestRailwayNetwork.STATION_ELIZABETH_MID,
            TestRailwayNetwork.STATION_HUBNORTH_ELIZABETH,
            TestRailwayNetwork.STATION_ELIZABETH_WEST,
        ]


class TestNetworkValidation:
    """Tests validating network structure and hub consistency."""

    @pytest.mark.parametrize(
        ("factory_methods", "expected_hub_naptan", "expected_hub_name"),
        [
            (
                [
                    "create_parallel_north",
                    "create_hubnorth_overground",
                    "create_hubnorth_elizabeth",
                    "create_hubnorth_bus",
                ],
                TestRailwayNetwork.HUB_NORTH,
                TestRailwayNetwork.HUB_NORTH_NAME,
            ),
            (
                ["create_fork_mid_1", "create_hubcentral_dlr"],
                TestRailwayNetwork.HUB_CENTRAL,
                TestRailwayNetwork.HUB_CENTRAL_NAME,
            ),
        ],
        ids=["hub-north", "hub-central"],
    )
    def test_hub_children_share_naptan_code(
        self,
        factory_methods: list[str],
        expected_hub_naptan: str,
        expected_hub_name: str,
    ) -> None:
        """Test all hub children have correct hub_naptan_code and hub_common_name."""
        hub_children = [getattr(TestRailwayNetwork, method)() for method in factory_methods]

        # All must have the expected hub naptan code and name
        for station in hub_children:
            assert station.hub_naptan_code == expected_hub_naptan
            assert station.hub_common_name == expected_hub_name

    def test_branch_junctions_are_not_hubs(self) -> None:
        """Test branch junctions have NO hub_naptan_code (they are NOT hubs)."""
        junctions = [
            TestRailwayNetwork.create_fork_junction(),
            TestRailwayNetwork.create_parallel_split(),
            TestRailwayNetwork.create_parallel_rejoin(),
        ]

        # None should be hubs
        for station in junctions:
            assert station.hub_naptan_code is None
            assert station.hub_common_name is None

    def test_shared_station_appears_on_exactly_three_lines(self) -> None:
        """Test shared-station appears on exactly 3 lines."""
        shared_station = TestRailwayNetwork.create_shared_station()

        assert len(shared_station.lines) == 3
        assert set(shared_station.lines) == {
            TestRailwayNetwork.LINE_SHAREDLINE_A,
            TestRailwayNetwork.LINE_SHAREDLINE_B,
            TestRailwayNetwork.LINE_SHAREDLINE_C,
        }

    def test_asymmetricline_eastbound_westbound_are_different(self) -> None:
        """Test asymmetricline eastbound != westbound (non-symmetric)."""
        line = TestRailwayNetwork.create_asymmetricline()

        assert line.route_variants is not None
        eastbound = next(r for r in line.route_variants["routes"] if r["name"] == "Eastbound")
        assert line.route_variants is not None
        westbound = next(r for r in line.route_variants["routes"] if r["name"] == "Westbound")

        # Eastbound has 5 stations, westbound has 4
        assert len(eastbound["stations"]) == 5
        assert len(westbound["stations"]) == 4

        # asym-skip-station only in eastbound
        assert TestRailwayNetwork.STATION_ASYM_SKIP_STATION in eastbound["stations"]
        assert TestRailwayNetwork.STATION_ASYM_SKIP_STATION not in westbound["stations"]

    def test_hub_north_has_four_modes(self) -> None:
        """Test HUB_NORTH has children from 4 different modes."""
        hub_north_children = [
            TestRailwayNetwork.create_parallel_north(),  # tube
            TestRailwayNetwork.create_hubnorth_overground(),  # overground
            TestRailwayNetwork.create_hubnorth_elizabeth(),  # elizabeth-line
            TestRailwayNetwork.create_hubnorth_bus(),  # bus (no line)
        ]

        # Verify 3 have lines (bus has empty list)
        children_with_lines = [s for s in hub_north_children if s.lines]
        assert len(children_with_lines) == 3

        # Verify bus child exists with empty lines
        bus_child = TestRailwayNetwork.create_hubnorth_bus()
        assert bus_child.lines == []
        assert bus_child.hub_naptan_code == TestRailwayNetwork.HUB_NORTH

    def test_forkedline_branches_converge_at_fork_junction(self) -> None:
        """Test forkedline west and east branches both pass through fork-junction."""
        line = TestRailwayNetwork.create_forkedline()

        assert line.route_variants is not None
        west_sb = next(r for r in line.route_variants["routes"] if r["name"] == "West Branch Southbound")
        assert line.route_variants is not None
        east_sb = next(r for r in line.route_variants["routes"] if r["name"] == "East Branch Southbound")

        # Both branches must include fork-junction
        assert TestRailwayNetwork.STATION_FORK_JUNCTION in west_sb["stations"]
        assert TestRailwayNetwork.STATION_FORK_JUNCTION in east_sb["stations"]

        # After junction, both follow same trunk
        west_after_junction = west_sb["stations"][west_sb["stations"].index(TestRailwayNetwork.STATION_FORK_JUNCTION) :]
        east_after_junction = east_sb["stations"][east_sb["stations"].index(TestRailwayNetwork.STATION_FORK_JUNCTION) :]

        assert west_after_junction == east_after_junction

    def test_parallelline_branches_split_and_rejoin(self) -> None:
        """Test parallelline branches split and rejoin at correct stations."""
        line = TestRailwayNetwork.create_parallelline()

        assert line.route_variants is not None
        bank_sb = next(r for r in line.route_variants["routes"] if r["name"] == "Via Bank Southbound")
        assert line.route_variants is not None
        charing_sb = next(r for r in line.route_variants["routes"] if r["name"] == "Via Charing Southbound")

        # Both must split at parallel-split
        assert bank_sb["stations"][1] == TestRailwayNetwork.STATION_PARALLEL_SPLIT
        assert charing_sb["stations"][1] == TestRailwayNetwork.STATION_PARALLEL_SPLIT

        # Both must rejoin at parallel-rejoin
        assert TestRailwayNetwork.STATION_PARALLEL_REJOIN in bank_sb["stations"]
        assert TestRailwayNetwork.STATION_PARALLEL_REJOIN in charing_sb["stations"]

        # Before split, same stations
        assert bank_sb["stations"][:2] == charing_sb["stations"][:2]

        # After rejoin, same stations
        bank_after_rejoin = bank_sb["stations"][bank_sb["stations"].index(TestRailwayNetwork.STATION_PARALLEL_REJOIN) :]
        charing_after_rejoin = charing_sb["stations"][
            charing_sb["stations"].index(TestRailwayNetwork.STATION_PARALLEL_REJOIN) :
        ]
        assert bank_after_rejoin == charing_after_rejoin
