// contains the TfL types that i need, rearranged under a single namespace
// so that they can automtically be imported into zod types
export interface Identifier {
  id: string;
  name: string;
  uri: string;
  fullName?: string;
  type: string;
  crowding?: Crowding;
  routeType: string;
  status: string;
}

export interface Crowding {
  passengerFlows?: PassengerFlow[];
  trainLoadings?: TrainLoading[];
}

export interface PassengerFlow {
  timeSlice?: string;
  value?: number;
}

export interface TrainLoading {
  line: string;
  lineDirection: string;
  platformDirection: string;
  direction: string;
  naptanTo: string;
  timeSlice: string;
  value: number;
}

export interface MatchedStop {
  routeId?: number;
  parentId?: string;
  stationId?: string;
  icsId: string;
  topMostParentId?: string;
  direction?: string;
  towards?: string;
  modes: string[];
  stopType: string;
  stopLetter?: string;
  zone: string;
  accessibilitySummary?: string;
  hasDisruption?: boolean;
  lines: Identifier[];
  status?: boolean;
  id: string;
  url?: string;
  name: string;
  lat: number;
  lon: number;
}

export interface StopPointSequence {
  lineId: string;
  lineName: string;
  direction: string;
  branchId: number;
  nextBranchIds: number[];
  prevBranchIds: number[];
  stopPoint: MatchedStop[];
  serviceType: 'Regular' | 'Night';
}

export interface OrderedRoute {
  name: string;
  naptanIds: string[];
  serviceType: string;
}

export interface RouteSequence {
  lineId: string;
  lineName: string;
  direction: string;
  isOutboundOnly: boolean;
  mode: string;
  lineStrings: string[];
  stations: MatchedStop[];
  stopPointSequences: StopPointSequence[];
  orderedLineRoutes: OrderedRoute[];
}

// https://github.com/fabien0102/ts-to-zod/issues/153
export type StopPointArray = Array<StopPoint>


export interface StopPoint {
  naptanId: string;
  platformName?: string;
  /** @description The indicator of the stop point e.g. "Stop K" */
  indicator?: string;
  /** @description The stop letter, if it could be cleansed from the Indicator e.g. "K" */
  stopLetter?: string;
  modes: string[];
  icsCode?: string;
  smsCode?: string;
  stopType: string;
  stationNaptan: string;
  accessibilitySummary?: string;
  hubNaptanCode?: string;
  lines: Identifier[];
  lineGroup: LineGroup[];
  lineModeGroups: LineModeGroup[];
  fullName?: string;
  naptanMode?: string;
  status: boolean;
  /** @description A unique identifier. */
  id: string;
  /** @description The unique location of this resource. */
  url?: string;
  /** @description A human readable name. */
  commonName: string;
  /**
   * Format: double
   * @description The distance of the place from its search point, if this is the result
   *             of a geographical search, otherwise zero.
   */
  distance?: number;
  /** @description The type of Place. See /Place/Meta/placeTypes for possible values. */
  placeType?: string;
  /** @description A bag of additional key/value pairs with extra information about this place. */
  additionalProperties?: AdditionalProperties[];
  children?: Place[];
  childrenUrls?: string[];
  /**
   * Format: double
   * @description WGS84 latitude of the location.
   */
  lat: number;
  /**
   * Format: double
   * @description WGS84 longitude of the location.
   */
  lon: number;
};
export interface LineGroup {
  naptanIdReference?: string;
  stationAtcoCode?: string;
  lineIdentifier?: string[];
};
export interface LineModeGroup {
  modeName: string;
  lineIdentifier: string[];
};

export interface AdditionalProperties {
  category?: string;
  key?: string;
  sourceSystemKey?: string;
  value?: string;
  /** Format: date-time */
  modified?: string;
};

export interface Place {
  /** @description A unique identifier. */
  id: string;
  /** @description The unique location of this resource. */
  url?: string;
  /** @description A human readable name. */
  commonName: string;
  /**
   * Format: double
   * @description The distance of the place from its search point, if this is the result
   *             of a geographical search, otherwise zero.
   */
  distance?: number;
  /** @description The type of Place. See /Place/Meta/placeTypes for possible values. */
  placeType: string;
  /** @description A bag of additional key/value pairs with extra information about this place. */
  additionalProperties?: AdditionalProperties[];
  children?: Place[];
  childrenUrls?: string[];
  /**
   * Format: double
   * @description WGS84 latitude of the location.
   */
  lat: number;
  /**
   * Format: double
   * @description WGS84 longitude of the location.
   */
  lon: number;
};
export interface Line {
  id: string;
  name: string;
  modeName: string;
  disruptions?: Disruption[];
  /** Format: date-time */
  created?: string;
  /** Format: date-time */
  modified?: string;
  lineStatuses: LineStatus[];
  routeSections: MatchedRoute[];
  serviceTypes: LineServiceTypeInfo[];
  crowding?: Crowding;
};

