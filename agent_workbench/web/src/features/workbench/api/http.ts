export async function fetchJson<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const response = await fetch(path, options);
  const raw = await response.text();
  let data: unknown = null;

  if (raw) {
    try {
      data = JSON.parse(raw) as unknown;
    } catch {
      data = raw;
    }
  }

  if (!response.ok) {
    if (data && typeof data === "object") {
      const payload = data as Record<string, unknown>;
      throw new Error(
        String(payload.detail || payload.error || `请求失败：${response.status}`),
      );
    }
    throw new Error(String(data || `请求失败：${response.status}`));
  }

  return data as T;
}
