# Test Railway Network Documentation

## Overview

The `TestRailwayNetwork` class in `/backend/tests/helpers/railway_network.py` provides a comprehensive fictional railway network for testing all TfL routing patterns without requiring knowledge of real London Underground geography.

**Network Statistics:**
- **8 lines** across 4 modes (tube, overground, dlr, elizabeth-line)
- **2 multi-mode hubs** (HUB_NORTH with 4 children, HUB_CENTRAL with 2 children)
- **~46 stations** covering all routing edge cases
- **Complex patterns**: Y-forks, parallel paths, non-symmetric routes, shared stations

**Why This Network?**
This fictional network makes tests self-documenting and easier to understand. Instead of memorizing real TfL station names and relationships, tests use descriptive station names like `fork-junction` and `parallel-split` that clearly indicate their purpose.

---

## Network Diagram

### Full Network Overview

```
HUB_NORTH (4-mode interchange)
├─ parallel-north (Tube - parallelline)
├─ hubnorth-overground (Overground - asymmetricline)
├─ hubnorth-elizabeth (Elizabeth line - elizabethline)
└─ hubnorth-bus (Bus - no line in network)

HUB_CENTRAL (2-mode interchange)
├─ fork-mid-1 (Tube - forkedline)
└─ hubcentral-dlr (DLR - 2stopline)
```

