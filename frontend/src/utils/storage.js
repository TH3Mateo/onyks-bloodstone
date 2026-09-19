export function readStorage(key, fallback)
{
    try
    {
        const raw = localStorage.getItem(key)
        return raw === null ? fallback : JSON.parse(raw)
    }
    catch (e)
    {
        return fallback
    }
}

export function writeStorage(key, value)
{
    try
    {
        localStorage.setItem(key, JSON.stringify(value))
    }
    catch (e)
    {
        // ignore write failures (private mode, quota, etc.)
    }
}
