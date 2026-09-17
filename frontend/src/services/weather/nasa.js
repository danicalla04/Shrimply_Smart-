async function fetchJson(url, { signal } = {}) {
  const res = await fetch(url, { signal });
  if (!res.ok) {
    let extra = '';
    try {
      const err = await res.json();
      if (err?.msg) extra = `: ${err.msg}`;
    } catch {
      // ignore
    }
    throw new Error(`NASA request failed (${res.status})${extra}`);
  }
  return await res.json();
}

export async function fetchApod({ apiKey = 'DEMO_KEY', signal } = {}) {
  const key = String(apiKey || '').trim() || 'DEMO_KEY';
  const params = new URLSearchParams({ api_key: key });
  const url = `https://api.nasa.gov/planetary/apod?${params.toString()}`;
  return await fetchJson(url, { signal });
}
