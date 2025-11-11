"""Unit tests for TestRailwayNetwork factory methods."""

from tests.conftest import TestRailwayNetwork


class TestHubChildrenFactories:
    """Tests for hub children station factories."""

    def test_create_parallel_north(self) -> None:
        """Test parallel-north station (HUB_NORTH tube child)."""
        station = TestRailwayNetwork.create_parallel_north()

        assert station.tfl_id == TestRailwayNetwork.STATION_PARALLEL_NORTH
        assert station.name == "North Interchange (Tube)"
        assert station.lines == [TestRailwayNetwork.LINE_PARALLELLINE]
        assert station.hub_naptan_code == TestRailwayNetwork.HUB_NORTH
        assert station.hub_common_name == TestRailwayNetwork.HUB_NORTH_NAME

    def test_create_hubnorth_overground(self) -> None:
        """Test hubnorth-overground station (HUB_NORTH overground child)."""
        station = TestRailwayNetwork.create_hubnorth_overground()

        assert station.tfl_id == TestRailwayNetwork.STATION_HUBNORTH_OVERGROUND
        assert station.name == "North Interchange (Overground)"
        assert station.lines == [TestRailwayNetwork.LINE_ASYMMETRICLINE]
        assert station.hub_naptan_code == TestRailwayNetwork.HUB_NORTH
        assert station.hub_common_name == TestRailwayNetwork.HUB_NORTH_NAME

    def test_create_hubnorth_elizabeth(self) -> None:
        """Test hubnorth-elizabeth station (HUB_NORTH elizabeth-line child)."""
        station = TestRailwayNetwork.create_hubnorth_elizabeth()

        assert station.tfl_id == TestRailwayNetwork.STATION_HUBNORTH_ELIZABETH
        assert station.name == "North Interchange (Elizabeth line)"
        assert station.lines == [TestRailwayNetwork.LINE_ELIZABETHLINE]
        assert station.hub_naptan_code == TestRailwayNetwork.HUB_NORTH
        assert station.hub_common_name == TestRailwayNetwork.HUB_NORTH_NAME

    def test_create_hubnorth_bus(self) -> None:
        """Test hubnorth-bus station (HUB_NORTH bus child with no line)."""
        station = TestRailwayNetwork.create_hubnorth_bus()

        assert station.tfl_id == TestRailwayNetwork.STATION_HUBNORTH_BUS
        assert station.name == "North Interchange (Bus)"
        assert station.lines == []  # No line - bus mode not in network
        assert station.hub_naptan_code == TestRailwayNetwork.HUB_NORTH
        assert station.hub_common_name == TestRailwayNetwork.HUB_NORTH_NAME

    def test_create_fork_mid_1(self) -> None:
        """Test fork-mid-1 station (HUB_CENTRAL tube child)."""
        station = TestRailwayNetwork.create_fork_mid_1()

        assert station.tfl_id == TestRailwayNetwork.STATION_FORK_MID_1
        assert station.name == "Central Hub (Tube)"
        assert station.lines == [TestRailwayNetwork.LINE_FORKEDLINE]
        assert station.hub_naptan_code == TestRailwayNetwork.HUB_CENTRAL
        assert station.hub_common_name == TestRailwayNetwork.HUB_CENTRAL_NAME

    def test_create_hubcentral_dlr(self) -> None:
        """Test hubcentral-dlr station (HUB_CENTRAL dlr child)."""
        station = TestRailwayNetwork.create_hubcentral_dlr()

        assert station.tfl_id == TestRailwayNetwork.STATION_HUBCENTRAL_DLR
        assert station.name == "Central Hub (DLR)"
        assert station.lines == [TestRailwayNetwork.LINE_2STOPLINE]
        assert station.hub_naptan_code == TestRailwayNetwork.HUB_CENTRAL
        assert station.hub_common_name == TestRailwayNetwork.HUB_CENTRAL_NAME


