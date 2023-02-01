interface RouteQueryResult {
  data: { _items: RouteItem[] }
}

interface RouteItem {
  labels: any[],
  objects: [RouteItemLineSegment | RouteItemStoppoint]
}

interface RouteItemLineSegment {
  id: string;
  inV: string;
  inVLabel: "stoppoint";
  label: string;
  outV: string;
  outVLabel: "stoppoint";
  properties: { [key: string]: string | number | boolean | { [key: string]: string | number | boolean }[] };
  flattenedProperties?: FlattenedProperties;
  type: "edge";
}

interface RouteItemStoppoint {
  id: string;
  label: string;
  properties:  { [key: string]: string | number | boolean | { [key: string]: string | number | boolean }[] };
  flattenedProperties?: FlattenedProperties;
  type: "vertex";
}

interface FlattenedProperties {
   [key: string]: string | number | boolean | (string | number | boolean)[] 
}

interface PropertyBucket {
  [key: string]: string | number | boolean | { [key: string]: string | number | boolean }[] 

}

export {
  RouteQueryResult,
  RouteItem,
  RouteItemLineSegment,
  RouteItemStoppoint,
  FlattenedProperties,
  PropertyBucket
};
