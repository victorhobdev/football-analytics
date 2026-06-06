const DEFAULT_TIMEOUT_MS = 15_000;

type QueryPrimitive = string | number | boolean | null | undefined;

export type QueryParamValue = QueryPrimitive | QueryPrimitive[];
export type QueryParams = Record<string, QueryParamValue>;

type JsonObjectBody = Record<string, unknown>;
type ApiRequestBody = RequestInit["body"] | JsonObjectBody | null;

export type ApiRequestOptions = Omit<RequestInit, "body"> & {
  params?: QueryParams;
  timeoutMs?: number;
  body?: ApiRequestBody;
};

type ApiClientErrorCode =
  | "CONFIG_ERROR"
  | "HTTP_ERROR"
  | "NETWORK_ERROR"
  | "TIMEOUT_ERROR"
  | "INVALID_JSON_RESPONSE";

type ApiClientErrorOptions = {
  status?: number;
  code: ApiClientErrorCode;
  details?: unknown;
};

export class ApiClientError extends Error {
  public readonly status?: number;
  public readonly code: ApiClientErrorCode;
  public readonly details?: unknown;

  public constructor(message: string, options: ApiClientErrorOptions) {
    super(message);
    this.name = "ApiClientError";
    this.status = options.status;
    this.code = options.code;
    this.details = options.details;
  }
}

function resolveBffBaseUrl(): string {
  const serverBaseUrl = process.env.FOOTBALL_BFF_ORIGIN?.trim() ?? process.env.BFF_ORIGIN?.trim();
  if (typeof window === "undefined" && serverBaseUrl) {
    return serverBaseUrl;
  }

  const baseUrl = process.env.NEXT_PUBLIC_BFF_BASE_URL?.trim();

  if (baseUrl) {
    return baseUrl;
  }

  if (serverBaseUrl) {
    return serverBaseUrl;
  }

  throw new ApiClientError(
    "NEXT_PUBLIC_BFF_BASE_URL nao configurado. Defina a variavel no ambiente.",
    { code: "CONFIG_ERROR" },
  );
}

function normalizeBaseUrl(baseUrl: string): string {
  if (baseUrl === "/") {
    return "";
  }

  return baseUrl.endsWith("/") ? baseUrl.slice(0, -1) : baseUrl;
}

function normalizePath(path: string): string {
  if (!path) {
    return "/";
  }

  return path.startsWith("/") ? path : `/${path}`;
}

function joinBaseAndPath(baseUrl: string, path: string): string {
  const normalizedBase = normalizeBaseUrl(baseUrl);
  const normalizedPath = normalizePath(path);

  return `${normalizedBase}${normalizedPath}`;
}

function appendQueryParamsToSearchParams(searchParams: URLSearchParams, params?: QueryParams): void {
  if (!params) {
    return;
  }

  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null) {
      continue;
    }

    const values = Array.isArray(value) ? value : [value];

    for (const item of values) {
      if (item === undefined || item === null) {
        continue;
      }

      searchParams.append(key, String(item));
    }
  }
}

function buildRequestUrl(path: string, params?: QueryParams): string {
  const baseUrl = resolveBffBaseUrl();
  const joinedUrl = joinBaseAndPath(baseUrl, path);
  const isAbsoluteUrl = /^https?:\/\//i.test(joinedUrl);

  if (isAbsoluteUrl) {
    const url = new URL(joinedUrl);
    appendQueryParamsToSearchParams(url.searchParams, params);
    return url.toString();
  }

  const searchParams = new URLSearchParams();
  appendQueryParamsToSearchParams(searchParams, params);

  const queryString = searchParams.toString();
  return queryString.length > 0 ? `${joinedUrl}?${queryString}` : joinedUrl;
}

function isPlainJsonObject(value: unknown): value is JsonObjectBody {
  if (value === null || typeof value !== "object") {
    return false;
  }

  if (Array.isArray(value)) {
    return false;
  }

  if (value instanceof FormData) {
    return false;
  }

  if (value instanceof Blob) {
    return false;
  }

  if (value instanceof URLSearchParams) {
    return false;
  }

  if (value instanceof ArrayBuffer) {
    return false;
  }

  if (ArrayBuffer.isView(value)) {
    return false;
  }

  return true;
}

