export interface DataWithTTL {
  // returned by specific TfL API requests
  data: any;  // Replace 'any' with the actual type of 'data'
  ttl: number;
}

export interface APIResponse extends DataWithTTL {
  // returned by the TfL API Query
  status: number;
  success: boolean;
  error?: string;
}

/*
export interface TfLAPIQuery {
  query(querystring: string, params?: { [key: string]: number | string | boolean }): Promise<TfLApiResponse>
}*/

export interface TfLAPIQuery {
  (querystring: string, params?: { [key: string]: number | string | boolean }): Promise<APIResponse>;
}
