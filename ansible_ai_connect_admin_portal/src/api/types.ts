// Loading statuses and payloads
export type Status =
  | "NOT_ASKED"
  | "LOADING"
  | "FAILURE"
  | "SUCCESS"
  | "SUCCESS_NOT_FOUND";
export type NotAsked = { status: "NOT_ASKED" };
export type Loading = { status: "LOADING" };
export type Failure = { status: "FAILURE"; error: Error };
export type Success<R> = { status: "SUCCESS"; data: R };
export type SuccessNotFound = { status: "SUCCESS_NOT_FOUND" };

export type WcaKey =
  | NotAsked
  | Loading
  | Failure
  | Success<WcaKeyResponse>
  | SuccessNotFound;
export type WcaModelId =
  | NotAsked
  | Loading
  | Failure
  | Success<WcaModelIdResponse>
  | SuccessNotFound;
export type Telemetry =
  | NotAsked
  | Loading
  | Failure
  | Success<TelemetryResponse>
  | SuccessNotFound;

// Request objects for the REST [GET] APIs
export interface WcaKeyRequest {
  key: string;
}

export interface WcaModelIdRequest {
  model_id: string;
}

// Response objects for the REST [POST] APIs
export interface WcaKeyResponse {
  lastUpdate: Date;
}

export interface WcaModelIdResponse {
  model_id: string;
  lastUpdate: Date;
}

export interface TelemetryRequest {
  optOut: boolean;
}

export interface TelemetryResponse {
  optOut: boolean;
}

export interface APIException {
  status_code: number;
  detail: string;
  code: string;
}
