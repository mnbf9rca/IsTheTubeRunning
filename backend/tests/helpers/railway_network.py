"""
Test railway network factory for comprehensive TfL routing pattern testing.

This module provides a shared test railway network covering all real-world TfL
routing scenarios without requiring knowledge of actual TfL station names.

See /docs/test_network_diagram.md for full network diagram and documentation.
"""

import uuid
from datetime import UTC, datetime

from app.models.tfl import Line, Station


class TestRailwayNetwork:
    """
    Comprehensive test railway network covering all TfL routing patterns.

    This provides a complex, controlled test dataset covering Y-forks, parallel paths,
    non-symmetric routes, and intra-mode routing. It's designed to test all real-world
    TfL routing scenarios without requiring knowledge of actual TfL station names.

    Network structure:
    - 8 lines across 4 modes (tube, overground, dlr, elizabeth-line)
    - 2 multi-mode hubs (HUB_NORTH: 4-mode hub with 4 children, HUB_CENTRAL: 2-mode hub with 2 children)
    - ~46 stations covering:
      * Y-shaped forks (forkedline)
      * Parallel paths that rejoin (parallelline)
      * Non-symmetric routes (asymmetricline)
      * Intra-mode shared stations (sharedline-a/b/c)
      * Minimal lines (2stopline)

    See /docs/test_network_diagram.md for full network diagram and documentation.

    Naming convention (hybrid):
    - Hubs: UPPERCASE (HUB_NORTH, HUB_CENTRAL)
    - Stations: lowercase-kebab-case (parallel-north, fork-mid-1)
    - Lines: lowercase descriptive (forkedline, parallelline)
    """

    # =============================================================================
    # DEPRECATED CONSTANTS (Issue #70 Part 1)
    # The following constants are deprecated and will be removed in Part 2.
    # Use the new comprehensive network constants below instead.
    # =============================================================================

    # DEPRECATED - use new network
    LINE_1 = "line1"
    LINE_2 = "line2"
    LINE_3 = "line3"

    # DEPRECATED - use HUB_NORTH or HUB_CENTRAL
    HUB_ALPHA_CODE = "HUB_ALPHA"
    HUB_ALPHA_NAME = "Alpha Junction"
    HUB_ALPHA_TUBE_ID = "TUBE_ALPHA"
    HUB_ALPHA_TUBE_NAME = "Alpha Junction (Tube)"
    HUB_ALPHA_RAIL_ID = "RAIL_ALPHA"
    HUB_ALPHA_RAIL_NAME = "Alpha Junction (Rail)"

    # DEPRECATED - use HUB_NORTH or HUB_CENTRAL
    HUB_BETA_CODE = "HUB_BETA"
    HUB_BETA_NAME = "Beta Station"
    HUB_BETA_CHILD1_ID = "BETA_CHILD_1"
    HUB_BETA_CHILD1_NAME = "Beta Station Platform A"
    HUB_BETA_CHILD2_ID = "BETA_CHILD_2"
    HUB_BETA_CHILD2_NAME = "Beta Station Platform B"

    # DEPRECATED - use new network stations
    STANDALONE_CHARLIE_ID = "STATION_CHARLIE"
    STANDALONE_CHARLIE_NAME = "Charlie Station"
    STANDALONE_DELTA_ID = "STATION_DELTA"
    STANDALONE_DELTA_NAME = "Delta Station"

    # =============================================================================
    # NEW COMPREHENSIVE NETWORK (Issue #70 Part 1)
    # =============================================================================

    # -----------------------------------------------------------------------------
    # Line Constants (8 lines across 4 modes)
    # -----------------------------------------------------------------------------
    LINE_FORKEDLINE = "forkedline"  # tube - Y-shaped with branches
    LINE_PARALLELLINE = "parallelline"  # tube - parallel paths
    LINE_ASYMMETRICLINE = "asymmetricline"  # overground - non-symmetric
    LINE_2STOPLINE = "2stopline"  # dlr - minimal
    LINE_SHAREDLINE_A = "sharedline-a"  # tube - shared station
    LINE_SHAREDLINE_B = "sharedline-b"  # tube - shared station
    LINE_SHAREDLINE_C = "sharedline-c"  # tube - shared station
    LINE_ELIZABETHLINE = "elizabethline"  # elizabeth-line

    # -----------------------------------------------------------------------------
    # Hub Constants (2 multi-mode interchanges)
    # -----------------------------------------------------------------------------
    HUB_NORTH = "HUBNORTH"  # 4-mode hub (tube, overground, elizabeth-line, bus)
    HUB_NORTH_NAME = "North Interchange"
    HUB_CENTRAL = "HUBCENTRAL"  # 2-mode hub
    HUB_CENTRAL_NAME = "Central Hub"

    # -----------------------------------------------------------------------------
    # Station Constants (~45 stations organized by category)
    # -----------------------------------------------------------------------------

    # HUB_NORTH children (4 stations - tube, overground, elizabeth-line, bus)
    STATION_PARALLEL_NORTH = "parallel-north"  # tube at HUB_NORTH
    STATION_HUBNORTH_OVERGROUND = "hubnorth-overground"  # overground at HUB_NORTH
    STATION_HUBNORTH_ELIZABETH = "hubnorth-elizabeth"  # elizabeth-line at HUB_NORTH
    STATION_HUBNORTH_BUS = "hubnorth-bus"  # bus at HUB_NORTH (no line in network)

    # HUB_CENTRAL children (2 stations - tube, dlr)
    STATION_FORK_MID_1 = "fork-mid-1"  # tube at HUB_CENTRAL
    STATION_HUBCENTRAL_DLR = "hubcentral-dlr"  # dlr at HUB_CENTRAL

    # FORKEDLINE stations (Y-shaped fork, 9 total)
    STATION_WEST_FORK_2 = "west-fork-2"  # west branch terminus
    STATION_WEST_FORK = "west-fork"  # west branch
    STATION_EAST_FORK_2 = "east-fork-2"  # east branch terminus
    STATION_EAST_FORK = "east-fork"  # east branch
    STATION_FORK_JUNCTION = "fork-junction"  # convergence point (NOT a hub)
    # STATION_FORK_MID_1 defined above (at HUB_CENTRAL)
    STATION_FORK_MID_2 = "fork-mid-2"  # trunk
    STATION_FORK_SOUTH_END = "fork-south-end"  # southern terminus

    # PARALLELLINE stations (parallel paths, 8 total)
    # STATION_PARALLEL_NORTH defined above (at HUB_NORTH)
    STATION_PARALLEL_SPLIT = "parallel-split"  # split point (NOT a hub)
    STATION_VIA_BANK_1 = "via-bank-1"  # Bank branch
    STATION_VIA_BANK_2 = "via-bank-2"  # Bank branch
    STATION_VIA_CHARING_1 = "via-charing-1"  # Charing branch
    STATION_VIA_CHARING_2 = "via-charing-2"  # Charing branch
    STATION_PARALLEL_REJOIN = "parallel-rejoin"  # rejoin point (NOT a hub)
    STATION_PARALLEL_SOUTH = "parallel-south"  # southern terminus

    # ASYMMETRICLINE stations (non-symmetric routes, 5 total)
    STATION_ASYM_WEST = "asym-west"  # western terminus
    STATION_ASYM_REGULAR_1 = "asym-regular-1"  # serves both directions
    STATION_ASYM_SKIP_STATION = "asym-skip-station"  # eastbound only!
    STATION_ASYM_REGULAR_2 = "asym-regular-2"  # serves both directions
    STATION_ASYM_EAST = "asym-east"  # eastern terminus

    # 2STOPLINE stations (minimal line, 2 total)
    STATION_TWOSTOP_WEST = "twostop-west"  # western terminus
    STATION_TWOSTOP_EAST = "twostop-east"  # eastern terminus
    # STATION_HUBCENTRAL_DLR defined above (at HUB_CENTRAL)

    # SHAREDLINE-A stations (5 stations)
    STATION_SHAREDA_1 = "shareda-1"
    STATION_SHAREDA_2 = "shareda-2"
    # STATION_SHARED_STATION defined below (shared by all 3 sharedlines)
    STATION_SHAREDA_4 = "shareda-4"
    STATION_SHAREDA_5 = "shareda-5"

    # SHAREDLINE-B stations (5 stations)
    STATION_SHAREDB_1 = "sharedb-1"
    STATION_SHAREDB_2 = "sharedb-2"
    # STATION_SHARED_STATION shared with A and C
    STATION_SHAREDB_4 = "sharedb-4"
    STATION_SHAREDB_5 = "sharedb-5"

    # SHAREDLINE-C stations (5 stations)
    STATION_SHAREDC_1 = "sharedc-1"
    STATION_SHAREDC_2 = "sharedc-2"
    # STATION_SHARED_STATION shared with A and B
    STATION_SHAREDC_4 = "sharedc-4"
    STATION_SHAREDC_5 = "sharedc-5"

    # Shared station (served by all 3 sharedlines, NOT a hub)
    STATION_SHARED_STATION = "shared-station"

    # ELIZABETHLINE stations (4 total)
    STATION_ELIZABETH_WEST = "elizabeth-west"  # western terminus
    # STATION_HUBNORTH_ELIZABETH defined above (at HUB_NORTH)
    STATION_ELIZABETH_MID = "elizabeth-mid"
    STATION_ELIZABETH_EAST = "elizabeth-east"  # eastern terminus

    # =============================================================================
    # DEPRECATED FACTORY METHODS (Issue #70 Part 1)
    # The following factory methods are deprecated and will be removed in Part 2.
    # Use the new network factory methods below instead.
    # =============================================================================

    @staticmethod
    def create_hub_alpha_tube() -> Station:
        """DEPRECATED: Use create_parallel_north() or other new network factories."""
        return create_test_station(
            TestRailwayNetwork.HUB_ALPHA_TUBE_ID,
            TestRailwayNetwork.HUB_ALPHA_TUBE_NAME,
            [TestRailwayNetwork.LINE_1],
            hub_naptan_code=TestRailwayNetwork.HUB_ALPHA_CODE,
            hub_common_name=TestRailwayNetwork.HUB_ALPHA_NAME,
        )

    @staticmethod
    def create_hub_alpha_rail() -> Station:
        """DEPRECATED: Use create_hubnorth_overground() or other new network factories."""
        return create_test_station(
            TestRailwayNetwork.HUB_ALPHA_RAIL_ID,
            TestRailwayNetwork.HUB_ALPHA_RAIL_NAME,
            [TestRailwayNetwork.LINE_2],
            hub_naptan_code=TestRailwayNetwork.HUB_ALPHA_CODE,
            hub_common_name=TestRailwayNetwork.HUB_ALPHA_NAME,
        )

    @staticmethod
    def create_hub_beta_child1() -> Station:
        """DEPRECATED: Use new network factories."""
        return create_test_station(
            TestRailwayNetwork.HUB_BETA_CHILD1_ID,
            TestRailwayNetwork.HUB_BETA_CHILD1_NAME,
            [TestRailwayNetwork.LINE_1],
            hub_naptan_code=TestRailwayNetwork.HUB_BETA_CODE,
            hub_common_name=TestRailwayNetwork.HUB_BETA_NAME,
        )

    @staticmethod
    def create_hub_beta_child2() -> Station:
        """DEPRECATED: Use new network factories."""
        return create_test_station(
            TestRailwayNetwork.HUB_BETA_CHILD2_ID,
            TestRailwayNetwork.HUB_BETA_CHILD2_NAME,
            [TestRailwayNetwork.LINE_2],
            hub_naptan_code=TestRailwayNetwork.HUB_BETA_CODE,
            hub_common_name=TestRailwayNetwork.HUB_BETA_NAME,
        )

    @staticmethod
    def create_standalone_charlie() -> Station:
        """DEPRECATED: Use new network station factories."""
        return create_test_station(
            TestRailwayNetwork.STANDALONE_CHARLIE_ID,
            TestRailwayNetwork.STANDALONE_CHARLIE_NAME,
            [TestRailwayNetwork.LINE_1],
        )

    @staticmethod
    def create_standalone_delta() -> Station:
        """DEPRECATED: Use new network station factories."""
        return create_test_station(
            TestRailwayNetwork.STANDALONE_DELTA_ID,
            TestRailwayNetwork.STANDALONE_DELTA_NAME,
            [TestRailwayNetwork.LINE_2],
        )

    # =============================================================================
    # NEW STATION FACTORY METHODS (Issue #70 Part 1)
    # =============================================================================

    # -----------------------------------------------------------------------------
    # Hub Children Factories (6 stations: 4 at HUB_NORTH + 2 at HUB_CENTRAL)
    # -----------------------------------------------------------------------------

    @staticmethod
    def create_parallel_north() -> Station:
        """HUB_NORTH tube child serving parallelline."""
        return create_test_station(
            TestRailwayNetwork.STATION_PARALLEL_NORTH,
            "North Interchange (Tube)",
            [TestRailwayNetwork.LINE_PARALLELLINE],
            hub_naptan_code=TestRailwayNetwork.HUB_NORTH,
            hub_common_name=TestRailwayNetwork.HUB_NORTH_NAME,
        )

    @staticmethod
    def create_hubnorth_overground() -> Station:
        """HUB_NORTH overground child serving asymmetricline."""
        return create_test_station(
            TestRailwayNetwork.STATION_HUBNORTH_OVERGROUND,
            "North Interchange (Overground)",
            [TestRailwayNetwork.LINE_ASYMMETRICLINE],
            hub_naptan_code=TestRailwayNetwork.HUB_NORTH,
            hub_common_name=TestRailwayNetwork.HUB_NORTH_NAME,
        )

    @staticmethod
    def create_hubnorth_elizabeth() -> Station:
        """HUB_NORTH elizabeth-line child serving elizabethline."""
        return create_test_station(
            TestRailwayNetwork.STATION_HUBNORTH_ELIZABETH,
            "North Interchange (Elizabeth line)",
            [TestRailwayNetwork.LINE_ELIZABETHLINE],
            hub_naptan_code=TestRailwayNetwork.HUB_NORTH,
            hub_common_name=TestRailwayNetwork.HUB_NORTH_NAME,
        )

    @staticmethod
    def create_hubnorth_bus() -> Station:
        """HUB_NORTH bus child (no line in network)."""
        return create_test_station(
            TestRailwayNetwork.STATION_HUBNORTH_BUS,
            "North Interchange (Bus)",
            [],  # No line - bus mode not in network
            hub_naptan_code=TestRailwayNetwork.HUB_NORTH,
            hub_common_name=TestRailwayNetwork.HUB_NORTH_NAME,
        )

    @staticmethod
    def create_fork_mid_1() -> Station:
        """HUB_CENTRAL tube child serving forkedline."""
        return create_test_station(
            TestRailwayNetwork.STATION_FORK_MID_1,
            "Central Hub (Tube)",
            [TestRailwayNetwork.LINE_FORKEDLINE],
            hub_naptan_code=TestRailwayNetwork.HUB_CENTRAL,
            hub_common_name=TestRailwayNetwork.HUB_CENTRAL_NAME,
        )

    @staticmethod
    def create_hubcentral_dlr() -> Station:
        """HUB_CENTRAL dlr child serving 2stopline."""
        return create_test_station(
            TestRailwayNetwork.STATION_HUBCENTRAL_DLR,
            "Central Hub (DLR)",
            [TestRailwayNetwork.LINE_2STOPLINE],
            hub_naptan_code=TestRailwayNetwork.HUB_CENTRAL,
            hub_common_name=TestRailwayNetwork.HUB_CENTRAL_NAME,
        )

    # -----------------------------------------------------------------------------
    # Branch Junction Factories (3 stations - NOT hubs, just convergence points)
    # -----------------------------------------------------------------------------

    @staticmethod
    def create_fork_junction() -> Station:
        """Fork junction where west-fork and east-fork converge (NOT a hub)."""
        return create_test_station(
            TestRailwayNetwork.STATION_FORK_JUNCTION,
            "Fork Junction",
            [TestRailwayNetwork.LINE_FORKEDLINE],
        )

    @staticmethod
    def create_parallel_split() -> Station:
        """Parallel split where parallelline splits into Bank/Charing branches (NOT a hub)."""
        return create_test_station(
            TestRailwayNetwork.STATION_PARALLEL_SPLIT,
            "Parallel Split",
            [TestRailwayNetwork.LINE_PARALLELLINE],
        )

    @staticmethod
    def create_parallel_rejoin() -> Station:
        """Parallel rejoin where Bank/Charing branches rejoin (NOT a hub)."""
        return create_test_station(
            TestRailwayNetwork.STATION_PARALLEL_REJOIN,
            "Parallel Rejoin",
            [TestRailwayNetwork.LINE_PARALLELLINE],
        )

    # -----------------------------------------------------------------------------
    # Shared Station Factory (1 station - serves 3 tube lines, NOT a hub)
    # -----------------------------------------------------------------------------

    @staticmethod
    def create_shared_station() -> Station:
        """Shared station served by sharedline-a/b/c (NOT a hub, same mode)."""
        return create_test_station(
            TestRailwayNetwork.STATION_SHARED_STATION,
            "Shared Station",
            [
                TestRailwayNetwork.LINE_SHAREDLINE_A,
                TestRailwayNetwork.LINE_SHAREDLINE_B,
                TestRailwayNetwork.LINE_SHAREDLINE_C,
            ],
        )

    # -----------------------------------------------------------------------------
    # Standalone Station Factories (33 stations organized by line)
    # -----------------------------------------------------------------------------

    # FORKEDLINE standalone stations (6 stations)

    @staticmethod
    def create_west_fork_2() -> Station:
        """West branch terminus on forkedline."""
        return create_test_station(
            TestRailwayNetwork.STATION_WEST_FORK_2,
            "West Fork 2",
            [TestRailwayNetwork.LINE_FORKEDLINE],
        )

    @staticmethod
    def create_west_fork() -> Station:
        """West branch station on forkedline."""
        return create_test_station(
            TestRailwayNetwork.STATION_WEST_FORK,
            "West Fork",
            [TestRailwayNetwork.LINE_FORKEDLINE],
        )

    @staticmethod
    def create_east_fork_2() -> Station:
        """East branch terminus on forkedline."""
        return create_test_station(
            TestRailwayNetwork.STATION_EAST_FORK_2,
            "East Fork 2",
            [TestRailwayNetwork.LINE_FORKEDLINE],
        )

    @staticmethod
    def create_east_fork() -> Station:
        """East branch station on forkedline."""
        return create_test_station(
            TestRailwayNetwork.STATION_EAST_FORK,
            "East Fork",
            [TestRailwayNetwork.LINE_FORKEDLINE],
        )

    @staticmethod
    def create_fork_mid_2() -> Station:
        """Trunk station on forkedline."""
        return create_test_station(
            TestRailwayNetwork.STATION_FORK_MID_2,
            "Fork Mid 2",
            [TestRailwayNetwork.LINE_FORKEDLINE],
        )

    @staticmethod
    def create_fork_south_end() -> Station:
        """Southern terminus on forkedline."""
        return create_test_station(
            TestRailwayNetwork.STATION_FORK_SOUTH_END,
            "Fork South End",
            [TestRailwayNetwork.LINE_FORKEDLINE],
        )

    # PARALLELLINE standalone stations (5 stations)

    @staticmethod
    def create_via_bank_1() -> Station:
        """Bank branch station 1 on parallelline."""
        return create_test_station(
            TestRailwayNetwork.STATION_VIA_BANK_1,
            "Via Bank 1",
            [TestRailwayNetwork.LINE_PARALLELLINE],
        )

    @staticmethod
    def create_via_bank_2() -> Station:
        """Bank branch station 2 on parallelline."""
        return create_test_station(
            TestRailwayNetwork.STATION_VIA_BANK_2,
            "Via Bank 2",
            [TestRailwayNetwork.LINE_PARALLELLINE],
        )

    @staticmethod
    def create_via_charing_1() -> Station:
        """Charing branch station 1 on parallelline."""
        return create_test_station(
            TestRailwayNetwork.STATION_VIA_CHARING_1,
            "Via Charing 1",
            [TestRailwayNetwork.LINE_PARALLELLINE],
        )

    @staticmethod
    def create_via_charing_2() -> Station:
        """Charing branch station 2 on parallelline."""
        return create_test_station(
            TestRailwayNetwork.STATION_VIA_CHARING_2,
            "Via Charing 2",
            [TestRailwayNetwork.LINE_PARALLELLINE],
        )

    @staticmethod
    def create_parallel_south() -> Station:
        """Southern terminus on parallelline."""
        return create_test_station(
            TestRailwayNetwork.STATION_PARALLEL_SOUTH,
            "Parallel South",
            [TestRailwayNetwork.LINE_PARALLELLINE],
        )

    # ASYMMETRICLINE standalone stations (5 stations)

    @staticmethod
    def create_asym_west() -> Station:
        """Western terminus on asymmetricline."""
        return create_test_station(
            TestRailwayNetwork.STATION_ASYM_WEST,
            "Asym West",
            [TestRailwayNetwork.LINE_ASYMMETRICLINE],
        )

    @staticmethod
    def create_asym_regular_1() -> Station:
        """Regular station 1 on asymmetricline (both directions)."""
        return create_test_station(
            TestRailwayNetwork.STATION_ASYM_REGULAR_1,
            "Asym Regular 1",
            [TestRailwayNetwork.LINE_ASYMMETRICLINE],
        )

    @staticmethod
    def create_asym_skip_station() -> Station:
        """Skip station on asymmetricline (eastbound only)."""
        return create_test_station(
            TestRailwayNetwork.STATION_ASYM_SKIP_STATION,
            "Asym Skip Station",
            [TestRailwayNetwork.LINE_ASYMMETRICLINE],
        )

    @staticmethod
    def create_asym_regular_2() -> Station:
        """Regular station 2 on asymmetricline (both directions)."""
        return create_test_station(
            TestRailwayNetwork.STATION_ASYM_REGULAR_2,
            "Asym Regular 2",
            [TestRailwayNetwork.LINE_ASYMMETRICLINE],
        )

    @staticmethod
    def create_asym_east() -> Station:
        """Eastern terminus on asymmetricline."""
        return create_test_station(
            TestRailwayNetwork.STATION_ASYM_EAST,
            "Asym East",
            [TestRailwayNetwork.LINE_ASYMMETRICLINE],
        )

    # 2STOPLINE standalone stations (2 stations)

    @staticmethod
    def create_twostop_west() -> Station:
        """Western terminus on 2stopline."""
        return create_test_station(
            TestRailwayNetwork.STATION_TWOSTOP_WEST,
            "TwoStop West",
            [TestRailwayNetwork.LINE_2STOPLINE],
        )

    @staticmethod
    def create_twostop_east() -> Station:
        """Eastern terminus on 2stopline."""
        return create_test_station(
            TestRailwayNetwork.STATION_TWOSTOP_EAST,
            "TwoStop East",
            [TestRailwayNetwork.LINE_2STOPLINE],
        )

    # SHAREDLINE-A standalone stations (4 stations)

    @staticmethod
    def create_shareda_1() -> Station:
        """Station 1 on sharedline-a."""
        return create_test_station(
            TestRailwayNetwork.STATION_SHAREDA_1,
            "SharedA 1",
            [TestRailwayNetwork.LINE_SHAREDLINE_A],
        )

    @staticmethod
    def create_shareda_2() -> Station:
        """Station 2 on sharedline-a."""
        return create_test_station(
            TestRailwayNetwork.STATION_SHAREDA_2,
            "SharedA 2",
            [TestRailwayNetwork.LINE_SHAREDLINE_A],
        )

    @staticmethod
    def create_shareda_4() -> Station:
        """Station 4 on sharedline-a."""
        return create_test_station(
            TestRailwayNetwork.STATION_SHAREDA_4,
            "SharedA 4",
            [TestRailwayNetwork.LINE_SHAREDLINE_A],
        )

    @staticmethod
    def create_shareda_5() -> Station:
        """Station 5 on sharedline-a."""
        return create_test_station(
            TestRailwayNetwork.STATION_SHAREDA_5,
            "SharedA 5",
            [TestRailwayNetwork.LINE_SHAREDLINE_A],
        )

    # SHAREDLINE-B standalone stations (4 stations)

    @staticmethod
    def create_sharedb_1() -> Station:
        """Station 1 on sharedline-b."""
        return create_test_station(
            TestRailwayNetwork.STATION_SHAREDB_1,
            "SharedB 1",
            [TestRailwayNetwork.LINE_SHAREDLINE_B],
        )

    @staticmethod
    def create_sharedb_2() -> Station:
        """Station 2 on sharedline-b."""
        return create_test_station(
            TestRailwayNetwork.STATION_SHAREDB_2,
            "SharedB 2",
            [TestRailwayNetwork.LINE_SHAREDLINE_B],
        )

    @staticmethod
    def create_sharedb_4() -> Station:
        """Station 4 on sharedline-b."""
        return create_test_station(
            TestRailwayNetwork.STATION_SHAREDB_4,
            "SharedB 4",
            [TestRailwayNetwork.LINE_SHAREDLINE_B],
        )

    @staticmethod
    def create_sharedb_5() -> Station:
        """Station 5 on sharedline-b."""
        return create_test_station(
            TestRailwayNetwork.STATION_SHAREDB_5,
            "SharedB 5",
            [TestRailwayNetwork.LINE_SHAREDLINE_B],
        )

    # SHAREDLINE-C standalone stations (4 stations)

    @staticmethod
    def create_sharedc_1() -> Station:
        """Station 1 on sharedline-c."""
        return create_test_station(
            TestRailwayNetwork.STATION_SHAREDC_1,
            "SharedC 1",
            [TestRailwayNetwork.LINE_SHAREDLINE_C],
        )

    @staticmethod
    def create_sharedc_2() -> Station:
        """Station 2 on sharedline-c."""
        return create_test_station(
            TestRailwayNetwork.STATION_SHAREDC_2,
            "SharedC 2",
            [TestRailwayNetwork.LINE_SHAREDLINE_C],
        )

    @staticmethod
    def create_sharedc_4() -> Station:
        """Station 4 on sharedline-c."""
        return create_test_station(
            TestRailwayNetwork.STATION_SHAREDC_4,
            "SharedC 4",
            [TestRailwayNetwork.LINE_SHAREDLINE_C],
        )

    @staticmethod
    def create_sharedc_5() -> Station:
        """Station 5 on sharedline-c."""
        return create_test_station(
            TestRailwayNetwork.STATION_SHAREDC_5,
            "SharedC 5",
            [TestRailwayNetwork.LINE_SHAREDLINE_C],
        )

    # ELIZABETHLINE standalone stations (3 stations)

    @staticmethod
    def create_elizabeth_west() -> Station:
        """Western terminus on elizabethline."""
        return create_test_station(
            TestRailwayNetwork.STATION_ELIZABETH_WEST,
            "Elizabeth West",
            [TestRailwayNetwork.LINE_ELIZABETHLINE],
        )

    @staticmethod
    def create_elizabeth_mid() -> Station:
        """Mid station on elizabethline."""
        return create_test_station(
            TestRailwayNetwork.STATION_ELIZABETH_MID,
            "Elizabeth Mid",
            [TestRailwayNetwork.LINE_ELIZABETHLINE],
        )

    @staticmethod
    def create_elizabeth_east() -> Station:
        """Eastern terminus on elizabethline."""
        return create_test_station(
            TestRailwayNetwork.STATION_ELIZABETH_EAST,
            "Elizabeth East",
            [TestRailwayNetwork.LINE_ELIZABETHLINE],
        )

    # =============================================================================
    # LINE FACTORY METHODS (Issue #70 Part 1)
    # =============================================================================

    @staticmethod
    def create_forkedline() -> Line:
        """
        FORKEDLINE (tube) - Y-shaped line with branches converging at fork-junction.

        Routes:
          - West Branch Southbound: west-fork-2 → ... → fork-south-end
          - West Branch Northbound: fork-south-end → ... → west-fork-2
          - East Branch Southbound: east-fork-2 → ... → fork-south-end
          - East Branch Northbound: fork-south-end → ... → east-fork-2
        """
        return Line(
            tfl_id=TestRailwayNetwork.LINE_FORKEDLINE,
            name="Forked Line",
            mode="tube",
            last_updated=datetime.now(UTC),
            routes={
                "routes": [
                    {
                        "name": "West Branch Southbound",
                        "direction": "southbound",
                        "stations": [
                            TestRailwayNetwork.STATION_WEST_FORK_2,
                            TestRailwayNetwork.STATION_WEST_FORK,
                            TestRailwayNetwork.STATION_FORK_JUNCTION,
                            TestRailwayNetwork.STATION_FORK_MID_1,
                            TestRailwayNetwork.STATION_FORK_MID_2,
                            TestRailwayNetwork.STATION_FORK_SOUTH_END,
                        ],
                    },
                    {
                        "name": "West Branch Northbound",
                        "direction": "northbound",
                        "stations": [
                            TestRailwayNetwork.STATION_FORK_SOUTH_END,
                            TestRailwayNetwork.STATION_FORK_MID_2,
                            TestRailwayNetwork.STATION_FORK_MID_1,
                            TestRailwayNetwork.STATION_FORK_JUNCTION,
                            TestRailwayNetwork.STATION_WEST_FORK,
                            TestRailwayNetwork.STATION_WEST_FORK_2,
                        ],
                    },
                    {
                        "name": "East Branch Southbound",
                        "direction": "southbound",
                        "stations": [
                            TestRailwayNetwork.STATION_EAST_FORK_2,
                            TestRailwayNetwork.STATION_EAST_FORK,
                            TestRailwayNetwork.STATION_FORK_JUNCTION,
                            TestRailwayNetwork.STATION_FORK_MID_1,
                            TestRailwayNetwork.STATION_FORK_MID_2,
                            TestRailwayNetwork.STATION_FORK_SOUTH_END,
                        ],
                    },
                    {
                        "name": "East Branch Northbound",
                        "direction": "northbound",
                        "stations": [
                            TestRailwayNetwork.STATION_FORK_SOUTH_END,
                            TestRailwayNetwork.STATION_FORK_MID_2,
                            TestRailwayNetwork.STATION_FORK_MID_1,
                            TestRailwayNetwork.STATION_FORK_JUNCTION,
                            TestRailwayNetwork.STATION_EAST_FORK,
                            TestRailwayNetwork.STATION_EAST_FORK_2,
                        ],
                    },
                ]
            },
        )

    @staticmethod
    def create_parallelline() -> Line:
        """
        PARALLELLINE (tube) - Parallel paths (Bank/Charing Cross pattern).

        Routes:
          - Via Bank Southbound: parallel-north → ... → parallel-south
          - Via Bank Northbound: parallel-south → ... → parallel-north
          - Via Charing Southbound: parallel-north → ... → parallel-south
          - Via Charing Northbound: parallel-south → ... → parallel-north
        """
        return Line(
            tfl_id=TestRailwayNetwork.LINE_PARALLELLINE,
            name="Parallel Line",
            mode="tube",
            last_updated=datetime.now(UTC),
            routes={
                "routes": [
                    {
                        "name": "Via Bank Southbound",
                        "direction": "southbound",
                        "stations": [
                            TestRailwayNetwork.STATION_PARALLEL_NORTH,
                            TestRailwayNetwork.STATION_PARALLEL_SPLIT,
                            TestRailwayNetwork.STATION_VIA_BANK_1,
                            TestRailwayNetwork.STATION_VIA_BANK_2,
                            TestRailwayNetwork.STATION_PARALLEL_REJOIN,
                            TestRailwayNetwork.STATION_PARALLEL_SOUTH,
                        ],
                    },
                    {
                        "name": "Via Bank Northbound",
                        "direction": "northbound",
                        "stations": [
                            TestRailwayNetwork.STATION_PARALLEL_SOUTH,
                            TestRailwayNetwork.STATION_PARALLEL_REJOIN,
                            TestRailwayNetwork.STATION_VIA_BANK_2,
                            TestRailwayNetwork.STATION_VIA_BANK_1,
                            TestRailwayNetwork.STATION_PARALLEL_SPLIT,
                            TestRailwayNetwork.STATION_PARALLEL_NORTH,
                        ],
                    },
                    {
                        "name": "Via Charing Southbound",
                        "direction": "southbound",
                        "stations": [
                            TestRailwayNetwork.STATION_PARALLEL_NORTH,
                            TestRailwayNetwork.STATION_PARALLEL_SPLIT,
                            TestRailwayNetwork.STATION_VIA_CHARING_1,
                            TestRailwayNetwork.STATION_VIA_CHARING_2,
                            TestRailwayNetwork.STATION_PARALLEL_REJOIN,
                            TestRailwayNetwork.STATION_PARALLEL_SOUTH,
                        ],
                    },
                    {
                        "name": "Via Charing Northbound",
                        "direction": "northbound",
                        "stations": [
                            TestRailwayNetwork.STATION_PARALLEL_SOUTH,
                            TestRailwayNetwork.STATION_PARALLEL_REJOIN,
                            TestRailwayNetwork.STATION_VIA_CHARING_2,
                            TestRailwayNetwork.STATION_VIA_CHARING_1,
                            TestRailwayNetwork.STATION_PARALLEL_SPLIT,
                            TestRailwayNetwork.STATION_PARALLEL_NORTH,
                        ],
                    },
                ]
            },
        )

    @staticmethod
    def create_asymmetricline() -> Line:
        """
        ASYMMETRICLINE (overground) - Non-symmetric routes.

        Routes:
          - Eastbound: asym-west → asym-regular-1 → asym-skip-station → asym-regular-2 → asym-east
          - Westbound: asym-east → asym-regular-2 → asym-regular-1 → asym-west (SKIPS asym-skip-station)
        """
        return Line(
            tfl_id=TestRailwayNetwork.LINE_ASYMMETRICLINE,
            name="Asymmetric Line",
            mode="overground",
            last_updated=datetime.now(UTC),
            routes={
                "routes": [
                    {
                        "name": "Eastbound",
                        "direction": "eastbound",
                        "stations": [
                            TestRailwayNetwork.STATION_ASYM_WEST,
                            TestRailwayNetwork.STATION_ASYM_REGULAR_1,
                            TestRailwayNetwork.STATION_ASYM_SKIP_STATION,  # Eastbound ONLY
                            TestRailwayNetwork.STATION_ASYM_REGULAR_2,
                            TestRailwayNetwork.STATION_ASYM_EAST,
                        ],
                    },
                    {
                        "name": "Westbound",
                        "direction": "westbound",
                        "stations": [
                            TestRailwayNetwork.STATION_ASYM_EAST,
                            TestRailwayNetwork.STATION_ASYM_REGULAR_2,
                            TestRailwayNetwork.STATION_ASYM_REGULAR_1,
                            TestRailwayNetwork.STATION_ASYM_WEST,
                            # SKIPS asym-skip-station!
                        ],
                    },
                ]
            },
        )

    @staticmethod
    def create_2stopline() -> Line:
        """
        2STOPLINE (dlr) - Minimal two-station line (Waterloo & City pattern).

        Routes:
          - Eastbound: twostop-west → twostop-east
          - Westbound: twostop-east → twostop-west
        """
        return Line(
            tfl_id=TestRailwayNetwork.LINE_2STOPLINE,
            name="2 Stop Line",
            mode="dlr",
            last_updated=datetime.now(UTC),
            routes={
                "routes": [
                    {
                        "name": "Eastbound",
                        "direction": "eastbound",
                        "stations": [
                            TestRailwayNetwork.STATION_TWOSTOP_WEST,
                            TestRailwayNetwork.STATION_TWOSTOP_EAST,
                        ],
                    },
                    {
                        "name": "Westbound",
                        "direction": "westbound",
                        "stations": [
                            TestRailwayNetwork.STATION_TWOSTOP_EAST,
                            TestRailwayNetwork.STATION_TWOSTOP_WEST,
                        ],
                    },
                ]
            },
        )

    @staticmethod
    def create_sharedline_a() -> Line:
        """
        SHAREDLINE-A (tube) - Shares 'shared-station' with SHAREDLINE-B and SHAREDLINE-C.

        Route: shareda-1 → shareda-2 → shared-station → shareda-4 → shareda-5
        """
        return Line(
            tfl_id=TestRailwayNetwork.LINE_SHAREDLINE_A,
            name="SharedLine A",
            mode="tube",
            last_updated=datetime.now(UTC),
            routes={
                "routes": [
                    {
                        "name": "Eastbound",
                        "direction": "eastbound",
                        "stations": [
                            TestRailwayNetwork.STATION_SHAREDA_1,
                            TestRailwayNetwork.STATION_SHAREDA_2,
                            TestRailwayNetwork.STATION_SHARED_STATION,
                            TestRailwayNetwork.STATION_SHAREDA_4,
                            TestRailwayNetwork.STATION_SHAREDA_5,
                        ],
                    },
                    {
                        "name": "Westbound",
                        "direction": "westbound",
                        "stations": [
                            TestRailwayNetwork.STATION_SHAREDA_5,
                            TestRailwayNetwork.STATION_SHAREDA_4,
                            TestRailwayNetwork.STATION_SHARED_STATION,
                            TestRailwayNetwork.STATION_SHAREDA_2,
                            TestRailwayNetwork.STATION_SHAREDA_1,
                        ],
                    },
                ]
            },
        )

    @staticmethod
    def create_sharedline_b() -> Line:
        """
        SHAREDLINE-B (tube) - Shares 'shared-station' with SHAREDLINE-A and SHAREDLINE-C.

        Route: sharedb-1 → sharedb-2 → shared-station → sharedb-4 → sharedb-5
        """
        return Line(
            tfl_id=TestRailwayNetwork.LINE_SHAREDLINE_B,
            name="SharedLine B",
            mode="tube",
            last_updated=datetime.now(UTC),
            routes={
                "routes": [
                    {
                        "name": "Eastbound",
                        "direction": "eastbound",
                        "stations": [
                            TestRailwayNetwork.STATION_SHAREDB_1,
                            TestRailwayNetwork.STATION_SHAREDB_2,
                            TestRailwayNetwork.STATION_SHARED_STATION,
                            TestRailwayNetwork.STATION_SHAREDB_4,
                            TestRailwayNetwork.STATION_SHAREDB_5,
                        ],
                    },
                    {
                        "name": "Westbound",
                        "direction": "westbound",
                        "stations": [
                            TestRailwayNetwork.STATION_SHAREDB_5,
                            TestRailwayNetwork.STATION_SHAREDB_4,
                            TestRailwayNetwork.STATION_SHARED_STATION,
                            TestRailwayNetwork.STATION_SHAREDB_2,
                            TestRailwayNetwork.STATION_SHAREDB_1,
                        ],
                    },
                ]
            },
        )

    @staticmethod
    def create_sharedline_c() -> Line:
        """
        SHAREDLINE-C (tube) - Shares 'shared-station' with SHAREDLINE-A and SHAREDLINE-B.

        Route: sharedc-1 → sharedc-2 → shared-station → sharedc-4 → sharedc-5
        """
        return Line(
            tfl_id=TestRailwayNetwork.LINE_SHAREDLINE_C,
            name="SharedLine C",
            mode="tube",
            last_updated=datetime.now(UTC),
            routes={
                "routes": [
                    {
                        "name": "Eastbound",
                        "direction": "eastbound",
                        "stations": [
                            TestRailwayNetwork.STATION_SHAREDC_1,
                            TestRailwayNetwork.STATION_SHAREDC_2,
                            TestRailwayNetwork.STATION_SHARED_STATION,
                            TestRailwayNetwork.STATION_SHAREDC_4,
                            TestRailwayNetwork.STATION_SHAREDC_5,
                        ],
                    },
                    {
                        "name": "Westbound",
                        "direction": "westbound",
                        "stations": [
                            TestRailwayNetwork.STATION_SHAREDC_5,
                            TestRailwayNetwork.STATION_SHAREDC_4,
                            TestRailwayNetwork.STATION_SHARED_STATION,
                            TestRailwayNetwork.STATION_SHAREDC_2,
                            TestRailwayNetwork.STATION_SHAREDC_1,
                        ],
                    },
                ]
            },
        )

    @staticmethod
    def create_elizabethline() -> Line:
        """
        ELIZABETHLINE (elizabeth-line) - Simple line for hub diversity.

        Route: elizabeth-west → hubnorth-elizabeth → elizabeth-mid → elizabeth-east
        """
        return Line(
            tfl_id=TestRailwayNetwork.LINE_ELIZABETHLINE,
            name="Elizabeth Line",
            mode="elizabeth-line",
            last_updated=datetime.now(UTC),
            routes={
                "routes": [
                    {
                        "name": "Eastbound",
                        "direction": "eastbound",
                        "stations": [
                            TestRailwayNetwork.STATION_ELIZABETH_WEST,
                            TestRailwayNetwork.STATION_HUBNORTH_ELIZABETH,
                            TestRailwayNetwork.STATION_ELIZABETH_MID,
                            TestRailwayNetwork.STATION_ELIZABETH_EAST,
                        ],
                    },
                    {
                        "name": "Westbound",
                        "direction": "westbound",
                        "stations": [
                            TestRailwayNetwork.STATION_ELIZABETH_EAST,
                            TestRailwayNetwork.STATION_ELIZABETH_MID,
                            TestRailwayNetwork.STATION_HUBNORTH_ELIZABETH,
                            TestRailwayNetwork.STATION_ELIZABETH_WEST,
                        ],
                    },
                ]
            },
        )


