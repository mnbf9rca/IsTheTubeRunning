export type ValidJSONValue = string | number | boolean | null | ValidJSONObject | ValidJSONArray;
export interface ValidJSONObject {
  [key: string]: ValidJSONValue;
}

export interface ValidJSONArray extends Array<ValidJSONValue> { }

export interface GenericEdge extends ValidJSONObject {
  id: string;
  from: string;
  to: string;
}