class TestBranchJunctionFactories:
    """Tests for branch junction station factories (NOT hubs)."""

    def test_create_fork_junction(self) -> None:
        """Test fork-junction station (branch convergence, NOT a hub)."""
        station = TestRailwayNetwork.create_fork_junction()

        assert station.tfl_id == TestRailwayNetwork.STATION_FORK_JUNCTION
        assert station.name == "Fork Junction"
        assert station.lines == [TestRailwayNetwork.LINE_FORKEDLINE]
        assert station.hub_naptan_code is None  # NOT a hub
        assert station.hub_common_name is None

    def test_create_parallel_split(self) -> None:
        """Test parallel-split station (branch split, NOT a hub)."""
        station = TestRailwayNetwork.create_parallel_split()

        assert station.tfl_id == TestRailwayNetwork.STATION_PARALLEL_SPLIT
        assert station.name == "Parallel Split"
        assert station.lines == [TestRailwayNetwork.LINE_PARALLELLINE]
        assert station.hub_naptan_code is None  # NOT a hub
        assert station.hub_common_name is None

    def test_create_parallel_rejoin(self) -> None:
        """Test parallel-rejoin station (branch rejoin, NOT a hub)."""
        station = TestRailwayNetwork.create_parallel_rejoin()

        assert station.tfl_id == TestRailwayNetwork.STATION_PARALLEL_REJOIN
        assert station.name == "Parallel Rejoin"
        assert station.lines == [TestRailwayNetwork.LINE_PARALLELLINE]
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


class TestForkedlineStationFactories:
    """Tests for forkedline standalone station factories."""

    def test_create_west_fork_2(self) -> None:
        """Test west-fork-2 station (west branch terminus)."""
        station = TestRailwayNetwork.create_west_fork_2()

        assert station.tfl_id == TestRailwayNetwork.STATION_WEST_FORK_2
        assert station.name == "West Fork 2"
        assert station.lines == [TestRailwayNetwork.LINE_FORKEDLINE]
        assert station.hub_naptan_code is None

    def test_create_west_fork(self) -> None:
        """Test west-fork station."""
        station = TestRailwayNetwork.create_west_fork()

        assert station.tfl_id == TestRailwayNetwork.STATION_WEST_FORK
        assert station.name == "West Fork"
        assert station.lines == [TestRailwayNetwork.LINE_FORKEDLINE]

    def test_create_east_fork_2(self) -> None:
        """Test east-fork-2 station (east branch terminus)."""
        station = TestRailwayNetwork.create_east_fork_2()

        assert station.tfl_id == TestRailwayNetwork.STATION_EAST_FORK_2
        assert station.name == "East Fork 2"
        assert station.lines == [TestRailwayNetwork.LINE_FORKEDLINE]

    def test_create_east_fork(self) -> None:
        """Test east-fork station."""
        station = TestRailwayNetwork.create_east_fork()

        assert station.tfl_id == TestRailwayNetwork.STATION_EAST_FORK
        assert station.name == "East Fork"
        assert station.lines == [TestRailwayNetwork.LINE_FORKEDLINE]

    def test_create_fork_mid_2(self) -> None:
        """Test fork-mid-2 station (trunk)."""
        station = TestRailwayNetwork.create_fork_mid_2()

        assert station.tfl_id == TestRailwayNetwork.STATION_FORK_MID_2
        assert station.name == "Fork Mid 2"
        assert station.lines == [TestRailwayNetwork.LINE_FORKEDLINE]

    def test_create_fork_south_end(self) -> None:
        """Test fork-south-end station (southern terminus)."""
        station = TestRailwayNetwork.create_fork_south_end()

        assert station.tfl_id == TestRailwayNetwork.STATION_FORK_SOUTH_END
        assert station.name == "Fork South End"
        assert station.lines == [TestRailwayNetwork.LINE_FORKEDLINE]


class TestParallellineStationFactories:
    """Tests for parallelline standalone station factories."""

    def test_create_via_bank_1(self) -> None:
        """Test via-bank-1 station."""
        station = TestRailwayNetwork.create_via_bank_1()

        assert station.tfl_id == TestRailwayNetwork.STATION_VIA_BANK_1
        assert station.name == "Via Bank 1"
        assert station.lines == [TestRailwayNetwork.LINE_PARALLELLINE]

    def test_create_via_bank_2(self) -> None:
        """Test via-bank-2 station."""
        station = TestRailwayNetwork.create_via_bank_2()

        assert station.tfl_id == TestRailwayNetwork.STATION_VIA_BANK_2
        assert station.name == "Via Bank 2"
        assert station.lines == [TestRailwayNetwork.LINE_PARALLELLINE]

    def test_create_via_charing_1(self) -> None:
        """Test via-charing-1 station."""
        station = TestRailwayNetwork.create_via_charing_1()

        assert station.tfl_id == TestRailwayNetwork.STATION_VIA_CHARING_1
        assert station.name == "Via Charing 1"
        assert station.lines == [TestRailwayNetwork.LINE_PARALLELLINE]

    def test_create_via_charing_2(self) -> None:
        """Test via-charing-2 station."""
        station = TestRailwayNetwork.create_via_charing_2()

        assert station.tfl_id == TestRailwayNetwork.STATION_VIA_CHARING_2
        assert station.name == "Via Charing 2"
        assert station.lines == [TestRailwayNetwork.LINE_PARALLELLINE]

    def test_create_parallel_south(self) -> None:
        """Test parallel-south station (southern terminus)."""
        station = TestRailwayNetwork.create_parallel_south()

        assert station.tfl_id == TestRailwayNetwork.STATION_PARALLEL_SOUTH
        assert station.name == "Parallel South"
        assert station.lines == [TestRailwayNetwork.LINE_PARALLELLINE]


