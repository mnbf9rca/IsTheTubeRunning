// contains the TfL types that i need, rearranged under a single namespace
// so that they can automtically be imported into zod types

export namespace TfLResponse {
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

 // export interface StopPointArray extends Array<StopPoint> {}
  export type StopPointArray = StopPoint[];


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

}