export type LineArray = Array<Line>

export interface Disruption {
  /** @description Gets or sets the category of this dispruption. */
  category?: 'Undefined' | 'RealTime' | 'PlannedWork' | 'Information' | 'Event' | 'Crowding' | 'StatusAlert';
  /** @description Gets or sets the disruption type of this dispruption. */
  type?: string;
  /** @description Gets or sets the description of the category. */
  categoryDescription?: string;
  /** @description Gets or sets the description of this disruption. */
  description?: string;
  /** @description Gets or sets the summary of this disruption. */
  summary?: string;
  /** @description Gets or sets the additionaInfo of this disruption. */
  additionalInfo?: string;
  /**
   * Format: date-time
   * @description Gets or sets the date/time when this disruption was created.
   */
  created?: string;
  /**
   * Format: date-time
   * @description Gets or sets the date/time when this disruption was last updated.
   */
  lastUpdate?: string;
  /** @description Gets or sets the routes affected by this disruption */
  affectedRoutes?: DisruptedRoute[];
  /** @description Gets or sets the stops affected by this disruption */
  affectedStops?: StopPoint[];
  /** @description Text describing the closure type */
  closureText?: string;
};

export interface LineStatus {
  /** Format: int32 */
  id: number;
  lineId: string;
  /** Format: int32 */
  statusSeverity: number;
  statusSeverityDescription?: string;
  reason?: string;
  /** Format: date-time */
  created?: string;
  /** Format: date-time */
  modified?: string;
  validityPeriods?: ValidityPeriod[];
  disruption: Disruption;
};

export interface MatchedRoute {
  /** @description The route code */
  routeCode?: string;
  /** @description Name such as "72" */
  name: string;
  /** @description Inbound or Outbound */
  direction?: string;
  /** @description The name of the Origin StopPoint */
  originationName: string;
  /** @description The name of the Destination StopPoint */
  destinationName: string;
  /** @description The Id (NaPTAN code) of the Origin StopPoint */
  originator: string;
  /** @description The Id (NaPTAN code) or the Destination StopPoint */
  destination: string;
  /** @description Regular or Night */
  serviceType?: string;
  /**
   * Format: date-time
   * @description The DateTime that the Service containing this Route is valid until.
   */
  validTo?: string;
  /**
   * Format: date-time
   * @description The DateTime that the Service containing this Route is valid from.
   */
  validFrom?: string;
};

export interface DisruptedRoute {
  /** @description The Id of the route */
  id?: string;
  /** @description The Id of the Line */
  lineId?: string;
  /** @description The route code */
  routeCode?: string;
  /** @description Name such as "72" */
  name?: string;
  /** @description The co-ordinates of the route's path as a geoJSON lineString */
  lineString?: string;
  /** @description Inbound or Outbound */
  direction?: string;
  /** @description The name of the Origin StopPoint */
  originationName?: string;
  /** @description The name of the Destination StopPoint */
  destinationName?: string;
  /** @description (where applicable) via Charing Cross / Bank / King's Cross / Embankment / Newbury Park / Woodford */
  via?: RouteSectionNaptanEntrySequence;
  /** @description Whether this represents the entire route section */
  isEntireRouteSection?: boolean;
  /**
   * Format: date-time
   * @description The DateTime that the Service containing this Route is valid until.
   */
  validTo?: string;
  /**
   * Format: date-time
   * @description The DateTime that the Service containing this Route is valid from.
   */
  validFrom?: string;
  routeSectionNaptanEntrySequence?: RouteSectionNaptanEntrySequence[];
};

export interface RouteSectionNaptanEntrySequence {
  /** Format: int32 */
  ordinal: number;
  stopPoint: StopPoint;
};

  /** @description Represents a period for which a planned works is valid. */
  export interface ValidityPeriod {
    /**
     * Format: date-time
     * @description Gets or sets the start date.
     */
    fromDate: string;
    /**
     * Format: date-time
     * @description Gets or sets the end date.
     */
    toDate: string;
    /** @description If true is a realtime status rather than planned or info */
    isNow?: boolean;
};

export interface LineServiceTypeInfo {
  name: string;
  uri?: string;
};