function serializeBody(body: ApiRequestBody, headers: Headers): RequestInit["body"] {
  if (body === undefined || body === null) {
    return undefined;
  }

  if (isPlainJsonObject(body)) {
    if (!headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }

    return JSON.stringify(body);
  }

  return body;
}

function extractErrorMessage(payload: unknown, status: number): string {
  if (typeof payload === "string" && payload.trim().length > 0) {
    return payload;
  }

  if (payload && typeof payload === "object") {
    const maybeRecord = payload as Record<string, unknown>;
    const candidate = maybeRecord.message ?? maybeRecord.error ?? maybeRecord.detail ?? maybeRecord.title;

    if (typeof candidate === "string" && candidate.trim().length > 0) {
      return candidate;
    }
  }

  return `Falha na requisicao para BFF (HTTP ${status}).`;
}

async function parseResponsePayload(response: Response): Promise<unknown> {
  if (response.status === 204 || response.status === 205) {
    return null;
  }

  const rawText = await response.text();

  if (rawText.trim().length === 0) {
    return null;
  }

  const contentType = response.headers.get("content-type")?.toLowerCase() ?? "";
  const isJsonResponse = contentType.includes("application/json") || contentType.includes("+json");

  if (!isJsonResponse) {
    return rawText;
  }

  try {
    return JSON.parse(rawText) as unknown;
  } catch {
    throw new ApiClientError("Resposta JSON invalida recebida da BFF.", {
      code: "INVALID_JSON_RESPONSE",
      status: response.status,
      details: rawText,
    });
  }
}

function createRequestSignal(signal: AbortSignal | null | undefined, timeoutMs: number) {
  const controller = new AbortController();
  let didTimeout = false;

  const abortFromParent = (): void => {
    controller.abort(signal?.reason);
  };

  if (signal?.aborted) {
    abortFromParent();
  } else if (signal) {
    signal.addEventListener("abort", abortFromParent, { once: true });
  }

  const timeoutId = setTimeout(() => {
    didTimeout = true;
    controller.abort(new DOMException("Request timeout", "TimeoutError"));
  }, timeoutMs);

  const cleanup = (): void => {
    clearTimeout(timeoutId);

    if (signal) {
      signal.removeEventListener("abort", abortFromParent);
    }
  };

  return {
    signal: controller.signal,
    cleanup,
    didTimeout: (): boolean => didTimeout,
  };
}

export async function apiRequest<T>(path: string, options: ApiRequestOptions = {}): Promise<T> {
  const { params, timeoutMs = DEFAULT_TIMEOUT_MS, headers, signal, body, ...requestInit } = options;
  const url = buildRequestUrl(path, params);
  const requestHeaders = new Headers(headers);
  const serializedBody = serializeBody(body, requestHeaders);
  const requestSignal = createRequestSignal(signal, timeoutMs);

  try {
    const response = await fetch(url, {
      ...requestInit,
      headers: requestHeaders,
      body: serializedBody,
      signal: requestSignal.signal,
    });

    const payload = await parseResponsePayload(response);

    if (!response.ok) {
      throw new ApiClientError(extractErrorMessage(payload, response.status), {
        code: "HTTP_ERROR",
        status: response.status,
        details: payload,
      });
    }

    return payload as T;
  } catch (error) {
    if (error instanceof ApiClientError) {
      throw error;
    }

    if (requestSignal.didTimeout()) {
      throw new ApiClientError(`Requisicao expirou apos ${timeoutMs}ms.`, {
        code: "TIMEOUT_ERROR",
      });
    }

    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiClientError("Requisicao cancelada.", {
        code: "NETWORK_ERROR",
      });
    }

    throw new ApiClientError("Falha de rede ao chamar a BFF.", {
      code: "NETWORK_ERROR",
      details: error,
    });
  } finally {
    requestSignal.cleanup();
  }
}
