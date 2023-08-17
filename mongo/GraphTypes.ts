/**
 * Represents a generic edge object that includes 'from' and 'to' fields as strings.
 * The type allows for any additional properties with string keys.
 * 
 * @typedef {object} GenericEdge
 * @property {string} from - The starting point of the edge. Must match the .id property of a vertex.
 * @property {string} to - The ending point of the edge. Must match the .id property of a vertex.
 * @property {any} [key] - Optional additional properties with string keys.
 */
export type GenericEdge = {
  from: string;
  to: string;
} & {
  [key: string]: any;
};

/**
 * Represents a generic vertex object that includes an 'id' field as a string.
 * The type allows for any additional properties with string keys.
 *
 * @typedef {object} GenericVertex
 * @property {string} id - The unique identifier of the vertex.
 * @property {any} [key] - Optional additional properties with string keys.
 */
export type GenericVertex = {
  id: string;
} & {
  [key: string]: any;
};
