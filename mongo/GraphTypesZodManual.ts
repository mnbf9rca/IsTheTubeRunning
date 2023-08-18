import { z } from "zod";
import * as GraphTypesZod from "./GraphTypesZod";
import { Json } from "./GraphTypes";
import { ObjectId } from "mongodb";


const isJsonSerializable = (value: any): value is Json => {
  if (value === null || typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    return true;
  }

  if (Array.isArray(value)) {
    return value.every(isJsonSerializable);
  }

  if (typeof value === 'object') {
    return Object.values(value).every(isJsonSerializable);
  }

  return false; // value is a function, symbol, or other non-serializable type
};

export const jsonSerializable: z.ZodSchema<Json> = z.custom<Json>(
  isJsonSerializable,
  { message: "Invalid JSON value" }
);


export const jsonWithoutFromOrTo = z.
  record(jsonSerializable)
  .and(
    z.object({
      from: z.never().optional(),
      to: z.never().optional(),
    })
  );

const objectIdSchema = z.custom<ObjectId>(
  (value): value is ObjectId => value instanceof ObjectId,
  { message: 'Invalid ObjectId' }
);

/*
// this doesnt work
export const edgeWithObjectIdsOld = z.object({
  from: objectIdSchema,
  to: objectIdSchema,
}).and(
  z.record(jsonSerializable)
);
*/

export const edgeWithObjectIds = z.object({
  from: objectIdSchema,
  to: objectIdSchema,
}).catchall(jsonSerializable);



  export const edgeWithStringss = z
  .record(jsonSerializable)
  .and(
    z.object({
      from: z.string(),
      to: z.string(),
    })
  );

  export const anyEdge = z.union([edgeWithObjectIds, edgeWithStringss]);

export * from "./GraphTypesZod";
