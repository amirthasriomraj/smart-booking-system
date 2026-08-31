// The backend's error.message is usually a plain string (an HTTPException
// detail, e.g. for 403/404/409), but for a 422 request-validation failure
// it's an array of Pydantic error objects (main.py's
// validation_exception_handler, DEBUG mode). Rendering that array directly
// as JSX children crashes the whole page ("Objects are not valid as a React
// child") — this coerces either shape to a safe, readable string.
export function extractErrorMessage(err, fallback) {
  const message = err.response?.data?.error?.message

  if (typeof message === "string" && message) {
    return message
  }

  if (Array.isArray(message) && message.length > 0) {
    return message.map((item) => item?.msg || JSON.stringify(item)).join("; ")
  }

  return fallback
}
