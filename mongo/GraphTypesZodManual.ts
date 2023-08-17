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

export const ObjectIdSchema = z.custom<ObjectId>(
  (value): value is ObjectId => value instanceof ObjectId,
  { message: 'Invalid ObjectId' }
);

export const edgeWithObjectIdsSchemaBase = z
  .object({
    from: ObjectIdSchema,
    to: ObjectIdSchema,
  })

export const edgeWithObjectIdsSchema = z
  .union([
    edgeWithObjectIdsSchemaBase,
    GraphTypesZod.genericEdgeSchema
  ])

export * from "./GraphTypesZod";
