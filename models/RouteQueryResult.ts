// Author: rob aleck, https://github.com/mnbf9rca

// interfaces for the results of a route query
// i think this might be the same for any query, but i'm not sure
interface RouteTraversalResultSet {
  /* a route traversal result the response to a query to find the route between two stoppoints */
  data: {
    _items: RouteTraversalResult[],
    attributes: PropertyBucket,
    length: number,
  },
  success: boolean;
  status_code: number | null;

}

interface RouteTraversalResult {
  labels: any[], // i dont know what this item is...
  objects: [TraversalLineSegment | TraversalStoppoint]
}

interface TraversalLineSegment {
  /* a line segment is an edge between two stoppoints */
  id: string;
  inV: string;
  inVLabel: "stoppoint";
  label: string;
  outV: string;
  outVLabel: "stoppoint";
  properties: PropertyBucket;
  type: "edge";
}

interface TraversalStoppoint {
  /* a stoppoint is a vertex */
  id: string;
  label: string;
  properties: PropertyBucket;
  type: "vertex";
}


// interfaces for the results of adding a stoppoint
interface IAddStoppointResult {
  data: StoppointQueryItem[];
}

interface StoppointQueryItem extends FlattenedProperties {
  id: string;
  label: string;
  type: "vertex";
  lat: number;
  lon: number;
  name: string;
  modes: string[];
  lines: string[];
  naptanId: string;
}

interface LineQueryItem extends FlattenedProperties {
  id: string;
  from: string;
  to: string;
  inV: string;
  outV: string;
  label: string;
  type: "edge";
  inVLabel: string;
  outVLabel: string;
  line: string;
  branch: string;
  direction: string;
}


interface RouteQueryResult {
  data: (StoppointQueryItem | LineQueryItem)[][];
  success: boolean;
  status_code: number | null;
};

interface FlattenedProperties {
  [key: string]: string | number | boolean | (string | number | boolean)[];
}

interface PropertyBucket {
  /* a property bucket is a collection of properties 
  *  that are associated with a vertex or edge
  * some are key:value pairs, some are arrays of key:value pairs
  * */
  [key: string]: string | number | boolean | { [key: string]: string | number | boolean }[];
}

export {
  RouteTraversalResultSet,
  RouteTraversalResult,
  TraversalLineSegment,
  TraversalStoppoint,
  FlattenedProperties,
  PropertyBucket,
  IAddStoppointResult,
  StoppointQueryItem,
  LineQueryItem,
  RouteQueryResult,
};
