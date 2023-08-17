/**
 * Represents a literal value, which can be a string, number, boolean, or null.
 * 
 * @typedef {string | number | boolean | null} Literal
 */
export type Literal = string | number | boolean | null;

/**
 * Represents a JSON value, which can be a literal, an object, or an array.
 * 
 * @typedef {Literal | { [key: string]: Json } | Json[]} Json
 */
export type Json = Literal | { [key: string]: Json } | Json[];

/**
 * Represents a generic edge object that includes 'from' and 'to' fields as strings.
 * The type allows for any additional JSON-compatible properties.
 * 
 * @typedef {object} GenericEdge
 * @property {string} from - The starting point of the edge. Must match the .id property of a vertex.
 * @property {string} to - The ending point of the edge. Must match the .id property of a vertex.
 * @property {Json} [key] - Optional additional properties with string keys.
 */
export type GenericEdge = {
  from: string;
  to: string;
} & Json;

/**
 * Represents a generic vertex object that includes an 'id' field as a string.
 * The type allows for any additional JSON-compatible properties.
 *
 * @typedef {object} GenericVertex
 * @property {string} id - The unique identifier of the vertex.
 * @property {Json} [key] - Optional additional properties with string keys.
 */
export type GenericVertex = {
  id: string;
} & Json;