class TestAsymmetriclineStationFactories:
    """Tests for asymmetricline standalone station factories."""

    def test_create_asym_west(self) -> None:
        """Test asym-west station (western terminus)."""
        station = TestRailwayNetwork.create_asym_west()

        assert station.tfl_id == TestRailwayNetwork.STATION_ASYM_WEST
        assert station.name == "Asym West"
        assert station.lines == [TestRailwayNetwork.LINE_ASYMMETRICLINE]

    def test_create_asym_regular_1(self) -> None:
        """Test asym-regular-1 station (serves both directions)."""
        station = TestRailwayNetwork.create_asym_regular_1()

        assert station.tfl_id == TestRailwayNetwork.STATION_ASYM_REGULAR_1
        assert station.name == "Asym Regular 1"
        assert station.lines == [TestRailwayNetwork.LINE_ASYMMETRICLINE]

    def test_create_asym_skip_station(self) -> None:
        """Test asym-skip-station (eastbound only)."""
        station = TestRailwayNetwork.create_asym_skip_station()

        assert station.tfl_id == TestRailwayNetwork.STATION_ASYM_SKIP_STATION
        assert station.name == "Asym Skip Station"
        assert station.lines == [TestRailwayNetwork.LINE_ASYMMETRICLINE]

    def test_create_asym_regular_2(self) -> None:
        """Test asym-regular-2 station (serves both directions)."""
        station = TestRailwayNetwork.create_asym_regular_2()

        assert station.tfl_id == TestRailwayNetwork.STATION_ASYM_REGULAR_2
        assert station.name == "Asym Regular 2"
        assert station.lines == [TestRailwayNetwork.LINE_ASYMMETRICLINE]

    def test_create_asym_east(self) -> None:
        """Test asym-east station (eastern terminus)."""
        station = TestRailwayNetwork.create_asym_east()

        assert station.tfl_id == TestRailwayNetwork.STATION_ASYM_EAST
        assert station.name == "Asym East"
        assert station.lines == [TestRailwayNetwork.LINE_ASYMMETRICLINE]


class TestTwoStoplineStationFactories:
    """Tests for 2stopline standalone station factories."""

    def test_create_twostop_west(self) -> None:
        """Test twostop-west station (western terminus)."""
        station = TestRailwayNetwork.create_twostop_west()

        assert station.tfl_id == TestRailwayNetwork.STATION_TWOSTOP_WEST
        assert station.name == "TwoStop West"
        assert station.lines == [TestRailwayNetwork.LINE_2STOPLINE]

    def test_create_twostop_east(self) -> None:
        """Test twostop-east station (eastern terminus)."""
        station = TestRailwayNetwork.create_twostop_east()

        assert station.tfl_id == TestRailwayNetwork.STATION_TWOSTOP_EAST
        assert station.name == "TwoStop East"
        assert station.lines == [TestRailwayNetwork.LINE_2STOPLINE]


class TestSharedlineAStationFactories:
    """Tests for sharedline-a standalone station factories."""

    def test_create_shareda_1(self) -> None:
        """Test shareda-1 station."""
        station = TestRailwayNetwork.create_shareda_1()

        assert station.tfl_id == TestRailwayNetwork.STATION_SHAREDA_1
        assert station.name == "SharedA 1"
        assert station.lines == [TestRailwayNetwork.LINE_SHAREDLINE_A]

    def test_create_shareda_2(self) -> None:
        """Test shareda-2 station."""
        station = TestRailwayNetwork.create_shareda_2()

        assert station.tfl_id == TestRailwayNetwork.STATION_SHAREDA_2
        assert station.name == "SharedA 2"
        assert station.lines == [TestRailwayNetwork.LINE_SHAREDLINE_A]

    def test_create_shareda_4(self) -> None:
        """Test shareda-4 station."""
        station = TestRailwayNetwork.create_shareda_4()

        assert station.tfl_id == TestRailwayNetwork.STATION_SHAREDA_4
        assert station.name == "SharedA 4"
        assert station.lines == [TestRailwayNetwork.LINE_SHAREDLINE_A]


