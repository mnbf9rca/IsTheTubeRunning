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
}