**Note on Hub Children**: The notation above shows which lines each hub child "serves" (i.e., which lines appear in the station's `lines` array). However, **hub children are NOT part of the route sequences** for these lines. They represent interchange points that provide access to the lines without being on the actual routes. For example, `hubcentral-dlr` has `2stopline` in its `lines` array, but it does not appear in the 2STOPLINE route sequences (which only include `twostop-west` and `twostop-east`).

---

### Line 1: FORKEDLINE (Tube)

**Pattern:** Y-shaped fork with west/east branches converging at fork-junction

```
West Branch:                      East Branch:
west-fork-2                       east-fork-2
    |                                 |
west-fork                         east-fork
    |                                 |
    └─────── fork-junction ──────────┘
                 |
            fork-mid-1 (at HUB_CENTRAL)
                 |
            fork-mid-2
                 |
          fork-south-end
```

**Routes:**
- **West Branch Southbound:** west-fork-2 → west-fork → fork-junction → fork-mid-1 → fork-mid-2 → fork-south-end
- **West Branch Northbound:** fork-south-end → fork-mid-2 → fork-mid-1 → fork-junction → west-fork → west-fork-2
- **East Branch Southbound:** east-fork-2 → east-fork → fork-junction → fork-mid-1 → fork-mid-2 → fork-south-end
- **East Branch Northbound:** fork-south-end → fork-mid-2 → fork-mid-1 → fork-junction → east-fork → east-fork-2

**Testing Scenarios:** Y-shaped forks, multiple route variants, branch convergence

---

### Line 2: PARALLELLINE (Tube)

**Pattern:** Parallel paths that split and rejoin (Bank/Charing Cross pattern)

```
parallel-north (at HUB_NORTH)
         |
  parallel-split
         |
    ┌────┴────┐
    |         |
via-bank-1  via-charing-1
    |         |
via-bank-2  via-charing-2
    |         |
    └────┬────┘
         |
  parallel-rejoin
         |
  parallel-south
```

**Routes:**
- **Via Bank Southbound:** parallel-north → parallel-split → via-bank-1 → via-bank-2 → parallel-rejoin → parallel-south
- **Via Bank Northbound:** parallel-south → parallel-rejoin → via-bank-2 → via-bank-1 → parallel-split → parallel-north
- **Via Charing Southbound:** parallel-north → parallel-split → via-charing-1 → via-charing-2 → parallel-rejoin → parallel-south
- **Via Charing Northbound:** parallel-south → parallel-rejoin → via-charing-2 → via-charing-1 → parallel-split → parallel-north

**Testing Scenarios:** Parallel paths, route alternatives, split/rejoin points

---

### Line 3: ASYMMETRICLINE (Overground)

**Pattern:** Non-symmetric routes (eastbound has extra station)

```
Eastbound (5 stations):
asym-west → asym-regular-1 → asym-skip-station → asym-regular-2 → asym-east

Westbound (4 stations):
asym-east → asym-regular-2 → asym-regular-1 → asym-west
                            (SKIPS asym-skip-station!)
```

**Routes:**
- **Eastbound:** asym-west → asym-regular-1 → asym-skip-station → asym-regular-2 → asym-east
- **Westbound:** asym-east → asym-regular-2 → asym-regular-1 → asym-west

**Note:** The ASYMMETRICLINE routes use standalone stations. `hubnorth-overground` is a separate hub child at HUB_NORTH that serves the line (has `asymmetricline` in its `lines` array) but is not part of the route sequences. This represents a hub interchange point that provides access to the line without being on the actual route.

**Testing Scenarios:** Non-symmetric routes, direction-dependent station service, skipped stations

---

### Line 4: 2STOPLINE (DLR)

**Pattern:** Minimal two-station line (Waterloo & City pattern)

```
twostop-west ←→ twostop-east
```

**Routes:**
- **Eastbound:** twostop-west → twostop-east
- **Westbound:** twostop-east → twostop-west

**Note:** The 2STOPLINE routes use standalone stations. `hubcentral-dlr` is a separate hub child at HUB_CENTRAL that serves the line (has `2stopline` in its `lines` array) but is not part of the route sequences. This represents a hub interchange point that provides access to the line without being on the actual route.

**Testing Scenarios:** Minimal line, edge case with only 2 stations

---

### Lines 5-7: SHAREDLINE-A/B/C (Tube)

**Pattern:** Three separate lines sharing one station (NOT a hub - same mode)

```
Line A:  shareda-1 → shareda-2 → shared-station → shareda-4 → shareda-5

Line B:  sharedb-1 → sharedb-2 → shared-station → sharedb-4 → sharedb-5

Line C:  sharedc-1 → sharedc-2 → shared-station → sharedc-4 → sharedc-5
```

**Routes (each line has 2 routes):**
- **Line A Eastbound/Westbound:** shareda-1 ↔ shareda-2 ↔ shared-station ↔ shareda-4 ↔ shareda-5
- **Line B Eastbound/Westbound:** sharedb-1 ↔ sharedb-2 ↔ shared-station ↔ sharedb-4 ↔ sharedb-5
- **Line C Eastbound/Westbound:** sharedc-1 ↔ sharedc-2 ↔ shared-station ↔ sharedc-4 ↔ sharedc-5

**Key Distinction:** `shared-station` is NOT a hub because all three lines are the same mode (tube). Hubs require multiple modes.

**Testing Scenarios:** Intra-mode shared stations, multi-line stations, hub vs non-hub distinction

---

### Line 8: ELIZABETHLINE (Elizabeth Line)

**Pattern:** Simple line for hub diversity

```
elizabeth-west → hubnorth-elizabeth (at HUB_NORTH) → elizabeth-mid → elizabeth-east
```

**Routes:**
- **Eastbound:** elizabeth-west → hubnorth-elizabeth → elizabeth-mid → elizabeth-east
- **Westbound:** elizabeth-east → elizabeth-mid → hubnorth-elizabeth → elizabeth-west

**Testing Scenarios:** Elizabeth line mode, hub diversity

---

## Station Reference Table

| Station ID | Name | Lines Served | Hub Affiliation | Type | Notes |
|-----------|------|-------------|----------------|------|-------|
| `parallel-north` | North Interchange (Tube) | parallelline | HUB_NORTH | Hub Child | Tube child at 3-mode hub |
| `hubnorth-overground` | North Interchange (Overground) | asymmetricline | HUB_NORTH | Hub Child | Overground child at 3-mode hub |
| `hubnorth-elizabeth` | North Interchange (Elizabeth line) | elizabethline | HUB_NORTH | Hub Child | Elizabeth line child at 3-mode hub |
| `hubnorth-bus` | North Interchange (Bus) | (none) | HUB_NORTH | Hub Child | Bus child, no line in network |
| `fork-mid-1` | Central Hub (Tube) | forkedline | HUB_CENTRAL | Hub Child | Tube child at 2-mode hub |
| `hubcentral-dlr` | Central Hub (DLR) | 2stopline | HUB_CENTRAL | Hub Child | DLR child at 2-mode hub |
| `fork-junction` | Fork Junction | forkedline | None | Junction | Y-fork convergence point |
| `parallel-split` | Parallel Split | parallelline | None | Junction | Parallel path split point |
| `parallel-rejoin` | Parallel Rejoin | parallelline | None | Junction | Parallel path rejoin point |
| `shared-station` | Shared Station | sharedline-a/b/c | None | Shared | Served by 3 tube lines, NOT a hub |
| `west-fork-2` | West Fork 2 | forkedline | None | Terminus | West branch terminus |
| `west-fork` | West Fork | forkedline | None | Station | West branch station |
| `east-fork-2` | East Fork 2 | forkedline | None | Terminus | East branch terminus |
| `east-fork` | East Fork | forkedline | None | Station | East branch station |
| `fork-mid-2` | Fork Mid 2 | forkedline | None | Station | Trunk station |
| `fork-south-end` | Fork South End | forkedline | None | Terminus | Southern terminus |
| `via-bank-1` | Via Bank 1 | parallelline | None | Station | Bank branch station 1 |
| `via-bank-2` | Via Bank 2 | parallelline | None | Station | Bank branch station 2 |
| `via-charing-1` | Via Charing 1 | parallelline | None | Station | Charing branch station 1 |
| `via-charing-2` | Via Charing 2 | parallelline | None | Station | Charing branch station 2 |
| `parallel-south` | Parallel South | parallelline | None | Terminus | Southern terminus |
| `asym-west` | Asym West | asymmetricline | None | Terminus | Western terminus |
| `asym-regular-1` | Asym Regular 1 | asymmetricline | None | Station | Both directions |
| `asym-skip-station` | Asym Skip Station | asymmetricline | None | Station | Eastbound only! |
| `asym-regular-2` | Asym Regular 2 | asymmetricline | None | Station | Both directions |
| `asym-east` | Asym East | asymmetricline | None | Terminus | Eastern terminus |
| `twostop-west` | TwoStop West | 2stopline | None | Terminus | Western terminus |
| `twostop-east` | TwoStop East | 2stopline | None | Terminus | Eastern terminus |
| `shareda-1` | SharedA 1 | sharedline-a | None | Terminus | Line A western terminus |
| `shareda-2` | SharedA 2 | sharedline-a | None | Station | Line A station |
| `shareda-4` | SharedA 4 | sharedline-a | None | Station | Line A station |
| `shareda-5` | SharedA 5 | sharedline-a | None | Terminus | Line A eastern terminus |
| `sharedb-1` | SharedB 1 | sharedline-b | None | Terminus | Line B western terminus |
| `sharedb-2` | SharedB 2 | sharedline-b | None | Station | Line B station |
| `sharedb-4` | SharedB 4 | sharedline-b | None | Station | Line B station |
| `sharedb-5` | SharedB 5 | sharedline-b | None | Terminus | Line B eastern terminus |
| `sharedc-1` | SharedC 1 | sharedline-c | None | Terminus | Line C western terminus |
| `sharedc-2` | SharedC 2 | sharedline-c | None | Station | Line C station |
| `sharedc-4` | SharedC 4 | sharedline-c | None | Station | Line C station |
| `sharedc-5` | SharedC 5 | sharedline-c | None | Terminus | Line C eastern terminus |
| `elizabeth-west` | Elizabeth West | elizabethline | None | Terminus | Western terminus |
| `elizabeth-mid` | Elizabeth Mid | elizabethline | None | Station | Mid station |
| `elizabeth-east` | Elizabeth East | elizabethline | None | Terminus | Eastern terminus |

---

## Hub vs Shared Station Distinction

### Hubs (Multi-Mode Interchanges)

Hubs are multi-mode interchanges where passengers transfer between different transport modes.

**HUB_NORTH (4-mode hub):**
- NaPTAN Code: `HUBNORTH`
- Common Name: "North Interchange"
- Children:
  - `parallel-north` (Tube)
  - `hubnorth-overground` (Overground)
  - `hubnorth-elizabeth` (Elizabeth line)
  - `hubnorth-bus` (Bus - no line in network)

**HUB_CENTRAL (2-mode hub):**
- NaPTAN Code: `HUBCENTRAL`
- Common Name: "Central Hub"
- Children:
  - `fork-mid-1` (Tube)
  - `hubcentral-dlr` (DLR)

### Shared Stations (Intra-Mode)

Shared stations serve multiple lines of the SAME mode. These are NOT hubs.

**SHARED_STATION:**
- Station ID: `shared-station`
- Name: "Shared Station"
- Lines: sharedline-a, sharedline-b, sharedline-c (all tube)
- Hub: None

**Other Shared Points (NOT hubs):**
- `fork-junction` - convergence point for forkedline branches
- `parallel-split` - split point for parallelline branches
- `parallel-rejoin` - rejoin point for parallelline branches

---

## Usage Examples

### Creating Stations in Tests

```python
from tests.conftest import TestRailwayNetwork

# Hub station
station = TestRailwayNetwork.create_parallel_north()
assert station.hub_naptan_code == TestRailwayNetwork.HUB_NORTH
assert station.hub_common_name == "North Interchange"

# Shared station (serves 3 lines, NOT a hub)
shared = TestRailwayNetwork.create_shared_station()
assert len(shared.lines) == 3
assert shared.hub_naptan_code is None  # NOT a hub

# Junction station (NOT a hub)
junction = TestRailwayNetwork.create_fork_junction()
assert junction.hub_naptan_code is None
```

### Creating Lines in Tests

```python
from tests.conftest import TestRailwayNetwork

# Y-shaped fork line
forkedline = TestRailwayNetwork.create_forkedline()
assert forkedline.mode == "tube"
assert len(forkedline.routes["routes"]) == 4  # 2 branches × 2 directions

# Parallel paths line
parallelline = TestRailwayNetwork.create_parallelline()
assert len(parallelline.routes["routes"]) == 4  # 2 paths × 2 directions

# Non-symmetric line
asymmetricline = TestRailwayNetwork.create_asymmetricline()
routes = asymmetricline.routes["routes"]
eastbound = next(r for r in routes if r["direction"] == "eastbound")
westbound = next(r for r in routes if r["direction"] == "westbound")
assert len(eastbound["stations"]) == 5  # includes skip station
assert len(westbound["stations"]) == 4  # skips skip station
```

### Testing Route Variants

```python
from tests.conftest import TestRailwayNetwork

# Test Y-fork routing
line = TestRailwayNetwork.create_forkedline()
routes = line.routes["routes"]

# Get west branch southbound
west_south = next(r for r in routes if "West Branch" in r["name"] and r["direction"] == "southbound")
assert west_south["stations"][0] == TestRailwayNetwork.STATION_WEST_FORK_2
assert west_south["stations"][-1] == TestRailwayNetwork.STATION_FORK_SOUTH_END

# Get east branch southbound
east_south = next(r for r in routes if "East Branch" in r["name"] and r["direction"] == "southbound")
assert east_south["stations"][0] == TestRailwayNetwork.STATION_EAST_FORK_2
assert east_south["stations"][-1] == TestRailwayNetwork.STATION_FORK_SOUTH_END

# Both branches converge at fork-junction and share trunk
assert TestRailwayNetwork.STATION_FORK_JUNCTION in west_south["stations"]
assert TestRailwayNetwork.STATION_FORK_JUNCTION in east_south["stations"]
```

### Testing Hub Relationships

```python
from tests.conftest import TestRailwayNetwork

# Create hub children
tube_child = TestRailwayNetwork.create_parallel_north()
overground_child = TestRailwayNetwork.create_hubnorth_overground()
elizabeth_child = TestRailwayNetwork.create_hubnorth_elizabeth()
bus_child = TestRailwayNetwork.create_hubnorth_bus()

# All belong to same hub
assert tube_child.hub_naptan_code == TestRailwayNetwork.HUB_NORTH
assert overground_child.hub_naptan_code == TestRailwayNetwork.HUB_NORTH
assert elizabeth_child.hub_naptan_code == TestRailwayNetwork.HUB_NORTH
assert bus_child.hub_naptan_code == TestRailwayNetwork.HUB_NORTH

# Different modes
assert tube_child.lines == [TestRailwayNetwork.LINE_PARALLELLINE]
assert overground_child.lines == [TestRailwayNetwork.LINE_ASYMMETRICLINE]
assert elizabeth_child.lines == [TestRailwayNetwork.LINE_ELIZABETHLINE]
assert bus_child.lines == []  # No line in network
```

### Testing Shared Stations (Non-Hub)

```python
from tests.conftest import TestRailwayNetwork

# Shared station serves 3 tube lines
shared = TestRailwayNetwork.create_shared_station()
assert shared.hub_naptan_code is None  # NOT a hub
assert len(shared.lines) == 3
assert TestRailwayNetwork.LINE_SHAREDLINE_A in shared.lines
assert TestRailwayNetwork.LINE_SHAREDLINE_B in shared.lines
assert TestRailwayNetwork.LINE_SHAREDLINE_C in shared.lines

# All three lines pass through shared station
line_a = TestRailwayNetwork.create_sharedline_a()
line_b = TestRailwayNetwork.create_sharedline_b()
line_c = TestRailwayNetwork.create_sharedline_c()

for line in [line_a, line_b, line_c]:
    for route in line.routes["routes"]:
        assert TestRailwayNetwork.STATION_SHARED_STATION in route["stations"]
```

### Testing Minimal Lines

```python
from tests.conftest import TestRailwayNetwork

# 2-station line (Waterloo & City pattern)
line = TestRailwayNetwork.create_2stopline()
routes = line.routes["routes"]

for route in routes:
    assert len(route["stations"]) == 2  # Only 2 stations

eastbound = next(r for r in routes if r["direction"] == "eastbound")
assert eastbound["stations"] == [
    TestRailwayNetwork.STATION_TWOSTOP_WEST,
    TestRailwayNetwork.STATION_TWOSTOP_EAST,
]
```

---

## Testing Scenarios by Pattern

### Y-Fork Pattern (FORKEDLINE)

**Use Case:** Lines that split into branches (e.g., Northern Line Edgware/High Barnet branches)

**What It Tests:**
- Route variant handling (4 routes: 2 branches × 2 directions)
- Branch convergence at junction point
- Shared trunk sections
- Origin-to-destination routing with branch selection

**Example Test:**
```python
# Routing from west branch to east branch requires passing through junction
origin = TestRailwayNetwork.STATION_WEST_FORK_2
destination = TestRailwayNetwork.STATION_EAST_FORK_2
# Route must go: west-fork-2 → west-fork → fork-junction →
#                fork-mid-1 → fork-junction → east-fork → east-fork-2
# (requires backtracking or multi-segment journey)
```

---

### Parallel Paths Pattern (PARALLELLINE)

**Use Case:** Lines with alternative routes between same endpoints (e.g., Northern Line Bank/Charing branches)

**What It Tests:**
- Multiple valid routes between endpoints
- Route preference/selection logic
- Split and rejoin handling
- Alternative path calculation

**Example Test:**
```python
# Two valid routes from north to south
origin = TestRailwayNetwork.STATION_PARALLEL_NORTH
destination = TestRailwayNetwork.STATION_PARALLEL_SOUTH
# Route 1: via-bank-1 → via-bank-2
# Route 2: via-charing-1 → via-charing-2
```

---

### Non-Symmetric Routes Pattern (ASYMMETRICLINE)

**Use Case:** Lines where stations served differ by direction (e.g., Piccadilly Line T5 loop)

**What It Tests:**
- Direction-dependent station service
- Skipped stations in one direction
- Asymmetric route validation
- Directional routing logic

**Example Test:**
```python
# Station only served in one direction
skip_station = TestRailwayNetwork.STATION_ASYM_SKIP_STATION
line = TestRailwayNetwork.create_asymmetricline()
routes = line.routes["routes"]

eastbound = next(r for r in routes if r["direction"] == "eastbound")
westbound = next(r for r in routes if r["direction"] == "westbound")

assert skip_station in eastbound["stations"]  # Served eastbound
assert skip_station not in westbound["stations"]  # NOT served westbound
```

---

### Shared Station Pattern (SHAREDLINE-A/B/C)

**Use Case:** Stations served by multiple lines of same mode (e.g., Baker Street: 5 tube lines)

**What It Tests:**
- Intra-mode transfers
- Multi-line station handling
- Hub vs shared station distinction
- Line-switching at shared stations

**Example Test:**
```python
# Station served by 3 tube lines but NOT a hub
shared = TestRailwayNetwork.create_shared_station()
assert shared.hub_naptan_code is None  # NOT a hub (same mode)
assert len(shared.lines) == 3  # But serves 3 lines
```

---

### Minimal Line Pattern (2STOPLINE)

**Use Case:** Edge case of smallest possible line (e.g., Waterloo & City Line)

**What It Tests:**
- Minimum viable line handling
- Edge case with only 2 stations
- Simple bidirectional routing
- Line with no intermediate stations

**Example Test:**
```python
# Line with only 2 stations
line = TestRailwayNetwork.create_2stopline()
routes = line.routes["routes"]

for route in routes:
    assert len(route["stations"]) == 2  # No intermediate stations
```

---

### Multi-Mode Hub Pattern (HUB_NORTH, HUB_CENTRAL)

**Use Case:** Multi-mode interchanges (e.g., Stratford: Tube/DLR/Overground/Elizabeth)

**What It Tests:**
- Multi-mode hub relationships
- Hub child station grouping
- Cross-mode journey planning
- Hub-based routing optimization

**Example Test:**
```python
# 4-mode hub with 4 children
tube = TestRailwayNetwork.create_parallel_north()
overground = TestRailwayNetwork.create_hubnorth_overground()
elizabeth = TestRailwayNetwork.create_hubnorth_elizabeth()
bus = TestRailwayNetwork.create_hubnorth_bus()

# All share same hub code but different modes
assert tube.hub_naptan_code == TestRailwayNetwork.HUB_NORTH
assert overground.hub_naptan_code == TestRailwayNetwork.HUB_NORTH
assert elizabeth.hub_naptan_code == TestRailwayNetwork.HUB_NORTH
assert bus.hub_naptan_code == TestRailwayNetwork.HUB_NORTH
```

---

## Constants Reference

### Line Constants

```python
# Tube lines
TestRailwayNetwork.LINE_FORKEDLINE = "forkedline"
TestRailwayNetwork.LINE_PARALLELLINE = "parallelline"
TestRailwayNetwork.LINE_SHAREDLINE_A = "sharedline-a"
TestRailwayNetwork.LINE_SHAREDLINE_B = "sharedline-b"
TestRailwayNetwork.LINE_SHAREDLINE_C = "sharedline-c"

# Overground
TestRailwayNetwork.LINE_ASYMMETRICLINE = "asymmetricline"

# DLR
TestRailwayNetwork.LINE_2STOPLINE = "2stopline"

# Elizabeth line
TestRailwayNetwork.LINE_ELIZABETHLINE = "elizabethline"
```

### Hub Constants

```python
# HUB_NORTH (3-mode hub)
TestRailwayNetwork.HUB_NORTH = "HUBNORTH"
TestRailwayNetwork.HUB_NORTH_NAME = "North Interchange"

# HUB_CENTRAL (2-mode hub)
TestRailwayNetwork.HUB_CENTRAL = "HUBCENTRAL"
TestRailwayNetwork.HUB_CENTRAL_NAME = "Central Hub"
```

### Station Constants by Category

**Hub Children:**
```python
# HUB_NORTH children
TestRailwayNetwork.STATION_PARALLEL_NORTH = "parallel-north"
TestRailwayNetwork.STATION_HUBNORTH_OVERGROUND = "hubnorth-overground"
TestRailwayNetwork.STATION_HUBNORTH_ELIZABETH = "hubnorth-elizabeth"
TestRailwayNetwork.STATION_HUBNORTH_BUS = "hubnorth-bus"

# HUB_CENTRAL children
TestRailwayNetwork.STATION_FORK_MID_1 = "fork-mid-1"
TestRailwayNetwork.STATION_HUBCENTRAL_DLR = "hubcentral-dlr"
```

**FORKEDLINE Stations:**
```python
TestRailwayNetwork.STATION_WEST_FORK_2 = "west-fork-2"
TestRailwayNetwork.STATION_WEST_FORK = "west-fork"
TestRailwayNetwork.STATION_EAST_FORK_2 = "east-fork-2"
TestRailwayNetwork.STATION_EAST_FORK = "east-fork"
TestRailwayNetwork.STATION_FORK_JUNCTION = "fork-junction"
TestRailwayNetwork.STATION_FORK_MID_2 = "fork-mid-2"
TestRailwayNetwork.STATION_FORK_SOUTH_END = "fork-south-end"
```

**PARALLELLINE Stations:**
```python
TestRailwayNetwork.STATION_PARALLEL_SPLIT = "parallel-split"
TestRailwayNetwork.STATION_VIA_BANK_1 = "via-bank-1"
TestRailwayNetwork.STATION_VIA_BANK_2 = "via-bank-2"
TestRailwayNetwork.STATION_VIA_CHARING_1 = "via-charing-1"
TestRailwayNetwork.STATION_VIA_CHARING_2 = "via-charing-2"
TestRailwayNetwork.STATION_PARALLEL_REJOIN = "parallel-rejoin"
TestRailwayNetwork.STATION_PARALLEL_SOUTH = "parallel-south"
```

**ASYMMETRICLINE Stations:**
```python
TestRailwayNetwork.STATION_ASYM_WEST = "asym-west"
TestRailwayNetwork.STATION_ASYM_REGULAR_1 = "asym-regular-1"
TestRailwayNetwork.STATION_ASYM_SKIP_STATION = "asym-skip-station"  # Eastbound only!
TestRailwayNetwork.STATION_ASYM_REGULAR_2 = "asym-regular-2"
TestRailwayNetwork.STATION_ASYM_EAST = "asym-east"
```

**2STOPLINE Stations:**
```python
TestRailwayNetwork.STATION_TWOSTOP_WEST = "twostop-west"
TestRailwayNetwork.STATION_TWOSTOP_EAST = "twostop-east"
```

**SHAREDLINE Stations:**
```python
# Shared station (all 3 lines)
TestRailwayNetwork.STATION_SHARED_STATION = "shared-station"

# Line A exclusive
TestRailwayNetwork.STATION_SHAREDA_1 = "shareda-1"
TestRailwayNetwork.STATION_SHAREDA_2 = "shareda-2"
TestRailwayNetwork.STATION_SHAREDA_4 = "shareda-4"
TestRailwayNetwork.STATION_SHAREDA_5 = "shareda-5"

# Line B exclusive
TestRailwayNetwork.STATION_SHAREDB_1 = "sharedb-1"
TestRailwayNetwork.STATION_SHAREDB_2 = "sharedb-2"
TestRailwayNetwork.STATION_SHAREDB_4 = "sharedb-4"
TestRailwayNetwork.STATION_SHAREDB_5 = "sharedb-5"

# Line C exclusive
TestRailwayNetwork.STATION_SHAREDC_1 = "sharedc-1"
TestRailwayNetwork.STATION_SHAREDC_2 = "sharedc-2"
TestRailwayNetwork.STATION_SHAREDC_4 = "sharedc-4"
TestRailwayNetwork.STATION_SHAREDC_5 = "sharedc-5"
```

**ELIZABETHLINE Stations:**
```python
TestRailwayNetwork.STATION_ELIZABETH_WEST = "elizabeth-west"
TestRailwayNetwork.STATION_ELIZABETH_MID = "elizabeth-mid"
TestRailwayNetwork.STATION_ELIZABETH_EAST = "elizabeth-east"
```

---

## Factory Method Reference

### Station Factory Methods

**Hub Children (6 methods):**
- `create_parallel_north()` - HUB_NORTH tube child
- `create_hubnorth_overground()` - HUB_NORTH overground child
- `create_hubnorth_elizabeth()` - HUB_NORTH elizabeth-line child
- `create_hubnorth_bus()` - HUB_NORTH bus child
- `create_fork_mid_1()` - HUB_CENTRAL tube child
- `create_hubcentral_dlr()` - HUB_CENTRAL dlr child

**Junction Points (3 methods):**
- `create_fork_junction()` - Y-fork convergence point
- `create_parallel_split()` - Parallel path split point
- `create_parallel_rejoin()` - Parallel path rejoin point

**Shared Station (1 method):**
- `create_shared_station()` - Serves 3 tube lines (NOT a hub)

**Standalone Stations (33 methods):**
- FORKEDLINE: `create_west_fork_2()`, `create_west_fork()`, `create_east_fork_2()`, `create_east_fork()`, `create_fork_mid_2()`, `create_fork_south_end()`
- PARALLELLINE: `create_via_bank_1()`, `create_via_bank_2()`, `create_via_charing_1()`, `create_via_charing_2()`, `create_parallel_south()`
- ASYMMETRICLINE: `create_asym_west()`, `create_asym_regular_1()`, `create_asym_skip_station()`, `create_asym_regular_2()`, `create_asym_east()`
- 2STOPLINE: `create_twostop_west()`, `create_twostop_east()`
- SHAREDLINE-A: `create_shareda_1()`, `create_shareda_2()`, `create_shareda_4()`, `create_shareda_5()`
- SHAREDLINE-B: `create_sharedb_1()`, `create_sharedb_2()`, `create_sharedb_4()`, `create_sharedb_5()`
- SHAREDLINE-C: `create_sharedc_1()`, `create_sharedc_2()`, `create_sharedc_4()`, `create_sharedc_5()`
- ELIZABETHLINE: `create_elizabeth_west()`, `create_elizabeth_mid()`, `create_elizabeth_east()`

### Line Factory Methods (8 methods)

- `create_forkedline()` - Y-shaped fork line (tube)
- `create_parallelline()` - Parallel paths line (tube)
- `create_asymmetricline()` - Non-symmetric line (overground)
- `create_2stopline()` - Minimal 2-station line (dlr)
- `create_sharedline_a()` - Shared station line A (tube)
- `create_sharedline_b()` - Shared station line B (tube)
- `create_sharedline_c()` - Shared station line C (tube)
- `create_elizabethline()` - Elizabeth line

---

## Design Principles

### Naming Convention

**Hybrid Approach:**
- **Hubs:** UPPERCASE (e.g., `HUB_NORTH`, `HUB_CENTRAL`)
- **Stations:** lowercase-kebab-case (e.g., `parallel-north`, `fork-mid-1`)
- **Lines:** lowercase descriptive (e.g., `forkedline`, `parallelline`)

**Rationale:** Hub names are UPPERCASE to distinguish them from regular stations, while station and line names are lowercase for readability and consistency with typical identifiers.

### Self-Documenting Names

Station names describe their purpose:
- `fork-junction` - where Y-fork branches converge
- `parallel-split` - where parallel paths split
- `asym-skip-station` - station skipped in one direction
- `shared-station` - shared by multiple lines

### Fictional Network Benefits

1. **No Real-World Knowledge Required:** Tests are self-contained and don't require knowing London geography
2. **Clear Purpose:** Station names indicate their testing purpose
3. **Consistent Structure:** Predictable patterns make tests easier to write and understand
4. **Complete Coverage:** Network covers all edge cases found in real TfL data

---

## Migration Notes

### Deprecated Network (Issue #70)

The original test network (HUB_ALPHA, HUB_BETA, etc.) is deprecated and will be removed in Part 2.

**Old Constants (Deprecated):**
- `LINE_1`, `LINE_2`, `LINE_3`
- `HUB_ALPHA_CODE`, `HUB_ALPHA_TUBE_ID`, etc.
- `HUB_BETA_CODE`, `HUB_BETA_CHILD1_ID`, etc.
- `STANDALONE_CHARLIE_ID`, `STANDALONE_DELTA_ID`

**Migration Path:**
- Use new network constants (e.g., `LINE_FORKEDLINE`, `HUB_NORTH`)
- Use new factory methods (e.g., `create_parallel_north()` instead of `create_hub_alpha_tube()`)
- Update tests to use descriptive station names

---

## Quick Reference

### Common Test Patterns

**Create a hub station:**
```python
station = TestRailwayNetwork.create_parallel_north()
```

**Create a line:**
```python
line = TestRailwayNetwork.create_forkedline()
```

**Access station constant:**
```python
station_id = TestRailwayNetwork.STATION_FORK_JUNCTION
```

**Access line constant:**
```python
line_id = TestRailwayNetwork.LINE_PARALLELLINE
```

**Check if station is a hub child:**
```python
station = TestRailwayNetwork.create_parallel_north()
is_hub = station.hub_naptan_code is not None
```

**Get all routes for a line:**
```python
line = TestRailwayNetwork.create_forkedline()
routes = line.routes["routes"]  # List of route dicts
```

---

## Visual Network Map

```
                    elizabeth-west ←→ HUBNORTH (elizabeth) ←→ elizabeth-mid ←→ elizabeth-east
                                             |
                                      HUBNORTH (tube)
                                             |
                                      parallel-north
                                             |
                                      parallel-split
                                        /         \
                                      /             \
                             via-bank-1          via-charing-1
                                  |                    |
                             via-bank-2          via-charing-2
                                      \             /
                                        \         /
                                      parallel-rejoin
                                             |
                                      parallel-south


west-fork-2 ←→ west-fork                             east-fork-2 ←→ east-fork
                      \                               /
                        \                           /
                          fork-junction (Y-fork)
                                 |
                            fork-mid-1 (at HUBCENTRAL tube)
                                 |
                            fork-mid-2
                                 |
                          fork-south-end


asym-west ←→ asym-regular-1 ←→ asym-skip-station (eastbound only) ←→ asym-regular-2 ←→ asym-east


twostop-west ←→ twostop-east


shareda-1 ←→ shareda-2 ←→ shared-station ←→ shareda-4 ←→ shareda-5
                                |
sharedb-1 ←→ sharedb-2 ←→ shared-station ←→ sharedb-4 ←→ sharedb-5
                                |
sharedc-1 ←→ sharedc-2 ←→ shared-station ←→ sharedc-4 ←→ sharedc-5
```

---

## Summary

The test railway network provides comprehensive coverage of TfL routing patterns:

1. **Y-Forks:** FORKEDLINE with west/east branches
2. **Parallel Paths:** PARALLELLINE with Bank/Charing alternatives
3. **Non-Symmetric Routes:** ASYMMETRICLINE with eastbound-only station
4. **Minimal Lines:** 2STOPLINE with only 2 stations
5. **Shared Stations:** SHAREDLINE-A/B/C with common station (non-hub)
6. **Multi-Mode Hubs:** HUB_NORTH (3 modes) and HUB_CENTRAL (2 modes)
7. **Hub Diversity:** Tube, Overground, DLR, Elizabeth line, Bus

This fictional network makes tests self-documenting and eliminates the need to understand real London Underground geography while ensuring complete coverage of all routing edge cases.