class TestSharedlineBStationFactories:
    """Tests for sharedline-b standalone station factories."""

    def test_create_sharedb_1(self) -> None:
        """Test sharedb-1 station."""
        station = TestRailwayNetwork.create_sharedb_1()

        assert station.tfl_id == TestRailwayNetwork.STATION_SHAREDB_1
        assert station.name == "SharedB 1"
        assert station.lines == [TestRailwayNetwork.LINE_SHAREDLINE_B]

    def test_create_sharedb_2(self) -> None:
        """Test sharedb-2 station."""
        station = TestRailwayNetwork.create_sharedb_2()

        assert station.tfl_id == TestRailwayNetwork.STATION_SHAREDB_2
        assert station.name == "SharedB 2"
        assert station.lines == [TestRailwayNetwork.LINE_SHAREDLINE_B]

    def test_create_sharedb_4(self) -> None:
        """Test sharedb-4 station."""
        station = TestRailwayNetwork.create_sharedb_4()

        assert station.tfl_id == TestRailwayNetwork.STATION_SHAREDB_4
        assert station.name == "SharedB 4"
        assert station.lines == [TestRailwayNetwork.LINE_SHAREDLINE_B]


class TestSharedlineCStationFactories:
    """Tests for sharedline-c standalone station factories."""

    def test_create_sharedc_1(self) -> None:
        """Test sharedc-1 station."""
        station = TestRailwayNetwork.create_sharedc_1()

        assert station.tfl_id == TestRailwayNetwork.STATION_SHAREDC_1
        assert station.name == "SharedC 1"
        assert station.lines == [TestRailwayNetwork.LINE_SHAREDLINE_C]

    def test_create_sharedc_2(self) -> None:
        """Test sharedc-2 station."""
        station = TestRailwayNetwork.create_sharedc_2()

        assert station.tfl_id == TestRailwayNetwork.STATION_SHAREDC_2
        assert station.name == "SharedC 2"
        assert station.lines == [TestRailwayNetwork.LINE_SHAREDLINE_C]

    def test_create_sharedc_4(self) -> None:
        """Test sharedc-4 station."""
        station = TestRailwayNetwork.create_sharedc_4()

        assert station.tfl_id == TestRailwayNetwork.STATION_SHAREDC_4
        assert station.name == "SharedC 4"
        assert station.lines == [TestRailwayNetwork.LINE_SHAREDLINE_C]


class TestElizabethlineStationFactories:
    """Tests for elizabethline standalone station factories."""

    def test_create_elizabeth_west(self) -> None:
        """Test elizabeth-west station (western terminus)."""
        station = TestRailwayNetwork.create_elizabeth_west()

        assert station.tfl_id == TestRailwayNetwork.STATION_ELIZABETH_WEST
        assert station.name == "Elizabeth West"
        assert station.lines == [TestRailwayNetwork.LINE_ELIZABETHLINE]

    def test_create_elizabeth_mid(self) -> None:
        """Test elizabeth-mid station."""
        station = TestRailwayNetwork.create_elizabeth_mid()

        assert station.tfl_id == TestRailwayNetwork.STATION_ELIZABETH_MID
        assert station.name == "Elizabeth Mid"
        assert station.lines == [TestRailwayNetwork.LINE_ELIZABETHLINE]

    def test_create_elizabeth_east(self) -> None:
        """Test elizabeth-east station (eastern terminus)."""
        station = TestRailwayNetwork.create_elizabeth_east()

        assert station.tfl_id == TestRailwayNetwork.STATION_ELIZABETH_EAST
        assert station.name == "Elizabeth East"
        assert station.lines == [TestRailwayNetwork.LINE_ELIZABETHLINE]