def create_test_station(
    tfl_id: str,
    name: str,
    lines: list[str],
    latitude: float = 51.5,
    longitude: float = -0.1,
    last_updated: datetime | None = None,
    hub_naptan_code: str | None = None,
    hub_common_name: str | None = None,
) -> Station:
    """
    Factory for creating Station model instances for testing.

    Provides sensible defaults while allowing customization of key fields.
    Uses abstract test data by default to avoid coupling tests to real TfL data.

    Args:
        tfl_id: Station TfL ID (e.g., "STATION_A", "910GTEST1")
        name: Station name (e.g., "Test Station Alpha")
        lines: List of line IDs serving this station (e.g., ["line1", "line2"])
        latitude: Latitude coordinate (defaults to 51.5)
        longitude: Longitude coordinate (defaults to -0.1)
        last_updated: Last update timestamp (defaults to 2025-01-01)
        hub_naptan_code: Hub NaPTAN code if part of a hub (e.g., "HUB1")
        hub_common_name: Hub common name if part of a hub (e.g., "Test Hub Alpha")

    Returns:
        Station model instance ready for testing

    Examples:
        >>> # Standalone station
        >>> station = create_test_station("STATION_A", "Alpha Station", ["line1"])

        >>> # Hub station
        >>> hub_station = create_test_station(
        ...     "STATION_B",
        ...     "Beta Station",
        ...     ["line2"],
        ...     hub_naptan_code="HUB1",
        ...     hub_common_name="Test Hub"
        ... )
    """
    return Station(
        id=uuid.uuid4(),
        tfl_id=tfl_id,
        name=name,
        latitude=latitude,
        longitude=longitude,
        lines=lines,
        last_updated=last_updated or datetime(2025, 1, 1, tzinfo=UTC),
        hub_naptan_code=hub_naptan_code,
        hub_common_name=hub_common_name,
    )