class TestLineFactories:
    """Tests for line factory methods."""

    def test_create_forkedline(self) -> None:
        """Test forkedline (tube) factory."""
        line = TestRailwayNetwork.create_forkedline()

        assert line.tfl_id == TestRailwayNetwork.LINE_FORKEDLINE
        assert line.name == "Forked Line"
        assert line.mode == "tube"
        assert line.routes is not None
        assert "routes" in line.routes
        assert len(line.routes["routes"]) == 4  # 4 route variants (2 branches x 2 directions)

        # Verify route names
        assert line.routes is not None
        route_names = {route["name"] for route in line.routes["routes"]}
        assert route_names == {
            "West Branch Southbound",
            "West Branch Northbound",
            "East Branch Southbound",
            "East Branch Northbound",
        }

        # Verify West Branch Southbound sequence
        assert line.routes is not None
        west_sb = next(r for r in line.routes["routes"] if r["name"] == "West Branch Southbound")
        assert west_sb["stations"] == [
            TestRailwayNetwork.STATION_WEST_FORK_2,
            TestRailwayNetwork.STATION_WEST_FORK,
            TestRailwayNetwork.STATION_FORK_JUNCTION,
            TestRailwayNetwork.STATION_FORK_MID_1,
            TestRailwayNetwork.STATION_FORK_MID_2,
            TestRailwayNetwork.STATION_FORK_SOUTH_END,
        ]

        # Verify East Branch Southbound sequence
        assert line.routes is not None
        east_sb = next(r for r in line.routes["routes"] if r["name"] == "East Branch Southbound")
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
        assert line.routes is not None
        assert "routes" in line.routes
        assert len(line.routes["routes"]) == 4  # 4 route variants (2 branches x 2 directions)

        # Verify route names
        assert line.routes is not None
        route_names = {route["name"] for route in line.routes["routes"]}
        assert route_names == {
            "Via Bank Southbound",
            "Via Bank Northbound",
            "Via Charing Southbound",
            "Via Charing Northbound",
        }

        # Verify Via Bank Southbound sequence
        assert line.routes is not None
        bank_sb = next(r for r in line.routes["routes"] if r["name"] == "Via Bank Southbound")
        assert bank_sb["stations"] == [
            TestRailwayNetwork.STATION_PARALLEL_NORTH,
            TestRailwayNetwork.STATION_PARALLEL_SPLIT,
            TestRailwayNetwork.STATION_VIA_BANK_1,
            TestRailwayNetwork.STATION_VIA_BANK_2,
            TestRailwayNetwork.STATION_PARALLEL_REJOIN,
            TestRailwayNetwork.STATION_PARALLEL_SOUTH,
        ]

        # Verify Via Charing Southbound sequence
        assert line.routes is not None
        charing_sb = next(r for r in line.routes["routes"] if r["name"] == "Via Charing Southbound")
        assert charing_sb["stations"] == [
            TestRailwayNetwork.STATION_PARALLEL_NORTH,
            TestRailwayNetwork.STATION_PARALLEL_SPLIT,
            TestRailwayNetwork.STATION_VIA_CHARING_1,
            TestRailwayNetwork.STATION_VIA_CHARING_2,
            TestRailwayNetwork.STATION_PARALLEL_REJOIN,
            TestRailwayNetwork.STATION_PARALLEL_SOUTH,
        ]

    def test_create_asymmetricline(self) -> None:
        """Test asymmetricline (overground) factory."""
        line = TestRailwayNetwork.create_asymmetricline()

        assert line.tfl_id == TestRailwayNetwork.LINE_ASYMMETRICLINE
        assert line.name == "Asymmetric Line"
        assert line.mode == "overground"
        assert line.routes is not None
        assert "routes" in line.routes
        assert len(line.routes["routes"]) == 2  # 2 route variants (eastbound, westbound)

        # Verify route names
        assert line.routes is not None
        route_names = {route["name"] for route in line.routes["routes"]}
        assert route_names == {"Eastbound", "Westbound"}

        # Verify Eastbound sequence (includes skip station)
        assert line.routes is not None
        eastbound = next(r for r in line.routes["routes"] if r["name"] == "Eastbound")
        assert eastbound["stations"] == [
            TestRailwayNetwork.STATION_ASYM_WEST,
            TestRailwayNetwork.STATION_ASYM_REGULAR_1,
            TestRailwayNetwork.STATION_ASYM_SKIP_STATION,  # Only in eastbound!
            TestRailwayNetwork.STATION_ASYM_REGULAR_2,
            TestRailwayNetwork.STATION_ASYM_EAST,
        ]

        # Verify Westbound sequence (SKIPS skip station)
        assert line.routes is not None
        westbound = next(r for r in line.routes["routes"] if r["name"] == "Westbound")
        assert westbound["stations"] == [
            TestRailwayNetwork.STATION_ASYM_EAST,
            TestRailwayNetwork.STATION_ASYM_REGULAR_2,
            TestRailwayNetwork.STATION_ASYM_REGULAR_1,
            TestRailwayNetwork.STATION_ASYM_WEST,
        ]
        assert TestRailwayNetwork.STATION_ASYM_SKIP_STATION not in westbound["stations"]

    def test_create_2stopline(self) -> None:
        """Test 2stopline (dlr) factory."""
        line = TestRailwayNetwork.create_2stopline()

        assert line.tfl_id == TestRailwayNetwork.LINE_2STOPLINE
        assert line.name == "2 Stop Line"
        assert line.mode == "dlr"
        assert line.routes is not None
        assert "routes" in line.routes
        assert len(line.routes["routes"]) == 2  # 2 route variants (eastbound, westbound)

        # Verify route names
        assert line.routes is not None
        route_names = {route["name"] for route in line.routes["routes"]}
        assert route_names == {"Eastbound", "Westbound"}

        # Verify Eastbound sequence
        assert line.routes is not None
        eastbound = next(r for r in line.routes["routes"] if r["name"] == "Eastbound")
        assert eastbound["stations"] == [
            TestRailwayNetwork.STATION_TWOSTOP_WEST,
            TestRailwayNetwork.STATION_TWOSTOP_EAST,
        ]

        # Verify Westbound sequence
        assert line.routes is not None
        westbound = next(r for r in line.routes["routes"] if r["name"] == "Westbound")
        assert westbound["stations"] == [
            TestRailwayNetwork.STATION_TWOSTOP_EAST,
            TestRailwayNetwork.STATION_TWOSTOP_WEST,
        ]

    def test_create_sharedline_a(self) -> None:
        """Test sharedline-a (tube) factory."""
        line = TestRailwayNetwork.create_sharedline_a()

        assert line.tfl_id == TestRailwayNetwork.LINE_SHAREDLINE_A
        assert line.name == "SharedLine A"
        assert line.mode == "tube"
        assert line.routes is not None
        assert "routes" in line.routes
        assert len(line.routes["routes"]) == 2  # 2 route variants (eastbound, westbound)

        # Verify Eastbound sequence includes shared-station
        assert line.routes is not None
        eastbound = next(r for r in line.routes["routes"] if r["name"] == "Eastbound")
        assert eastbound["stations"] == [
            TestRailwayNetwork.STATION_SHAREDA_1,
            TestRailwayNetwork.STATION_SHAREDA_2,
            TestRailwayNetwork.STATION_SHARED_STATION,
            TestRailwayNetwork.STATION_SHAREDA_4,
            TestRailwayNetwork.STATION_SHAREDA_5,
        ]

    def test_create_sharedline_b(self) -> None:
        """Test sharedline-b (tube) factory."""
        line = TestRailwayNetwork.create_sharedline_b()

        assert line.tfl_id == TestRailwayNetwork.LINE_SHAREDLINE_B
        assert line.name == "SharedLine B"
        assert line.mode == "tube"
        assert line.routes is not None
        assert "routes" in line.routes
        assert len(line.routes["routes"]) == 2  # 2 route variants (eastbound, westbound)

        # Verify Eastbound sequence includes shared-station
        assert line.routes is not None
        eastbound = next(r for r in line.routes["routes"] if r["name"] == "Eastbound")
        assert eastbound["stations"] == [
            TestRailwayNetwork.STATION_SHAREDB_1,
            TestRailwayNetwork.STATION_SHAREDB_2,
            TestRailwayNetwork.STATION_SHARED_STATION,
            TestRailwayNetwork.STATION_SHAREDB_4,
            TestRailwayNetwork.STATION_SHAREDB_5,
        ]

    def test_create_sharedline_c(self) -> None:
        """Test sharedline-c (tube) factory."""
        line = TestRailwayNetwork.create_sharedline_c()

        assert line.tfl_id == TestRailwayNetwork.LINE_SHAREDLINE_C
        assert line.name == "SharedLine C"
        assert line.mode == "tube"
        assert line.routes is not None
        assert "routes" in line.routes
        assert len(line.routes["routes"]) == 2  # 2 route variants (eastbound, westbound)

        # Verify Eastbound sequence includes shared-station
        assert line.routes is not None
        eastbound = next(r for r in line.routes["routes"] if r["name"] == "Eastbound")
        assert eastbound["stations"] == [
            TestRailwayNetwork.STATION_SHAREDC_1,
            TestRailwayNetwork.STATION_SHAREDC_2,
            TestRailwayNetwork.STATION_SHARED_STATION,
            TestRailwayNetwork.STATION_SHAREDC_4,
            TestRailwayNetwork.STATION_SHAREDC_5,
        ]

    def test_create_elizabethline(self) -> None:
        """Test elizabethline (elizabeth-line) factory."""
        line = TestRailwayNetwork.create_elizabethline()

        assert line.tfl_id == TestRailwayNetwork.LINE_ELIZABETHLINE
        assert line.name == "Elizabeth Line"
        assert line.mode == "elizabeth-line"
        assert line.routes is not None
        assert "routes" in line.routes
        assert len(line.routes["routes"]) == 2  # 2 route variants (eastbound, westbound)

        # Verify route names
        assert line.routes is not None
        route_names = {route["name"] for route in line.routes["routes"]}
        assert route_names == {"Eastbound", "Westbound"}

        # Verify Eastbound sequence
        assert line.routes is not None
        eastbound = next(r for r in line.routes["routes"] if r["name"] == "Eastbound")
        assert eastbound["stations"] == [
            TestRailwayNetwork.STATION_ELIZABETH_WEST,
            TestRailwayNetwork.STATION_HUBNORTH_ELIZABETH,
            TestRailwayNetwork.STATION_ELIZABETH_MID,
            TestRailwayNetwork.STATION_ELIZABETH_EAST,
        ]

        # Verify Westbound sequence
        assert line.routes is not None
        westbound = next(r for r in line.routes["routes"] if r["name"] == "Westbound")
        assert westbound["stations"] == [
            TestRailwayNetwork.STATION_ELIZABETH_EAST,
            TestRailwayNetwork.STATION_ELIZABETH_MID,
            TestRailwayNetwork.STATION_HUBNORTH_ELIZABETH,
            TestRailwayNetwork.STATION_ELIZABETH_WEST,
        ]


class TestNetworkValidation:
    """Tests validating network structure and hub consistency."""

    def test_hub_north_children_share_naptan_code(self) -> None:
        """Test all HUB_NORTH children have same hub_naptan_code."""
        hub_north_children = [
            TestRailwayNetwork.create_parallel_north(),
            TestRailwayNetwork.create_hubnorth_overground(),
            TestRailwayNetwork.create_hubnorth_elizabeth(),
            TestRailwayNetwork.create_hubnorth_bus(),
        ]

        # All must have HUB_NORTH naptan code
        for station in hub_north_children:
            assert station.hub_naptan_code == TestRailwayNetwork.HUB_NORTH
            assert station.hub_common_name == TestRailwayNetwork.HUB_NORTH_NAME

    def test_hub_central_children_share_naptan_code(self) -> None:
        """Test all HUB_CENTRAL children have same hub_naptan_code."""
        hub_central_children = [
            TestRailwayNetwork.create_fork_mid_1(),
            TestRailwayNetwork.create_hubcentral_dlr(),
        ]

        # All must have HUB_CENTRAL naptan code
        for station in hub_central_children:
            assert station.hub_naptan_code == TestRailwayNetwork.HUB_CENTRAL
            assert station.hub_common_name == TestRailwayNetwork.HUB_CENTRAL_NAME

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

        assert line.routes is not None
        eastbound = next(r for r in line.routes["routes"] if r["name"] == "Eastbound")
        assert line.routes is not None
        westbound = next(r for r in line.routes["routes"] if r["name"] == "Westbound")

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

        assert line.routes is not None
        west_sb = next(r for r in line.routes["routes"] if r["name"] == "West Branch Southbound")
        assert line.routes is not None
        east_sb = next(r for r in line.routes["routes"] if r["name"] == "East Branch Southbound")

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

        assert line.routes is not None
        bank_sb = next(r for r in line.routes["routes"] if r["name"] == "Via Bank Southbound")
        assert line.routes is not None
        charing_sb = next(r for r in line.routes["routes"] if r["name"] == "Via Charing Southbound")

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
